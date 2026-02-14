# DBEDA Framework Setup Guide

이 문서는 DBEDA Framework를 새로운 환경에서 Docker 기반으로 셋업하고, `client/DBEDA.ipynb`를 정상 실행하기까지의 전체 과정을 설명합니다.

---

## 목차

1. [Prerequisites](#1-prerequisites)
2. [Repository Clone](#2-repository-clone)
3. [Docker 이미지 Pull](#3-docker-이미지-pull)
4. [docker-compose.yml 수정](#4-docker-composeyml-수정)
5. [설정 파일 확인](#5-설정-파일-확인)
6. [컨테이너 시작](#6-컨테이너-시작)
7. [서비스 시작 (컨테이너 내부)](#7-서비스-시작-컨테이너-내부)
8. [Target DB 설정](#8-target-db-설정)
9. [접속 확인](#9-접속-확인)
10. [포트 요약](#10-포트-요약)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites

다음 소프트웨어가 호스트 머신에 설치되어 있어야 합니다.

- **Docker** + **Docker Compose** (v2 이상 권장)
- **NVIDIA Container Toolkit** (nvidia-docker) - GPU 사용을 위해 필요
- **GPU가 있는 Linux 머신** - CUDA 지원 NVIDIA GPU
- **git**

NVIDIA Container Toolkit 설치 확인:
```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

---

## 2. Repository Clone

```bash
git clone https://github.com/hyukkyukang/DBEDA_Framework.git
cd DBEDA_Framework
```

---

## 3. Docker 이미지 Pull

서버와 클라이언트 이미지를 미리 pull합니다.

```bash
docker pull anonymous824/dbeda_server:latest
docker pull anonymous824/dbeda_client:latest
```

---

## 4. docker-compose.yml 수정

프로젝트 루트의 `docker-compose.yml`에서 image를 pull한 이미지로 변경합니다.

### 예시 docker-compose.yml

```yaml
services:
  dbeda_server:
    image: anonymous824/dbeda_server:latest
    container_name: dbeda_server
    stdin_open: true
    tty: true
    network_mode: host
    shm_size: 4gb
    environment:
      - TZ=Asia/Seoul
      - NVIDIA_VISIBLE_DEVICES=all
    volumes:
      - ./:/root/DBEDA
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]

  dbeda_client:
    image: anonymous824/dbeda_client:latest
    container_name: dbeda_client
    stdin_open: true
    tty: true
    network_mode: host
    shm_size: 4gb
    environment:
      - TZ=Asia/Seoul
      - NVIDIA_VISIBLE_DEVICES=all
    volumes:
      - ./:/root/DBEDA
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              capabilities: [gpu]
```

### 핵심 설정 설명

| 항목 | 값 | 설명 |
|------|-----|------|
| `network_mode` | `host` | 모든 포트가 호스트에 직접 바인딩됨 (별도 포트 매핑 불필요) |
| `stdin_open` / `tty` | `true` | 대화형 셸 접속을 위해 필요 (`docker exec -it`) |
| `shm_size` | `4gb` | 공유 메모리 크기 (PostgreSQL, ML 학습에 필요) |
| `deploy.resources` | GPU 예약 | NVIDIA GPU를 컨테이너에서 사용 가능하도록 설정 |
| `volumes` | `./:/root/DBEDA` | 프로젝트 루트를 컨테이너 내부 `/root/DBEDA`에 마운트 |
| `TZ` | `Asia/Seoul` | 타임존 설정 |
| `NVIDIA_VISIBLE_DEVICES` | `all` | 모든 GPU를 컨테이너에서 사용 가능 |

> **참고**: `network_mode: host`를 사용하므로 `ports` 매핑은 필요하지 않습니다. 컨테이너 내부에서 리슨하는 포트가 곧 호스트의 포트입니다.

---

## 5. 설정 파일 확인

### config.json

프로젝트 루트의 `config.json`에서 각 서비스의 포트를 설정합니다.

```json
{
  "serverdb": 5437,
  "clientdb": 5438,
  "server": 85,
  "dbsherlock": {
    "model": {"num_anomaly_cause": 11, "num_feature": 200},
    "model_path": "checkpoints/DBS_checkpoint.pth",
    "scaler_path": "checkpoints/DBS_scaler.pkl",
    "stats_path": "checkpoints/DBS_config.json"
  }
}
```

- **serverdb (5437)**: Server 컨테이너의 PostgreSQL 포트 (DB 이름: `dbeda`, 메트릭 저장용)
- **clientdb (5438)**: Client 컨테이너의 PostgreSQL 포트 (DB 이름: `test_cli`, 모니터링 대상)
- **server (85)**: Flask API 서버 포트
- **dbsherlock**: DBSherlock 이상 탐지 모델 설정 (체크포인트 경로 등)

> 코드에서 `config.json`은 `/root/DBEDA/config.json` 경로로 참조됩니다.

### .env

프로젝트 루트의 `.env` 파일에 Python 경로를 설정합니다.

```
PYTHONPATH=./server:./client
```

---

## 6. 컨테이너 시작

```bash
docker compose up -d
```

컨테이너 상태 확인:
```bash
docker compose ps
```

두 컨테이너(`dbeda_server`, `dbeda_client`)가 `running` 상태인지 확인합니다.

---

## 7. 서비스 시작 (컨테이너 내부)

컨테이너가 실행된 후, 각 컨테이너 내부에서 PostgreSQL과 애플리케이션 서비스를 수동으로 시작해야 합니다.

### Server 컨테이너

```bash
# 컨테이너 접속
docker exec -it dbeda_server bash

# PostgreSQL 시작
service postgresql start

# Flask API 서버 시작 (백그라운드)
cd /root/DBEDA/server && \
PYTHONPATH=/root/DBEDA/server:/root/DBEDA \
python3 server.py > /tmp/server.log 2>&1 &
```

서버 로그 확인:
```bash
tail -f /tmp/server.log
```

### Client 컨테이너

```bash
# 컨테이너 접속
docker exec -it dbeda_client bash

# PostgreSQL 시작
service postgresql start

# Jupyter Lab 시작 (백그라운드)
cd /root/DBEDA/client && \
PYTHONPATH=/root/DBEDA:/root/DBEDA/client \
jupyter lab --allow-root --ip=0.0.0.0 --port=8888 --no-browser --ServerApp.token='' \
> /tmp/jupyter.log 2>&1 &
```

Jupyter Lab 로그 확인:
```bash
tail -f /tmp/jupyter.log
```

---

## 8. Target DB 설정

### PostgreSQL 인증 정보

양쪽 컨테이너 모두 동일한 PostgreSQL 인증 정보를 사용합니다:

- **User**: `postgres`
- **Password**: `postgres`

### Server 컨테이너 DB

Server 컨테이너의 PostgreSQL (포트 5437)에는 `dbeda` 데이터베이스가 Dockerfile에서 미리 생성되어 있습니다.

- DB 이름: `dbeda`
- 테이블: `db_config` (클라이언트 DB 연결 설정 저장)

### Client 컨테이너 DB (모니터링 대상)

Client 컨테이너의 PostgreSQL (포트 5438)에 `test_cli` 데이터베이스가 Docker 이미지에 이미 포함되어 있습니다 (Dockerfile에서 생성).

### pg_stat_statements 확장

`pg_stat_statements` 확장도 Client Dockerfile에서 미리 설정되어 있어, 쿼리 성능 통계 수집이 가능합니다.

설정 내역 (이미지에 포함):
- `shared_preload_libraries = 'pg_stat_statements'`
- `pg_stat_statements.track = all`

확인 방법 (client 컨테이너 내부):
```bash
psql -U postgres -d test_cli -p 5438 -c "SELECT * FROM pg_stat_statements LIMIT 5;"
```

### 테스트 데이터 생성 (선택)

Client 컨테이너에는 sysbench가 미리 설치되어 있습니다. 추가 테스트 데이터를 생성할 수 있습니다.

```bash
# 예시: sysbench로 OLTP 테스트 데이터 생성 (client 컨테이너 내부에서 실행)
sysbench oltp_read_write \
  --db-driver=pgsql \
  --pgsql-host=127.0.0.1 \
  --pgsql-port=5438 \
  --pgsql-user=postgres \
  --pgsql-password=postgres \
  --pgsql-db=test_cli \
  --tables=4 \
  --table-size=100000 \
  prepare
```

---

## 9. 접속 확인

### Jupyter Lab

브라우저에서 아래 URL로 접속합니다:

```
http://<호스트IP>:8888/lab
```

> token 없이 접속 가능 (`--ServerApp.token=''` 설정)

### Flask API

```
http://<호스트IP>:85
```

### DBEDA.ipynb 실행 검증

1. 브라우저에서 `http://<호스트IP>:8888/lab` 접속
2. 파일 브라우저에서 `DBEDA.ipynb` 열기
3. **첫 번째 셀** 실행: `from client_side import *`
   - config 파일이 정상 로드되면 성공
4. **두 번째 셀** 실행: `connect_db(...)`
   - `"Configuration data sent successfully."` 출력 확인
5. **세 번째 셀** 실행: `visualize(connection)`
   - 대시보드 위젯이 정상 표시되면 성공

---

## 10. 포트 요약

| 서비스 | 포트 | DB/설명 |
|--------|------|---------|
| Server PostgreSQL | 5437 | DB: `dbeda` / 메트릭 저장, 연결 설정 관리 |
| Client PostgreSQL | 5438 | DB: `test_cli` / 모니터링 대상 DB |
| Flask API | 85 | DBEDA 서버 API (`/connect`, `/collect`, `/schema`, `/train`, `/predict`) |
| Jupyter Lab | 8888 | 노트북 인터페이스 (`DBEDA.ipynb`) |

> `network_mode: host`를 사용하므로, 위 포트들이 호스트에서 직접 접근 가능합니다. 방화벽 설정에서 해당 포트들이 열려 있는지 확인하세요.

---

## 11. Troubleshooting

### PostgreSQL이 시작되지 않는 경우

```bash
# 로그 확인
cat /var/log/postgresql/postgresql-*-main.log

# 포트 충돌 확인
ss -tlnp | grep 5437
ss -tlnp | grep 5438

# 수동 시작 시도
pg_ctlcluster <version> main start
```

### Flask API에 연결할 수 없는 경우

```bash
# 서버 프로세스 확인
ps aux | grep server.py

# 포트 리슨 확인
ss -tlnp | grep 85

# 서버 로그 확인
cat /tmp/server.log
```

### Jupyter Lab에 접속할 수 없는 경우

```bash
# Jupyter 프로세스 확인
ps aux | grep jupyter

# 포트 리슨 확인
ss -tlnp | grep 8888

# Jupyter 로그 확인
cat /tmp/jupyter.log
```

### GPU가 인식되지 않는 경우

```bash
# 호스트에서 확인
nvidia-smi

# 컨테이너 내부에서 확인
docker exec -it dbeda_server nvidia-smi

# NVIDIA Container Toolkit 설치 확인
dpkg -l | grep nvidia-container-toolkit
```

### DBEDA.ipynb 첫 번째 셀에서 ImportError 발생 시

```bash
# PYTHONPATH 확인
echo $PYTHONPATH

# client 디렉토리에 client_side 모듈이 있는지 확인
ls /root/DBEDA/client/

# 수동으로 PYTHONPATH 설정 후 Jupyter 재시작
export PYTHONPATH=/root/DBEDA:/root/DBEDA/client
jupyter lab --allow-root --ip=0.0.0.0 --port=8888 --no-browser --ServerApp.token=''
```

### connect_db에서 연결 실패 시

```bash
# Server 컨테이너의 PostgreSQL 상태 확인
docker exec -it dbeda_server service postgresql status

# Flask API 응답 확인
curl http://localhost:85

# Client 컨테이너의 PostgreSQL 상태 확인
docker exec -it dbeda_client service postgresql status
psql -U postgres -p 5438 -c "SELECT 1;"
```

### 컨테이너 재시작 후 서비스 복구

컨테이너를 재시작하면 PostgreSQL과 애플리케이션 서비스가 중지됩니다. [7. 서비스 시작](#7-서비스-시작-컨테이너-내부) 단계를 다시 수행하세요.

```bash
# 컨테이너 재시작
docker compose restart

# 각 컨테이너에서 서비스 재시작 (위 7번 참고)
docker exec -it dbeda_server bash -c "service postgresql start && cd /root/DBEDA/server && PYTHONPATH=/root/DBEDA/server:/root/DBEDA python3 server.py > /tmp/server.log 2>&1 &"
docker exec -it dbeda_client bash -c "service postgresql start && cd /root/DBEDA/client && PYTHONPATH=/root/DBEDA:/root/DBEDA/client jupyter lab --allow-root --ip=0.0.0.0 --port=8888 --no-browser --ServerApp.token='' > /tmp/jupyter.log 2>&1 &"
```
