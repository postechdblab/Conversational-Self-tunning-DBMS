import json
import re
import os
import sqlite3
import copy

from pathlib import Path
from typing import List, Dict

import attr
import psycopg2
import torch
import networkx as nx
from tqdm import tqdm

from source.text2sql.ratsql.utils import registry
from source.text2sql.ratsql.datasets.spider_lib import evaluation, evaluation_original
from source.text2sql.ratsql.datasets.utils import db_utils


@attr.s
class CosqlItem:
    text_ = attr.ib()
    intent = attr.ib()
    schema = attr.ib()
    orig = attr.ib()
    history = attr.ib(default=[])

    @property
    def text(self):
        return self.text_ + [
            sub_tmp for tmp in self.history for sub_tmp in ["[CLS]"] + tmp
        ]

    @property
    def unsplit_text(self):
        return " [CLS] ".join(
            [self.orig["utterance"]] + [" ".join(tmp) for tmp in self.history]
        )


@attr.s
class Column:
    id = attr.ib()
    table = attr.ib()
    name = attr.ib()
    unsplit_name = attr.ib()
    orig_name = attr.ib()
    type = attr.ib()
    foreign_key_for = attr.ib(default=None)
    description = attr.ib(default=None)


@attr.s
class Table:
    id = attr.ib()
    name = attr.ib()
    unsplit_name = attr.ib()
    orig_name = attr.ib()
    columns = attr.ib(factory=list)
    primary_keys = attr.ib(factory=list)


@attr.s
class Schema:
    db_id = attr.ib()
    tables = attr.ib()
    columns = attr.ib()
    foreign_key_graph = attr.ib()
    orig = attr.ib()
    connection = attr.ib(default=None)


def postprocess_original_name(s: str):
    return re.sub(r"([A-Z]+)", r" \1", s).replace("_", " ").lower().strip()


def load_tables(paths, use_original_evaluation, use_column_description=False):
    schemas = {}
    eval_foreign_key_maps = {}

    for path in paths:
        schema_dicts = json.load(open(path))
        for schema_dict in schema_dicts:
            tables = tuple(
                Table(
                    id=i,
                    name=name.split(),
                    unsplit_name=name,
                    orig_name=orig_name,
                )
                for i, (name, orig_name) in enumerate(
                    zip(schema_dict["table_names"], schema_dict["table_names_original"])
                )
            )

            if use_column_description:
                columns = []
                for i, (
                    (table_id, col_name),
                    (_, orig_col_name),
                    col_type,
                ) in enumerate(
                    zip(
                        schema_dict["column_names"],
                        schema_dict["column_names_original"],
                        schema_dict["column_types"],
                    )
                ):
                    try:
                        col_desc = schema_dict["column_descriptions"][i]
                    except:
                        col_desc = f"{col_name} of {tables[table_id].unsplit_name}"

                    column = Column(
                        id=i,
                        table=tables[table_id] if table_id >= 0 else None,
                        name=col_name.split(),
                        unsplit_name=col_name,
                        orig_name=orig_col_name,
                        type=col_type,
                        description=col_desc,
                    )
                    columns.append(column)
                columns = tuple(columns)
            else:
                columns = tuple(
                    Column(
                        id=i,
                        table=tables[table_id] if table_id >= 0 else None,
                        name=col_name.split(),
                        unsplit_name=col_name,
                        orig_name=orig_col_name,
                        type=col_type,
                    )
                    for i, (
                        (table_id, col_name),
                        (_, orig_col_name),
                        col_type,
                    ) in enumerate(
                        zip(
                            schema_dict["column_names"],
                            schema_dict["column_names_original"],
                            schema_dict["column_types"],
                        )
                    )
                )

            # Link columns to tables
            for column in columns:
                if column.table:
                    column.table.columns.append(column)

            for column_id in schema_dict["primary_keys"]:
                # Register primary keys
                column = columns[column_id]
                column.table.primary_keys.append(column)

            foreign_key_graph = nx.DiGraph()
            for source_column_id, dest_column_id in schema_dict["foreign_keys"]:
                # Register foreign keys
                source_column = columns[source_column_id]
                dest_column = columns[dest_column_id]
                source_column.foreign_key_for = dest_column
                foreign_key_graph.add_edge(
                    source_column.table.id,
                    dest_column.table.id,
                    columns=(source_column_id, dest_column_id),
                )
                foreign_key_graph.add_edge(
                    dest_column.table.id,
                    source_column.table.id,
                    columns=(dest_column_id, source_column_id),
                )

            db_id = schema_dict["db_id"]
            assert db_id not in schemas
            schemas[db_id] = Schema(
                db_id, tables, columns, foreign_key_graph, schema_dict
            )
            if use_original_evaluation:
                build_foreign_key_map_func = evaluation.build_foreign_key_map
            else:
                build_foreign_key_map_func = evaluation_original.build_foreign_key_map
            eval_foreign_key_maps[db_id] = build_foreign_key_map_func(schema_dict)

    return schemas, eval_foreign_key_maps


@registry.register("dataset", "cosql")
class CosqlDataset(torch.utils.data.Dataset):
    # XXX: if db_type varies, add factory class for database connection to datasets.utils
    def __init__(
        self,
        paths,
        tables_paths,
        db_path=None,
        limit=None,
        use_original_evaluation=False,
        use_column_description=False,
        db_type="sqlite",
        grammar="spider",
    ):
        self.paths = paths
        self.cache_path = "/".join(paths[0].split("/")[:-1] + ["preproc_cache.jsonl"])
        self.db_path = db_path
        self.db_type = db_type
        self.grammar = grammar
        self.tables_path = tables_paths
        self.examples = []

        self.schemas, self.eval_foreign_key_maps = load_tables(
            tables_paths,
            use_original_evaluation,
            use_column_description=use_column_description,
        )
        self.use_original_evaluation = use_original_evaluation

        for path in paths:
            history = []
            prev_db_id = None
            raw_data = json.load(open(path))
            for entry in raw_data:
                # Pass if no intent
                if entry["intent"] in [[None], None]:
                    print("Passing data without gold intent")
                    continue
                # Reset history if db_id changes
                if entry["database_id"] != prev_db_id:
                    history = []
                # Create item and save item
                item = CosqlItem(
                    text_=entry["utterance_toks"],
                    intent=[s.lower() for s in entry["intent"]],
                    schema=self.schemas[entry["database_id"]],
                    orig=entry,
                    history=copy.deepcopy(history),
                )
                self.examples.append(item)
                # Change DB state
                prev_db_id = entry["database_id"]
                # Reset history
                if "GOOD_BYE" in entry["intent"]:
                    history = []
                else:
                    history.append(entry["utterance_toks"])

        # Backup in-memory copies of all the DBs and create the live connections
        for db_id, schema in tqdm(self.schemas.items(), desc="DB connections"):
            db_conn_str = db_utils.create_db_conn_str(db_path, db_id, db_type=db_type)
            if os.path.isfile(db_conn_str):
                conn = db_utils.connect(db_conn_str, db_type=db_type).con

                if db_type in db_utils.SQLITE_DBTYPE_IDENTIFIERS:
                    dest = sqlite3.connect(":memory:")
                    dest.row_factory = sqlite3.Row
                    conn.backup(dest)
                    conn.close()
                    conn = dest

                schema.connection = conn

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        return self.examples[idx]

    def __del__(self):
        for _, schema in self.schemas.items():
            if schema.connection:
                schema.connection.close()

    def create_key_from(self, item):
        return f"<db_id>:[{item.schema.db_id}]<text>:{item.text}<intent>:{item.intent}"

    class Metrics:
        def __init__(self, *args, **kwargs):
            self.results = []

        def add(self, item, pred_label):
            gold = item.intent[0]
            ret_dict = {
                "question": " ".join(item.text),
                "gold": gold,
                "pred": pred_label,
                "correct": gold == pred_label,
            }
            self.results.append(ret_dict)
            return ret_dict

        def finalize(self):
            total_acc = sum([1 for r in self.results if r["correct"]]) / len(
                self.results
            )
            return {"per_item": self.results, "total_scores": total_acc}
