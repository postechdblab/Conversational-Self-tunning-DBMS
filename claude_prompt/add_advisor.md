Objective: @/home/shpark/Conversational-Self-tunning-DBMS/source/tuning/OpAdviserPrivate 를 이 repository에서 세팅하고싶어. 
- 그래야 frontend에서 자연어 질의를 제출하고, backend에서 sql query를 번역한 것을 OpAdviser에서 실행해서 실행 결과를 반환하고, 이를 frontend에 반환하지.
- 그리고 이 OpAdviser에 대한 container는 "anonymous824/opadvisor:latest" 라는 이미지로 docker-compose.yml에 추가하여 같이 올라갔으면 좋겠어.
- 우선 container를 먼저 만들고, 그 다음에 정상적으로 그 내부의 mysql server나 tuning 동작이 돌아가는지 @source/tuning/OpAdviserPrivate/documents/setup_guide.md 의 내용을 바탕으로 체크해보자. anonymous824/opadvisor:latest는 이미 해당 markdown 파일의 절차를 밟은 환경을 image로 만든거야.

위를 수행하기 위한 상세한 계획을 작성하여 공유해라.