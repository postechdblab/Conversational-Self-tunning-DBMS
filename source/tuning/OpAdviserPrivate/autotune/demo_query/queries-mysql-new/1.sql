
select current_timestamp(6) into @query_start;
set @query_name='1';
SELECT DISTINCT c.concert_ID, s.Capacity FROM concert c JOIN stadium s ON c.Stadium_ID = s.Stadium_ID WHERE s.Capacity < (   SELECT AVG(Capacity)   FROM stadium   WHERE Location = 'Peterhead' );
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
