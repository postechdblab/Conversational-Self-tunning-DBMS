#!/bin/bash
db="write"
mysql -ppassword -e"drop database sb${db};"
mysql -ppassword -e"create database sb${db};"
sysbench  \
    --db-driver=mysql  \
    --mysql-host=localhost  \
    --mysql-port=3308  \
    --mysql-user=root  \
    --mysql-password=password  \
    --table_size=800000  \
    --tables=300  \
    --events=0  \
    --threads=80  \
    --mysql-db=sb${db}  \
    oltp_${db}_only  \
    prepare
for optimize_method in "DDPG" "GA" "MBO" "SMAC"; do
  lowercase="${optimize_method,,}"
  for knob_num in 40 96 170; do
    python3 scripts/optimize.py \
    --config=scripts/cluster.ini \
    --knob_config_file=scripts/experiment/gen_knobs/SYSBENCH_randomforest.json \
    --knob_num=$knob_num \
    --dbname=sb${db} \
    --workload=sysbench \
    --task_id="sysbench_${lowercase}_${knob_num}" \
    --optimize_method="$optimize_method" \
    --workload_type="$db"
  done
done
