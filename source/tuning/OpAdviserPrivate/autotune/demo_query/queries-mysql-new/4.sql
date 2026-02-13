
select current_timestamp(6) into @query_start;
set @query_name='4';
SELECT COUNT(*) as cnt FROM singer;
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
