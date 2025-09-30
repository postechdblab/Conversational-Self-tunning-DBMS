import os
import torch
import tqdm
import sqlite3
import json
import _jsonnet
from pathlib import Path
from source.text2sql.ratsql.models.spider.spider_enc import SpiderEncoderBertPreproc, Bertokens
from source.text2sql.ratsql.datasets.spider import load_tables, SpiderItem
from source.text2sql.ratsql.commands.analysis import Attribution
from source.text2sql.ratsql.commands.infer import Inferer


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


def get_model(config, model_type="text_to_sql", preprocessor=None):
    device = config["model"][model_type]["device"]
    if model_type in ["text_to_sql", "result_analysis"]:
        # get model config
        experiment_config_path = config["model"][model_type]["experiment_config_path"]
        if os.path.isfile(experiment_config_path):
            exp_config = json.loads(_jsonnet.evaluate_file(experiment_config_path))
            model_config_file = exp_config["model_config"]
            model_config_args = exp_config["model_config_args"]
            model_config = json.loads(
                _jsonnet.evaluate_file(
                    model_config_file, tla_codes={"args": json.dumps(model_config_args)}
                )
            )
        else:
            raise RuntimeError(f"config file does not exist: {experiment_config_path}")
        db_path = config["data"]["database_path"]
        table_path = config["data"]["table_path"]
        model_config["model"]["encoder_preproc"]["save_path"] = config["model"][
            model_type
        ]["model_ckpt_dir_path"]
        model_config["model"]["decoder_preproc"]["save_path"] = config["model"][
            model_type
        ]["model_ckpt_dir_path"]
        # get preprocessor
        if model_type == "text_to_sql":
            preprocessor = One_time_Preprocesser(
                db_path, table_path, model_config["model"]["encoder_preproc"]
            )
        else:
            preprocessor = Attribution(model_config)

        # get model
        inferer = Inferer(model_config)
        model, step = inferer.load_model(
            config["model"][model_type]["model_ckpt_dir_path"]
        )
        model.to(device)

    elif model_type == "text_to_intent":
        # get model config
        # get model config
        experiment_config_path = config["model"][model_type]["experiment_config_path"]
        if os.path.isfile(experiment_config_path):
            exp_config = json.loads(_jsonnet.evaluate_file(experiment_config_path))
            model_config_file = exp_config["model_config"]
            model_config_args = exp_config["model_config_args"]
            model_config = json.loads(
                _jsonnet.evaluate_file(
                    model_config_file, tla_codes={"args": json.dumps(model_config_args)}
                )
            )
        else:
            assert "config file does not exist"
        inferer = Inferer(model_config)
        model, step = inferer.load_model(
            config["model"][model_type]["model_ckpt_dir_path"]
        )

    return model, preprocessor


def nl2intent_inferer(model, preproc_item):
    enc_features = model.encoder([preproc_item])
    logits = model.decoder.decoder_layers(enc_features)
    pred_ids = logits.argmax(dim=1)
    pred_labels = [model.decoder.output_classes[id] for id in pred_ids]
    return pred_labels
