import pickle
import random
import logging
from typing import *

import hydra
from config.path import ABS_CONFIG_DIR
from omegaconf import DictConfig, OmegaConf
import redis
from flask import Flask, request
from flask_cors import CORS
from waitress import serve
from source.text2sql.text_to_sql import Text2SQL
from source.text2intent.intent_inferer import IntentInferer
from source.conversation.text2confidence.text_to_confidence import Text2Confidence
from source.conversation.table2text.table_to_text import Table2Text


random.seed(0)

# Global variables
config: DictConfig = None

# Initialize flask
app = Flask(__name__)
cors = CORS(app)

# Initialize logger
logger = logging.getLogger("FlaskServer")

# These will be initialized in main()
rd_text2sql = None
rd_analysis = None
rd_user_intent = None
rd_table2text = None
text_to_sql_model = None
text_to_intent_model = None
text_to_confidence_model = None
table_to_text_model = None
result_analysis_model = None
analyser = None
text_history = ""


def generate_redis_key(text: str, db_id: str) -> str:
    return text + db_id


@app.route("/")
def Testing():
    logger.info("Hello world?")
    return "<p>Hello, World!</p>"


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
        logger.info(f"Returning cached result")
        summary = pickle.loads(rd_table2text.get(redis_key))
    else:
        if len(table) == 0 or not isinstance(table, list):
            summary = "There is no data in the table."
        else:
            summary: str = table_to_text_model.generate(table)
        # Save into redis cache
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
    reset_history: bool = params["reset_history"]
    logger.info(
        f"DB_id: {db_id}, analyse: {analyse}, text: {text} reset_history: {reset_history} text_history: {text_history}"
    )
    if reset_history:
        text_history = ""

    tune_intent = text_to_intent_model.infer(text, db_id, is_tune_check=True)[0]

    if tune_intent:
        print("tune_intent: ", tune_intent)
        response = {
            "pred_sql": "conduct tuning",
            "confidence": 100,
            "user_intent": "database_tuning",
        }
        return response

    input_text = "<s> " + text + text_history

    # check and return cached result
    redis_key = generate_redis_key(text=input_text, db_id=db_id)
    cache_used = False
    if rd_text2sql.exists(redis_key):
        logger.info(f"Returning cached result")
        response = pickle.loads(rd_text2sql.get(redis_key))
        cache_used = True
        if not text_history.endswith(text):
            text_history += " <s> " + text
    else:
        orig_item, preproc_item = text_to_sql_model.preprocess(
            text,
            text_history,
            db_id,
        )

        if not text_history.endswith(text):
            text_history += " <s> " + text

        # translate text to sql

        beams, inferred_code = text_to_sql_model.translate(text, text_history, db_id)
        confidence = text_to_confidence_model.calculate(beams, inferred_code)

        response["confidence"] = f"{confidence:.2f}"
        response["pred_sql"] = inferred_code

        # Save the result to redis
        rd_text2sql.set(redis_key, pickle.dumps(response))

    # analyse the result
    if analyse and float(response["confidence"]) < 80:
        if rd_analysis.exists(redis_key):
            analyze_result = pickle.loads(rd_analysis.get(redis_key))
        else:
            if cache_used:
                orig_item, preproc_item = text_to_sql_model.preprocess(
                    text,
                    text_history,
                    db_id,
                )
            analyze_result = text_to_confidence_model.analyze(
                input_text, orig_item, preproc_item
            )

            # Save the result to redis
            rd_analysis.set(redis_key, pickle.dumps(analyze_result))

        response["analyse_result"] = analyze_result

    # guess the user's intent
    input_changed = input_text[len("<s> ") :]
    input_changed = input_changed.replace("<s>", "[CLS]")
    if rd_user_intent.exists(redis_key):
        user_intent = pickle.loads(rd_user_intent.get(redis_key))
    else:
        user_intent = text_to_intent_model.infer(input_text, db_id)
        rd_user_intent.set(redis_key, pickle.dumps(user_intent))
    response["user_intent"] = user_intent[0]
    logger.info(f"Response complete: {response['pred_sql']}")
    return response


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    """Main entry point using Hydra for configuration management"""
    global config, rd_text2sql, rd_analysis, rd_user_intent, rd_table2text
    global text_to_sql_model, text_to_intent_model, text_to_confidence_model, table_to_text_model
    global result_analysis_model, analyser

    config = cfg

    # Setup logging
    logging.basicConfig(
        format="[%(asctime)s %(levelname)s %(name)s] %(message)s",
        datefmt="%m/%d %H:%M:%S",
        level=logging.INFO,
    )

    logger.info("Initializing backend server with Hydra configuration...")
    logger.info(f"Configuration:\n{OmegaConf.to_yaml(cfg)}")

    # Initialize redis
    rd_text2sql = redis.StrictRedis(
        host=config.redis.host,
        port=config.redis.port,
        db=config.redis.api_text2sql_cache_db,
    )

    rd_analysis = redis.StrictRedis(
        host=config.redis.host,
        port=config.redis.port,
        db=config.redis.api_analyze_cache_db,
    )

    rd_user_intent = redis.StrictRedis(
        host=config.redis.host,
        port=config.redis.port,
        db=config.redis.api_user_intent_cache_db,
    )

    rd_table2text = redis.StrictRedis(
        host=config.redis.host,
        port=config.redis.port,
        db=config.redis.api_table2text_cache_db,
    )

    if config.redis.is_flush:
        logger.info("Flushing Redis databases...")
        rd_text2sql.flushdb()
        rd_analysis.flushdb()
        rd_user_intent.flushdb()
        rd_table2text.flushdb()

    # Initialize models
    logger.info("Loading text-to-sql model...")
    text_to_sql_model = Text2SQL(config, config.text2sql)

    logger.info("Loading text-to-intent model...")
    text_to_intent_model = IntentInferer(config, config.text2intent)

    logger.info("Loading result analysis model...")
    text_to_confidence_model = Text2Confidence(config.conversation.text2confidence)

    logger.info("Loading table-to-text model...")
    table_to_text_model = Table2Text(config.conversation.table2text)

    logger.info(f"Starting server on {config.host}:{config.port}")
    serve(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
