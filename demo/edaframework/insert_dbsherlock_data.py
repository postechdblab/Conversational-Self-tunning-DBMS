import psycopg2
import datetime
import hkkang_utils.file as file_utils

def insert_data(server_conn, cur, col_names, row_values, table_name):
    # 딕셔너리에 저장된 키를 컬럼으로 하여 테이블에 컬럼 추가
    cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'")
    existing_columns = [col[0] for col in cur.fetchall()]

    new_col_names = []
    for col in col_names:
        if ' ' in col:
            col = col.replace(' ','_').replace("(core_#", "core").replace(")", "")
        assert col.lower() in existing_columns, f"Column {col} does not exist in table {table_name}"
        new_col_names.append(col)

    # 데이터를 삽입
    for values in row_values:
        query = "INSERT INTO {}  ({}) VALUES ({});".format(table_name,
            ','.join(new_col_names),
            ','.join(['%s'] * len(values))
        )
        cur.execute(query, values)
    
    server_conn.commit()
    # 커넥션 닫기
    cur.close()
    server_conn.close()

def main() -> None:
    server_conn = psycopg2.connect(
        host='localhost',
        database='dbeda',
        user='postgres',
        password='postgres',
        port=5437
    )
    # 커서 생성
    cur = server_conn.cursor()
    
    # Load data
    file_path = (
        "/root/DBEDA/tpcc_500w_test.json"
    )
    dataset = file_utils.read_json_file(file_path)["data"]
    data = dataset[0]

    # Create data_dict
    attributes = data["attributes"][1:]
    values = [d[1:] for d in data["values"]]
    # Append timestamp
    attributes.append("timestamp")
    timestamp = datetime.datetime(2026,2,14,15,0,10)
    for i, row in enumerate(values):
        row.append(timestamp.strftime('%Y-%m-%d %H:%M:%S'))
        timestamp += datetime.timedelta(seconds=60)
    
    insert_data(server_conn, cur, attributes, values, 'dbsherlock')
    
    
if __name__ == "__main__":
    main()