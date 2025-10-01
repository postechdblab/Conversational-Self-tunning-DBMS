import argparse
import pprint
from datetime import timedelta

import mysql
from flask import Flask, jsonify, request
from flask_cors import CORS

from autotune.database.mysqldb import MysqlDB
from autotune.database.postgresqldb import PostgresqlDB
from autotune.dbenv import DBEnv
from autotune.tuner import DBTuner
from autotune.utils.config import parse_args

dbconfig = {
    "user": "root",
    "password": "password",
    "database": "concert_singer",
    "unix_socket": "/var/run/mysqld/mysqld.sock",
}
while True:
    try:
        mydb = mysql.connector.connect(**dbconfig)
        cursor = mydb.cursor()
        cursor.execute(
            """
SHOW VARIABLES 
where variable_name!='optimizer_switch'
and variable_name!='sql_mode'
and variable_name!='session_track_system_variables';
"""
        )
        data = cursor.fetchall()
        pprint.pprint(data)
        break
    except Exception as e:
        print(e)
    finally:
        if "cursor" in locals():
            cursor.close()
        if "mydb" in locals():
            mydb.close()
app = Flask(__name__)
CORS(app)


parser = argparse.ArgumentParser()
parser.add_argument(
    "--config", type=str, default="scripts/demo.ini", help="config file"
)
parser.add_argument("run")
parser.add_argument("--no-debugger", action="store_true")
parser.add_argument("--no-reload", action="store_true")
opt = parser.parse_args()


args_db, args_tune = parse_args(opt.config)
if args_db["db"] == "mysql":
    db = MysqlDB(args_db)
elif args_db["db"] == "postgresql":
    db = PostgresqlDB(args_db)

env = DBEnv(args_db, args_tune, db)
tuner = DBTuner(args_db, args_tune, env)
queries = list()
times = list()


@app.post("/query")
def query():
    query = request.get_json()
    if query == "conduct tuning":
        with open(
            "/workspaces/OpAdviserPrivate/autotune/cli/selectedList_demo.txt", "w"
        ) as _:
            pass
        for i, q in enumerate(queries):
            with open(
                f"/workspaces/OpAdviserPrivate/autotune/demo_query/queries-mysql-new/{i}.sql",
                "w",
            ) as f1:
                f1.write(
                    f"""
select current_timestamp(6) into @query_start;
set @query_name='{i}';
{q};
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
"""
                )
            with open(
                "/workspaces/OpAdviserPrivate/autotune/cli/selectedList_demo.txt", "a"
            ) as f2:
                f2.write(
                    f"""{i}.sql
"""
                )
        while True:
            tuner.tune()
            try:
                mydb = mysql.connector.connect(**dbconfig)
                execution_times = []
                for q in queries:
                    cursor = mydb.cursor(dictionary=True)
                    cursor.execute("""select current_timestamp(6);""")
                    start_time = cursor.fetchall()[0]["current_timestamp(6)"]
                    cursor.execute(q)
                    cursor.fetchall()
                    cursor.execute("""select current_timestamp(6);""")
                    end_time = cursor.fetchall()[0]["current_timestamp(6)"]
                    execution_times.append(
                        (end_time - start_time) / timedelta(milliseconds=1)
                    )
                b = True
                for i in range(len(times)):
                    if execution_times[i] > times[i]:
                        b = False
                if b:
                    return {
                        "execution_times": execution_times,
                    }
            finally:
                if "cursor" in locals():
                    cursor.close()
                if "mydb" in locals():
                    mydb.close()
    try:
        queries.append(query)
        mydb = mysql.connector.connect(**dbconfig)
        cursor = mydb.cursor(dictionary=True)
        cursor.execute("""select current_timestamp(6);""")
        start_time = cursor.fetchall()[0]["current_timestamp(6)"]
        cursor.execute(query)
        data = cursor.fetchall()
        cursor.execute("""select current_timestamp(6);""")
        end_time = cursor.fetchall()[0]["current_timestamp(6)"]
        execution_time = (end_time - start_time) / timedelta(milliseconds=1)
        times.append(execution_time)
        return {
            "data": data[:10],
            "execution_time": execution_time,
        }
    finally:
        if "cursor" in locals():
            cursor.close()
        if "mydb" in locals():
            mydb.close()


@app.post("/knobs")
def knobs():
    try:
        mydb = mysql.connector.connect(**dbconfig)
        cursor = mydb.cursor()
        cursor.execute(
            """
SHOW VARIABLES 
where variable_name!='optimizer_switch'
and variable_name!='sql_mode'
and variable_name!='session_track_system_variables';
"""
        )
        data = cursor.fetchall()
        return jsonify(data)
    finally:
        if "cursor" in locals():
            cursor.close()
        if "mydb" in locals():
            mydb.close()


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False, port=1234)
