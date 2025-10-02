import os
import csv
import sys
import json
import argparse
from pathlib import Path
import traceback

sys.path.append(".")
from source.text2sql.ratsql.datasets.spider_lib.process_sql import (
    Schema,
    get_sql,
    get_schema,
)


# you need to execute it using command below
# python -m ratsql.datasets.utils.pair_tsv_to_json
def pair_tsv_to_json(
    tsv_file: Path, json_file: Path, tables_file: Path, grammar: str = "spider"
):
    """converts tsv formatted nl-sql pair dataset to json format"""

    # get schema
    with open(tables_file, "r") as f:
        tables = json.load(f)
    schema = Schema(
        get_schema(
            "dbname=samsung user=postgres password=postgres host=localhost port=5435",
            db_type="postgresql",
        ),
        tables=tables[0],
    )

    # read tsv file
    examples = []
    with open(tsv_file, "r") as f:
        rows = csv.reader(f, delimiter="\t")
        next(rows)
        total_fail = 0
        nested_query = 0
        in_operator = 0
        etc_counter = 0
        for row in rows:
            if row == [] or row[0][0] == "#":
                continue
            sql = row[0].replace("\n", " ")
            nl = row[1]
            try:
                sql_dict = get_sql(schema, sql, grammar=grammar)
                example = {
                    "db_id": "samsung",
                    "query": sql,
                    "query_toks": sql.split(),
                    "question": nl,
                    "question_toks": nl.split(),
                    "sql": sql_dict,
                }
                examples.append(example)
            except:
                total_fail += 1
                if "(select" in sql:
                    nested_query += 1
                elif " in (" in sql:
                    in_operator += 1
                else:
                    print(f"{sql}")
                    traceback.print_exc()
                    print()
                    # sql_dict = get_sql(schema, sql, grammar=grammar)
                    etc_counter += 1

        print(f"total_fail: {total_fail}")
        print(f"(select : {nested_query}")
        print(f"in_operator : {in_operator}")
        print(f"etc: {etc_counter}")

    # write json file
    with open(json_file, "w") as f:
        json.dump(examples, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    workspaceFolder = "/data/hkkang/NL2QGM/"
    parser = argparse.ArgumentParser()
    parser.add_argument("--tsv_file", type=Path, default=os.path.join("all.tsv"))
    parser.add_argument("--json_file", type=Path, default=os.path.join("all.json"))
    parser.add_argument(
        "--tables_file",
        type=Path,
        default=os.path.join(
            workspaceFolder, "data/samsung-addop-hkkang-testing/tables.json"
        ),
    )
    parser.add_argument("--grammar", type=str, default="postgres")
    args = parser.parse_args()

    pair_tsv_to_json(args.tsv_file, args.json_file, args.tables_file, args.grammar)
