
select current_timestamp(6) into @query_start;
set @query_name='21';
SELECT s.Singer_ID,    s.Name,    COUNT(*) AS concert_count FROM singer_in_concert sic JOIN singer s ON sic.Singer_ID = s.Singer_ID GROUP BY s.Singer_ID, s.Name ORDER BY concert_count DESC LIMIT 10;
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
