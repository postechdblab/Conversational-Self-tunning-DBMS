import json
from pathlib import Path


def read_json(path):
    with open(path) as f:
        return json.load(f)

def write_json(data, path):
    with open(path, "w") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    root = Path("/mnt/sdc/jjkim/NL2QGM/data/samsung-addop-nopre3")
    data1 = read_json(root / "train_original.json")
    data2 = read_json(root / "manual_raw_examples.json")
    write_json(data1+data2, root / "train.json")
