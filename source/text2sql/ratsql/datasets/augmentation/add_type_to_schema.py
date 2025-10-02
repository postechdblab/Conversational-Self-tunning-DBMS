import os
import json


def read_json(path):
    with open(path, "r") as f:
        return json.load(f)

def write_json(data, path):
    with open(path, "w") as f:
        f.write(json.dumps(data, indent=4, ensure_ascii=False))

def read_in_values(path):
    dic = {}
    with open(path, "r") as f:
        for line in f.readlines():
            line = line.strip()
            items = line.split('\t')
            assert len(items) == 4
            col_name, col_type = items[1], items[3]
            dic[col_name.lower()] = col_type.lower()
    return dic


if __name__ == "__main__":
    workspaceFolder = "/data/hkkang/NL2QGM"
    schema_path = os.path.join(workspaceFolder, "ratsql/datasets/augmentation/schema.txt")
    column_dir = os.path.join(workspaceFolder, "ratsql/datasets/augmentation/column_types/")

    schema = read_json(schema_path)

    # Read and load column types
    for table in schema['tables']:
        table_name = table['name']
        file_path = os.path.join(column_dir, f"{table_name}.tsv")
        assert os.path.isfile(file_path), f"{file_path} does not exist!"
        col_type_dic = read_in_values(file_path)

        for column in table['columns']:
            column_name = column['name']
            column['type'] = col_type_dic[column_name]

    # overwrite schema file
    write_json(schema, schema_path)
    print("Done!")
