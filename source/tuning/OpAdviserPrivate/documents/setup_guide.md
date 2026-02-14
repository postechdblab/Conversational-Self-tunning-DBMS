# OpAdviser Setup Guide

이 문서는 OpAdviser 데모 환경을 처음부터 구축하기까지 수행한 전체 과정을 기록한다.

---

## 목차

1. [DevContainer 설정](#1-devcontainer-설정)
2. [컨테이너 빌드 및 실행](#2-컨테이너-빌드-및-실행)
3. [시스템 패키지 설치](#3-시스템-패키지-설치)
4. [Python 환경 구성](#4-python-환경-구성)
5. [MySQL 설정](#5-mysql-설정)
6. [데이터베이스 생성 및 데이터 적재](#6-데이터베이스-생성-및-데이터-적재)
7. [Flask 서버 실행](#7-flask-서버-실행)
8. [트러블슈팅 기록](#8-트러블슈팅-기록)
9. [버그 수정 기록](#9-버그-수정-기록)

---

## 1. DevContainer 설정

### 디스크 현황 파악

호스트 머신의 디스크 구성을 확인하여 SSD 마운트 대상을 결정했다.

- `sda` (894.3G) - 시스템 디스크, 99% 사용
- `sdb` (1.8T) - HDD, `/mnt/sdb1`
- `sdc`~`sdh` - 여러 SSD (1.8T~916G 범위)

성능을 위해 MySQL 데이터 디렉토리와 Python 라이브러리를 SSD에 마운트해야 했다. 여유 공간이 165G인 `/mnt/sdd`를 선택했다.

### 마운트 디렉토리 생성

```bash
mkdir -p /mnt/sdd/shpark/OpAdviser/mysql
mkdir -p /mnt/sdd/shpark/OpAdviser/lib
mkdir -p /mnt/sdd/shpark/OpAdviser/root
```

### devcontainer.json 설정

기존 설정에서 발견된 문제:
- `workspaceMount`가 주석 처리되어 기본 루트 디스크에 마운트됨
- `mounts`에 존재하지 않는 경로(`/mnt/nvme0n1/jeseok/...`)가 설정되어 있었음
- `workspaceFolder` 경로가 잘못 지정됨

수정된 `.devcontainer/devcontainer.json`:

```json
{
    "name": "OpAdviser",
    "image": "mcr.microsoft.com/devcontainers/base:bionic",
    "workspaceMount": "source=${localWorkspaceFolder},target=/workspaces/${localWorkspaceFolderBasename},type=bind,consistency=cached",
    "workspaceFolder": "/workspaces/${localWorkspaceFolderBasename}",
    "shutdownAction": "none",
    "customizations": {
        "jetbrains": {
            "backend": "PyCharm"
        }
    },
    "runArgs": [
        "--memory=64gb",
        "--network=host",
        "--dns=141.223.1.2",
        "--dns=1.0.0.1"
    ],
    "mounts": [
        "source=/mnt/sdd/shpark/OpAdviser/mysql,target=/var/lib/mysql,type=bind,consistency=cached",
        "source=/mnt/sdd/shpark/OpAdviser/lib,target=/usr/local/lib,type=bind,consistency=cached",
        "source=/mnt/sdd/shpark/OpAdviser/root,target=/root,type=bind,consistency=cached"
    ],
    "containerEnv": {
        "DOCKER_CLI_EXPERIMENTAL": "enabled"
    },
    "remoteUser": "root"
}
```

핵심 설정:
| 항목 | 값 | 설명 |
|------|-----|------|
| `image` | `base:bionic` | Ubuntu 18.04 (Bionic) 기반 |
| `--memory` | `64gb` | 컨테이너 메모리 제한 |
| `--network` | `host` | 호스트 네트워크 모드 (포트 직접 접근) |
| `/var/lib/mysql` | SSD 마운트 | MySQL 데이터 I/O 성능 |
| `/usr/local/lib` | SSD 마운트 | Python 패키지 로드 성능 |

---

## 2. 컨테이너 빌드 및 실행

```bash
devcontainer open /home/shpark/OpAdviserPrivate
```

생성된 컨테이너(`gifted_khorana`)가 host network 모드로 실행되었다.

마운트 확인:
```bash
docker exec gifted_khorana df -h /var/lib/mysql /usr/local/lib /root
# 모두 /dev/sdd1에 마운트됨을 확인
```

---

## 3. 시스템 패키지 설치

컨테이너 내부에서 다음 패키지를 설치했다:

```bash
docker exec gifted_khorana bash -c "apt update && apt install -y \
    mysql-server-5.7 \
    git \
    default-jdk \
    ant \
    build-essential \
    openssh-client \
    cgroup-tools \
    libaio1 \
    libaio-dev \
    python3.8 \
    python3.8-dev \
    python3.8-venv \
    python3-pip \
    python3-setuptools \
    autoconf \
    pkg-config \
    libtool \
    libmysqlclient-dev \
    automake \
    sudo"
```

주요 패키지 용도:
- `mysql-server-5.7`: 튜닝 대상 DBMS
- `default-jdk`, `ant`: OLTP-Bench 빌드용
- `cgroup-tools`: 리소스 격리
- `python3.8`: OpAdviser 실행 환경
- `libmysqlclient-dev`: `mysql-connector-python` 빌드 의존성

---

## 4. Python 환경 구성

### Python 3.8을 기본으로 설정

```bash
update-alternatives --install /usr/bin/python python /usr/bin/python3.8 1
update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.8 1
python -m pip install --upgrade pip
pip install --user --upgrade setuptools
pip install --upgrade wheel
```

### 의존성 설치

```bash
python -m pip install -r requirements.txt
```

`requirements.txt` 주요 패키지:

| 카테고리 | 패키지 |
|----------|--------|
| ML/Data | `pandas==1.4.4`, `numpy<1.20.0`, `scikit_learn==1`, `scipy==1.10.1` |
| Deep Learning | `torch>=1.5.0` |
| DB 연결 | `mysql-connector-python-rf==2.2.2`, `psycopg2-binary==2.9.9` |
| 최적화 | `openbox==0.8.3`, `hyperopt==0.2.7`, `botorch==0.8.5`, `smac==1.2`, `scikit-optimize==0.9.0`, `cma` |
| 설정 공간 | `ConfigSpace==0.4.21` |
| 트리 모델 | `lightgbm==4.4.0`, `xgboost==2.1.0` |
| Feature 분석 | `shap==0.44.1` |
| 서버 | `Flask`, `flask_cors` |
| 시각화 | `matplotlib==3.6.3`, `hiplot` |

---

## 5. MySQL 설정

### 기본 설정 추가

```bash
echo '[mysqld]
port=3308
innodb_log_checksums = 0' | sudo tee -a /etc/mysql/my.cnf
```

- **Port 3308**: 호스트의 기본 MySQL(3306)과 충돌 방지
- **innodb_log_checksums = OFF**: 튜닝 실험 시 성능 오버헤드 제거

### MySQL 서비스 시작 및 사용자 설정

```bash
service mysql start

# root 비밀번호 설정
mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'password';"

# 다양한 호스트에서의 접속 허용
mysql -ppassword -e "CREATE USER 'root'@'127.0.0.1' IDENTIFIED BY 'password';"
mysql -ppassword -e "CREATE USER 'root'@'::1' IDENTIFIED BY 'password';"
mysql -ppassword -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1';"
mysql -ppassword -e "GRANT ALL PRIVILEGES ON *.* TO 'root'@'::1';"
mysql -ppassword -e "FLUSH PRIVILEGES;"

# 최대 연결 수 설정
mysql -ppassword -e "SET GLOBAL max_connections=100000;"
```

### 튜닝용 MySQL 설정 파일 (initial2.cnf)

Flask 서버 기동 시 `initial2.cnf`를 사용하여 MySQL을 실행한다. 이 파일에는 197개의 knob이 명시적으로 설정되어 있으며, 주요 항목:

```ini
[mysqld]
port = 3308
socket = /var/run/mysqld/mysqld.sock
datadir = /var/lib/mysql
max_connections = 5000
innodb_buffer_pool_size = 100
innodb_log_file_size = 1073741824
innodb_flush_method = O_DIRECT
binlog-format = ROW
```

---

## 6. 데이터베이스 생성 및 데이터 적재

### 스키마 생성

`concert_singer.sql`로 데이터베이스와 테이블을 생성했다:

```bash
mysql --socket=/var/run/mysqld/mysqld.sock -u root -ppassword < concert_singer.sql
```

생성되는 스키마:
- `concert_singer` 데이터베이스
- `stadium` 테이블 (Stadium_ID, Location, Name, Capacity, Highest, Lowest, Average)
- `singer` 테이블 (Singer_ID, Name, Country, Song_Name, Song_release_year, Age, Is_male)
- `concert` 테이블 (concert_ID, concert_Name, Theme, Stadium_ID, Year)
- `singer_in_concert` 테이블 (concert_ID, Singer_ID)

초기 데이터: stadium 9건, singer 6건, concert 6건, singer_in_concert 10건

### 대량 데이터 적재

`concert_singer.py`를 실행하여 stadium 테이블에 약 50만 건의 랜덤 데이터를 추가했다:

```bash
python concert_singer.py
```

- ID 범위: 35,020 ~ 500,000
- 배치 크기: 1,000건씩 INSERT
- 목적: 튜닝 효과를 체감할 수 있을 만큼의 데이터 볼륨 확보

---

## 7. Flask 서버 실행

### 실행 방법

컨테이너 안에서 아래 명령으로 서버를 기동한다:

```bash
# 기존 MySQL 서비스 중지 후, 튜닝용 cnf로 직접 실행
service mysql stop
/usr/sbin/mysqld --defaults-file=initial2.cnf &

# Flask 서버 실행
export PYTHONPATH=.
export FLASK_RUN_PORT=1234
export FLASK_APP=server/app.py
flask run
```

### 서버 구조

`server/app.py`가 제공하는 엔드포인트:

| 엔드포인트 | 메서드 | 기능 |
|------------|--------|------|
| `/query` | POST | SQL 쿼리 실행 또는 `"conduct tuning"` 요청 시 튜닝 수행 |
| `/knobs` | POST | 현재 MySQL 변수(knob) 목록 반환 |

동작 흐름:
1. 클라이언트가 SQL 쿼리를 `/query`로 전송하면, 쿼리를 실행하고 결과와 실행 시간을 반환
2. 내부적으로 `queries`와 `times` 리스트에 쿼리와 실행 시간을 누적
3. `"conduct tuning"` 요청 시, 누적된 쿼리들을 `.sql` 파일로 생성하고 `tuner.tune()`을 반복 호출
4. 모든 쿼리의 실행 시간이 튜닝 전보다 개선되면 결과를 반환하고 `queries`/`times`를 초기화

### 튜닝 설정 (scripts/demo.ini)

```ini
[database]
db = mysql
host = localhost
port = 3308
user = root
passwd = password
sock = /var/run/mysqld/mysqld.sock
dbname = concert_singer
workload = demo
thread_num = 80
workload_time = 180

[tune]
task_id = demo
performance_metric = ['tps']
max_runs = 100
selector_type = shap
optimize_method = DDPG
transfer_framework = none
space_transfer = True
latent_dim = 1
```

---

## 8. 트러블슈팅 기록

### 8.1 DevContainer 마운트 경로 오류

**문제**: 기존 설정에 `/mnt/nvme0n1/jeseok/...` 경로가 하드코딩되어 있었으나, 해당 경로가 존재하지 않아 컨테이너 빌드 실패.

**해결**: `/mnt/sdd/shpark/OpAdviser/` 아래에 디렉토리를 새로 생성하고 devcontainer.json을 수정.

### 8.2 InnoDB Redo Log 복구 지연

**문제**: MySQL 최초 기동 시 InnoDB가 10GB redo log를 재생성하느라 시작이 지연됨.

**해결**: 로그 복구가 완료될 때까지 대기. Flask 서버가 연결 실패를 반복 출력하다가 MySQL 준비 완료 후 정상 동작.

### 8.3 Docker exec 파이프 리다이렉션 문제

**문제**: 호스트에서 `docker exec gifted_khorana mysql -u root -ppassword < concert_singer.sql` 실행 시, `<` 리다이렉션이 **호스트 셸**에서 처리되어 호스트의 기본 MySQL(3306)로 연결됨. 컨테이너 내부의 MySQL(3308)에 데이터베이스가 생성되지 않음.

**해결**: `bash -c`로 감싸서 리다이렉션을 컨테이너 내부에서 실행:
```bash
docker exec gifted_khorana bash -c \
    "mysql --socket=/var/run/mysqld/mysqld.sock -u root -ppassword < concert_singer.sql"
```

### 8.4 Flask 실행 인자 오류

**문제**: `flask run --host=0.0.0.0` 실행 시 `unrecognized arguments` 에러 발생.

**해결**: `--network=host` 모드이므로 `--host` 플래그 없이 `flask run`만 실행. 컨테이너가 호스트 네트워크를 공유하므로 `localhost:1234`로 직접 접근 가능.

---

## 9. 버그 수정 기록

### 9.1 app.py 튜닝 세션 간 상태 누적 문제

**문제**: `queries`와 `times` 리스트가 튜닝 성공 후에도 초기화되지 않아, 다음 튜닝 요청 시 이전 세션의 쿼리까지 포함하여 모든 쿼리를 개선해야 했음. 연속 튜닝이 점점 어려워지고 의미적으로도 잘못된 동작.

**수정**: 튜닝 성공 시 `queries.clear()`와 `times.clear()` 호출 추가:
```python
if b:
    queries.clear()
    times.clear()
    return {
        "execution_times": execution_times,
    }
```
