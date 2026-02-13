# DBAdminBot 배포 가이드

현재 서버의 컨테이너를 `docker commit`으로 이미지화한 뒤, 다른 서버에서 동일하게 실행하기 위한 가이드.

---

## 1. 아키텍처 개요

```
                   +-----------------+
                   |   Frontend      |  port 3000 (Next.js)
                   |   (sqlbot)      |  → PostgreSQL 5434 (내장, schema 표시용)
                   +--------+--------+
                            |
              +-------------+-------------+
              |                           |
    +---------v---------+       +---------v---------+
    |   Backend         |       |   OpAdviser       |  port 1234 (Flask)
    |   (nl2qgm)        |       |   (opadvisor)     |  → MySQL 3308 (내장)
    |   port 7000       |       +-------------------+
    +--------+----------+
             |
    +--------v----------+       +-----------------+
    |   Redis           |       |   LLM (SGLang)  |
    |   port 6379       |       |   port 30000    |
    +-------------------+       +-----------------+
```

### 포트 요약

| 서비스 | 포트 | 설명 |
|--------|------|------|
| Frontend (Next.js) | 3000 | 웹 UI |
| Backend (Flask/Waitress) | 7000 | Text2SQL API 서버 |
| Redis | 6379 | 캐시 서버 |
| OpAdviser (Flask) | 1234 | DB 튜닝 서비스 |
| MySQL (OpAdviser 내장) | 3308 | 튜닝 대상 MySQL |
| SGLang LLM | 30000 | LLM 추론 서버 |
| PostgreSQL (Frontend 내장) | 5434 | 스키마 표시용 (현재 미사용, 5432로 내장) |

---

## 2. 현재 서버에서 이미지 생성

### 2.1 컨테이너 commit

```bash
# 현재 실행 중인 컨테이너를 이미지로 저장
docker commit DBAdminBot-frontend   myregistry/dbadminbot-frontend:v1
docker commit DBAdminBot-backend    myregistry/dbadminbot-backend:v1
docker commit DBAdminBot-opadvisor  myregistry/dbadminbot-opadvisor:v1
# Redis는 공식 이미지 그대로 사용
# SGLang도 공식 이미지 그대로 사용 (lmsysorg/sglang:latest)
```

### 2.2 이미지 export (레지스트리 없는 경우)

```bash
docker save myregistry/dbadminbot-frontend:v1  | gzip > dbadminbot-frontend.tar.gz
docker save myregistry/dbadminbot-backend:v1   | gzip > dbadminbot-backend.tar.gz
docker save myregistry/dbadminbot-opadvisor:v1 | gzip > dbadminbot-opadvisor.tar.gz
docker save lmsysorg/sglang:latest             | gzip > sglang.tar.gz
docker save redis:latest                       | gzip > redis.tar.gz
```

대상 서버에서:
```bash
docker load < dbadminbot-frontend.tar.gz
docker load < dbadminbot-backend.tar.gz
docker load < dbadminbot-opadvisor.tar.gz
docker load < sglang.tar.gz
docker load < redis.tar.gz
```

### 2.3 이미지 크기 참고

| 이미지 | 대략적 크기 |
|--------|------------|
| `dbadminbot-frontend` (sqlbot) | ~8.5 GB |
| `dbadminbot-backend` (nl2qgm) | ~23 GB |
| `dbadminbot-opadvisor` | ~1.5 GB |
| `lmsysorg/sglang:latest` | ~38.5 GB |
| `redis:latest` | ~150 MB |

---

## 3. 데이터 디렉토리 구조

호스트 서버에 아래 디렉토리 구조를 준비해야 한다. 현재 서버에서 복사하여 사용.

### 3.1 소스 코드 (Git 저장소)

```
<PROJECT_ROOT>/                          # git clone한 저장소 루트
├── demo/dbadminbot/frontend/            # Frontend 소스
│   └── web/                             # Next.js 앱 (node_modules 포함)
│       ├── .env                         # ← 수정 필요 (MODEL_API_ADDR)
│       ├── app/
│       ├── databases/                   # DB 스키마 정의 (JSON)
│       ├── prisma/                      # Prisma 스키마
│       └── ...
├── demo/dbadminbot/backend/             # Backend 소스
│   ├── backend_server_v2.py             # 메인 서버 코드
│   └── requirements.txt
├── source/                              # 모든 ML 모듈 소스코드
│   ├── text2sql/
│   ├── text2intent/
│   ├── conversation/
│   ├── diagnosis/
│   └── tuning/OpAdviserPrivate/         # OpAdviser 소스 + 설정
│       ├── server/app.py                # OpAdviser Flask 서버
│       ├── entrypoint.sh                # 컨테이너 시작 스크립트
│       ├── initial2.cnf                 # MySQL 설정 파일
│       ├── concert_singer.sql           # 데모 DB 스키마
│       ├── concert_singer.py            # 데모 데이터 생성 스크립트
│       ├── scripts/demo.ini             # 튜닝 설정
│       └── repo/                        # 튜닝 히스토리 (런타임 생성)
└── config/                              # Hydra 설정 파일들
    ├── config.yaml                      # ← 수정 필요 (호스트 설정)
    ├── text2sql/default.yaml            # ← 수정 필요 (모델 경로)
    ├── text2intent/default.yaml         # ← 수정 필요 (모델 경로)
    ├── conversation/
    ├── diagnosis/
    ├── redis/default.yaml
    ├── remote/llm.yaml                  # ← 수정 필요 (GPU, 모델 경로)
    ├── data/spider.yaml                 # ← 수정 필요 (데이터 경로)
    └── path.py
```

### 3.2 모델 체크포인트 (필수 복사)

현재 서버의 `/mnt/sdd/shpark/` 디렉토리에 저장되어 있다.

```
<DATA_ROOT>/
├── logdir/                              # ~28 GB
│   ├── cosql-model/                     # Text2SQL 모델 (~11 GB)
│   │   ├── config.jsonnet
│   │   ├── config_captum.jsonnet
│   │   └── (체크포인트 파일들)
│   └── intent-model/                    # Intent 분류 모델 (~7.6 GB)
│       └── bs=24,lr=7.4e-04,.../
│           ├── config.jsonnet
│           └── (체크포인트 파일들)
├── spider/                              # Spider 데이터셋 (~878 MB)
│   ├── database/                        # SQLite DB 파일들
│   ├── tables.json                      # 스키마 정보
│   └── dev.json                         # 평가 데이터
└── OpAdviser/
    └── lib/                             # OpAdviser Python 라이브러리 (~5.9 GB)
        └── python3.8/                   # site-packages
```

### 3.3 LLM 모델 (필수 복사)

현재 서버의 `/mnt/sde/shpark/models/` 디렉토리에 저장되어 있다.

```
<LLM_ROOT>/
└── models/
    └── gpt-oss-20b/                     # SGLang이 사용하는 LLM (~39 GB)
```

### 3.4 크기 요약

| 항목 | 경로 (현재 서버) | 크기 | 용도 |
|------|-----------------|------|------|
| Text2SQL 모델 | `/mnt/sdd/shpark/logdir/cosql-model/` | ~11 GB | NL→SQL 변환 |
| Intent 모델 | `/mnt/sdd/shpark/logdir/intent-model/` | ~7.6 GB | 사용자 의도 분류 |
| Spider 데이터셋 | `/mnt/sdd/shpark/spider/` | ~878 MB | DB 스키마 + 평가 데이터 |
| OpAdviser lib | `/mnt/sdd/shpark/OpAdviser/lib/` | ~5.9 GB | Python 패키지 (OpAdviser용) |
| LLM 모델 | `/mnt/sde/shpark/models/gpt-oss-20b/` | ~39 GB | LLM 추론 |
| **합계** | | **~64 GB** | |

---

## 4. 환경 변수 및 설정 파일 수정

새 서버의 경로에 맞게 수정해야 하는 파일들을 정리한다. 아래에서 `<NEW_IP>`는 새 서버 IP, `<DATA_ROOT>`는 모델/데이터가 위치한 경로, `<LLM_ROOT>`는 LLM 모델이 위치한 경로를 의미한다.

### 4.1 `docker-compose.yml`

```yaml
services:
    DBAdminBot-frontend:
        image: myregistry/dbadminbot-frontend:v1   # commit한 이미지로 변경
        # ... (나머지 동일)

    DBAdminBot-backend:
        image: myregistry/dbadminbot-backend:v1    # commit한 이미지로 변경
        volumes:
            - /etc/timezone:/etc/timezone:ro
            - ./demo/dbadminbot/backend:/root/dbadminbot/
            - ./source:/root/dbadminbot/source
            - ./config:/root/dbadminbot/config
            - redis_data:/root/dbadminbot/data/redis/
            - /var/run/docker.sock:/var/run/docker.sock
            - <LLM_ROOT>:<LLM_ROOT>               # ← LLM 모델 경로로 변경
            # 주의: /mnt:/mnt 대신 필요한 경로만 마운트

    DBAdminBot-opadvisor:
        image: myregistry/dbadminbot-opadvisor:v1  # commit한 이미지로 변경
        volumes:
            - /etc/timezone:/etc/timezone:ro
            - ./source/tuning/OpAdviserPrivate:/workspaces/OpAdviserPrivate
            - <DATA_ROOT>/OpAdviser/lib:/usr/local/lib    # ← 경로 변경
            - opadvisor_mysql:/var/lib/mysql
```

**핵심 volume mount 정리:**

| 컨테이너 | 호스트 경로 | 컨테이너 경로 | 설명 |
|----------|------------|--------------|------|
| frontend | `./demo/dbadminbot/frontend` | `/root/dbadminbot` | Next.js 소스코드 |
| backend | `./demo/dbadminbot/backend` | `/root/dbadminbot/` | Backend 소스코드 |
| backend | `./source` | `/root/dbadminbot/source` | ML 모듈 소스코드 |
| backend | `./config` | `/root/dbadminbot/config` | Hydra 설정 파일 |
| backend | (docker volume) `redis_data` | `/root/dbadminbot/data/redis/` | Redis 데이터 |
| backend | `/var/run/docker.sock` | `/var/run/docker.sock` | SGLang 컨테이너 실행용 |
| backend | `/mnt` (또는 LLM 모델 경로) | `/mnt` | LLM 모델 접근 |
| opadvisor | `./source/tuning/OpAdviserPrivate` | `/workspaces/OpAdviserPrivate` | OpAdviser 소스 |
| opadvisor | `<DATA_ROOT>/OpAdviser/lib` | `/usr/local/lib` | Python 라이브러리 |
| opadvisor | (docker volume) `opadvisor_mysql` | `/var/lib/mysql` | MySQL 데이터 |
| redis | (docker volume) `redis_data` | `/data` | Redis 영속 데이터 |

### 4.2 `config/remote/llm.yaml` (LLM 서버 설정)

```yaml
host: localhost
port: 30000
tp: 1                         # tensor parallelism (GPU 수에 맞게 조정)
dp: 1                         # data parallelism
mem_fraction_static: 0.95
gpu_ids: [0]                  # ← 새 서버의 사용 가능한 GPU ID로 변경

model_path: <LLM_ROOT>/models/gpt-oss-20b    # ← LLM 모델 경로
hf_token: ""                                   # 필요시 HuggingFace 토큰
docker_image: lmsysorg/sglang:latest
mount_source: <LLM_ROOT>                       # ← 호스트 마운트 소스
mount_target: <LLM_ROOT>                       # ← 컨테이너 마운트 타겟
health_check_timeout: 300
health_check_interval: 10
```

### 4.3 `config/text2sql/default.yaml` (Text2SQL 모델)

```yaml
experiment_config_path: <DATA_ROOT>/logdir/cosql-model/config.jsonnet
model_ckpt_dir_path: <DATA_ROOT>/logdir/cosql-model
# ... (나머지는 동일)
```

> 주의: 이 경로들은 **backend 컨테이너 내부에서** 접근 가능해야 한다. backend 컨테이너에 `/mnt:/mnt`로 마운트하는 경우 호스트 경로와 동일하게 쓸 수 있다. 그렇지 않으면 컨테이너 내부 경로에 맞게 조정.

### 4.4 `config/text2intent/default.yaml` (Intent 모델)

```yaml
experiment_config_path: <DATA_ROOT>/logdir/intent-model/bs=24,lr=7.4e-04,bert_lr=3.0e-06,end_lr=0e0,seed=4/config.jsonnet
model_ckpt_dir_path: <DATA_ROOT>/logdir/intent-model/bs=24,lr=7.4e-04,bert_lr=3.0e-06,end_lr=0e0,seed=4
```

### 4.5 `config/conversation/text2confidence/default.yaml`

```yaml
experiment_config_path: <DATA_ROOT>/logdir/cosql-model/config_captum.jsonnet
model_ckpt_dir_path: <DATA_ROOT>/logdir/cosql-model
```

### 4.6 `config/data/spider.yaml` (Spider 데이터셋)

```yaml
name: spider
database_path: <DATA_ROOT>/spider/database
table_path: <DATA_ROOT>/spider/tables.json
eval_data_path: <DATA_ROOT>/spider/dev.json
```

### 4.7 `demo/dbadminbot/frontend/web/.env` (Frontend 환경변수)

```bash
# PostgreSQL — Frontend 내장 DB (스키마 표시용)
# Frontend 컨테이너 내부에서 PostgreSQL을 실행해야 함
DATABASE_URL="postgresql://postgres:postgres@localhost:5434/test_db?schema=public"
CONCERT_SINGER_DATABASE_URL="postgresql://postgres:postgres@localhost:5434/concert_singer?schema=public"
DORM_1_DATABASE_URL="postgresql://postgres:postgres@localhost:5434/dorm_1?schema=public"
FORMULA_1_DATABASE_URL="postgresql://postgres:postgres@localhost:5434/formula_1?schema=public"

# Backend API 주소 — 새 서버 IP로 변경
MODEL_API_ADDR=http://<NEW_IP>:7000
```

### 4.8 `.env` (루트, Backend용)

```bash
CUDA_VISIBLE_DEVICES=0       # ← 새 서버의 GPU 번호로 변경
PYTHONPATH=.
```

### 4.9 Frontend 하드코딩된 주소

Frontend 코드에 OpAdviser 주소가 `localhost:1234`로 하드코딩되어 있다. `host` 네트워크 모드를 사용하므로 **같은 서버에서 실행하는 한 변경 불필요**:

- `demo/dbadminbot/frontend/web/app/conversation/page.tsx:32` → `http://localhost:1234/knobs`
- `demo/dbadminbot/frontend/web/app/conversation/chatWindow.tsx:55` → `http://localhost:1234/query`
- `demo/dbadminbot/frontend/web/lib/api/frontend/query.ts:5` → `http://localhost:1234/query`

---

## 5. 새 서버 사전 요구사항

### 5.1 하드웨어

- **GPU**: 최소 2개 (Backend용 1개 + LLM용 1개, VRAM 각각 24GB+ 권장)
- **RAM**: 32GB+
- **Disk**: 모델 데이터 ~64GB + Docker 이미지 ~72GB + 여유 공간

### 5.2 소프트웨어

- Docker 20.10+ (GPU 지원)
- Docker Compose v2
- NVIDIA Container Toolkit (`nvidia-docker2`)
- NVIDIA Driver (CUDA 12.1 호환)

확인 명령:
```bash
docker --version
docker compose version
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

---

## 6. 배포 절차 (새 서버)

### Step 1: 소스 코드 배치

```bash
git clone <repository-url> ~/Conversational-Self-tunning-DBMS
cd ~/Conversational-Self-tunning-DBMS
```

### Step 2: 데이터 디렉토리 복사

현재 서버에서 `rsync` 또는 `scp`로 복사:

```bash
# 모델 체크포인트 + Spider 데이터 + OpAdviser 라이브러리
rsync -avP <CURRENT_SERVER>:/mnt/sdd/shpark/logdir/     <DATA_ROOT>/logdir/
rsync -avP <CURRENT_SERVER>:/mnt/sdd/shpark/spider/     <DATA_ROOT>/spider/
rsync -avP <CURRENT_SERVER>:/mnt/sdd/shpark/OpAdviser/  <DATA_ROOT>/OpAdviser/

# LLM 모델
rsync -avP <CURRENT_SERVER>:/mnt/sde/shpark/models/gpt-oss-20b/  <LLM_ROOT>/models/gpt-oss-20b/
```

### Step 3: Docker 이미지 로드

```bash
docker load < dbadminbot-frontend.tar.gz
docker load < dbadminbot-backend.tar.gz
docker load < dbadminbot-opadvisor.tar.gz
docker load < sglang.tar.gz
docker load < redis.tar.gz
```

### Step 4: 설정 파일 수정

위 [섹션 4](#4-환경-변수-및-설정-파일-수정)에 따라 모든 경로와 IP를 새 서버에 맞게 수정.

수정 필요 파일 체크리스트:
- [ ] `docker-compose.yml` — 이미지 이름, volume 경로
- [ ] `config/remote/llm.yaml` — GPU ID, 모델 경로, mount 경로
- [ ] `config/text2sql/default.yaml` — 모델 체크포인트 경로
- [ ] `config/text2intent/default.yaml` — 모델 체크포인트 경로
- [ ] `config/conversation/text2confidence/default.yaml` — 모델 체크포인트 경로
- [ ] `config/data/spider.yaml` — Spider 데이터 경로
- [ ] `demo/dbadminbot/frontend/web/.env` — `MODEL_API_ADDR`
- [ ] `.env` — `CUDA_VISIBLE_DEVICES`

### Step 5: 서비스 시작

```bash
cd ~/Conversational-Self-tunning-DBMS
docker compose up -d
```

### Step 6: 서비스 시작 확인

```bash
# 전체 컨테이너 상태 확인
docker compose ps

# 각 서비스 헬스체크
curl http://localhost:1234/health          # OpAdviser (시작까지 ~2분 소요)
curl http://localhost:7000/                # Backend
curl http://localhost:3000                  # Frontend

# 로그 확인
docker compose logs -f DBAdminBot-backend    # Backend 로그
docker compose logs -f DBAdminBot-opadvisor  # OpAdviser 로그
```

### Step 7: Frontend 수동 시작 (필요 시)

Frontend 컨테이너는 자동 시작되지 않으므로 수동으로 진입하여 시작:

```bash
docker exec -it DBAdminBot-frontend bash

# 컨테이너 내부에서:
cd /root/dbadminbot/web

# PostgreSQL 시작 (스키마 표시용, 선택사항)
service postgresql start
# → 포트 변경 필요하면 /etc/postgresql/14/main/postgresql.conf 수정

# Next.js 개발 서버 시작
npm run dev
# 또는 프로덕션 빌드:
# npm run build && npm start
```

### Step 8: Backend 수동 시작 (필요 시)

Backend 컨테이너도 수동으로 서버를 시작해야 한다:

```bash
docker exec -it DBAdminBot-backend bash

# 컨테이너 내부에서:
cd /root/dbadminbot
python backend_server_v2.py
# → LLM 컨테이너가 없으면 자동으로 SGLang 컨테이너를 시작함
# → 최초 시작 시 LLM 로딩에 ~5분 소요
```

---

## 7. 트러블슈팅

### LLM 서버가 시작되지 않음

Backend가 자동으로 SGLang Docker 컨테이너를 시작한다. 실패 시:
```bash
# 수동으로 LLM 컨테이너 시작
docker run -d \
  --gpus "device=0" \
  -p 30000:30000 \
  --ipc=host \
  --mount type=bind,source=<LLM_ROOT>,target=<LLM_ROOT> \
  lmsysorg/sglang:latest \
  python3 -m sglang.launch_server \
    --model-path <LLM_ROOT>/models/gpt-oss-20b \
    --host 0.0.0.0 --port 30000 \
    --tp 1 --dp 1 \
    --mem-fraction-static 0.95

# 헬스체크
curl http://localhost:30000/health
```

### OpAdviser healthcheck 실패

OpAdviser는 MySQL 초기화 후 Flask를 시작하며 `start_period: 120s`가 설정되어 있다.
```bash
docker logs DBAdminBot-opadvisor
# "MySQL failed to start" → /var/lib/mysql 볼륨 초기화 필요:
docker volume rm conversational-self-tunning-dbms_opadvisor_mysql
docker compose up -d DBAdminBot-opadvisor
```

### 경로 관련 오류

Backend 컨테이너는 `network_mode: host`와 `/mnt:/mnt` 마운트를 사용한다. 새 서버에서 모델 파일 경로가 다르면:

**방법 A**: 현재 서버와 동일한 경로 구조를 유지 (심볼릭 링크 활용)
```bash
ln -s <DATA_ROOT> /mnt/sdd/shpark
ln -s <LLM_ROOT> /mnt/sde/shpark
```

**방법 B**: 모든 config 파일의 경로를 새 경로로 변경 (섹션 4 참조)

### Redis 연결 오류

Redis는 bridge 네트워크를 사용하고 포트 6379로 노출된다. Backend는 `localhost:6379`로 접속한다.
```bash
redis-cli -p 6379 ping   # PONG이 나와야 함
```
