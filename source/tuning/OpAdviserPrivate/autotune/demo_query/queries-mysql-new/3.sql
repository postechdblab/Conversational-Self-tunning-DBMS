
select current_timestamp(6) into @query_start;
set @query_name='3';
SELECT stadium.Name FROM stadium NATURAL JOIN concert WHERE concert.concert_Name = 'Auditions';
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
