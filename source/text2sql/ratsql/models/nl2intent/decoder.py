import collections
import collections.abc
import json
import os

from pathlib import Path

import attr
import entmax
import torch
import torch.nn.functional as F
from source.text2sql.ratsql.datasets.spider_lib.process_sql import Schema, get_schema
from source.text2sql.ratsql.datasets.utils import db_utils
from source.text2sql.ratsql.models import abstract_preproc, attention
from source.text2sql.ratsql.utils import registry


@attr.s
class NL2IntentDecoderPreprocItem:
    tree = attr.ib()
    orig_code = attr.ib()


class NL2IntentDecoderPreproc(abstract_preproc.AbstractPreproc):
    def __init__(self, save_path, db_path, db_type="sqlite"):
        self.data_dir = os.path.join(save_path, "dec")
        self.items = collections.defaultdict(list)
        # Custom
        # tables_dir = '/'.join([dir for dir in db_path.split('/') if dir][:-1])
        tables_dir = os.path.dirname(db_path)
        tables_path = os.path.join(tables_dir, "tables.json")
        db_names = [item["db_id"] for item in json.load(open(tables_path))]
        self.schemas = {}
        for db_name in db_names:
            db_conn_str = db_utils.create_db_conn_str(db_path, db_name, db_type=db_type)
            if not os.path.isfile(db_conn_str):
                print(f"DB file not found: {db_conn_str}")
                continue
            self.schemas[db_name] = Schema(get_schema(db_conn_str, db_type=db_type))

    @property
    def possible_ouput_path(self):
        return os.path.join(self.data_dir, "possible_outputs.json")

    def validate_item(self, item, section):
        return item.intent is not None and item.intent != [None], item.intent

    def add_item(self, item, section, validation_info):
        return self.items[section].append(item.intent)

    def add_item_from_cache(self, item, intent, section):
        self.items[section].append(intent)

    def clear_items(self):
        self.items = collections.defaultdict(list)

    def save(self, is_inference=False):
        os.makedirs(self.data_dir, exist_ok=True)

        if is_inference:
            assert len(self.items) > 0

        # Find all possible outputs
        possible_outputs = set()
        for section, items in self.items.items():
            if section == "train":
                for item in items:
                    possible_outputs.update(set(item))
        # Save all possible outputs
        with open(self.possible_ouput_path, "w") as f:
            json.dump(list(possible_outputs), f)
        # Save all preprocessed items
        for section, items in self.items.items():
            with open(os.path.join(self.data_dir, section + ".jsonl"), "w") as f:
                for item in items:
                    f.write(json.dumps(item) + "\n")

    def load(self, checkpoint_path=None):
        with open(self.possible_ouput_path, "r") as f:
            self.possible_output = json.load(f)

    def dataset(self, section):
        with open(os.path.join(self.data_dir, section + ".jsonl")) as f:
            return [json.loads(line) for line in f]


@registry.register("decoder", "NL2Intent")
class NL2IntentDecoder(torch.nn.Module):
    Preproc = NL2IntentDecoderPreproc

    def __init__(
        self, device, preproc, enc_recurrent_size=256, recurrent_size=256, dropout=0.1
    ):
        super().__init__()
        self.preproc = preproc
        self.output_classes = [
            "ambiguous",
            "infer_sql",
            "addtion",
            "sorry",
            "cannot_answer",
            "not_related",
            "greeting",
            "good_bye",
            "cannot_understand",
            "inform_sql:",
            "affirm",
            "negate",
            "thank_you",
            "inform_sql",
        ]
        self.enc_recurrent_size = enc_recurrent_size
        self.recurrent_size = recurrent_size

        self.output_class_embs = torch.nn.Embedding(
            len(self.output_classes), self.recurrent_size, device=device
        )

        self.decoder_layers = torch.nn.Sequential(
            torch.nn.Linear(self.enc_recurrent_size, self.recurrent_size),
            torch.nn.Dropout(dropout),
            torch.nn.ReLU(),
            torch.nn.Linear(self.recurrent_size, self.recurrent_size),
            torch.nn.Dropout(dropout),
            torch.nn.ReLU(),
            torch.nn.Linear(self.recurrent_size, len(self.output_classes)),
        )

    @property
    def _device(self):
        return next(self.parameters()).device

    def label_smooth_loss(self, X, target, smooth_value=0.1):
        if self.training:
            logits = torch.log_softmax(X, dim=1)
            size = X.size()[1]
            one_hot = torch.full(
                X.size(),
                smooth_value / (size - 1 if size > 1 else size),
                device=X.device,
            )
            one_hot.scatter_(1, target.unsqueeze(0), 1 - smooth_value)
            loss = F.kl_div(logits, one_hot, reduction="batchmean")
            return loss.unsqueeze(0)
        else:
            return torch.nn.functional.cross_entropy(X, target, reduction="none")

    def compute_loss(self, batch, enc_features):
        # Go through some layers
        logits = self.decoder_layers(enc_features)
        probs = torch.nn.functional.log_softmax(logits, dim=1)
        # Get gold index
        gold_indices = []
        for item in batch:
            gold_label = item[1][0]
            gold_idx = self.output_classes.index(gold_label)
            gold_indices.append(gold_idx)
        gold_indices = torch.tensor(gold_indices, device=self._device)
        # Compute loss
        losses = torch.nn.functional.cross_entropy(probs, gold_indices)
        return losses

    def compute_mle_loss(self, enc_input, example, desc_enc, debug=False):
        raise NotImplementedError

    def _desc_attention(self, prev_state, desc_enc):
        # prev_state shape:
        # - h_n: batch (=1) x emb_size
        # - c_n: batch (=1) x emb_size
        query = prev_state[0]
        if self.attn_type != "sep":
            return self.desc_attn(query, desc_enc.memory, attn_mask=None)
        else:
            question_context, question_attention_logits = self.question_attn(
                query, desc_enc.question_memory
            )
            schema_context, schema_attention_logits = self.schema_attn(
                query, desc_enc.schema_memory
            )
            return question_context + schema_context, schema_attention_logits
