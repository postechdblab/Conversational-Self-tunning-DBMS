
CUDA_VISIBLE_DEVICES=2 python /root/dbadminbot/source/text2sql/eval.py \
    text2sql.glist_output_path=/root/dbadminbot/eval_results/glist_beam_15.json \
    text2sql.plist_output_path=/root/dbadminbot/eval_results/plist_beam_15.json \
    text2sql.beam_size=15

CUDA_VISIBLE_DEVICES=2 python /root/dbadminbot/source/text2sql/eval.py \
    text2sql.glist_output_path=/root/dbadminbot/eval_results/glist_beam_20.json \
    text2sql.plist_output_path=/root/dbadminbot/eval_results/plist_beam_20.json \
    text2sql.beam_size=20