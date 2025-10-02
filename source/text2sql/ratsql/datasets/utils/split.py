import os
import random
import json
from pathlib import Path


def read_json(path):
    with open(path) as f:
        return json.load(f)

def write_json(data, path):
    with open(path, "w") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False))


def random_split(data, ratio=0.2):
    random.shuffle(data)
    split_idx = round(len(data) * ratio)
    data1 = data[:split_idx]
    data2 = data[split_idx:]
    print(f"data len compare: {len(data1)} vs {len(data2)}")
    return data1, data2

def split_wrt_existing_file(data, existing_path):
    existing_dev_data = read_json(existing_path)
    existing_dev_data_query = [datum['query'] for datum in existing_dev_data]
    # Filter data in existing_train_data
    train_data = []
    dev_data = []
    for datum in data:
        if datum['query'] in existing_dev_data_query:
            dev_data.append(datum)
        else:
            train_data.append(datum)
    print(f"data len compare: {len(train_data)} vs {len(dev_data)}")
    return train_data, dev_data

if __name__ == "__main__":
    workspaceFolder = "/data/hkkang/NL2QGM/"
    random.seed(0)
    root = Path(os.path.join(workspaceFolder, "data/samsung-yes-extra-op/"))
    data = read_json(root / "all.json")
    # data1, data2 = random_split(data)
    data1, data2 = split_wrt_existing_file(data, "data/samsung-yes-extra-op/dev_original.json")
    write_json(data1, root / "train.json")
    write_json(data2, root / "dev.json")
