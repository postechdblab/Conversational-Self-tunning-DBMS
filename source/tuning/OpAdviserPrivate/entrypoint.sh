#!/bin/bash
set -e

WORKDIR=/workspaces/OpAdviserPrivate

# 1. MySQL 런타임 및 데이터 디렉토리 준비
mkdir -p /var/run/mysqld /var/log/mysql /var/log/mysql/base
chown -R mysql:mysql /var/run/mysqld /var/log/mysql /var/lib/mysql

# 2. 기본 MySQL 중지
service mysql stop 2>/dev/null || true
pkill -9 mysqld 2>/dev/null || true
sleep 2

# 3. cnf 파일 복사 (bind mount는 777이라 MySQL이 무시함)
cp ${WORKDIR}/initial2.cnf /tmp/initial2.cnf
chmod 644 /tmp/initial2.cnf

# 4. 데이터 디렉토리에 mysql 시스템 DB가 없으면 초기화
if [ ! -d /var/lib/mysql/mysql ]; then
    rm -rf /var/lib/mysql/*
    mysqld --defaults-file=/tmp/initial2.cnf --initialize-insecure --user=mysql
fi

# 5. 튜닝용 cnf로 MySQL 시작
/usr/sbin/mysqld --defaults-file=/tmp/initial2.cnf &

# 6. MySQL 준비 대기 (최대 120초)
RETRIES=0
until mysqladmin ping -u root -S /var/run/mysqld/mysqld.sock --silent 2>/dev/null; do
    RETRIES=$((RETRIES + 1))
    [ $RETRIES -ge 120 ] && echo "MySQL failed to start" && exit 1
    sleep 1
done

# 7. root 비밀번호 설정 (초기화 직후에만 필요)
mysql -u root -S /var/run/mysqld/mysqld.sock \
  -e "ALTER USER 'root'@'localhost' IDENTIFIED BY 'password';" 2>/dev/null || true

# 7.1. TCP(127.0.0.1) 접속 허용 (backend 컨테이너가 host network로 접속)
mysql -u root -ppassword -S /var/run/mysqld/mysqld.sock \
  -e "CREATE USER IF NOT EXISTS 'root'@'127.0.0.1' IDENTIFIED BY 'password'; \
      GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' WITH GRANT OPTION; \
      FLUSH PRIVILEGES;" 2>/dev/null || true

# 7.5. Buffer pool cold start 보장
mysql -u root -ppassword -S /var/run/mysqld/mysqld.sock \
  -e "SET GLOBAL innodb_buffer_pool_dump_at_shutdown = OFF;" 2>/dev/null || true
mysql -u root -ppassword -S /var/run/mysqld/mysqld.sock \
  -e "SET GLOBAL innodb_buffer_pool_load_at_startup = OFF;" 2>/dev/null || true

# 8. concert_singer DB 존재 확인, 없으면 로드
DB_EXISTS=$(mysql -u root -ppassword -S /var/run/mysqld/mysqld.sock -N \
  -e "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='concert_singer';" 2>/dev/null)
if [ -z "$DB_EXISTS" ]; then
    mysql -u root -ppassword -S /var/run/mysqld/mysqld.sock < ${WORKDIR}/concert_singer.sql
    cd ${WORKDIR} && python concert_singer.py
fi

# 8.5. 튜닝 히스토리 초기화 (매 데모 세션마다 fresh start)
rm -f ${WORKDIR}/repo/history_demo.json
rm -f ${WORKDIR}/all.record
rm -f ${WORKDIR}/space.record
rm -f ${WORKDIR}/demo_sample_list
rm -f ${WORKDIR}/demo_similarity_list
echo "Tuning history cleared for fresh demo session"

# 9. Flask 서버 시작
cd ${WORKDIR}
exec flask run
