import json
import logging
import os
import pickle
import random
import threading
from typing import *
import requests
import redis
import torch
from flask import Flask, request
from flask_cors import CORS
from get_model import get_model, nl2intent_inferer
from utils import add_value_one_sql, token_score_to_noun_score
from waitress import serve

from ratsql.models.spider import spider_beam_search
from table2text.model import Table2TextModel

random.seed(0)

file_dir_path = os.path.dirname(os.path.abspath(__file__))  # Intialize config

config_file_path = os.path.join(file_dir_path, "backend_config.json")
with open(config_file_path, "r") as config_file:
    config = json.load(config_file)

# Initialize flask
app = Flask(__name__)
cors = CORS(app)

# Initialize logger
logger = logging.getLogger("FlaskServer")

flush_redis = True

# Initialize redis
rd_text2sql = redis.StrictRedis(
    host=config["server"]["redis"]["host"],
    port=config["server"]["redis"]["port"],
    db=config["server"]["redis"]["api_text2sql_cache_db"],
)

rd_analysis = redis.StrictRedis(
    host=config["server"]["redis"]["host"],
    port=config["server"]["redis"]["port"],
    db=config["server"]["redis"]["api_analyze_cache_db"],
)

rd_user_intent = redis.StrictRedis(
    host=config["server"]["redis"]["host"],
    port=config["server"]["redis"]["port"],
    db=config["server"]["redis"]["api_user_intent_cache_db"],
)

rd_table2text = redis.StrictRedis(
    host=config["server"]["redis"]["host"],
    port=config["server"]["redis"]["port"],
    db=config["server"]["redis"]["api_table2text_cache_db"],
)
if flush_redis:
    rd_text2sql.flushdb()
    rd_analysis.flushdb()
    rd_user_intent.flushdb()
    rd_table2text.flushdb()

# Initialize model
##text-to-sql model
text_to_sql_model, text_to_sql_preprocessor = get_model(
    config, model_type="text_to_sql"
)

##text-to-intent model
text_to_intent_model, _ = get_model(
    config, model_type="text_to_intent", preprocessor=text_to_sql_preprocessor
)

##result analysis model
result_analysis_model, analyser = get_model(config, model_type="result_analysis")

# Initialize text history
text_history = ""

# Locks for thread safety
model_lock = threading.Lock()
history_lock = threading.Lock()


def generate_redis_key(text: str, db_id: str) -> str:
    return text + db_id


@app.route("/")
def Testing():
    logger.info("Hello world?")
    return "<p>Hello, World!</p>"


@app.route("/reset_history")
def reset_history() -> Dict:
    global text_history
    with history_lock:
        text_history = ""
    logger.info("History Reset!")
    return {"response": True}


@app.route("/undo_last")
def undo_last() -> Dict:
    global text_history
    with history_lock:
        if not text_history:
            return {"response": False}
        last_sep_idx = text_history.rfind(" <s> ")
        if last_sep_idx == -1:
            text_history = ""
        else:
            text_history = text_history[:last_sep_idx]
    logger.info(f"Undo last! Remaining history: {text_history}")
    return {"response": True}


@app.route("/table_to_text", methods=["POST"])
def table_to_text() -> Dict:
    logger.info(f"Received table2text request from {request.remote_addr}")
    table: List[Dict] = request.json["rows"]
    print("table", table)
    model = Table2TextModel()
    redis_key = str(table)
    if rd_table2text.exists(redis_key):
        logger.info(f"Returning cached result")
        summary = pickle.loads(rd_table2text.get(redis_key))
    else:
        if len(table) == 0 or not isinstance(table, list):
            summary = "There is no data in the table."
        else:
            summary: str = model.infer(table_in_dict=table)
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

    response_list = requests.post(
        "http://0.0.0.0:5000/predict",
        json={"question": text},
        timeout=None,
    ).json()

    tune_intent = response_list["intent"]

    if tune_intent:
        print("tune_intent: ", tune_intent)
        response = {
            "pred_sql": "conduct tuning",
            "confidence": 100,
            "user_intent": "database_tuning",
        }
        return response

    # Serialize access to shared models and text_history to prevent race conditions
    with model_lock:
        if reset_history:
            text_history = ""

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
            orig_item, preproc_item = text_to_sql_preprocessor.run(input_text, db_id)

            if not text_history.endswith(text):
                text_history += " <s> " + text

            # translate text to sql
            beams = spider_beam_search.beam_search_with_heuristics(
                text_to_sql_model,
                orig_item,
                (preproc_item, None),
                beam_size=config["model"]["text_to_sql"]["beam_size"],
                max_steps=config["model"]["text_to_sql"]["max_steps"],
            )
            confidence = (
                torch.softmax(torch.tensor([tmp.score for tmp in beams]), dim=0)
                .cpu()
                .numpy()[0]
            )
            sql_dict, inferred_code = beams[0].inference_state.finalize()
            # Postprocess: Add missing values to the sql
            inferred_code = add_value_one_sql(
                question=text, db_name=db_id, sql=inferred_code, history=text_history
            )
            # Heuristic: refine confidence
            if (
                "where" in inferred_code.lower()
                and "terminal" not in inferred_code.lower()
                and confidence < 0.7
            ):
                confidence = min(confidence + 0.2, 1.0)

            response["confidence"] = f"{confidence*100:.2f}"
            response["pred_sql"] = inferred_code

            # Save the result to redis
            rd_text2sql.set(redis_key, pickle.dumps(response))

        # analyse the result
        if analyse and float(response["confidence"]) < 80:
            if rd_analysis.exists(redis_key):
                analyze_result = pickle.loads(rd_analysis.get(redis_key))
            else:
                if cache_used:
                    orig_item, preproc_item = text_to_sql_preprocessor.run(
                        input_text, db_id
                    )
                while_cnt = 6
                while while_cnt:
                    try:
                        input_raw, word_attributions = analyser.run(
                            result_analysis_model, input_text, orig_item, preproc_item
                        )
                        print("input raw", input_raw)
                        # Remove history
                        input_text_splitted = input_text.split(" ")
                        indices = [
                            index for index, word in enumerate(input_raw) if word == "s"
                        ]
                        if len(indices) > 1:
                            # Find the index of second s
                            index = indices[1]
                            input_raw = input_raw[: index - 1]
                            word_attributions = word_attributions[: index - 1]
                        print("new input raw", input_raw)
                        noun_words, noun_scores = token_score_to_noun_score(
                            tokens=input_raw[3:], token_scores=word_attributions[3:]
                        )
                        while_cnt = 0

                    except Exception:
                        noun_words = input_text.split(" ")
                        noun_scores = [0.1 for _ in range(len(noun_words))]
                        noun_words, noun_scores = token_score_to_noun_score(
                            tokens=noun_words, token_scores=noun_scores
                        )
                        while_cnt -= 1

                print("Noun words:", noun_words)
                print("Noun scores:", noun_scores)

                # Filter only one noun word with highest score
                if noun_scores:
                    highest_score = max(noun_scores)
                    noun_words = [
                        noun_words[idx]
                        for idx, score in enumerate(noun_scores)
                        if score == highest_score
                    ]
                    noun_scores = [highest_score]
                if len(noun_words) > 0:
                    noun_word = noun_words[0]
                    noun_score = noun_scores[0]
                else:
                    noun_word = ""
                    noun_score = 0.0

                print(noun_word, noun_score)
                analyze_result = {
                    "raw_input": noun_word,
                    "word_attributions": noun_score,
                }

                # Save the result to redis
                rd_analysis.set(redis_key, pickle.dumps(analyze_result))

            response["analyse_result"] = analyze_result

        # guess the user's intent
        input_changed = input_text[len("<s> ") :]
        input_changed = input_changed.replace("<s>", "[CLS]")
        if rd_user_intent.exists(redis_key):
            user_intent = pickle.loads(rd_user_intent.get(redis_key))
        else:
            orig_item, preproc_item = text_to_sql_preprocessor.run(input_changed, db_id)
            user_intent = nl2intent_inferer(text_to_intent_model, preproc_item)
            rd_user_intent.set(redis_key, pickle.dumps(user_intent))
        response["user_intent"] = user_intent[0]

    logger.info(f"Response complete: {response['pred_sql']}")
    return response


if __name__ == "__main__":
    logging.basicConfig(
        format="[%(asctime)s %(levelname)s %(name)s] %(message)s",
        datefmt="%m/%d %H:%M:%S",
        level=logging.INFO,
    )
    serve(app, host=config["server"]["host"], port=config["server"]["port"])
