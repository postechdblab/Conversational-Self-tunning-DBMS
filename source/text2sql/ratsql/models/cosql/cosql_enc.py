import collections
from copy import deepcopy
import itertools
import copy
import json
import os

import attr
import numpy as np
import torch
import transformers

from source.text2sql.ratsql.models import abstract_preproc
from source.text2sql.ratsql.models.cosql import cosql_enc_modules
from source.text2sql.ratsql.models.cosql.cosql_match_utils import (
    compute_schema_linking,
    compute_cell_value_linking,
)
from source.text2sql.ratsql.resources import corenlp
from source.text2sql.ratsql.utils import registry
from source.text2sql.ratsql.utils import serialization
from source.text2sql.ratsql.utils import vocab


@attr.s
class CosqlEncoderState:
    encoded_feature = attr.ib()

    def find_word_occurrences(self, word):
        return [i for i, w in enumerate(self.words) if w == word]


@attr.s
class PreprocessedSchema:
    column_names = attr.ib(factory=list)
    table_names = attr.ib(factory=list)
    table_bounds = attr.ib(factory=list)
    column_to_table = attr.ib(factory=dict)
    table_to_columns = attr.ib(factory=dict)
    foreign_keys = attr.ib(factory=dict)
    foreign_keys_tables = attr.ib(factory=lambda: collections.defaultdict(set))
    primary_keys = attr.ib(factory=list)

    # only for bert version
    normalized_column_names = attr.ib(factory=list)
    normalized_table_names = attr.ib(factory=list)


def preprocess_schema_uncached(
    schema,
    tokenize_func,
    include_table_name_in_column,
    fix_issue_16_primary_keys,
    bert=False,
    bert_version="bert-base-uncased",
):
    """If it's bert, we also cache the normalized version of
    question/column/table for schema linking"""
    r = PreprocessedSchema()

    if bert:
        assert not include_table_name_in_column

    last_table_id = None
    for i, column in enumerate(schema.columns):
        col_toks = tokenize_func(column.name, column.unsplit_name)

        # assert column.type in ["text", "number", "time", "boolean", "others"]
        type_tok = f"<type: {column.type}>"
        if bert:
            # for bert, we take the representation of the first word
            column_name = col_toks + [type_tok]
            r.normalized_column_names.append(
                Bertokens(col_toks, bert_version=bert_version)
            )
        else:
            column_name = [type_tok] + col_toks

        if include_table_name_in_column:
            if column.table is None:
                table_name = ["<any-table>"]
            else:
                table_name = tokenize_func(column.table.name, column.table.unsplit_name)
            column_name += ["<table-sep>"] + table_name
        r.column_names.append(column_name)

        table_id = None if column.table is None else column.table.id
        r.column_to_table[str(i)] = table_id
        if table_id is not None:
            columns = r.table_to_columns.setdefault(str(table_id), [])
            columns.append(i)
        if last_table_id != table_id:
            r.table_bounds.append(i)
            last_table_id = table_id

        if column.foreign_key_for is not None:
            r.foreign_keys[str(column.id)] = column.foreign_key_for.id
            r.foreign_keys_tables[str(column.table.id)].add(
                column.foreign_key_for.table.id
            )

    r.table_bounds.append(len(schema.columns))
    assert len(r.table_bounds) == len(schema.tables) + 1

    for i, table in enumerate(schema.tables):
        table_toks = tokenize_func(table.name, table.unsplit_name)
        r.table_names.append(table_toks)
        if bert:
            r.normalized_table_names.append(
                Bertokens(table_toks, bert_version=bert_version)
            )
    last_table = schema.tables[-1]

    r.foreign_keys_tables = serialization.to_dict_with_sorted_values(
        r.foreign_keys_tables
    )
    r.primary_keys = (
        [column.id for table in schema.tables for column in table.primary_keys]
        if fix_issue_16_primary_keys
        else [
            column.id for column in last_table.primary_keys for table in schema.tables
        ]
    )

    return r


class CosqlEncoderPreproc(abstract_preproc.AbstractPreproc):
    def __init__(
        self,
        save_path,
        min_freq=3,
        max_count=5000,
        include_table_name_in_column=True,
        word_emb=None,
        count_tokens_in_word_emb_for_vocab=False,
        fix_issue_16_primary_keys=False,
        compute_sc_link=False,
        compute_cv_link=False,
        db_path=None,
    ):
        if word_emb is None:
            self.word_emb = None
        else:
            self.word_emb = registry.construct("word_emb", word_emb)

        self.data_dir = os.path.join(save_path, "enc")
        self.include_table_name_in_column = include_table_name_in_column
        self.count_tokens_in_word_emb_for_vocab = count_tokens_in_word_emb_for_vocab
        self.fix_issue_16_primary_keys = fix_issue_16_primary_keys
        self.compute_sc_link = compute_sc_link
        self.compute_cv_link = compute_cv_link
        self.texts = collections.defaultdict(list)
        self.db_path = db_path

        self.vocab_builder = vocab.VocabBuilder(min_freq, max_count)
        self.vocab_path = os.path.join(save_path, "enc_vocab.json")
        self.vocab_word_freq_path = os.path.join(save_path, "enc_word_freq.json")
        self.vocab = None
        self.counted_db_ids = set()
        self.preprocessed_schemas = {}

    def validate_item(self, item, section, bert_version=None):
        return True, None

    def add_item(
        self,
        item,
        section,
        validation_info,
        bert_version=None,
        manual_linking_info=None,
    ):
        preprocessed = self.preprocess_item(
            item, validation_info, manual_linking_info=manual_linking_info
        )
        self.texts[section].append(preprocessed)

        if section == "train":
            if item.schema.db_id in self.counted_db_ids:
                to_count = preprocessed["question"]
            else:
                self.counted_db_ids.add(item.schema.db_id)
                to_count = itertools.chain(
                    preprocessed["question"],
                    *preprocessed["columns"],
                    *preprocessed["tables"],
                )

            for token in to_count:
                count_token = (
                    self.word_emb is None
                    or self.count_tokens_in_word_emb_for_vocab
                    or self.word_emb.lookup(token) is None
                )
                if count_token:
                    self.vocab_builder.add_word(token)

    def clear_items(self):
        self.texts = collections.defaultdict(list)

    def preprocess_item(self, item, validation_info, manual_linking_info=None):
        question, question_for_copying = self._tokenize_for_copying(
            item.text, item.orig["question"]
        )
        preproc_schema = self._preprocess_schema(item.schema)
        if self.compute_sc_link:
            assert preproc_schema.column_names[0][0].startswith("<type:")
            column_names_without_types = [
                col[1:] for col in preproc_schema.column_names
            ]
            sc_link = compute_schema_linking(
                question,
                column_names_without_types,
                preproc_schema.table_names,
                manual_linking_info=manual_linking_info,
            )
        else:
            sc_link = {"q_col_match": {}, "q_tab_match": {}}

        if self.compute_cv_link:
            cv_link = compute_cell_value_linking(
                question, item.schema, manual_linking_info=manual_linking_info
            )
        else:
            cv_link = {"num_date_match": {}, "cell_match": {}}

        return {
            "raw_question": item.orig["question"],
            "question": question,
            "question_for_copying": question_for_copying,
            "db_id": item.schema.db_id,
            "sc_link": sc_link,
            "cv_link": cv_link,
            "columns": preproc_schema.column_names,
            "tables": preproc_schema.table_names,
            "table_bounds": preproc_schema.table_bounds,
            "column_to_table": preproc_schema.column_to_table,
            "table_to_columns": preproc_schema.table_to_columns,
            "foreign_keys": preproc_schema.foreign_keys,
            "foreign_keys_tables": preproc_schema.foreign_keys_tables,
            "primary_keys": preproc_schema.primary_keys,
        }

    def _preprocess_schema(self, schema):
        if schema.db_id in self.preprocessed_schemas:
            return self.preprocessed_schemas[schema.db_id]
        result = preprocess_schema_uncached(
            schema,
            self._tokenize,
            self.include_table_name_in_column,
            self.fix_issue_16_primary_keys,
        )
        self.preprocessed_schemas[schema.db_id] = result
        return result

    def _tokenize(self, presplit, unsplit):
        if self.word_emb:
            return self.word_emb.tokenize(unsplit)
        return presplit

    def _tokenize_for_copying(self, presplit, unsplit):
        if self.word_emb:
            return self.word_emb.tokenize_for_copying(unsplit)
        return presplit, presplit

    def save(self, is_testing=False):
        os.makedirs(self.data_dir, exist_ok=True)
        self.vocab = self.vocab_builder.finish()
        print(f"{len(self.vocab)} words in vocab")
        if not is_testing:
            self.vocab.save(self.vocab_path)
            self.vocab_builder.save(self.vocab_word_freq_path)

        for section, texts in self.texts.items():
            with open(os.path.join(self.data_dir, section + ".jsonl"), "w") as f:
                for text in texts:
                    f.write(json.dumps(text, ensure_ascii=False) + "\n")

    def load(self):
        self.vocab = vocab.Vocab.load(self.vocab_path)
        self.vocab_builder.load(self.vocab_word_freq_path)

    def dataset(self, section):
        return [
            json.loads(line)
            for line in open(os.path.join(self.data_dir, section + ".jsonl"))
        ]


class Bertokens:
    def __init__(self, pieces, bert_version="bert-base-uncased"):
        self.pieces = pieces
        self.bert_version = bert_version

        self.normalized_pieces = None
        self.recovered_pieces = None
        self.idx_map = None

        self.normalize_toks()

    def normalize_toks(self):
        UNDERSCORE = chr(9601)

        def is_dash(word):
            return word == "-"

        def is_int(word):
            try:
                int(word)
                return True
            except:
                return False

        def is_english(word):
            word = word.strip(UNDERSCORE)
            if word == "":
                return False
            if ord(word[0]) > 64 and ord(word[0]) < 91:
                return True
            if ord(word[0]) > 96 and ord(word[0]) < 123:
                return True
            return False

        def is_english_start(word):
            if len(word) < 2:
                return False
            return word[0] == UNDERSCORE and is_english(word)

        """
        If the token is not a word piece, then find its lemma
        If it is, combine pieces into a word, and then find its lemma
        E.g., a ##b ##c will be normalized as "abc", "", ""
        NOTE: this is only used for schema linking
        """
        if self.bert_version == "markussagen/xlm-roberta-longformer-base-4096":
            new_toks = []
            idx_map = {}
            for idx, tok in enumerate(self.pieces):
                # Indicating new english word
                if tok == UNDERSCORE:
                    continue
                if is_english_start(tok):
                    idx_map[len(new_toks)] = idx
                    new_toks += [tok.strip(UNDERSCORE)]
                elif is_english(tok):
                    if new_toks and any(
                        [func(new_toks[-1]) for func in [is_english, is_dash]]
                    ):
                        new_toks[-1] = new_toks[-1] + tok
                    else:
                        idx_map[len(new_toks)] = idx
                        new_toks += [tok.strip(UNDERSCORE)]
                elif is_int(tok):
                    if new_toks and any(
                        [func(new_toks[-1]) for func in [is_english, is_int, is_dash]]
                    ):
                        new_toks[-1] = new_toks[-1] + tok
                    else:
                        idx_map[len(new_toks)] = idx
                        new_toks += [tok.strip(UNDERSCORE)]
                elif is_dash(tok):
                    if new_toks and any(
                        [func(new_toks[-1]) for func in [is_english, is_int]]
                    ):
                        new_toks[-1] = new_toks[-1] + tok
                    else:
                        idx_map[len(new_toks)] = idx
                        new_toks += [tok.strip(UNDERSCORE)]
                else:
                    idx_map[len(new_toks)] = idx
                    new_toks += [tok.strip(UNDERSCORE)]
                pass
            self.idx_map = idx_map
        elif self.bert_version == "Salesforce/grappa_large_jnt":
            new_toks = []
            idx_map = {}
            for idx, tok in enumerate(self.pieces):
                if not new_toks:
                    idx_map[len(new_toks)] = idx
                    new_toks += [tok]
                elif tok[0] == chr(288):
                    idx_map[len(new_toks)] = idx
                    new_toks += [tok.strip(chr(288))]
                else:
                    new_toks[-1] = new_toks[-1] + tok
            self.idx_map = idx_map
        else:
            self.startidx2pieces = dict()
            self.pieces2startidx = dict()
            cache_start = None
            for i, piece in enumerate(self.pieces + [""]):
                if piece.startswith("##"):
                    if cache_start is None:
                        cache_start = i - 1

                    self.pieces2startidx[i] = cache_start
                    self.pieces2startidx[i - 1] = cache_start
                else:
                    if cache_start is not None:
                        self.startidx2pieces[cache_start] = i
                    cache_start = None
            assert cache_start is None

            # combine pieces, "abc", "", ""
            combined_word = {}
            for start, end in self.startidx2pieces.items():
                # assert end - start + 1 < 10
                pieces = [self.pieces[start]] + [
                    self.pieces[_id].strip("##") for _id in range(start + 1, end)
                ]
                word = "".join(pieces)
                combined_word[start] = word

            # remove "", only keep "abc"
            idx_map = {}
            new_toks = []
            for i, piece in enumerate(self.pieces):
                if i in combined_word:
                    idx_map[len(new_toks)] = i
                    new_toks.append(combined_word[i])
                elif i in self.pieces2startidx:
                    # remove it
                    pass
                else:
                    idx_map[len(new_toks)] = i
                    new_toks.append(piece)
            self.idx_map = idx_map

        # lemmatize "abc"
        normalized_toks = []
        for i, tok in enumerate(new_toks):
            ann = corenlp.annotate(tok, annotators=["tokenize", "ssplit", "lemma"])
            lemmas = [tok.lemma.lower() for sent in ann.sentence for tok in sent.token]
            lemma_word = " ".join(lemmas)
            normalized_toks.append(lemma_word)

        self.normalized_pieces = normalized_toks
        self.recovered_pieces = new_toks

    def bert_schema_linking(self, columns, tables, manual_linking_info=None):
        question_tokens = self.normalized_pieces
        column_tokens = [c.normalized_pieces for c in columns]
        table_tokens = [t.normalized_pieces for t in tables]
        sc_link = compute_schema_linking(
            question_tokens, column_tokens, table_tokens, manual_linking_info
        )

        new_sc_link = {}
        for m_type in sc_link:
            _match = {}
            for ij_str in sc_link[m_type]:
                q_id_str, col_tab_id_str = ij_str.split(",")
                q_id, col_tab_id = int(q_id_str), int(col_tab_id_str)
                real_q_id = self.idx_map[q_id]
                _match[f"{real_q_id},{col_tab_id}"] = sc_link[m_type][ij_str]

            new_sc_link[m_type] = _match
        return new_sc_link

    def bert_cv_linking(self, schema, manual_linking_info=None):
        question_tokens = (
            self.recovered_pieces
        )  # Not using normalized tokens here because values usually match exactly
        cv_link = compute_cell_value_linking(
            question_tokens, schema, manual_linking_info
        )

        new_cv_link = {}
        for m_type in cv_link:
            _match = {}
            for ij_str in cv_link[m_type]:
                q_id_str, col_tab_id_str = ij_str.split(",")
                q_id, col_tab_id = int(q_id_str), int(col_tab_id_str)
                real_q_id = self.idx_map[q_id]
                _match[f"{real_q_id},{col_tab_id}"] = cv_link[m_type][ij_str]
            new_cv_link[m_type] = _match
        return new_cv_link


class CosqlEncoderBertPreproc(CosqlEncoderPreproc):
    def __init__(
        self,
        save_path,
        db_path,
        fix_issue_16_primary_keys=False,
        include_table_name_in_column=False,
        bert_version="bert-base-uncased",
        compute_sc_link=True,
        compute_cv_link=False,
    ):

        self.bert_version = bert_version
        self.data_dir = os.path.join(save_path, "enc")
        self.db_path = db_path
        self.texts = collections.defaultdict(list)
        self.fix_issue_16_primary_keys = fix_issue_16_primary_keys
        self.include_table_name_in_column = include_table_name_in_column
        self.compute_sc_link = compute_sc_link
        self.compute_cv_link = compute_cv_link
        self.counted_db_ids = set()
        self.preprocessed_schemas = {}

        """ jjkim - Sep 30, 2021
        use transformers.AutoModel instead of specific models such as BertModel or ElectraModel
        """
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(bert_version)
        self.max_position_embeddings = transformers.AutoConfig.from_pretrained(
            bert_version
        ).max_position_embeddings

        # TODO: should get types from the data
        column_types = ["text", "number", "time", "boolean", "others"]
        self.tokenizer.add_tokens([f"<type: {t}>" for t in column_types])
        self._translate = None

    def translate(self, *args, **kwargs):
        """
        Assumption: It should be called only during preprocess stage.
                    The below configs should be set as true
        """
        assert (
            self.use_kor_nng_translate or self.use_kor_full_translate
        ), "Check your config"
        if self._translate == None:
            self._translate = transformers.pipeline(
                "translation_ko_to_en", model="Helsinki-NLP/opus-mt-ko-en", device=0
            )
        return self._translate(*args, **kwargs)

    def _tokenize(self, presplit, unsplit):
        if self.tokenizer:
            toks = self.tokenizer.tokenize(unsplit)
            return toks
        return presplit

    def add_item(
        self,
        item,
        section,
        validation_info,
        bert_version="bert-base-uncased",
        manual_linking_info=None,
    ):
        if section in {"aux"}:
            return True, None
        preprocessed = self.preprocess_item(
            item,
            validation_info,
            bert_version=bert_version,
            manual_linking_info=manual_linking_info,
        )

        to_add, _ = self.validate_item(item, section)
        if to_add:
            self.texts[section].append(preprocessed)
            return True, preprocessed
        else:
            return False, preprocessed

    def add_item_from_cache(self, cached_item, section):
        self.texts[section].append(cached_item)

    def preprocess_item(
        self,
        item,
        validation_info,
        bert_version="bert-base-uncased",
        manual_linking_info=None,
    ):
        def word_is_in_schema(word, schema):
            word = word.lower()
            tab_names = [table.name for table in schema.tables]
            col_names = [column.name for column in schema.columns]
            for name in tab_names + col_names:
                if word in name:
                    return True
            return False

        question = self._tokenize(item.text, item.unsplit_text)
        preproc_schema = self._preprocess_schema(item.schema)
        question_bert_tokens = Bertokens(question, bert_version=bert_version)
        if self.compute_sc_link:
            sc_link = question_bert_tokens.bert_schema_linking(
                preproc_schema.normalized_column_names,
                preproc_schema.normalized_table_names,
                manual_linking_info,
            )
        else:
            sc_link = {"q_col_match": {}, "q_tab_match": {}}

        if self.compute_cv_link:
            cv_link = question_bert_tokens.bert_cv_linking(
                item.schema, manual_linking_info
            )
        else:
            cv_link = {"num_date_match": {}, "cell_match": {}}

        return {
            "intent": item.intent,
            "raw_question": item.orig["utterance"],
            "question": question,
            "db_id": item.schema.db_id,
            "sc_link": sc_link,
            "cv_link": cv_link,
            "columns": preproc_schema.column_names,
            "tables": preproc_schema.table_names,
            "table_bounds": preproc_schema.table_bounds,
            "column_to_table": preproc_schema.column_to_table,
            "table_to_columns": preproc_schema.table_to_columns,
            "foreign_keys": preproc_schema.foreign_keys,
            "foreign_keys_tables": preproc_schema.foreign_keys_tables,
            "primary_keys": preproc_schema.primary_keys,
        }

    def validate_item(self, item, section, bert_version="bert-base-uncased"):
        if section in {"aux"}:
            return True, None

        question = self._tokenize(item.text, item.unsplit_text)
        preproc_schema = self._preprocess_schema(item.schema, bert_version=bert_version)

        num_words = (
            len(question)
            + 2
            + sum(len(c) + 1 for c in preproc_schema.column_names)
            + sum(len(t) + 1 for t in preproc_schema.table_names)
        )
        if num_words > self.max_position_embeddings:
            return False, None  # remove long sequences
        else:
            return True, None

    def _preprocess_schema(self, schema, bert_version="bert-base-uncased"):
        if schema.db_id in self.preprocessed_schemas:
            return self.preprocessed_schemas[schema.db_id]
        result = preprocess_schema_uncached(
            schema,
            self._tokenize,
            self.include_table_name_in_column,
            self.fix_issue_16_primary_keys,
            bert=True,
            bert_version=bert_version,
        )
        self.preprocessed_schemas[schema.db_id] = result
        return result

    def save(self, is_testing=False):
        os.makedirs(self.data_dir, exist_ok=True)
        if not is_testing:
            self.tokenizer.save_pretrained(self.data_dir)

        for section, texts in self.texts.items():
            with open(os.path.join(self.data_dir, section + ".jsonl"), "w") as f:
                for text in texts:
                    f.write(json.dumps(text, ensure_ascii=False) + "\n")

    def load(self):
        """jjkim - Sep 30, 2021
        use transformers.AutoModel instead of specific models such as BertModel or ElectraModel
        """
        self.tokenizer = transformers.AutoTokenizer.from_pretrained(
            self.data_dir,
            config=transformers.AutoConfig.from_pretrained(self.bert_version),
        )


@registry.register("encoder", "cosql-bert")
class CosqlEncoderBert(torch.nn.Module):
    Preproc = CosqlEncoderBertPreproc
    batched = True

    def __init__(
        self,
        device,
        preproc,
        bert_token_type=False,
        bert_version="bert-base-uncased",
        summarize_header="first",
        use_column_type=True,
        include_in_memory=("question", "column", "table"),
    ):
        super().__init__()
        self.preproc = preproc
        self.bert_token_type = bert_token_type
        transformers.logging.set_verbosity_error()
        self.base_enc_hidden_size = 768 if "base" in bert_version else 1024

        assert summarize_header in ["first", "avg"]
        self.summarize_header = summarize_header
        self.enc_hidden_size = self.base_enc_hidden_size
        self.use_column_type = use_column_type

        self.include_in_memory = set(include_in_memory)
        update_modules = {
            "relational_transformer": cosql_enc_modules.RelationalTransformerUpdate,
            "none": cosql_enc_modules.NoOpUpdate,
        }

        # self.encs_update = registry.instantiate(
        #     update_modules[update_config['name']],
        #     update_config,
        #     unused_keys={"name"},
        #     device=device,
        #     hidden_size=self.enc_hidden_size,
        #     sc_link=True,
        # )

        """ jjkim - Sep 30, 2021
        use transformers.AutoModel instead of specific models such as BertModel or ElectraModel
        """
        self.bert_model = transformers.AutoModel.from_pretrained(bert_version)

        self.tokenizer = self.preproc.tokenizer
        self.bert_model.resize_token_embeddings(
            len(self.tokenizer)
        )  # several tokens added

    @property
    def _device(self):
        return next(self.parameters()).device

    def forward(self, descs, debug=False):
        batch_token_lists = []
        for batch_idx, desc in enumerate(descs):
            # Question
            qs = self.pad_single_sentence_for_bert(desc["question"], cls=True)
            # Column
            cols = []
            for i, c in enumerate(desc["columns"]):
                col = c if self.use_column_type else c[:-1]
                cols.append(self.pad_single_sentence_for_bert(col, cls=False))
            # Table
            tabs = [
                self.pad_single_sentence_for_bert(t, cls=False) for t in desc["tables"]
            ]

            token_list = (
                qs + [c for col in cols for c in col] + [t for tab in tabs for t in tab]
            )
            assert self.check_bert_seq(token_list)
            assert len(token_list) <= self.bert_model.config.max_position_embeddings

            indexed_token_list = self.tokenizer.convert_tokens_to_ids(token_list)
            batch_token_lists.append(indexed_token_list)

        # Prepare input tensors
        padded_token_lists, att_mask_lists, tok_type_lists = (
            self.pad_sequence_for_bert_batch(batch_token_lists)
        )
        tokens_tensor = torch.tensor(
            padded_token_lists, dtype=torch.long, device=self._device
        )
        att_masks_tensor = torch.tensor(
            att_mask_lists, dtype=torch.long, device=self._device
        )

        # Encode with bert
        if self.bert_token_type:
            tok_type_tensor = torch.tensor(
                tok_type_lists, dtype=torch.long, device=self._device
            )
            enc_output = self.bert_model(
                tokens_tensor,
                attention_mask=att_masks_tensor,
                token_type_ids=tok_type_tensor,
            )[0]
        else:
            enc_output = self.bert_model(
                tokens_tensor, attention_mask=att_masks_tensor
            )[0]

        return enc_output[:, 0]

    @DeprecationWarning
    def encoder_long_seq(self, desc):
        """
        Since bert cannot handle sequence longer than 512, each column/table is encoded individually
        The representation of a column/table is the vector of the first token [CLS]
        """
        qs = self.pad_single_sentence_for_bert(desc["question"], cls=True)
        cols = [self.pad_single_sentence_for_bert(c, cls=True) for c in desc["columns"]]
        tabs = [self.pad_single_sentence_for_bert(t, cls=True) for t in desc["tables"]]

        enc_q = self._bert_encode(qs)
        enc_col = self._bert_encode(cols)
        enc_tab = self._bert_encode(tabs)
        return enc_q, enc_col, enc_tab

    @DeprecationWarning
    def _bert_encode(self, toks):
        if not isinstance(toks[0], list):  # encode question words
            indexed_tokens = self.tokenizer.convert_tokens_to_ids(toks)
            tokens_tensor = torch.tensor([indexed_tokens], device=self._device)
            outputs = self.bert_model(tokens_tensor)
            return outputs[0][0, 1:-1]  # remove [CLS] and [SEP]
        else:
            max_len = max([len(it) for it in toks])
            tok_ids = []
            for item_toks in toks:
                item_toks = item_toks + [self.tokenizer.pad_token] * (
                    max_len - len(item_toks)
                )
                indexed_tokens = self.tokenizer.convert_tokens_to_ids(item_toks)
                tok_ids.append(indexed_tokens)

            tokens_tensor = torch.tensor(tok_ids, device=self._device)
            outputs = self.bert_model(tokens_tensor)
            return outputs[0][:, 0, :]

    def check_bert_seq(self, toks):
        if toks[0] == self.tokenizer.cls_token and toks[-1] == self.tokenizer.sep_token:
            return True
        else:
            return False

    def pad_single_sentence_for_bert(self, toks, cls=True):
        if cls:
            return [self.tokenizer.cls_token] + toks + [self.tokenizer.sep_token]
        else:
            return toks + [self.tokenizer.sep_token]

    def pad_sequence_for_bert_batch(self, tokens_lists):
        pad_id = self.tokenizer.pad_token_id
        max_len = max([len(it) for it in tokens_lists])
        assert max_len <= self.bert_model.config.max_position_embeddings
        toks_ids = []
        att_masks = []
        tok_type_lists = []
        for item_toks in tokens_lists:
            padded_item_toks = item_toks + [pad_id] * (max_len - len(item_toks))
            toks_ids.append(padded_item_toks)

            _att_mask = [1] * len(item_toks) + [0] * (max_len - len(item_toks))
            att_masks.append(_att_mask)

            first_sep_id = padded_item_toks.index(self.tokenizer.sep_token_id)
            assert first_sep_id > 0
            _tok_type_list = [0] * (first_sep_id + 1) + [1] * (
                max_len - first_sep_id - 1
            )
            tok_type_lists.append(_tok_type_list)
        return toks_ids, att_masks, tok_type_lists
