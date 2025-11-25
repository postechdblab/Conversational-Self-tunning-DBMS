# 자연언어를 사용한 질의 인터랙션: 실행 정확도
# 자연언어를 사용한 질의 인터랙션: 자연언어 질의 분류 정확도
# 데이터 중심의 대화 시스템: 신뢰도 분석 오차율 
docker exec -it DBAdminBot-backend sh -c "/root/dbadminbot/eval.sh"

# 성능 이상 탐지 및 원인 분석: 성능 이상탐지의 정확도
docker exec -it DBAdminBot-AnomalyExp sh -c "sh /root/Anomaly_Explanation/eval.sh"