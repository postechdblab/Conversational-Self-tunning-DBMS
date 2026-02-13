
select current_timestamp(6) into @query_start;
set @query_name='16';
SELECT s.Name, COUNT(*) as cnt FROM singer_in_concert sc JOIN concert c ON sc.concert_ID = c.concert_ID JOIN stadium s ON c.Stadium_ID = s.Stadium_ID GROUP BY s.Name ORDER BY cnt DESC;
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
