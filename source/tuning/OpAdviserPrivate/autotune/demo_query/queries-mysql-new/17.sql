
select current_timestamp(6) into @query_start;
set @query_name='17';
SELECT si.Name, COUNT(*) as concerts FROM singer_in_concert sc JOIN singer si ON sc.Singer_ID = si.Singer_ID GROUP BY si.Name ORDER BY concerts DESC LIMIT 10;
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
