import argparse
import json
import logging
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

logger = logging.getLogger("OpAdviserDemo")

MAX_TUNING_ROUNDS = 20
NO_IMPROVE_PATIENCE = 20
IMPROVE_THRESHOLD = 0.005  # 0.5% 이상 개선되어야 "개선"으로 판정

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
        best_execution_times = None
        best_total_time = float("inf")
        best_round = 0
        original_total_time = sum(times)
        no_improve_count = 0
        history_path = (
            f"/workspaces/OpAdviserPrivate/repo/history_{args_tune['task_id']}.json"
        )

        for round_num in range(MAX_TUNING_ROUNDS):
            logger.info(f"[Tuning] Round {round_num + 1}/{MAX_TUNING_ROUNDS}")
            try:
                tuner.tune()
            except Exception as e:
                logger.error(f"[Tuning] tune() failed: {e}")
                continue

            # Apply best config found by the optimizer
            try:
                with open(history_path) as f:
                    history_data = json.load(f)["data"]
                best_entry = max(
                    (d for d in history_data if d.get("trial_state", 1) == 0),
                    key=lambda d: d["external_metrics"]["tps"],
                )
                best_knobs = best_entry["configuration"]
                env.apply_knobs(best_knobs)
                logger.info("[Tuning] Applied best config from history")
            except Exception as e:
                logger.warning(f"[Tuning] Could not apply best config: {e}")

            try:
                mydb = mysql.connector.connect(**dbconfig)
                cursor = mydb.cursor(dictionary=True)
                execution_times = []
                for q in queries:
                    cursor.execute("select current_timestamp(6);")
                    start_time = cursor.fetchall()[0]["current_timestamp(6)"]
                    cursor.execute(q)
                    cursor.fetchall()
                    cursor.execute("select current_timestamp(6);")
                    end_time = cursor.fetchall()[0]["current_timestamp(6)"]
                    execution_times.append(
                        (end_time - start_time) / timedelta(milliseconds=1)
                    )

                current_total_time = sum(execution_times)

                # Per-query diff 출력
                logger.info("=" * 60)
                logger.info(f"[Tuning] Round {round_num + 1}/{MAX_TUNING_ROUNDS} 결과:")
                for i, (orig, curr) in enumerate(zip(times, execution_times)):
                    diff = curr - orig
                    pct = (diff / orig * 100) if orig != 0 else 0
                    sign = "+" if diff >= 0 else ""
                    logger.info(
                        f"  Query {i}: {orig:.2f}ms → {curr:.2f}ms (diff: {sign}{diff:.2f}ms, {sign}{pct:.2f}%)"
                    )
                diff_total = current_total_time - original_total_time
                pct_total = (
                    (diff_total / original_total_time * 100)
                    if original_total_time != 0
                    else 0
                )
                sign_total = "+" if diff_total >= 0 else ""
                logger.info(f"  {'─' * 40}")
                logger.info(
                    f"  Total: {original_total_time:.2f}ms → {current_total_time:.2f}ms (diff: {sign_total}{diff_total:.2f}ms, {sign_total}{pct_total:.2f}%)"
                )
                if best_execution_times is not None:
                    logger.info(f"  Best: {best_total_time:.2f}ms (Round {best_round})")
                logger.info("=" * 60)

                # Track best result (require IMPROVE_THRESHOLD improvement to count)
                if current_total_time < best_total_time * (1 - IMPROVE_THRESHOLD):
                    best_total_time = current_total_time
                    best_execution_times = list(execution_times)
                    best_round = round_num + 1
                    no_improve_count = 0
                else:
                    no_improve_count += 1

                # Early exit 1: all queries improved
                all_improved = all(
                    execution_times[i] <= times[i] for i in range(len(times))
                )
                if all_improved:
                    logger.info(
                        f"[Tuning] All queries improved after {round_num + 1} rounds"
                    )
                    queries.clear()
                    times.clear()
                    return {"execution_times": execution_times}

                # Early exit 2: no improvement for N consecutive rounds
                if no_improve_count >= NO_IMPROVE_PATIENCE:
                    logger.info(
                        f"[Tuning] No improvement for {NO_IMPROVE_PATIENCE} rounds, stopping"
                    )
                    break
            except Exception as e:
                logger.error(f"[Tuning] Measurement failed: {e}")
                no_improve_count += 1
                if no_improve_count >= NO_IMPROVE_PATIENCE:
                    logger.info(f"[Tuning] Too many failures/no improvement, stopping")
                    break
                continue
            finally:
                if "cursor" in locals():
                    cursor.close()
                if "mydb" in locals():
                    mydb.close()

        # Max rounds or convergence reached: return best result
        if no_improve_count >= NO_IMPROVE_PATIENCE:
            logger.info(f"[Tuning] Converged after {round_num + 1} rounds.")
        else:
            logger.info(f"[Tuning] Max rounds ({MAX_TUNING_ROUNDS}) reached.")
        result_times = (
            best_execution_times if best_execution_times is not None else list(times)
        )

        # 최종 결과 요약
        logger.info("=" * 60)
        logger.info(f"[Tuning] 최종 결과 ({round_num + 1}라운드 후 종료):")
        for i, (orig, final) in enumerate(zip(times, result_times)):
            diff = final - orig
            pct = (diff / orig * 100) if orig != 0 else 0
            sign = "+" if diff >= 0 else ""
            logger.info(
                f"  Query {i}: {orig:.2f}ms → {final:.2f}ms (diff: {sign}{diff:.2f}ms, {sign}{pct:.2f}%)"
            )
        final_total = sum(result_times)
        diff_total = final_total - original_total_time
        pct_total = (
            (diff_total / original_total_time * 100) if original_total_time != 0 else 0
        )
        sign = "+" if diff_total >= 0 else ""
        logger.info(
            f"  Total: {original_total_time:.2f}ms → {final_total:.2f}ms (diff: {sign}{diff_total:.2f}ms, {sign}{pct_total:.2f}%)"
        )
        logger.info("=" * 60)

        queries.clear()
        times.clear()
        return {"execution_times": result_times}
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
            "data": data[:8],
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


@app.route("/health")
def health():
    try:
        mydb = mysql.connector.connect(**dbconfig)
        cursor = mydb.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        mydb.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}, 503


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False, port=1234)
