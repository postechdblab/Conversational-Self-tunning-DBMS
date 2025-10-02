import os
import json
from os import listdir
from os.path import isfile, join

def read_json(path):
    with open(path, 'r') as f:
        return json.load(f)

def read_col_desc_from_tsv(path):
    dic = {}
    with open(path, 'r') as f:
        for line in f.readlines():
            line = line.strip()
            items = line.split("\t")
            assert len(items) == 4
            tab_name, col_name, col_desc, col_type = items
            dic[col_name.lower()] = col_desc
    return dic

def read_in_tsv_files(dir_path="./"):
    tsv_files = [join(dir_path, f) for f in listdir(dir_path) if isfile(join(dir_path, f)) and f.endswith(".tsv")]
    dic = {}
    for tsv_file in tsv_files:
        tab_name = tsv_file.split("/")[-1][:-len(".tsv")]
        col_desc_dic = read_col_desc_from_tsv(tsv_file)
        dic[tab_name] = col_desc_dic
    return dic

def add_col_desc(tab_dic, tables):
    tables[0]['column_descriptions'] = []
    for tab_id, col_name in tables[0]['column_names_original']:
        if tab_id == -1 or col_name == "*":
            col_desc = "*"
        else:
            tab_name = tables[0]['table_names_original'][tab_id]
            if col_name in tab_dic[tab_name]:
                col_desc = tab_dic[tab_name][col_name]
            else:
                print(f"{tab_name}-{col_name} has no description")
                col_desc = "no description"
        tables[0]['column_descriptions'].append(col_desc)
    return tables

if __name__ == "__main__":
    col_desc_dir_path = "/data/hkkang/NL2QGM/ratsql/datasets/column_descriptions/"
    tables_json_path = "/data/hkkang/NL2QGM/data/samsung-addop-hkkang/tables.json"
    
    tab_dic = read_in_tsv_files(col_desc_dir_path)
    tables = read_json(tables_json_path)
    new_tables = add_col_desc(tab_dic, tables)

    with open(tables_json_path, 'w') as f:
        f.write(json.dumps(new_tables, indent=4, ensure_ascii=False))

    