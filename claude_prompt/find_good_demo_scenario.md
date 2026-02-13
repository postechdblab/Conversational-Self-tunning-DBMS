Objective: @source/tuning/OpAdviserPrivate 로 다음의 workload에 대해 tuning한 결과 @source/tuning/OpAdviserPrivate/initial2.cnf 로 초기화된 mysql에서의 실행 시간보다 모든 질의에 대해 실행 시간이 더 빨라져야 한다.

queries:
- SELECT * FROM stadium
- SELECT name, capacity FROM stadium
- SELECT name, location FROM stadium
- SELECT name, location, capacity FROM stadium
- SELECT s.Name,    COUNT(c.concert_ID) AS concert_count FROM stadium s LEFT JOIN concert c    ON s.Stadium_ID = c.Stadium_ID GROUP BY s.Stadium_ID, s.Name
- SELECT concert.concert_ID, stadium.Capacity FROM concert JOIN stadium ON concert.Stadium_ID = stadium.Stadium_ID WHERE stadium.Capacity < (   SELECT AVG(stadium.Capacity)   FROM stadium   WHERE stadium.Location = 'Peterhead' )

데모에서와 같이 tuning하라고 했을 때, 모든 질의에 대해 실행 시간이 더 빨라지는 initial2.cnf를 구해라. 
혹은 그렇게 되도록 코드의 일부를 수정해도 괜찮다. 위에 대한 상세한 계획을 작성해라.

Verification:
- 위 query들에 대해서 tuning이후에 각 질의들 모두에 대해 실행 시간이 단축됨을 확인해야 한다.