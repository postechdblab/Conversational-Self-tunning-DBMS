import argparse
import json

from source.text2sql.ratsql.datasets.spider_lib import (
    evaluation_postgres,
    evaluation_spider,
)
from source.text2sql.ratsql.datasets.spider_lib.evaluation_spider import *
from source.text2sql.ratsql.grammars.postgres import POSTGRES_GRAMMAR_IDENTIFIERS
from source.text2sql.ratsql.grammars.spider import SPIDER_GRAMMAR_IDENTIFIERS


def Evaluator(*args, **kwargs):
    grammar = kwargs["grammar"]
    if grammar in SPIDER_GRAMMAR_IDENTIFIERS:
        return evaluation_spider.Evaluator(*args, **kwargs)
    elif grammar in POSTGRES_GRAMMAR_IDENTIFIERS:
        return evaluation_postgres.Evaluator(*args, **kwargs)
    else:
        raise KeyError(f"no such grammar: {grammar}")


def evaluate(gold, predict, db_dir, etype, kmaps, db_type="sqlite", grammar="spider"):
    with open(gold) as f:
        glist = [l.strip().split("\t") for l in f.readlines() if len(l.strip()) > 0]

    with open(predict) as f:
        plist = [l.strip().split("\t") for l in f.readlines() if len(l.strip()) > 0]
    evaluator = Evaluator(db_dir, kmaps, etype, db_type=db_type, grammar=grammar)
    results = []
    for p, g in zip(plist, glist):
        (predicted,) = p
        gold, db_name = g
        results.append(evaluator.evaluate_one(db_name, gold, predicted))
    evaluator.finalize()

    print_scores(evaluator.scores, etype)
    return {
        "per_item": results,
        "total_scores": evaluator.scores,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", dest="gold", type=str)
    parser.add_argument("--pred", dest="pred", type=str)
    parser.add_argument("--db", dest="db", type=str)
    parser.add_argument("--table", dest="table", type=str)
    parser.add_argument("--etype", dest="etype", type=str)
    parser.add_argument("--output")
    parser.add_argument("--db_type", default="sqlite", type=str)
    parser.add_argument("--grammar", default="spider", type=str)
    args = parser.parse_args()

    gold = args.gold
    pred = args.pred
    db_dir = args.db
    table = args.table
    etype = args.etype
    db_type = args.db_type
    grammar = args.grammar

    assert etype in ["all", "exec", "match"], "Unknown evaluation method"

    kmaps = build_foreign_key_map_from_json(table)

    results = evaluate(
        gold, pred, db_dir, etype, kmaps, db_type=db_type, grammar=grammar
    )
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f)
