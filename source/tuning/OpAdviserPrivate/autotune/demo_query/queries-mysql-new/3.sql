
select current_timestamp(6) into @query_start;
set @query_name='3';
SELECT   concert.concert_ID,   concert.concert_Name,   concert.Theme,   concert.Stadium_ID,   concert.Year,   stadium.Name AS Stadium_Name FROM concert JOIN stadium ON concert.Stadium_ID = stadium.Stadium_ID WHERE concert.concert_Name = 'Auditions';
set @query_time_ms= timestampdiff(microsecond, @query_start, current_timestamp(6))/1000;
SELECT @query_name, @query_time_ms;
