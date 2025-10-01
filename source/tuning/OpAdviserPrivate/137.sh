#!/bin/bash
chmod +x ./cluster.sh
./cluster.sh
chmod +x ./job.sh
./job.sh
export PYTHONPATH="."
for optimize_method in "DDPG" "GA" "MBO" "SMAC"; do
  lowercase="${optimize_method,,}"
  for knob_num in 5 11 26; do

    python3 scripts/optimize.py \
    --config=scripts/cluster.ini \
    --knob_config_file=scripts/experiment/gen_knobs/JOB_shap.json \
    --knob_num=$knob_num \
    --dbname=imdbload \
    --workload=job \
    --task_id="job_${lowercase}_${knob_num}" \
    --optimize_method="$optimize_method"
  done
done
