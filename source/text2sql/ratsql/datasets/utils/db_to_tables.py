import argparse
import json
import sys
from pathlib import Path

sys.path.append(".")
from source.text2sql.ratsql.datasets.spider_lib.process_sql import (
    get_schema,
    get_dbs,
    get_foreign_key_constraints,
)


def db_to_tables(json_file: Path):
    """converts database to tables.json"""
    dbs = get_dbs(
        "user=postgres password=postgres host=localhost port=5435", db_type="postgresql"
    )
    tables = []
    for db in dbs:
        # get schema
        schema = get_schema(
            f"dbname={db} user=postgres password=postgres host=localhost port=5435",
            db_type="postgresql",
            with_data_type=True,
        )

        constraints = get_foreign_key_constraints(
            f"dbname={db} user=postgres password=postgres host=localhost port=5435",
            db_type="postgresql",
        )

        table_id_map = {}
        table_names_original = []
        for i, table in enumerate(schema.keys()):
            table_id_map[table] = i
            table_names_original.append(table.replace("public.", ""))

        column_names_original = [(-1, "*")]
        column_types = ["text"]
        for table, cols in schema.items():
            for col, type in cols:
                column_names_original.append((table_id_map[table], col))
                column_types.append(type)
        foreign_keys = []
        for ft, fk, pt, pk in constraints:
            for col_id, (t_id, col_name) in enumerate(column_names_original):
                if table_id_map[ft] == t_id and fk == col_name:
                    fkey_id = col_id
                if table_id_map[pt] == t_id and pk == col_name:
                    pkey_id = col_id
            foreign_keys.append([fkey_id, pkey_id])

        table = {
            "column_names": list(
                map(
                    lambda x: (x[0], x[1].lower().replace("_", " ")),
                    column_names_original,
                )
            ),
            "column_names_original": column_names_original,
            "column_types": column_types,
            "table_names": list(
                map(
                    lambda x: x.lower()
                    .replace("_", " ")
                    .replace(".", " ")
                    .replace("public ", ""),
                    table_names_original,
                )
            ),
            "table_names_original": table_names_original,
            "foreign_keys": foreign_keys,
            "primary_keys": [],
            "db_id": db,
        }
        tables.append(table)

    with open(json_file, "w") as f:
        json.dump(tables, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json_file", type=Path, default="data/samsung/tables.json")

    args = parser.parse_args()

    db_to_tables(args.json_file)
