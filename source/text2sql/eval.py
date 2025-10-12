import json
import hydra
import os
from tqdm import tqdm
from omegaconf import DictConfig
from functools import cached_property
from config.path import ABS_CONFIG_DIR
from torch.utils.data import Dataset, DataLoader
from source.text2sql.text_to_sql import Text2SQL, LLMBasedText2SQL
from source.text2sql.spider.evaluation import evaluate, build_foreign_key_map_from_json


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
        kmaps = build_foreign_key_map_from_json(self.cfg.table_path)
        return kmaps

    def __getitem__(self, idx):
        instance = self.eval_dataset[idx]
        question = f"{instance['question']}"
        gold_sql = instance["query"]
        db_id = instance["db_id"]
        return question, gold_sql, db_id


@hydra.main(version_base=None, config_path=ABS_CONFIG_DIR, config_name="config")
def main(cfg: DictConfig) -> None:
    """Main function for testing Text2SQL translation."""
    # Define output file paths
    glist_path = cfg.text2sql.get("glist_output_path", "eval_results/glist.json")
    plist_path = cfg.text2sql.get("plist_output_path", "eval_results/plist.json")
    load_existing = cfg.text2sql.get("load_existing_results", False)

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
        if cfg.text2sql.is_llm:
            translator = LLMBasedText2SQL(cfg, cfg.text2sql)
        else:
            translator = Text2SQL(cfg, cfg.text2sql)

        spider = SpiderDataset(cfg.data)
        eval_dataloader = DataLoader(spider, batch_size=1, shuffle=False)

        glist = []
        plist = []
        for eval_instance in tqdm(eval_dataloader):
            question, gold_sql, db_id = eval_instance
            _, inferred_code = translator.translate(
                question[0],
                "",
                db_id[0],
            )
            glist.append([gold_sql[0], db_id[0]])
            plist.append([inferred_code, db_id[0]])
            print(f"Question: {question[0]}")
            print(f"Gold SQL: {gold_sql[0]}")
            print(f"Predicted SQL: {inferred_code}\n")

        # Save results to JSON files
        print(f"Saving results to {glist_path} and {plist_path}")
        with open(glist_path, "w", encoding="utf-8") as f:
            json.dump(glist, f, indent=2, ensure_ascii=False)
        with open(plist_path, "w", encoding="utf-8") as f:
            json.dump(plist, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(glist)} gold queries and {len(plist)} predicted queries")

    # Convert loaded lists back to tuples for evaluation
    glist_tuples = [(item[0], item[1]) for item in glist]
    plist_tuples = [(item[0], item[1]) for item in plist]

    # Run evaluation
    spider = SpiderDataset(cfg.data)
    evaluate(
        cfg.data.database_path,
        "all",
        spider.kmaps,
        glist=glist_tuples,
        plist=plist_tuples,
    )

    # Print last predicted query as example
    if plist_tuples:
        print(f"\nExample prediction: {plist_tuples[-1][0]}")


if __name__ == "__main__":
    main()
