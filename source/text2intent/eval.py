import json
import hydra
import os
from tqdm import tqdm
from omegaconf import DictConfig
from functools import cached_property
from config.path import ABS_CONFIG_DIR
from torch.utils.data import Dataset, DataLoader
from source.text2intent.intent_inferer import IntentInferer
from source.text2sql.spider.evaluation import evaluate, build_foreign_key_map_from_json
import sqlglot
from sqlglot import exp


def remove_aliases(sql: str) -> str:
    """
    Remove aliases from SELECT expressions and tables in a SQL query.

    Args:
        sql (str): Input SQL query string.

    Returns:
        str: SQL query without aliases.
    """
    # SQL 파싱
    tree = sqlglot.parse_one(sql, dialect="sqlite")

    # SELECT 절의 alias 제거
    for select_expr in tree.find_all(exp.Alias):
        select_expr.replace(select_expr.this.copy())

    # FROM 절 테이블 alias 제거
    for table in tree.find_all(exp.TableAlias):
        parent = table.parent
        # 테이블 alias를 제거하고 원래 테이블로 대체
        if isinstance(parent, exp.Table):
            parent.set("alias", None)

    # 다시 SQL 문자열로 변환
    return tree.sql(dialect="sqlite")


class CoSQLDataset(Dataset):
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
        kmaps = build_foreign_key_map_from_json(self.cfg.table_path)
        return kmaps

    def __getitem__(self, idx):
        instance = self.eval_dataset[idx]
        question = f"{instance['utterance']}"
        intent = instance["intent"]
        db_id = instance["database_id"]
        return question, intent, db_id, ""


DATASET_REGISTRY = {"cosql": CoSQLDataset}


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    """Main function for testing Text2Intent."""
    # Define output file paths
    glist_path = cfg.text2intent.get("glist_output_path", "eval_results/glist.json")
    plist_path = cfg.text2intent.get("plist_output_path", "eval_results/plist.json")
    load_existing = cfg.text2intent.get("load_existing_results", False)

    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(glist_path), exist_ok=True)
    os.makedirs(os.path.dirname(plist_path), exist_ok=True)

    # Check if we should load existing results
    if load_existing and os.path.exists(glist_path) and os.path.exists(plist_path):
        print(f"Loading existing results from {glist_path} and {plist_path}")
        with open(glist_path, "r", encoding="utf-8") as f:
            glist = json.load(f)
        with open(plist_path, "r", encoding="utf-8") as f:
            plist = json.load(f)
        glist = glist[: len(plist)]  # Ensure both lists are of the same length
        print(f"Loaded {len(glist)} gold queries and {len(plist)} predicted queries")
    else:
        # Generate new results
        print("Generating new evaluation results...")
        inferer = IntentInferer(cfg, cfg.text2intent)

        dataset = DATASET_REGISTRY[cfg.data.name](cfg.data)
        eval_dataloader = DataLoader(dataset, batch_size=1, shuffle=False)

        glist = []
        plist = []
        count = 0
        for eval_instance in tqdm(eval_dataloader):
            question, gold_intent, db_id, table_id = eval_instance
            pred_intent = inferer.infer(f"<s> {question[0]} <s>", db_id[0])
            glist.append([gold_intent[0][0].lower(), db_id[0]])
            plist.append([pred_intent[0], db_id[0]])
            print(f"Question: {question[0]}")
            print(f"Gold Intent: {gold_intent[0][0].lower()}")
            print(f"Predicted Intent: {pred_intent[0]}\n")
            count += 1
            if count >= 15:
                break

        # Save results to JSON files
        print(f"Saving results to {glist_path} and {plist_path}")
        with open(glist_path, "w", encoding="utf-8") as f:
            json.dump(glist, f, indent=2, ensure_ascii=False)
        with open(plist_path, "w", encoding="utf-8") as f:
            json.dump(plist, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(glist)} gold queries and {len(plist)} predicted queries")

    # Convert loaded lists back to tuples for evaluation
    exact_math_count = 0
    for gold, pred in zip(glist, plist):
        if gold[0] == pred[0]:
            exact_math_count += 1

    total_count = len(glist)
    accuracy = exact_math_count / total_count if total_count > 0 else 0.0
    print(f"Exact Match Accuracy: {accuracy:.4f} ({exact_math_count}/{total_count})")


if __name__ == "__main__":
    main()
