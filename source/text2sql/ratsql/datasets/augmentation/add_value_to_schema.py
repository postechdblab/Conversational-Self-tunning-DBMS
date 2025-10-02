import os
import json

WEIRD_VALUES = ['**','[NULL]', '\{\}', 'NULL', '', "{}"]

def read_json(path):
    with open(path, "r") as f:
        return json.load(f)

def write_json(data, path):
    with open(path, "w") as f:
        f.write(json.dumps(data, indent=4, ensure_ascii=False))

def read_in_values(path):
    def is_array(value):
        return value[0] == '{' and value[-1] == '}' and ',' in value
    def shorten_array(value):
        return value.split(",")[0]+"}"
    def is_time(value):
        return isinstance(value, str) and value.count("-") == 2 and value.count(":") == 1
    def is_integer(value):
        try:
            int(value.replace(",",""))
            return True
        except ValueError:
            return False
    def is_float(value):
        try:
            float(value)
            return True
        except:
            return False
    with open(path, "r") as f:
        # Read in column names
        col_names =  f.readline().strip().split('\t')
        dic = {col_name:[] for col_name in col_names}
        # Read in values
        for line in f.readlines():
            line = line.strip()
            values = line.split('\t')
            for idx, value in enumerate(values):
                if value in WEIRD_VALUES:
                    continue
                if is_array(value):
                    value = shorten_array(value)
                    if value == '{}':
                        continue
                if is_integer(value):
                    value = value.replace(",", "")
                elif is_float(value):
                    value = str(round(float(value), 2))
                if is_time(value):
                    value = value.split(" ")[0]
                if value not in dic[col_names[idx]]:
                    dic[col_names[idx]].append(value)
    return dic

if __name__ == "__main__":
    workspaceFolder = "/data/hkkang/NL2QGM"
    schema_path = os.path.join(workspaceFolder, "ratsql/datasets/augmentation/schema.txt")
    table_dir = os.path.join(workspaceFolder, "ratsql/datasets/augmentation/table_values/")

    schema = read_json(schema_path)

    # Read and load values
    for table in schema['tables']:
        table_name = table['name']
        file_path = os.path.join(table_dir, f"{table_name}.tsv")
        assert os.path.isfile(file_path), f"{file_path} does not exist!"
        val_dic = read_in_values(file_path)

        for column in table['columns']:
            column_name = column['name']
            column['values'] = val_dic[column_name]
            if table_name == "master.m_defect_item" and column_name == "target":
                column['values'] = ["ABDF123", "DFD56"]
            elif table_name == "master.m_defect_item" and column_name == "spec_high":
                column['values'] = ["121", "223"]
            elif table_name == "quality.m_defect_summary" and column_name == "chamber_id":
                column['values'] = ["DFDA123", "DFD356"]

    # overwrite schema file
    write_json(schema, schema_path)
    print("Done!")
