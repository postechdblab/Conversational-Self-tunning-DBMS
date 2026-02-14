from client.client_side import *
config = connect_db(db_type='postgres', host='localhost', database='test_cli', user='postgres', password='postgres', port='5438', interval=10)
data = query_performance_data(config, table='dbsherlock')