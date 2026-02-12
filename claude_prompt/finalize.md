Objective: Postgresql에 대한 의존성을 아예 없애고, Opadvisor의 MySQL DB를 사용하도록 코드를 수정한다.
- Postgresql에 대한 의존성을 최소화하기 위해 @source/text2sql 를 수행할 때, value를 채워넣기 위해 all_values_from_db에서와 같은 postgresql 의존성을 mysql db option을 구현하고, configuration에서 이를 선택하는 방식으로 mysql에만 의존하는 버전을 구현한다.
- MySQL에 데이터 늘리기: @source/tuning/OpAdviserPrivate/concert_singer.py의 generate_random_data를 바탕으로 MySQL에 데어티를 더 insert한다.

위를 구현에 대한 상세 계획을 작성하여 공유해라.