import os
import sqlite3
from typing import Any
import traceback

SQLITE_DBTYPE_IDENTIFIERS = {'sqlite'}
POSTGRES_DBTYPE_IDENTIFIERS = {'postgres', 'postgresql'}
MYSQL_DBTYPE_IDENTIFIERS = {'mysql'}

class connect():
    def __init__(self, db, db_type='sqlite'):
        self.db = db
        self.db_type = db_type

        if self.db_type in SQLITE_DBTYPE_IDENTIFIERS and 'samsung' not in db:
            self.con = sqlite3.connect(self.db)
        elif self.db_type in POSTGRES_DBTYPE_IDENTIFIERS:
            import psycopg2
            self.con = psycopg2.connect(self.db)
        elif self.db_type in MYSQL_DBTYPE_IDENTIFIERS:
            import mysql.connector
            # db is expected to be a dict with connection params
            if isinstance(self.db, dict):
                self.con = mysql.connector.connect(**self.db)
            else:
                self.con = mysql.connector.connect(database=self.db)
        else:
            if 'samsung' not in db:
                raise ValueError('no such db type!')

    def __call__(self):
        return self.con

    def __enter__(self):
        return self.con

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is not None:
            traceback.print_exception(exc_type, exc_value, tb)
        
        self.con.close()
        return True


def create_db_conn_str(input_str, db_name, db_type='sqlite', ):
    if db_type in SQLITE_DBTYPE_IDENTIFIERS:
        db_conn_str = os.path.join(input_str, db_name, db_name + '.sqlite')
    elif db_type in POSTGRES_DBTYPE_IDENTIFIERS:
        # in this case, db_dir becomes libpq connection string
        # XXX: need to rename "db_dir" but should check db_dir used in outer scope
        db_conn_str = input_str + f' dbname={db_name}'
    elif db_type in MYSQL_DBTYPE_IDENTIFIERS:
        # input_str is expected to be a dict with MySQL connection params
        if isinstance(input_str, dict):
            db_conn_str = {**input_str, 'database': db_name}
        else:
            db_conn_str = {'database': db_name}
    else:
        raise ValueError('no such db type!')

    return db_conn_str


def fetch_table_names(cursor, db_type='sqlite'):
    if db_type in SQLITE_DBTYPE_IDENTIFIERS:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [str(table[0].lower()) for table in cursor.fetchall()]
    elif db_type in POSTGRES_DBTYPE_IDENTIFIERS:
        sql = """
            SELECT *
            FROM pg_catalog.pg_tables
            WHERE schemaname != 'pg_catalog' AND
                  schemaname != 'information_schema';
        """
        cursor.execute(sql)
        tables = [f"{str(table[0].lower())}.{str(table[1].lower())}".replace("public.", "")
                  for table in cursor.fetchall()]
    elif db_type in MYSQL_DBTYPE_IDENTIFIERS:
        cursor.execute("SHOW TABLES")
        tables = [str(table[0].lower()) for table in cursor.fetchall()]
    else:
        raise ValueError('no such db type!')

    return tables


def fetch_col_names(cursor, table, db_type='sqlite'):
    if db_type in SQLITE_DBTYPE_IDENTIFIERS:
        cursor.execute("PRAGMA table_info({})".format(table))
        cols = [str(col[1].lower()) for col in cursor.fetchall()]
    elif db_type in POSTGRES_DBTYPE_IDENTIFIERS:
        # XXX: need to check what is table_schema in postgresql
        if len(table.split('.')) > 1:
            sql = f"""
                SELECT *
                FROM
                    information_schema.columns
                WHERE
                    table_schema = '{table.split('.')[0]}'
                    AND table_name = '{table.split('.')[1]}';
            """
        else:
            sql = f"""
                SELECT *
                FROM
                    information_schema.columns
                WHERE
                    table_name = '{table.split('.')[0]}';
            """
        cursor.execute(sql)
        cols = [str(col[3].lower()) for col in cursor.fetchall()]
    elif db_type in MYSQL_DBTYPE_IDENTIFIERS:
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        cols = [str(col[0].lower()) for col in cursor.fetchall()]
    else:
        raise ValueError('no such db type!')

    return cols


def fetch_col_names_types(cursor, table, db_type='sqlite'):
    if db_type in SQLITE_DBTYPE_IDENTIFIERS:
        cursor.execute("PRAGMA table_info({})".format(table))
        cols = [str(col[1].lower()) for col in cursor.fetchall()]
    elif db_type in POSTGRES_DBTYPE_IDENTIFIERS:
        # XXX: need to check what is table_schema in postgresql
        if len(table.split('.')) > 1:
            sql = f"""
                SELECT *
                FROM
                    information_schema.columns
                WHERE
                    table_schema = '{table.split('.')[0]}'
                    AND table_name = '{table.split('.')[1]}';
            """
        else:
            sql = f"""
                SELECT *
                FROM
                    information_schema.columns
                WHERE
                    table_name = '{table.split('.')[0]}';
            """
        cursor.execute(sql)
        cols = [(str(col[3].lower()), str(col[7])) for col in cursor.fetchall()]
    elif db_type in MYSQL_DBTYPE_IDENTIFIERS:
        cursor.execute(f"SHOW COLUMNS FROM {table}")
        # SHOW COLUMNS returns: Field, Type, Null, Key, Default, Extra
        cols = [(str(col[0].lower()), str(col[1])) for col in cursor.fetchall()]
    else:
        raise ValueError('no such db type!')

    return cols
