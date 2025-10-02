import json
import os

import _jsonnet

from source.text2sql.ratsql import datasets
from source.text2sql.ratsql.utils import registry


def filter_examples(inferred_lines, data):
    filtered_examples = []
    inferred_idx = 0
    for idx, item in enumerate(data):
        target_infer = json.loads(inferred_lines[inferred_idx])
        target_line = target_infer["beams"][0]
        if (
            target_line["orig_question"] == item.orig["question"]
            and target_infer["db_id"] == item.orig["db_id"]
        ):
            filtered_examples.append(item)
            inferred_idx += 1
        if inferred_idx == len(inferred_lines):
            break
    assert len(filtered_examples) == len(inferred_lines)
    data.examples = filtered_examples
    return data


def compute_metrics(
    config_path,
    config_args,
    section,
    inferred_path,
    logdir=None,
    use_original_eval=False,
):
    if config_args:
        config = json.loads(
            _jsonnet.evaluate_file(config_path, tla_codes={"args": config_args})
        )
    else:
        config = json.loads(_jsonnet.evaluate_file(config_path))

    if "model_name" in config and logdir:
        logdir = os.path.join(logdir, config["model_name"])
    if logdir:
        inferred_path = inferred_path.replace("__LOGDIR__", logdir)

    inferred = open(inferred_path)
    data = registry.construct("dataset", config["data"][section])
    metrics = data.Metrics(
        data, config["data"][section]["tables_paths"][0], use_original_eval
    )

    inferred_lines = list(inferred)
    if len(inferred_lines) < len(data):
        data = filter_examples(inferred_lines, data)
        # raise Exception(f'Not enough inferred: {len(inferred_lines)} vs {len(data)}')

    for line in inferred_lines:
        infer_results = json.loads(line)
        if infer_results["beams"]:
            inferred_code = infer_results["beams"][0]["inferred_code"]
        else:
            inferred_code = None
        # Get confidence
        confidences = None
        if "confidence" in infer_results["beams"][0]:
            confidences = [tmp["confidence"] for tmp in infer_results["beams"]]
        if "index" in infer_results:
            metrics.add(
                data[infer_results["index"]],
                inferred_code,
                confidences=confidences,
                orig_question=True,
            )
        else:
            metrics.add(
                None,
                inferred_code,
                obsolete_gold_code=infer_results["gold_code"],
                orig_question=True,
            )

    return logdir, metrics.finalize()
