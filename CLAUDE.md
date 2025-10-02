# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a conversational self-tuning DBMS system (SQLBot/DBAdminBot) that combines natural language processing with database management. It translates natural language queries to SQL, detects user intent, analyzes query results, and performs database tuning operations.

## Architecture

### Core Components

**Backend Server** (`source/backend_server.py`)
- Flask-based REST API server (port 7000 by default)
- Integrates multiple ML models for text-to-SQL, intent classification, and result analysis
- Uses Redis for response caching across 4 separate databases
- Main endpoints: `/text_to_sql`, `/table_to_text`, `/reset_history`

**Module Structure**
- `source/text2sql/`: Text-to-SQL translation using RAT-SQL model with beam search
- `source/text2intent/`: User intent classification model
- `source/conversation/`: Conversational features including nl2confidence and table2text
- `source/diagnosis/`: Query analysis and detection modules
- `source/tuning/`: Database tuning functionality

**LLM Backend**
- Uses SGLang inference engine with Llama 3.1 8B Instruct
- Launched via Docker container on port 30000
- Communicates with backend server for advanced reasoning

### Configuration

The project uses both JSON and YAML configurations:
- `backend_config.json`: Main server configuration with model paths, Redis settings, and device allocation
- `config/backend_config.yaml`: Server host/port settings
- `config/text2sql.yaml`: Text-to-SQL model configuration
- `config/text2intent.yaml`: Intent classification model settings
- Module-specific configs in `config/conversation/` and `config/diagnosis/`

Model checkpoints are expected in `/mnt/sdd/shpark/logdir/` directory structure.

## Development Commands

### Setup and Running

Start all services (Redis, frontend, backend):
```bash
docker compose up -d
```

Start the LLM inference engine:
```bash
sh ./source/conversation/llm.sh
```

Run the backend server directly (requires models and Redis):
```bash
python source/backend_server.py
```

### Key Dependencies

- PyTorch with CUDA 12.1 support
- Transformers, spaCy with transformer models
- Redis for caching
- Flask with CORS for API server
- PostgreSQL drivers (psycopg)
- RAT-SQL framework for SQL generation

## Important Implementation Details

### Text History and Context
- The system maintains conversation history in `text_history` global variable
- History is prepended with `<s>` tokens for contextual SQL generation
- Use `/reset_history` endpoint to clear conversation context

### Caching Strategy
- Four separate Redis databases for different cache types:
  - DB 0: Text-to-SQL results
  - DB 1: Analysis results
  - DB 2: Table-to-text summaries
  - DB 3: User intent classifications
- Cache keys are generated from text + db_id combinations
- Set `flush_redis = False` in backend_server.py to preserve cache between restarts

### Model Pipeline
1. User text → Intent detection (database_tuning vs query)
2. If tuning intent: Route to tuning module
3. If query: Text-to-SQL with beam search (beam_size=2, max_steps=150)
4. Confidence calculation with heuristic refinement
5. Low confidence queries trigger result analysis using Captum attribution
6. Response includes SQL, confidence score, and user intent

### Docker Architecture
- Frontend container: `hyukkyukang/sqlbot:latest`
- Backend container: `hyukkyukang/nl2qgm:latest` with GPU support
- Redis container: Latest official image on port 6380
- All use host networking except Redis (bridge network)

## Configuration Notes

- Redis host in backend_config.json points to 141.223.197.19:6379 (update for local development)
- CUDA_VISIBLE_DEVICES can be set in llm.sh for GPU selection
- Model paths in configs assume `/mnt/sdd/shpark/logdir/` structure
- Database files expected in Spider dataset format