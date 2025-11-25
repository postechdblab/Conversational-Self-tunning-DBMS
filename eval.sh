export CUDA_VISIBLE_DEVICES=1
export PYTHONPATH=$PYTHONPATH:/root/dbadminbot

cd /root/dbadminbot

# 자연언어를 사용한 질의 인터랙션: 실행 정확도
python /root/dbadminbot/source/text2sql/eval.py data=wikisql

# 자연언어를 사용한 질의 인터랙션: 자연언어 질의 분류 정확도
python /root/dbadminbot/source/text2intent/eval.py data=cosql

# 데이터 중심의 대화 시스템: 신뢰도 분석 오차율 
python /root/dbadminbot/source/conversation/text2confidence/eval.py data=wikisql