from typing import NewType
import json
import ratsql.utils.registry

Symbol = NewType("Symbol", str)
Action = NewType("Action", str)


class SPIDER_SCHEMA:
    instance = None

    @classmethod
    def get_instance(cls, path=None):
        if cls.instance is None:
            cls.instance = SPIDER_SCHEMA(path)
        return cls.instance

    def __init__(self, path):
        with open(path) as f:
            schemas = json.load(f)
        self.schema_dict = dict()
        for schema in schemas:
            self.schema_dict[schema["db_id"]] = schema
            schema['column_names_original_lower'] = [[tab_id, col_name.lower()] for tab_id, col_name in schema["column_names_original"]]
            schema["table_names_original_lower"] = [table_name.lower() for table_name in schema["table_names_original"]]

    @classmethod
    def find_col_index(cls, db_id, table_name, col_name):
        if col_name == "*":
            return 0
        schema = cls.get_instance().schema_dict[db_id]
        table_idx = schema["table_names_original"].index(table_name)
        col_idx = schema["column_names_original_lower"].index([table_idx, col_name.lower()])
        return col_idx

    @classmethod
    def find_tab_index(cls, db_id, table_name):
        schema = cls.get_instance().schema_dict[db_id]
        table_idx = schema["table_names_original_lower"].index(table_name.lower())
        return table_idx

    @classmethod
    def get_db(cls, db_id):
        return cls.get_instance().schema_dict[db_id]


    @classmethod
    def find_parent_tab_index(cls, db_id, col_id):
        schema = cls.get_instance().schema_dict[db_id]
        table_idx = schema["column_names_original_lower"][col_id][0]
        return table_idx

    @classmethod
    def num_cols(cls, db_id):
        schema = cls.get_instance().schema_dict[db_id]
        return len(schema["column_names_original_lower"])

    @classmethod
    def num_tabs(cls, db_id):
        schema = cls.get_instance().schema_dict[db_id]
        return len(schema["table_names_original_lower"])