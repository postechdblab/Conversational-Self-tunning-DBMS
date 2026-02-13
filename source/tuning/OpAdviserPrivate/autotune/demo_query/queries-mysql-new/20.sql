
select current_timestamp(6) into @query_start;
set @query_name='20';
SELECT si.Name, si.Country, COUNT(DISTINCT c.Stadium_ID) as stadiums_performed FROM singer si JOIN singer_in_concert sc ON si.Singer_ID = sc.Singer_ID JOIN concert c ON sc.concert_ID = c.concert_ID GROUP BY si.Singer_ID ORDER BY stadiums_performed DESC LIMIT 10;
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
