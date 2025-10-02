import json
import re
import sqlite3
from copy import copy
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
class SpiderItem:
    text = attr.ib()
    code = attr.ib()
    schema = attr.ib()
    orig = attr.ib()
    orig_schema = attr.ib()


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


def create_global_schema(schema_dicts):
    global_schema_dict = {
        "db_id": "global_schema",
        "column_names": [[-1, "*"]],
        "column_names_original": [[-1, "*"]],
        "column_types": ["text"],
        "table_names": [],
        "table_names_original": [],
        "primary_keys": [],
        "foreign_keys": [],
    }
    for schema_dict in schema_dicts:
        last_tab_len = len(global_schema_dict["table_names"])
        last_col_len = len(global_schema_dict["column_names"])
        # Add column
        assert len(schema_dict["column_names"]) == len(
            schema_dict["column_names_original"]
        )
        for (local_tab_idx, col_name), (local_tab_idx_, col_name_original) in zip(
            schema_dict["column_names"], schema_dict["column_names_original"]
        ):
            assert local_tab_idx == local_tab_idx_
            if local_tab_idx == -1:
                continue
            global_schema_dict["column_names"].append(
                [local_tab_idx + last_tab_len, col_name]
            )
            global_schema_dict["column_names_original"].append(
                [local_tab_idx + last_tab_len, col_name_original]
            )

        # Add column type
        for col_type in schema_dict["column_types"][1:]:
            global_schema_dict["column_types"].append(col_type)

        # Add table
        for tab_name, tab_name_original in zip(
            schema_dict["table_names"], schema_dict["table_names_original"]
        ):
            global_schema_dict["table_names"].append(tab_name)
            global_schema_dict["table_names_original"].append(tab_name_original)

        # Add P/F keys
        for src, dest in schema_dict["foreign_keys"]:
            global_schema_dict["foreign_keys"].append(
                [src + last_col_len - 1, dest + last_col_len - 1]
            )
        for p_key in schema_dict["primary_keys"]:
            global_schema_dict["primary_keys"].append(p_key + last_col_len - 1)
        # # Add relationships
        # for rel in schema_dict['relationships']:
        #     global_schema_dict['relationships'].append(rel)
    return global_schema_dict


def add_db_id(list_of_table_names, db_id, deliminator=" "):
    tmp = []
    for item in list_of_table_names:
        if db_id == item:
            tmp.append(item)
        else:
            tmp.append(db_id.lower() + deliminator + item)
    return tmp


def create_schema(schema_dict, use_column_description=False):
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
        for i, ((table_id, col_name), (_, orig_col_name), col_type) in enumerate(
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
            for i, ((table_id, col_name), (_, orig_col_name), col_type) in enumerate(
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
    return Schema(db_id, tables, columns, foreign_key_graph, schema_dict)


def load_tables(
    paths,
    use_original_evaluation,
    use_column_description=False,
    append_db_id=False,
    use_global_schema=False,
):
    schemas = {}
    eval_foreign_key_maps = {}

    for path in paths:
        schema_dicts = json.load(open(path))
        if append_db_id or use_global_schema:
            for schema_dict in schema_dicts:
                schema_dict["table_names"] = add_db_id(
                    schema_dict["table_names"], schema_dict["db_id"], " "
                )
                schema_dict["table_names_original"] = add_db_id(
                    schema_dict["table_names_original"], schema_dict["db_id"], "_"
                )

        for schema_dict in schema_dicts:
            db_id = schema_dict["db_id"]
            assert db_id not in schemas
            schemas[db_id] = create_schema(schema_dict, use_column_description)
            if use_original_evaluation:
                build_foreign_key_map_func = evaluation.build_foreign_key_map
            else:
                build_foreign_key_map_func = evaluation_original.build_foreign_key_map
            eval_foreign_key_maps[db_id] = build_foreign_key_map_func(schema_dict)

    return schemas, eval_foreign_key_maps


@registry.register("dataset", "spider")
class SpiderDataset(torch.utils.data.Dataset):
    # XXX: if db_type varies, add factory class for database connection to datasets.utils
    def __init__(
        self,
        paths,
        tables_paths,
        db_path=None,
        demo_path=None,
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
            raw_data = json.load(open(path))
            for entry in raw_data:
                item = SpiderItem(
                    text=entry["question_toks"],
                    code=entry["sql"],
                    schema=self.schemas[entry["db_id"]],
                    orig=entry,
                    orig_schema=self.schemas[entry["db_id"]].orig,
                )
                self.examples.append(item)

        if demo_path:
            self.demos: Dict[str, List] = json.load(open(demo_path))

        # Backup in-memory copies of all the DBs and create the live connections
        for db_id, schema in tqdm(self.schemas.items(), desc="DB connections"):
            db_conn_str = db_utils.create_db_conn_str(db_path, db_id, db_type=db_type)
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

    class Metrics:
        def __init__(self, dataset, tables_path, use_original_evaluation=False):
            self.dataset = dataset
            self.use_original_evaluation = use_original_evaluation

            # Select which method to use
            if use_original_evaluation:
                build_foreign_key_map_func = evaluation_original.build_foreign_key_map
                evaluator_class = evaluation_original.Evaluator
            else:
                build_foreign_key_map_func = evaluation.build_foreign_key_map
                evaluator_class = evaluation.Evaluator

            self.foreign_key_maps = {
                db_id: build_foreign_key_map_func(schema.orig)
                for db_id, schema in self.dataset.schemas.items()
            }
            tables = json.load(open(tables_path))

            if use_original_evaluation:
                self.evaluator = evaluator_class(
                    self.dataset.db_path,
                    self.foreign_key_maps,
                    tables,
                    "match",
                    db_type=self.dataset.db_type,
                )
            else:
                self.evaluator = evaluator_class(
                    self.dataset.db_path,
                    self.foreign_key_maps,
                    tables,
                    "match",
                    db_type=self.dataset.db_type,
                    grammar=self.dataset.grammar,
                )
            self.results = []

        def add(self, item, inferred_code, confidences=None, orig_question=None):
            ret_dict = self.evaluator.evaluate_one(
                item.schema.db_id, item.orig["query"], inferred_code
            )
            if confidences:
                ret_dict["confidences"] = confidences
            if orig_question:
                # Insert new key in front
                tmp = {"orig_question": item.orig["question"]}
                tmp.update(ret_dict)
                ret_dict = tmp
            self.results.append(ret_dict)
            return ret_dict

        def add_beams(self, item, inferred_codes, orig_question=None):
            beam_dict = {}
            if orig_question:
                beam_dict["orig_question"] = orig_question
            for i, code in enumerate(inferred_codes):
                ret_dict = self.evaluator.evaluate_one(
                    item.schema.db_id, item.orig["query"], code
                )
                beam_dict[i] = ret_dict
                if ret_dict["exact"] is True:
                    break
            self.results.append(beam_dict)

        def finalize(self):
            self.evaluator.finalize()
            return {"per_item": self.results, "total_scores": self.evaluator.scores}
