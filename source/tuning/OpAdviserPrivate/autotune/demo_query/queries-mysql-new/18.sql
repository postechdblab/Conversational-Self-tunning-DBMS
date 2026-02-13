
select current_timestamp(6) into @query_start;
set @query_name='18';
SELECT s.Name, s.Capacity, COUNT(c.concert_ID) as num_concerts FROM stadium s LEFT JOIN concert c ON s.Stadium_ID = c.Stadium_ID GROUP BY s.Stadium_ID ORDER BY num_concerts DESC LIMIT 10;
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
