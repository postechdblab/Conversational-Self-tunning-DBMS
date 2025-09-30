import json
import argparse
from pathlib import Path
import sys

sys.path.append(".")
from source.text2sql.ratsql.datasets.spider_lib.process_sql import (
    Schema,
    get_schema,
    get_sql,
)


def package_example(sql, nl, schema, db_id, grammar):
    sql_dict = get_sql(schema, sql, grammar=grammar)

    example = {
        "db_id": db_id,
        "query": sql,
        "question": nl,
        "sql": sql_dict,
        "query_toks": sql.split(),
        "question_toks": nl.split(),
    }

    return example


def simple_query_generation(tables_file, out_file, grammar="spider"):
    # load alias file
    # load tables file
    with open(tables_file, "r") as f:
        dbs = json.load(f)

    examples = []
    for db in dbs:
        schema = Schema(
            get_schema(
                f'dbname={db["db_id"]} user=postgres password=postgres host=localhost port=5435',
                db_type="postgresql",
            ),
            tables=db,
        )

        tnames = db["table_names_original"]
        taliases = db["table_names_alias"]
        cname_calias_dict = db["column_names_alias"]

        # create examples
        for tid, tname in enumerate(tnames):
            sql = f"select * from {tname}"
            for talias in taliases[tid]:
                nl = f"{talias} 테이블을 출력하라."

                example = package_example(sql, nl, schema, db["db_id"], grammar)
                examples.append(example)

                for cname, caliases in cname_calias_dict[tid].items():
                    sql = f"select {cname} from {tname}"
                    for calias in caliases:
                        nl = f"{talias} 테이블에서 {calias} 컬럼을 출력하라."
                        example = package_example(sql, nl, schema, db["db_id"], grammar)
                        examples.append(example)

    # print out file
    with open(out_file, "w") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    dataset_root = Path("/mnt/sdc/jjkim/NL2QGM/data/samsung-adddata")
    parser.add_argument(
        "--tables_file", type=Path, default=dataset_root / "tables.json"
    )
    parser.add_argument("--out_file", type=Path, default=dataset_root / "examples.json")
    parser.add_argument("--grammar", type=str, default="spider")

    args = parser.parse_args()

    simple_query_generation(args.tables_file, args.out_file, grammar=args.grammar)
