#!/bin/bash
workload="ycsb"
mysql -ppassword -e"drop database ${workload};"
mysql -ppassword -e"create database ${workload};"
/oltpbench/oltpbenchmark -b $workload -c /oltpbench/config/sample_${workload}_config.xml  --create=true --load=true
for optimize_method in "DDPG" "GA" "MBO" "SMAC"; do
  lowercase="${optimize_method,,}"
  for knob_num in 57 26 144; do
    python3 scripts/optimize.py \
    --config=scripts/cluster.ini \
    --knob_config_file=scripts/experiment/gen_knobs/moreworkloads/${workload}_shap.json \
    --knob_num=$knob_num \
    --dbname=${workload} \
    --workload=oltpbench_${workload} \
    --oltpbench_config_xml=/oltpbench/config/sample_${workload}_config.xml \
    --task_id="${workload}_${lowercase}_${knob_num}" \
    --optimize_method="$optimize_method"
  done
done
