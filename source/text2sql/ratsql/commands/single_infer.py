import os
import json
import time
import tqdm
import logging
import sqlite3
import argparse
import _jsonnet
from pathlib import Path

from source.text2sql.ratsql.commands.infer import Inferer
from source.text2sql.ratsql.models.spider.spider_enc import (
    SpiderEncoderBertPreproc,
    Bertokens,
)
from source.text2sql.ratsql.models.spider import spider_beam_search
from source.text2sql.ratsql.datasets.spider import (
    load_tables,
    SpiderItem,
    add_db_id,
    create_global_schema,
    create_schema,
)
from source.text2sql.ratsql.datasets.spider_lib import evaluation_original


class One_time_Preprocesser:
    def __init__(self, db_path, table_path, preproc_args, append_db_id=False):
        self.enc_preproc = SpiderEncoderBertPreproc(**preproc_args)
        self.bert_version = preproc_args["bert_version"]
        self.table_path = table_path
        self.schemas = load_tables(
            [table_path], True, append_db_id=append_db_id, use_global_schema=False
        )[0]
        self._conn(db_path)

    def _conn(self, db_path):
        # Backup in-memory copies of all the DBs and create the live connections
        for db_id, schema in tqdm.tqdm(self.schemas.items(), desc="DB connections"):
            sqlite_path = Path(db_path) / db_id / f"{db_id}.sqlite"
            source: sqlite3.Connection
            if os.path.isfile(sqlite_path):
                with sqlite3.connect(str(sqlite_path)) as source:
                    dest = sqlite3.connect(":memory:")
                    dest.row_factory = sqlite3.Row
                    source.backup(dest)
                schema.connection = dest

    def create_global_schemas(self):
        db_set = {}
        tmp_dbs = []
        accum_len = 0
        for db_id, schema in self.schemas.items():
            preproc_schema = self.enc_preproc._preprocess_schema(
                schema, bert_version=self.bert_version
            )
            schema_len = sum(len(c) + 1 for c in preproc_schema.column_names) + sum(
                len(t) + 1 for t in preproc_schema.table_names
            )
            if accum_len + schema_len + 2100 < self.enc_preproc.max_position_embeddings:
                # Append
                tmp_dbs.append(db_id)
                accum_len += schema_len
            else:
                # Stop and create new schema
                db_set[f"global_schema_{len(db_set)}"] = tmp_dbs
                tmp_dbs = [db_id]
                accum_len = schema_len
        db_set[f"global_schema_{len(db_set)}"] = tmp_dbs

        # Load schema again
        schema_dicts = json.load(open(self.table_path))
        for schema_dict in schema_dicts:
            schema_dict["table_names"] = add_db_id(
                schema_dict["table_names"], schema_dict["db_id"], " "
            )
            schema_dict["table_names_original"] = add_db_id(
                schema_dict["table_names_original"], schema_dict["db_id"], "_"
            )

        # Create schemas and forieng_key_maps
        schemas = {}

        for key, db_ids in db_set.items():
            selected_schema_dicts = [
                schema_dict
                for schema_dict in schema_dicts
                if schema_dict["db_id"] in db_ids
            ]
            selected_global_dict = create_global_schema(selected_schema_dicts)
            selected_global_dict["db_id"] = key
            schemas[key] = create_schema(selected_global_dict)

        self.schemas.update(schemas)

        # Create inverted index:
        inverted_db_set = {}
        for key, items in db_set.items():
            for item in items:
                inverted_db_set[item] = key

        return inverted_db_set

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
        assert (
            num_words < self.enc_preproc.max_position_embeddings
        ), f"input too long (longer than {self.enc_preproc.max_position_embeddings})"
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


def get_model_from_path(
    path,
    device,
    db_path,
    table_path,
    append_db_id,
):
    # Load config
    if os.path.isfile(os.path.join(path, "config.jsonnet")):
        exp_config = json.loads(
            _jsonnet.evaluate_file(os.path.join(path, "config.jsonnet"))
        )
        model_config_file = exp_config["model_config"]
        model_config_args = exp_config["model_config_args"]
        config = json.loads(
            _jsonnet.evaluate_file(
                model_config_file, tla_codes={"args": json.dumps(model_config_args)}
            )
        )
    else:
        assert os.path.isfile(
            os.path.join(path, "config.json")
        ), "config file does not exist"
        config = json.load(open(os.path.join(path, "config.json")))

    config["model"]["encoder_preproc"]["save_path"] = path
    config["model"]["decoder_preproc"]["save_path"] = path
    # db_path = config['data']['train']['db_path']
    # table_paths = config['data']['train']['tables_paths']
    # Create preprocessor
    preprocessor = One_time_Preprocesser(
        db_path,
        table_path,
        config["model"]["encoder_preproc"],
        append_db_id=append_db_id,
    )

    # Create inferer
    inferer = Inferer(config)
    model, step = inferer.load_model(os.path.join(path))
    model.to(device)

    # Test inference
    # preproc_item = preprocessor.run("Show all singers", schema)
    # beams = spider_beam_search.beam_search_with_heuristics(model, None, preprocessor, beam_size=2, max_steps=150)

    return model, preprocessor


def main(args):
    # Settings
    model_path = args.model_path
    device = "cuda:0"
    db_path = "/home/hkkang/NL2QGM/data/spider/database/"
    table_path = "/home/hkkang/NL2QGM/data/spider/tables.json"
    data_path = "/home/hkkang/NL2QGM/data/spider/dev.json"
    append_db_id = True
    use_global_schema = False

    # Create table mapping
    with open(table_path) as f:
        dbs = json.load(f)
    db_table_mapping = {}
    for db in dbs:
        db_id = db["db_id"]
        table_names = db["table_names_original"]
        mapping = {}
        for table_name in table_names:
            if table_name != db_id:
                mapping[table_name] = db_id + "_" + table_name
        db_table_mapping[db_id] = mapping

    # Load model
    model_load_start_time = time.time()
    model, preprocessor = get_model_from_path(
        model_path, device, db_path, table_path, append_db_id=append_db_id
    )

    if use_global_schema:
        global_db_mapping = preprocessor.create_global_schemas()
    else:
        global_db_mapping = None

    logging.info(f"Model Load Time: {(time.time() - model_load_start_time):.2f}")

    # Load eval data
    with open(data_path) as f:
        eval_data = json.load(f)

    correct_cnt = 0
    for idx, eval_datum in enumerate(eval_data):
        db_id = eval_datum["db_id"]
        question = eval_datum["question"]
        gold_sql = eval_datum["query"]

        # append db_id to table name
        if append_db_id:
            mapping = db_table_mapping[db_id]
            for key, value in mapping.items():
                gold_sql = gold_sql.replace(";", "").lower()
                gold_sql = gold_sql + " "
                # gold_sql = gold_sql.replace(f" {key} ", f" {value} ")
                # gold_sql = gold_sql.replace(f" {key})", f" {value})")
                gold_sql = gold_sql.replace(f" {key.lower()} ", f" {value} ")
                gold_sql = gold_sql.replace(f" {key.lower()})", f" {value})").strip()
                # gold_sql = gold_sql.replace(f" {key.upper()} ", f" {value} ")
                # gold_sql = gold_sql.replace(f" {key.upper()})", f" {value})").strip()

        infer_start_time = time.time()
        # Infer
        orig_item, preproc_item = preprocessor.run(
            question, global_db_mapping[db_id] if use_global_schema else db_id
        )
        beams = spider_beam_search.beam_search_with_heuristics(
            model, orig_item, (preproc_item, None), beam_size=2, max_steps=150
        )
        sql_dict, inferred_code = beams[0].inference_state.finalize()
        pred_sql = inferred_code

        logging.info("Inference Time: %f" % (time.time() - infer_start_time))
        logging.info(f"idx:{idx}")
        logging.info(question)
        logging.info(pred_sql)
        logging.info(gold_sql)

        # Evaluate
        foreign_key_maps = {
            db_id: evaluation_original.build_foreign_key_map(schema.orig)
            for db_id, schema in preprocessor.schemas.items()
        }
        evaluator = evaluation_original.Evaluator(
            db_path, foreign_key_maps, table_path, "match", append_db_id=append_db_id
        )
        result = evaluator.evaluate_one(db_id, gold_sql, pred_sql)
        logging.info(bool(result["exact"]))
        print("\n")
        if bool(result["exact"]):
            correct_cnt += 1

    print(f"Accuracy:{correct_cnt/len(eval_data):.4f}")


if __name__ == "__main__":

    def _get_arguments():
        parser = argparse.ArgumentParser()

        model_path_group = parser.add_argument_group("model_path")
        model_path_group.add_argument(
            "--model_path",
            type=str,
            default="/home/hkkang/NL2QGM/logdir/spider-longformer/bs=3,lr=7.4e-04,bert_lr=3.0e-06,end_lr=0e0,seed=3,join_cond=false/",
        )

        parser.add_argument("--db_id", type=str, default=None)

        args = parser.parse_args()

        return args

    args = _get_arguments()

    logging.basicConfig(level=logging.INFO)
    main(args)
