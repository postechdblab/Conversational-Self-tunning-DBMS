import re
import argparse
from pathlib import Path
import json


def find_best_model():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_dir", type=Path, default="/mnt/disk1/jjkim/NL2QGM/logdir/spider-coldesc/bs=1,lr=7.4e-04,bert_lr=3.0e-06,end_lr=0e0,seed=0,join_cond=false")
    args = parser.parse_args()

    model_dir = args.model_dir

    pattern = re.compile("eval_result_")
    max_score = 0
    max_step = 0
    for model_eval_file in model_dir.iterdir():
        match_result = pattern.match(model_eval_file.stem)
        if match_result:
            with open(model_eval_file, 'r') as f:
                model_eval = json.load(f)
                exact_score = model_eval["total_scores"]["all"]["exact"]
                if exact_score > max_score:
                    max_score = exact_score
                    max_step = model_eval_file.stem[match_result.end():]
    
    print(f"model directory:\t{model_dir}")
    print(f"best model step:\t{max_step}")
    print(f"best model score:\t{max_score}")
   

if __name__ == '__main__':
    find_best_model()