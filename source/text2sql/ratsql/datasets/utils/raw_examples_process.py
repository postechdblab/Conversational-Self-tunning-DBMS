import argparse
import json
import sys
from pathlib import Path
import traceback

from tqdm import tqdm

sys.path.append(".")
from source.text2sql.ratsql.datasets.spider_lib.process_sql import (
    Schema,
    get_schema,
    get_sql,
)
from source.text2sql.ratsql.datasets.utils.db_utils import create_db_conn_str


def package_example(sql, nl, schema, db_id, grammar):
    try:
        sql_dict = get_sql(schema, sql, grammar=grammar)
    except:
        # sql_dict = get_sql(schema, sql, grammar=grammar)
        traceback.print_exc()
        print(sql)
        print()
        sql_dict = None

    example = {
        "db_id": db_id,
        "query": sql,
        "question": nl,
        "sql": sql_dict,
        "query_toks": sql.split(),
        "question_toks": nl.split(),
    }

    return example


def raw_examples_process(
    raw_examples_file, out_file, tables_file, db_path, db_type, grammar="spider"
):
    with open(tables_file, "r") as f:
        dbs = json.load(f)

    with open(raw_examples_file, "r") as f:
        raw_examples = json.load(f)

    examples = []
    for raw_example in tqdm(raw_examples):
        db_id = raw_example["db_id"]
        sql = raw_example["query"]
        nl = raw_example["question"]

        db_conn_str = create_db_conn_str(db_path, db_id, db_type)
        schema = get_schema(db_conn_str, db_type)
        db = next(filter(lambda x: x["db_id"] == db_id, dbs))
        schema = Schema(schema, tables=db)
        example = package_example(sql, nl, schema, db_id, grammar)
        examples.append(example)

    # print out file
    with open(out_file, "w") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    dataset_root = Path("/data/jjkim/NL2QGM/data/spider-kor-cloud-postgres")
    parser.add_argument(
        "--raw_examples_file", type=Path, default=dataset_root / "dev-raw.json"
    )
    parser.add_argument("--out_file", type=Path, default=dataset_root / "dev.json")
    parser.add_argument(
        "--tables_file", type=Path, default=dataset_root / "tables.json"
    )
    parser.add_argument("--db_path", type=str, default=dataset_root / "database")
    parser.add_argument("--db_type", type=str, default="sqlite")
    parser.add_argument("--grammar", type=str, default="postgres")

    args = parser.parse_args()

    raw_examples_process(
        args.raw_examples_file,
        args.out_file,
        args.tables_file,
        args.db_path,
        args.db_type,
        grammar=args.grammar,
    )
