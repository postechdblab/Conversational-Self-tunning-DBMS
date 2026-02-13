import logging
import os
import pickle
import subprocess
import time

import redis
import hydra
import requests as http_requests
from typing import Dict, List
from flask import Flask, request
from flask_cors import CORS
from omegaconf import DictConfig
from config.path import ABS_CONFIG_DIR
from waitress import serve

from source.text2intent.intent_inferer import IntentInferer
from source.text2sql.text_to_sql import LLMBasedText2SQL
from source.conversation.text2confidence.text_to_confidence import Text2Confidence
from source.conversation.table2text.table_to_text import Table2Text

# Initialize Flask
app = Flask(__name__)
cors = CORS(app)

# Initialize logger
logger = logging.getLogger("FlaskServer")

# Module-level globals (initialized in main)
translator = None
intent_inferer = None
confidence_calculator = None
table2text_model = None
rd_text2sql = None
rd_analysis = None
rd_user_intent = None
rd_table2text = None
text_history = ""


def generate_redis_key(text: str, db_id: str) -> str:
    return text + db_id


@app.route("/")
def Testing():
    logger.info("Hello world?")
    return "<p>Hello, World!</p>"


@app.route("/health")
def health():
    if translator is None:
        return {"status": "initializing"}, 503
    return {"status": "ok"}, 200


@app.route("/reset_history")
def reset_history() -> Dict:
    global text_history
    text_history = ""
    logger.info("History Reset!")
    return {"response": True}


@app.route("/table_to_text", methods=["POST"])
def table_to_text() -> Dict:
    logger.info(f"Received table2text request from {request.remote_addr}")
    table: List[Dict] = request.json["rows"]
    print("table", table)
    redis_key = str(table)
    if rd_table2text.exists(redis_key):
        logger.info("Returning cached result")
        summary = pickle.loads(rd_table2text.get(redis_key))
    else:
        if len(table) == 0 or not isinstance(table, list):
            summary = "There is no data in the table."
        else:
            summary = table2text_model.generate(table)
            if summary is None:
                summary = "There is no data in the table."
        rd_table2text.set(redis_key, pickle.dumps(summary))
    logger.info(f"Response: {summary[:20]}...")
    return {"summary": summary}


@app.route("/text_to_sql", methods=["POST"])
def text_to_sql() -> Dict:
    global text_history
    logger.info(f"Received text2sql request from {request.remote_addr}")
    response = {}
    params: Dict = request.json
    text: str = params["text"]
    print(text)
    db_id: str = params["db_id"]
    analyse: bool = params["analyse"]
    reset_hist: bool = params["reset_history"]
    logger.info(
        f"DB_id: {db_id}, analyse: {analyse}, text: {text} reset_history: {reset_hist} text_history: {text_history}"
    )
    if reset_hist:
        text_history = ""

    # Step 1: Tune check (replaces external API call to :5000)
    tune_result = intent_inferer.infer(text, db_id, is_tune_check=True)
    if tune_result[0]:
        print("tune_intent: ", tune_result[0])
        return {
            "pred_sql": "conduct tuning",
            "confidence": 100,
            "user_intent": "database_tuning",
        }

    # Step 2: Construct input_text and Redis key
    input_text = "<s> " + text + text_history
    redis_key = generate_redis_key(text=input_text, db_id=db_id)

    # Save snapshot before history update (needed for analysis preprocessing)
    text_history_snapshot = text_history

    # Step 3: Text2SQL with cache
    cache_used = False
    if rd_text2sql.exists(redis_key):
        logger.info("Returning cached result")
        response = pickle.loads(rd_text2sql.get(redis_key))
        cache_used = True
        if not text_history.endswith(text):
            text_history += " <s> " + text
    else:
        beams, inferred_code = translator.translate(text, text_history, db_id)
        confidence = confidence_calculator.calculate(beams, inferred_code)
        response["confidence"] = f"{confidence:.2f}"
        response["pred_sql"] = inferred_code
        rd_text2sql.set(redis_key, pickle.dumps(response))
        if not text_history.endswith(text):
            text_history += " <s> " + text

    # Step 4: Attribution analysis
    if analyse and float(response["confidence"]) < 80:
        if rd_analysis.exists(redis_key):
            analyze_result = pickle.loads(rd_analysis.get(redis_key))
        else:
            orig_item, preproc_item = translator.slm_translator.preprocess(
                text, text_history_snapshot, db_id
            )
            analyze_result = confidence_calculator.analyze(
                input_text, orig_item, preproc_item
            )
            rd_analysis.set(redis_key, pickle.dumps(analyze_result))
        response["analyse_result"] = analyze_result

    # Step 5: User intent classification
    if rd_user_intent.exists(redis_key):
        user_intent = pickle.loads(rd_user_intent.get(redis_key))
    else:
        user_intent = intent_inferer.infer(input_text, db_id, is_tune_check=False)
        rd_user_intent.set(redis_key, pickle.dumps(user_intent))
    response["user_intent"] = user_intent[0]

    logger.info(f"Response complete: {response['pred_sql']}")
    return response


def check_llm_health(host: str, port: int) -> bool:
    try:
        resp = http_requests.get(f"http://{host}:{port}/health", timeout=5)
        return resp.status_code == 200
    except (http_requests.ConnectionError, http_requests.Timeout):
        return False


def start_llm_container(cfg) -> str:
    gpu_ids_str = ",".join(str(g) for g in cfg.gpu_ids)
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "llm_container.log")

    cmd = [
        "docker", "run", "-d",
        "--gpus", f"device={gpu_ids_str}",
        "-p", f"{cfg.port}:{cfg.port}",
        "--env", f"HF_TOKEN={cfg.hf_token}",
        "--ipc=host",
        "--mount", f"type=bind,source={cfg.mount_source},target={cfg.mount_target}",
        cfg.docker_image,
        "python3", "-m", "sglang.launch_server",
        "--model-path", cfg.model_path,
        "--host", "0.0.0.0",
        "--port", str(cfg.port),
        "--tp", str(cfg.tp),
        "--dp", str(cfg.dp),
        "--mem-fraction-static", str(cfg.mem_fraction_static),
    ]
    logger.info(f"Starting LLM container: {' '.join(cmd)}")
    container_id = subprocess.check_output(cmd).decode().strip()
    logger.info(f"LLM container started: {container_id[:12]}")

    # Stream container logs to file in background
    log_fp = open(log_file, "w")
    subprocess.Popen(
        ["docker", "logs", "-f", container_id],
        stdout=log_fp, stderr=log_fp,
    )
    logger.info(f"LLM container logs: {log_file}")
    return container_id


def ensure_llm_server(cfg) -> None:
    if check_llm_health(cfg.host, cfg.port):
        logger.info(f"LLM server already running at {cfg.host}:{cfg.port}")
        return

    logger.info("LLM server not available. Starting container...")
    start_llm_container(cfg)

    timeout = cfg.get("health_check_timeout", 300)
    interval = cfg.get("health_check_interval", 10)
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_llm_health(cfg.host, cfg.port):
            logger.info("LLM server is ready.")
            return
        logger.info(f"Waiting for LLM server at {cfg.host}:{cfg.port}...")
        time.sleep(interval)

    raise TimeoutError(f"LLM server did not become ready within {timeout}s")


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    global translator, intent_inferer, confidence_calculator, table2text_model
    global rd_text2sql, rd_analysis, rd_user_intent, rd_table2text
    global text_history

    text_history = ""

    # Ensure LLM server is running before model initialization
    ensure_llm_server(cfg.remote)

    # Initialize models
    translator = LLMBasedText2SQL(cfg, cfg.text2sql)
    intent_inferer = IntentInferer(cfg, cfg.text2intent)
    confidence_calculator = Text2Confidence(cfg.conversation.text2confidence)
    table2text_model = Table2Text(cfg, cfg.conversation.table2text)

    # Warm up CoreNLP server so the first query isn't slow
    from source.text2sql.ratsql.resources import corenlp
    logger.info("Warming up CoreNLP server...")
    corenlp.annotate("warmup", annotators=["tokenize", "ssplit", "lemma"])
    logger.info("CoreNLP server is ready.")

    # Initialize Redis (4 DBs)
    redis_cfg = cfg.redis
    rd_text2sql = redis.StrictRedis(
        host=redis_cfg.host,
        port=redis_cfg.port,
        db=redis_cfg.api_text2sql_cache_db,
    )
    rd_analysis = redis.StrictRedis(
        host=redis_cfg.host,
        port=redis_cfg.port,
        db=redis_cfg.api_analyze_cache_db,
    )
    rd_user_intent = redis.StrictRedis(
        host=redis_cfg.host,
        port=redis_cfg.port,
        db=redis_cfg.api_user_intent_cache_db,
    )
    rd_table2text = redis.StrictRedis(
        host=redis_cfg.host,
        port=redis_cfg.port,
        db=redis_cfg.api_table2text_cache_db,
    )

    # Flush all Redis DBs on startup
    rd_text2sql.flushdb()
    rd_analysis.flushdb()
    rd_user_intent.flushdb()
    rd_table2text.flushdb()

    # Start server
    logging.basicConfig(
        format="[%(asctime)s %(levelname)s %(name)s] %(message)s",
        datefmt="%m/%d %H:%M:%S",
        level=logging.INFO,
    )
    serve(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    main()
