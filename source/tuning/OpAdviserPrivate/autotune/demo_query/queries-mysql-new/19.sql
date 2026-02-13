
select current_timestamp(6) into @query_start;
set @query_name='19';
SELECT c.concert_Name, c.Year, s.Name as stadium, COUNT(sc.Singer_ID) as num_singers FROM concert c JOIN stadium s ON c.Stadium_ID = s.Stadium_ID JOIN singer_in_concert sc ON c.concert_ID = sc.concert_ID GROUP BY c.concert_ID ORDER BY num_singers DESC LIMIT 10;
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
