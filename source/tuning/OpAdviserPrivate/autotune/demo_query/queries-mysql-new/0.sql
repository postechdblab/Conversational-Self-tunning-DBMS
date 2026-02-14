
select current_timestamp(6) into @query_start;
set @query_name='0';
SELECT s.Name,    COUNT(c.concert_ID) AS concert_count FROM stadium s LEFT JOIN concert c    ON s.Stadium_ID = c.Stadium_ID GROUP BY s.Stadium_ID, s.Name;
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
