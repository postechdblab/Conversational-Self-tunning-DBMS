"""
Anomaly prediction script using server/model/anomaly_transformer module.
Creates a checkpoint-based detector and runs inference following the same logic
as ade_predict_anomaly_transformer in server/model/anomaly_transformer.py.
"""
import sys
import os
# Ensure server/model package is found before root model.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

import json
import psycopg2
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine
from omegaconf import OmegaConf
from DBAnomTransformer.detector import DBAnomDector
from model.anomaly_transformer import CAUSES_DBSHERLOCK, CAUSES_EDA

# Config
with open('/root/DBEDA/config.json') as f:
    config = json.load(f)

server_db_port = config.get('serverdb', 5437)

# Connect to server DB
server_engine = create_engine(f'postgresql://postgres:postgres@localhost:{server_db_port}/dbeda')
server_conn = psycopg2.connect(
    host='localhost', database='dbeda', user='postgres',
    password='postgres', port=server_db_port
)

# Step 1: Register DB config if not exists
db_config = {
    "db_type": "postgres",
    "db_host": "localhost",
    "db_port": "5438",
    "db_name": "test_cli",
    "db_user": "postgres",
    "db_password": "postgres"
}

cur = server_conn.cursor()
cur.execute("""
    SELECT id FROM db_config
    WHERE db_type = %s AND db_host = %s AND db_port = %s AND db_name = %s AND db_user = %s;
""", (db_config['db_type'], db_config['db_host'], db_config['db_port'],
      db_config['db_name'], db_config['db_user']))
result = cur.fetchone()

if result:
    db_id = result[0]
    print(f"Found existing db config with id: {db_id}")
else:
    import uuid
    db_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO db_config (id, db_type, db_host, db_port, db_name, db_user, db_password)
        VALUES (%s, %s, %s, %s, %s, %s, %s);
    """, (db_id, db_config['db_type'], db_config['db_host'], db_config['db_port'],
          db_config['db_name'], db_config['db_user'], db_config['db_password']))
    server_conn.commit()
    print(f"Inserted new db config with id: {db_id}")
cur.close()

# Step 2: Load DBSherlock data
print("Loading dbsherlock data...")
test_df = pd.read_sql_query("SELECT * FROM dbsherlock ORDER BY timestamp ASC", server_engine)
print(f"Got {len(test_df)} rows, {len(test_df.columns)} columns")

# Step 3: Create detector from checkpoints (as configured in config.json)
print("Loading model from checkpoints...")
dbs_config = OmegaConf.create(config.get('dbsherlock'))
detector = DBAnomDector(override_config=dbs_config)

# Step 4: Run prediction (same logic as ade_predict_anomaly_transformer)
test_data = test_df.drop(columns=['timestamp'])
if 'combined_avg_latency' in test_data.columns:
    test_data = test_data.drop(columns=['combined_avg_latency'])

if len(test_data.columns) == 200:  # DBSHERLOCK
    dataset = 'dbsherlock_tpcc_500w'
    CAUSES = CAUSES_DBSHERLOCK
else:
    dataset = 'eda'
    CAUSES = CAUSES_EDA

print(f"Feature columns: {len(test_data.columns)}")
print("Running inference...")
anomaly_score, is_anomaly, anomaly_cause = detector.infer(data=test_data)
anomaly_cause = list(map(lambda x: CAUSES[x], anomaly_cause))

anomaly_df = pd.DataFrame({
    "timestamp": list(test_df['timestamp']),
    "anomaly_score": anomaly_score,
    "is_anomaly": is_anomaly,
    "anomaly_cause": anomaly_cause
})

print(f"Anomaly count: {sum(is_anomaly)}")
print(f"Anomaly causes: {set(c for c, a in zip(anomaly_cause, is_anomaly) if a)}")

# Step 5: Insert into anomaly_explanation (same as ade_predict_anomaly_transformer)
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
cur = server_conn.cursor()
anomaly_df_db = anomaly_df.applymap(
    lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if isinstance(x, pd.Timestamp) else x
)
anomaly_df_db['analysis_time'] = current_time
anomaly_df_db['dbid'] = db_id
anomaly_df_db['dataset'] = dataset
anomaly_df_db = anomaly_df_db[['dbid', 'analysis_time', 'timestamp', 'anomaly_score', 'is_anomaly', 'anomaly_cause', 'dataset']]

placeholders = ', '.join(['%s'] * len(anomaly_df_db.columns))
values = [tuple(row) for row in anomaly_df_db.values]
cur.executemany(f"INSERT INTO anomaly_explanation VALUES ({placeholders})", values)
server_conn.commit()
cur.close()

print(f"Inserted {len(values)} rows into anomaly_explanation")
print("Done!")
