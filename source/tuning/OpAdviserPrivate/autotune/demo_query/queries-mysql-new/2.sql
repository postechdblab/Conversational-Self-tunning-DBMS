
select current_timestamp(6) into @query_start;
set @query_name='2';
SELECT DISTINCT concert.concert_ID,         stadium.Capacity,         stadium.Stadium_ID FROM concert JOIN stadium ON concert.Stadium_ID = stadium.Stadium_ID WHERE stadium.Capacity < (   SELECT AVG(stadium.Capacity)   FROM stadium   WHERE stadium.Location = 'Peterhead' );
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
