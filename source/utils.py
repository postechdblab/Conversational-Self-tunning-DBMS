import os
import tqdm
import sqlite3
from pathlib import Path
from source.text2sql.ratsql.models.spider.spider_enc import (
    SpiderEncoderBertPreproc,
    Bertokens,
)
from source.text2sql.ratsql.datasets.spider import load_tables, SpiderItem


class One_time_Preprocesser:
    def __init__(self, db_path, table_path, preproc_args):
        self.enc_preproc = SpiderEncoderBertPreproc(**preproc_args)
        self.bert_version = preproc_args["bert_version"]
        self.schemas = load_tables([table_path], True)[0]
        self._conn(db_path)

    def _conn(self, db_path):
        # Backup in-memory copies of all the DBs and create the live connections
        for db_id, schema in tqdm.tqdm(self.schemas.items(), desc="DB connections"):
            sqlite_path = Path(db_path) / db_id / f"{db_id}.sqlite"
            source: sqlite3.Connection
            if os.path.isfile(sqlite_path):
                with sqlite3.connect(
                    str(sqlite_path), check_same_thread=False
                ) as source:
                    dest = sqlite3.connect(":memory:", check_same_thread=False)
                    dest.row_factory = sqlite3.Row
                    source.backup(dest)
                schema.connection = dest

    def run(self, text, db_id):
        schema = self.schemas[db_id]
        # Validate
        question = self.enc_preproc._tokenize(text.split(" "), text)
        preproc_schema = self.enc_preproc._preprocess_schema(
            schema, bert_version=self.bert_version
        )
        num_words = (
            len(question)
            + 2
            + sum(len(c) + 1 for c in preproc_schema.column_names)
            + sum(len(t) + 1 for t in preproc_schema.table_names)
        )
        assert num_words < 512, "input too long"
        question_bert_tokens = Bertokens(question, bert_version=self.bert_version)
        # preprocess
        sc_link = question_bert_tokens.bert_schema_linking(
            preproc_schema.normalized_column_names,
            preproc_schema.normalized_table_names,
        )
        cv_link = question_bert_tokens.bert_cv_linking(schema)
        spider_item = SpiderItem(
            text=text,
            code=None,
            schema=self.schemas[db_id],
            orig=None,
            orig_schema=self.schemas[db_id].orig,
        )
        preproc_item = {
            "sql": "",
            "raw_question": text,
            "question": question,
            "db_id": schema.db_id,
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
            "interaction_id": None,
            "turn_id": None,
        }
        return spider_item, preproc_item
