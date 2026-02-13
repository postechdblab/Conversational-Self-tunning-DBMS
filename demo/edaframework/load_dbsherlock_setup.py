import json
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

# Load config
with open('/root/DBEDA/config.json') as f:
    config = json.load(f)

server_db_port = config.get('serverdb', 5437)
server_engine = create_engine(f'postgresql://postgres:postgres@localhost:{server_db_port}/dbeda')

# Load DBSherlock data
with open('/root/DBEDA/tpcc_500w_test.json') as f:
    raw = json.load(f)

d = raw['data'][0]
attributes = d['attributes']  # 202 columns: Epoch, Combined Avg Latency, ...200 features
values = d['values']           # 131 rows x 202 cols

df = pd.DataFrame(values, columns=attributes)

# Drop original Epoch and create timestamps at 60-second intervals (matching insert_dbsherlock_data.py)
from datetime import timedelta
df.drop(columns=['Epoch'], inplace=True)
start_ts = datetime(2023, 11, 16, 15, 0, 10)
df['timestamp'] = [start_ts + timedelta(seconds=60 * i) for i in range(len(df))]

# Normalize column names (matching db/load_dbsherlock.py line 22)
df.columns = list(map(
    lambda x: x.replace(" ", "_").replace("(", "").replace(")", "").replace("_#", "").lower(),
    df.columns
))

print(f"DataFrame shape: {df.shape}")
print(f"Columns sample: {list(df.columns[:5])}")
print(f"Timestamp range: {df['timestamp'].min()} to {df['timestamp'].max()}")

# Write to database
df.to_sql('dbsherlock', con=server_engine, if_exists='replace', index=False)
print("Successfully loaded dbsherlock table")
