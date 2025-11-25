import json
import hydra
import os
import numpy as np
from tqdm import tqdm
from omegaconf import DictConfig
from functools import cached_property
from config.path import ABS_CONFIG_DIR
from torch.utils.data import Dataset, DataLoader
from source.text2sql.text_to_sql import Text2SQL
from source.conversation.text2confidence.text_to_confidence import Text2Confidence
from source.text2sql.spider.evaluation import evaluate, build_foreign_key_map_from_json
import sqlglot
from sqlglot import exp


def remove_aliases(sql: str) -> str:
    """
    Remove aliases from SELECT expressions and tables in a SQL query.
    """
    tree = sqlglot.parse_one(sql, dialect="sqlite")

    # SELECT 절의 alias 제거
    for select_expr in tree.find_all(exp.Alias):
        select_expr.replace(select_expr.this.copy())

    # FROM 절 테이블 alias 제거
    for table in tree.find_all(exp.TableAlias):
        parent = table.parent
        if isinstance(parent, exp.Table):
            parent.set("alias", None)

    return tree.sql(dialect="sqlite")


class SpiderDataset(Dataset):
    def __init__(self, cfg):
        self.cfg = cfg

    def __len__(self):
        return len(self.eval_dataset)

    @cached_property
    def eval_dataset(self):
        with open(self.cfg.eval_data_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)
        return dataset

    @cached_property
    def kmaps(self):
        return build_foreign_key_map_from_json(self.cfg.table_path)

    def __getitem__(self, idx):
        instance = self.eval_dataset[idx]
        question = instance["question"]
        gold_sql = instance["query"]
        db_id = instance["db_id"]
        return question, gold_sql, db_id, ""


class WikiDataset(Dataset):
    def __init__(self, cfg):
        self.cfg = cfg

    def __len__(self):
        return len(self.eval_dataset)

    @cached_property
    def eval_dataset(self):
        with open(self.cfg.eval_data_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)
        return dataset

    @cached_property
    def kmaps(self):
        return build_foreign_key_map_from_json(self.cfg.table_path)

    def __getitem__(self, idx):
        instance = self.eval_dataset[idx]
        question = instance["question"]
        gold_sql = instance["query"]
        db_id = instance["db_id"]
        table_id = instance.get("table_id", [])
        return question, gold_sql, db_id, table_id


DATASET_REGISTRY = {"wikisql": WikiDataset, "spider": SpiderDataset}


def evaluate_by_confidence_bins(
    database_path, kmaps, glist, plist, confidences, output_json_path
):
    """
    Evaluate SQL prediction accuracy by confidence bins (0–10%, 10–20%, …, 90–100%).
    """
    assert len(glist) == len(plist) == len(confidences), "List lengths must match."

    bin_edges = np.linspace(0, 100, 11)
    bin_labels = [
        f"{int(b)}-{int(bin_edges[i + 1])}" for i, b in enumerate(bin_edges[:-1])
    ]

    bin_results = {}

    for i in range(len(bin_edges) - 1):
        bin_lower, bin_upper = bin_edges[i], bin_edges[i + 1]
        bin_label = bin_labels[i]

        # 현재 구간에 해당하는 질의 선택
        bin_indices = [
            idx
            for idx, c in enumerate(confidences)
            if bin_lower <= c < bin_upper or (bin_upper == 1.0 and c == 1.0)
        ]

        if not bin_indices:
            print(f"Skipping empty bin {bin_label}")
            continue

        glist_bin = [glist[idx] for idx in bin_indices]
        plist_bin = [plist[idx] for idx in bin_indices]

        print(f"Evaluating confidence bin {bin_label} with {len(glist_bin)} samples...")

        scores = evaluate(
            database_path,
            "all",
            kmaps,
            glist=glist_bin,
            plist=plist_bin,
        )

        bin_results[bin_label] = {
            "exact": scores["all"]["exact"],
            "exec": scores["all"]["exec"],
            "avg_conf": float(np.mean([confidences[idx] for idx in bin_indices])),
            "count": len(glist_bin),
        }

    # JSON 저장
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(bin_results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Bin-wise evaluation results saved to: {output_json_path}")
    return bin_results


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    """Main function for testing Text2SQL translation."""
    glist_path = cfg.conversation.text2confidence.get(
        "glist_output_path", "eval_results/glist.json"
    )
    plist_path = cfg.conversation.text2confidence.get(
        "plist_output_path", "eval_results/plist.json"
    )
    conf_path = cfg.conversation.text2confidence.get(
        "confidence_output_path", "eval_results/confidence.json"
    )
    bin_eval_path = cfg.conversation.text2confidence.get(
        "bin_eval_output_path", "eval_results/confidence_bin_eval.json"
    )
    load_existing = cfg.conversation.text2confidence.get("load_existing_results", False)

    os.makedirs(os.path.dirname(glist_path), exist_ok=True)
    os.makedirs(os.path.dirname(plist_path), exist_ok=True)

    if (
        load_existing
        and os.path.exists(glist_path)
        and os.path.exists(plist_path)
        and os.path.exists(conf_path)
    ):
        print(f"Loading existing results from {glist_path}, {plist_path}, {conf_path}")
        with open(glist_path, "r", encoding="utf-8") as f:
            glist = json.load(f)
        with open(plist_path, "r", encoding="utf-8") as f:
            plist = json.load(f)
        with open(conf_path, "r", encoding="utf-8") as f:
            confidences = json.load(f)
    else:
        print("Generating new evaluation results...")
        translator = Text2SQL(cfg, cfg.text2sql)
        calculator = Text2Confidence(cfg.conversation.text2confidence)
        dataset = DATASET_REGISTRY[cfg.data.name](cfg.data)
        eval_dataloader = DataLoader(dataset, batch_size=1, shuffle=False)

        count = 0
        glist, plist, confidences = [], [], []
        for eval_instance in tqdm(eval_dataloader):
            question, gold_sql, db_id, table_id = eval_instance
            beams, inferred_code = translator.translate(
                question[0],
                "",
                db_id[0],
                table_id=[table_id[0]] if table_id[0] else [],
            )

            conf = calculator.calculate(beams, inferred_code)
            confidences.append(conf)

            try:
                inferred_code = remove_aliases(
                    inferred_code.lower().replace("distinct", "")
                )
            except Exception as e:
                print(f"Error removing aliases: {e}")
                inferred_code = inferred_code.lower().replace("distinct", "")

            glist.append([gold_sql[0], db_id[0]])
            plist.append([inferred_code, db_id[0]])

            print(f"Question: {question[0]}")
            print(f"Gold SQL: {gold_sql[0]}")
            print(f"Predicted SQL: {inferred_code}")
            print(f"Confidence: {conf:.4f}\n")
            count += 1
            if count % 1000 == 0:
                print(f"Processed {count} examples...")
                print(f"Saving results to {glist_path}, {plist_path}, and {conf_path}")
                with open(glist_path, "w", encoding="utf-8") as f:
                    json.dump(glist, f, indent=2, ensure_ascii=False)
                with open(plist_path, "w", encoding="utf-8") as f:
                    json.dump(plist, f, indent=2, ensure_ascii=False)
                with open(conf_path, "w", encoding="utf-8") as f:
                    json.dump(confidences, f, indent=2, ensure_ascii=False)

        print(f"Saving results to {glist_path}, {plist_path}, and {conf_path}")
        with open(glist_path, "w", encoding="utf-8") as f:
            json.dump(glist, f, indent=2, ensure_ascii=False)
        with open(plist_path, "w", encoding="utf-8") as f:
            json.dump(plist, f, indent=2, ensure_ascii=False)
        with open(conf_path, "w", encoding="utf-8") as f:
            json.dump(confidences, f, indent=2, ensure_ascii=False)

    # 튜플 변환
    glist_tuples = [(item[0], item[1]) for item in glist]
    plist_tuples = [(item[0], item[1]) for item in plist]

    # 전체 평가
    dataset = DATASET_REGISTRY[cfg.data.name](cfg.data)
    scores = evaluate(
        cfg.data.database_path,
        "all",
        dataset.kmaps,
        glist=glist_tuples,
        plist=plist_tuples,
    )

    print("\nOverall Evaluation Results:")
    print(json.dumps(scores, indent=2, ensure_ascii=False))

    # confidence bin별 평가
    evaluate_by_confidence_bins(
        cfg.data.database_path,
        dataset.kmaps,
        glist_tuples,
        plist_tuples,
        confidences,
        output_json_path=bin_eval_path,
    )

    if plist_tuples:
        print(f"\nExample prediction: {plist_tuples[-1][0]}")


if __name__ == "__main__":
    main()
