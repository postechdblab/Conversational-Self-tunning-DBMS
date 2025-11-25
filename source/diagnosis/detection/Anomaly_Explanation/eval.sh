export PYTHONPATH=$PYTHONPATH:/root/Anomaly_Explanation
cd /root/Anomaly_Explanation
CUDA_VISIBLE_DEVICES=0 python /root/Anomaly_Explanation/src/main.py --num_epochs=10 --batch_size=1024 --mode=test --dataset=DBS --win_size=25 --step_size=25 --data_path=dataset/dbsherlock/converted/tpcc_500w_test.json --find_best=True --add_stats=True