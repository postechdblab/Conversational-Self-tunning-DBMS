CUDA_VISIBLE_DEVICES=3 python /root/dbadminbot/source/text2sql/eval.py \
    text2sql.glist_output_path=/root/dbadminbot/eval_results/glist_granite.json \
    text2sql.plist_output_path=/root/dbadminbot/eval_results/plist_granite.json \
    text2sql.is_fix_mode=False

CUDA_VISIBLE_DEVICES=3 python /root/dbadminbot/source/text2sql/eval.py