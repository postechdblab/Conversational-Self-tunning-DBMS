from source.text2sql.ratsql.models.spider_schema import SPIDER_SCHEMA
import procbridge as pb


class PDTCommunicator:
    instance = None

    @classmethod
    def get_instance(cls):
        if cls.instance is None:
            cls.instance = PDTCommunicator()
        return cls.instance

    def __init__(self):
        self.client = pb.Client("127.0.0.1", 8090)

    @classmethod
    def init_request(cls, db_id):
        try:
            response = cls.get_instance().client.request("init", ["spider", db_id])
        except:
            print("Turn on PDT Server!")
            exit(-1)
        print(f"INIT {db_id}")
        print(response)
        return response[0]

    @classmethod
    def apply_action(cls, action):
        response = cls.get_instance().client.request("applyAction", action)
        print(action)
        print(response)
        return response[0]

    @classmethod
    def apply_column_action(cls, db_id, col_id, table_id):
        db = SPIDER_SCHEMA.get_db(db_id)
        tab_id, col_name = db["column_names_original"][col_id]
        if tab_id == -1:
            tab_name = db["table_names_original"][table_id]
        else:
            tab_name = db["table_names_original"][tab_id]
        response = cls.get_instance().client.request(
            "applyAction", f'[0,0,"{col_name}","{tab_name}"]'
        )
        print(f'[0,0,"{col_name}","{tab_name}"]')
        print(response)
        return response[0]

    @classmethod
    def apply_table_action(cls, db_id, tab_id):
        db = SPIDER_SCHEMA.get_db(db_id)
        tab_name = db["table_names_original"][tab_id]
        response = cls.get_instance().client.request("applyAction", f'["{tab_name}"]')
        print(f'["{tab_name}"]')
        print(response)
        return response[0]

    @classmethod
    def get_sql(cls):
        response = cls.get_instance().client.request("getSQL")
        return response
