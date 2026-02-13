
select current_timestamp(6) into @query_start;
set @query_name='1';
SELECT stadium.Name, stadium.Capacity FROM stadium;
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
