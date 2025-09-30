import json
import re
import shutil
import argparse
from pathlib import Path


def split_dataset_by_db():
    # kaggbeDBQA 데이터셋이 여러 db가 하나로 뭉쳐있는데,
    # 이를 db별로 나눠주는 코드
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_dir", type=Path, default="/mnt/disk1/jjkim/NL2QGM/data/kaggle-dbqa")
    args = parser.parse_args()

    root = args.dataset_dir
    src_table = root / "tables.json"

    src_db_root:Path = root / "database"
    src_ex_root:Path = root / "examples"
    for db in src_db_root.iterdir():
        dbname = db.stem
        dst_root = root.parent / f"{root.name}-div" / f"{dbname}"
        dst_root.mkdir(exist_ok=True, parents=True)
        
        # copy databse directory
        dst_db_root = dst_root / "database"
        dst_db_root.mkdir(exist_ok=True)
        shutil.copytree(db, dst_db_root / dbname)

        # copy tables.json file
        with open(src_table, 'r') as f:
            src_table_objects = json.load(f)
            dst_table_objects = list(filter(lambda x: x["db_id"]==dbname, src_table_objects))
        dst_table = dst_root / "tables.json"
        with open(dst_table, 'w') as f:
            json.dump(dst_table_objects, f, ensure_ascii=False, indent=4)

        # copy examples
        for src_ex in src_ex_root.iterdir():
            pattern = re.compile(f"{dbname}")
            if pattern.match(src_ex.stem):
                dst_ex_root = dst_root / "examples"
                dst_ex_root.mkdir(exist_ok=True)
                shutil.copy(src_ex, dst_ex_root)


if __name__ == '__main__':
    split_dataset_by_db()