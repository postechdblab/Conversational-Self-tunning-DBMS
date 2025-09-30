################################
# val: number(float)/string(str)/sql(dict)
# col_unit: (agg_id, col_id, isDistinct(bool))
# val_unit: (unit_op, col_unit1, col_unit2)
# table_unit: (table_type, col_unit/sql)
# cond_unit: (not_op, op_id, val_unit, val1, val2)
# condition: [cond_unit1, 'and'/'or', cond_unit2, ...]
# sql {
#   'select': (isDistinct(bool), [(agg_id, val_unit), (agg_id, val_unit), ...])
#   'from': {'table_units': [table_unit1, table_unit2, ...], 'conds': condition}
#   'where': condition
#   'groupBy': [col_unit1, col_unit2, ...]
#   'orderBy': ('asc'/'desc', [val_unit1, val_unit2, ...])
#   'having': condition
#   'limit': None/limit value
#   'intersect': None/sql
#   'except': None/sql
#   'union': None/sql
# }
################################

import argparse
import json
import os
import sqlite3
import copy


from source.text2sql.ratsql.datasets.spider_lib.process_sql import (
    get_schema,
    Schema,
    get_sql,
)
from source.text2sql.ratsql.datasets.utils import db_utils

# Flag to disable value evaluation
DISABLE_VALUE = True
# Flag to disable distinct in select evaluation
DISABLE_DISTINCT = True

CLAUSE_KEYWORDS = (
    "select",
    "from",
    "where",
    "group",
    "order",
    "limit",
    "intersect",
    "union",
    "except",
)
JOIN_KEYWORDS = ("join", "on", "as")

WHERE_OPS = (
    "not",
    "between",
    "=",
    ">",
    "<",
    ">=",
    "<=",
    "!=",
    "in",
    "like",
    "is",
    "exists",
)
UNIT_OPS = ("none", "-", "+", "*", "/")
AGG_OPS = ("none", "max", "min", "count", "sum", "avg")
TABLE_TYPE = {
    "sql": "sql",
    "table_unit": "table_unit",
}

COND_OPS = ("and", "or")
SQL_OPS = ("intersect", "union", "except")
ORDER_OPS = ("desc", "asc")

HARDNESS = {
    "component1": ("where", "group", "order", "limit", "join", "or", "like"),
    "component2": ("except", "union", "intersect"),
}

LEVELS = ["easy", "medium", "hard", "extra", "all"]
PARTIAL_TYPES = [
    "select",
    "select(no AGG)",
    "table",
    "join_condition",
    "where",
    "where(no OP)",
    "group(no Having)",
    "group",
    "order",
    "and/or",
    "IUEN",
    "keywords",
]


def condition_has_or(conds):
    return "or" in conds[1::2]


def condition_has_like(conds):
    return WHERE_OPS.index("like") in [cond_unit[1] for cond_unit in conds[::2]]


def condition_has_sql(conds):
    for cond_unit in conds[::2]:
        val1, val2 = cond_unit[3], cond_unit[4]
        if val1 is not None and type(val1) is dict:
            return True
        if val2 is not None and type(val2) is dict:
            return True
    return False


def val_has_op(val_unit):
    return val_unit[0] != UNIT_OPS.index("none")


def has_agg(unit):
    return unit[0] != AGG_OPS.index("none")


def accuracy(count, total):
    if count == total:
        return 1
    return 0


def recall(count, total):
    if count == total:
        return 1
    return 0


def F1(acc, rec):
    if (acc + rec) == 0:
        return 0
    return (2.0 * acc * rec) / (acc + rec)


def get_scores(count, pred_total, label_total):
    if pred_total != label_total:
        return 0, 0, 0
    elif count == pred_total:
        return 1, 1, 1
    return 0, 0, 0


def eval_sel(pred, label):
    pred_sel = copy.deepcopy(pred["select"][1])
    label_sel = copy.deepcopy(label["select"][1])
    label_wo_agg = [unit[1] for unit in label_sel]
    pred_total = len(pred_sel)
    label_total = len(label_sel)
    cnt = 0
    cnt_wo_agg = 0

    for unit in pred_sel:
        if unit in label_sel:
            cnt += 1
            label_sel.remove(unit)
        if unit[1] in label_wo_agg:
            cnt_wo_agg += 1
            label_wo_agg.remove(unit[1])

    return label_total, pred_total, cnt, cnt_wo_agg


def eval_table(pred, label):
    pred_from = copy.deepcopy(pred["from"]["table_units"])
    label_from = copy.deepcopy(label["from"]["table_units"])
    pred_total = len(pred_from)
    label_total = len(label_from)
    cnt = 0

    for unit in pred_from:
        if unit in label_from:
            cnt += 1
            label_from.remove(unit)

    return label_total, pred_total, cnt


def eval_join_condition(pred, label):
    # Check if the same
    pred_join_conds = copy.deepcopy(pred["from"]["conds"])
    label_join_conds = copy.deepcopy(label["from"]["conds"])

    cnt = 0
    pred_total = len(pred_join_conds)
    label_total = len(label_join_conds)
    for unit in pred_join_conds:
        if unit in label_join_conds:
            cnt += 1
            label_join_conds.remove(unit)

    return label_total, pred_total, cnt


def eval_where(pred, label):
    pred_conds = copy.deepcopy([unit for unit in pred["where"][::2]])
    label_conds = copy.deepcopy([unit for unit in label["where"][::2]])
    label_wo_agg = copy.deepcopy([unit[2] for unit in label_conds])
    pred_total = len(pred_conds)
    label_total = len(label_conds)
    cnt = 0
    cnt_wo_agg = 0

    for unit in pred_conds:
        if unit in label_conds:
            cnt += 1
            label_conds.remove(unit)
        if unit[2] in label_wo_agg:
            cnt_wo_agg += 1
            label_wo_agg.remove(unit[2])

    return label_total, pred_total, cnt, cnt_wo_agg


def eval_group(pred, label):
    pred_cols = copy.deepcopy([unit[1] for unit in pred["groupBy"]])
    label_cols = copy.deepcopy([unit[1] for unit in label["groupBy"]])
    pred_total = len(pred_cols)
    label_total = len(label_cols)
    cnt = 0
    pred_cols = [pred.split(".")[1] if "." in pred else pred for pred in pred_cols]
    label_cols = [
        label.split(".")[1] if "." in label else label for label in label_cols
    ]
    for col in pred_cols:
        if col in label_cols:
            cnt += 1
            label_cols.remove(col)
    return label_total, pred_total, cnt


def eval_having(pred, label):
    pred_total = label_total = cnt = 0
    if len(pred["groupBy"]) > 0:
        pred_total = 1
    if len(label["groupBy"]) > 0:
        label_total = 1

    pred_cols = [unit[1] for unit in pred["groupBy"]]
    label_cols = [unit[1] for unit in label["groupBy"]]
    if (
        pred_total == label_total == 1
        and pred_cols == label_cols
        and pred["having"] == label["having"]
    ):
        cnt = 1

    return label_total, pred_total, cnt


def eval_order(pred, label):
    pred_total = label_total = cnt = 0
    if len(pred["orderBy"]) > 0:
        pred_total = 1
    if len(label["orderBy"]) > 0:
        label_total = 1
    if (
        len(label["orderBy"]) > 0
        and pred["orderBy"] == label["orderBy"]
        and (
            (pred["limit"] is None and label["limit"] is None)
            or (pred["limit"] is not None and label["limit"] is not None)
        )
    ):
        cnt = 1
    return label_total, pred_total, cnt


def eval_and_or(pred, label):
    pred_ao = pred["where"][1::2]
    label_ao = label["where"][1::2]
    pred_ao = set(pred_ao)
    label_ao = set(label_ao)

    if pred_ao == label_ao:
        return 1, 1, 1
    return len(pred_ao), len(label_ao), 0


def get_nestedSQL(sql):
    nested = []
    for cond_unit in sql["from"]["conds"][::2] + sql["where"][::2] + sql["having"][::2]:
        if type(cond_unit[3]) is dict:
            nested.append(cond_unit[3])
        if type(cond_unit[4]) is dict:
            nested.append(cond_unit[4])
    if sql["intersect"] is not None:
        nested.append(sql["intersect"])
    if sql["except"] is not None:
        nested.append(sql["except"])
    if sql["union"] is not None:
        nested.append(sql["union"])
    return nested


def eval_nested(pred, label):
    label_total = 0
    pred_total = 0
    cnt = 0
    if pred is not None:
        pred_total += 1
    if label is not None:
        label_total += 1
    if pred is not None and label is not None:
        partial_scores = Evaluator.eval_partial_match(pred, label)
        cnt += Evaluator.eval_exact_match(pred, label, partial_scores)
    return label_total, pred_total, cnt


def eval_IUEN(pred, label):
    lt1, pt1, cnt1 = eval_nested(pred["intersect"], label["intersect"])
    lt2, pt2, cnt2 = eval_nested(pred["except"], label["except"])
    lt3, pt3, cnt3 = eval_nested(pred["union"], label["union"])
    label_total = lt1 + lt2 + lt3
    pred_total = pt1 + pt2 + pt3
    cnt = cnt1 + cnt2 + cnt3
    return label_total, pred_total, cnt


def get_keywords(sql):
    res = set()
    if len(sql["where"]) > 0:
        res.add("where")
    if len(sql["groupBy"]) > 0:
        res.add("group")
    if len(sql["having"]) > 0:
        res.add("having")
    if len(sql["orderBy"]) > 0:
        res.add(sql["orderBy"][0])
        res.add("order")
    if sql["limit"] is not None:
        res.add("limit")
    if sql["except"] is not None:
        res.add("except")
    if sql["union"] is not None:
        res.add("union")
    if sql["intersect"] is not None:
        res.add("intersect")

    # or keyword
    # ao = sql['from']['conds'][1::2] + sql['where'][1::2] + sql['having'][1::2]
    ao = sql["where"][1::2] + sql["having"][1::2]
    if len([token for token in ao if token == "or"]) > 0:
        res.add("or")

    # cond_units = sql['from']['conds'][::2] + sql['where'][::2] + sql['having'][::2]
    cond_units = sql["where"][::2] + sql["having"][::2]
    # not keyword
    if len([cond_unit for cond_unit in cond_units if cond_unit[0]]) > 0:
        res.add("not")

    # in keyword
    if (
        len(
            [
                cond_unit
                for cond_unit in cond_units
                if cond_unit[1] == WHERE_OPS.index("in")
            ]
        )
        > 0
    ):
        res.add("in")

    # like keyword
    if (
        len(
            [
                cond_unit
                for cond_unit in cond_units
                if cond_unit[1] == WHERE_OPS.index("like")
            ]
        )
        > 0
    ):
        res.add("like")

    return res


def eval_keywords(pred, label):
    pred_keywords = get_keywords(pred)
    label_keywords = get_keywords(label)
    pred_total = len(pred_keywords)
    label_total = len(label_keywords)
    cnt = 0

    for k in pred_keywords:
        if k in label_keywords:
            cnt += 1
    return label_total, pred_total, cnt


def count_agg(units):
    return len([unit for unit in units if has_agg(unit)])


def count_component1(sql):
    count = 0
    if len(sql["where"]) > 0:
        count += 1
    if len(sql["groupBy"]) > 0:
        count += 1
    if len(sql["orderBy"]) > 0:
        count += 1
    if sql["limit"] is not None:
        count += 1
    if len(sql["from"]["table_units"]) > 0:  # JOIN
        count += len(sql["from"]["table_units"]) - 1

    ao = sql["from"]["conds"][1::2] + sql["where"][1::2] + sql["having"][1::2]
    count += len([token for token in ao if token == "or"])
    cond_units = sql["from"]["conds"][::2] + sql["where"][::2] + sql["having"][::2]
    count += len(
        [
            cond_unit
            for cond_unit in cond_units
            if cond_unit[1] == WHERE_OPS.index("like")
        ]
    )

    return count


def count_component2(sql):
    nested = get_nestedSQL(sql)
    return len(nested)


def count_others(sql):
    count = 0
    # number of aggregation
    agg_count = count_agg(sql["select"][1])
    agg_count += count_agg(sql["where"][::2])
    agg_count += count_agg(sql["groupBy"])
    if len(sql["orderBy"]) > 0:
        agg_count += count_agg(
            [unit[1] for unit in sql["orderBy"][1] if unit[1]]
            + [unit[2] for unit in sql["orderBy"][1] if unit[2]]
        )
    agg_count += count_agg(sql["having"])
    if agg_count > 1:
        count += 1

    # number of select columns
    if len(sql["select"][1]) > 1:
        count += 1

    # number of where conditions
    if len(sql["where"]) > 1:
        count += 1

    # number of group by clauses
    if len(sql["groupBy"]) > 1:
        count += 1

    return count


class Evaluator:
    """A simple evaluator"""

    def __init__(
        self, db_dir, kmaps, tables, etype, db_type="sqlite", grammar="spider"
    ):
        self.db_dir = db_dir
        self.kmaps = kmaps
        self.tables = tables
        self.etype = etype
        self.db_type = db_type
        self.grammar = grammar

        self.db_paths = {}
        self.schemas = {}
        for db_name in self.kmaps.keys():
            db_conn_str = db_utils.create_db_conn_str(
                db_dir, db_name, db_type=self.db_type
            )
            self.db_paths[db_name] = db_conn_str
            self.schemas[db_name] = Schema(
                get_schema(db_conn_str, db_type=self.db_type)
            )

        self.scores = {
            level: {
                "count": 0,
                "partial": {
                    type_: {
                        "acc": 0.0,
                        "rec": 0.0,
                        "f1": 0.0,
                        "acc_count": 0,
                        "rec_count": 0,
                    }
                    for type_ in PARTIAL_TYPES
                },
                "exact": 0.0,
                "exec": 0,
            }
            for level in LEVELS
        }
        self.primary_keys = {
            db["db_id"]: self._parse_primary_keys(db) for db in self.tables
        }
        # Reverse the kmap
        self.kmaps = self._reverse_kmap()

    def _reverse_kmap(self):
        kmaps = {}
        for db_id, map in self.kmaps.items():
            # Reverse
            new_map = {}
            for source, target in map.items():
                if source == target:
                    continue
                if source in self.primary_keys[db_id]:
                    if source in new_map:
                        new_map[source] += [target]
                    else:
                        new_map[source] = [target]
                elif target in self.primary_keys[db_id]:
                    if target in new_map:
                        new_map[target] += [source]
                    else:
                        new_map[target] = [source]
                else:
                    pass
                    # print(f"Skipping {db_id}: {source}->{target}")
            kmaps[db_id] = new_map
        return kmaps

    def _parse_primary_keys(self, db):
        primary_keys = []
        for primary_key_id in db["primary_keys"]:
            table_id, column_name = db["column_names_original"][primary_key_id]
            table_name = db["table_names_original"][table_id]
            name = "__{}.{}__".format(table_name.lower(), column_name.lower())
            primary_keys.append(name)
        return primary_keys

    def eval_hardness(self, sql):
        count_comp1_ = count_component1(sql)
        count_comp2_ = count_component2(sql)
        count_others_ = count_others(sql)

        if count_comp1_ <= 1 and count_others_ == 0 and count_comp2_ == 0:
            return "easy"
        elif (count_others_ <= 2 and count_comp1_ <= 1 and count_comp2_ == 0) or (
            count_comp1_ <= 2 and count_others_ < 2 and count_comp2_ == 0
        ):
            return "medium"
        elif (
            (count_others_ > 2 and count_comp1_ <= 2 and count_comp2_ == 0)
            or (2 < count_comp1_ <= 3 and count_others_ <= 2 and count_comp2_ == 0)
            or (count_comp1_ <= 1 and count_others_ == 0 and count_comp2_ <= 1)
        ):
            return "hard"
        else:
            return "extra"

    @classmethod
    def eval_exact_match(cls, pred, label, partial_scores):
        for _, score in list(partial_scores.items()):
            if score["f1"] != 1:
                return 0
        if len(label["from"]["table_units"]) > 0:
            label_tables = sorted(label["from"]["table_units"])
            pred_tables = sorted(pred["from"]["table_units"])
            return label_tables == pred_tables
        return 1

    @classmethod
    def eval_partial_match(cls, pred, label):
        res = {}

        label_total, pred_total, cnt, cnt_wo_agg = eval_sel(pred, label)
        acc, rec, f1 = get_scores(cnt, pred_total, label_total)
        res["select"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }
        acc, rec, f1 = get_scores(cnt_wo_agg, pred_total, label_total)
        res["select(no AGG)"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }

        label_total, pred_total, cnt = eval_table(pred, label)
        acc, rec, f1 = get_scores(cnt, pred_total, label_total)
        res["table"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }

        label_total, pred_total, cnt = eval_join_condition(pred, label)
        acc, rec, f1 = get_scores(cnt, pred_total, label_total)
        res["join_condition"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }

        label_total, pred_total, cnt, cnt_wo_agg = eval_where(pred, label)
        acc, rec, f1 = get_scores(cnt, pred_total, label_total)
        res["where"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }
        acc, rec, f1 = get_scores(cnt_wo_agg, pred_total, label_total)
        res["where(no OP)"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }

        label_total, pred_total, cnt = eval_group(pred, label)
        acc, rec, f1 = get_scores(cnt, pred_total, label_total)
        res["group(no Having)"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }

        label_total, pred_total, cnt = eval_having(pred, label)
        acc, rec, f1 = get_scores(cnt, pred_total, label_total)
        res["group"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }

        label_total, pred_total, cnt = eval_order(pred, label)
        acc, rec, f1 = get_scores(cnt, pred_total, label_total)
        res["order"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }

        label_total, pred_total, cnt = eval_and_or(pred, label)
        acc, rec, f1 = get_scores(cnt, pred_total, label_total)
        res["and/or"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }

        label_total, pred_total, cnt = eval_IUEN(pred, label)
        acc, rec, f1 = get_scores(cnt, pred_total, label_total)
        res["IUEN"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }

        label_total, pred_total, cnt = eval_keywords(pred, label)
        acc, rec, f1 = get_scores(cnt, pred_total, label_total)
        res["keywords"] = {
            "acc": acc,
            "rec": rec,
            "f1": f1,
            "label_total": label_total,
            "pred_total": pred_total,
        }

        return res

    def evaluate_one(self, db_name, gold, predicted):
        def parse_primary_foreign_relations(kmap):
            # Create primary - foreign mapping
            foreign_maps = []
            for key, values in kmap.items():
                for value in values:
                    foreign_maps.append(set([key, value]))
            return foreign_maps

        schema = self.schemas[db_name]
        g_sql = get_sql(schema, gold, grammar=self.grammar)
        hardness = self.eval_hardness(g_sql)
        self.scores[hardness]["count"] += 1
        self.scores["all"]["count"] += 1

        parse_error = False
        try:
            # HACK: need to handle "table name with period" in column name more robustly
            predicted = predicted.replace("master.", "").replace("quality.", "")
            p_sql = get_sql(schema, predicted, grammar=self.grammar)
        except:
            # If p_sql is not valid, then we will use an empty sql to evaluate with the correct sql
            p_sql = {
                "except": None,
                "from": {"conds": [], "table_units": []},
                "groupBy": [],
                "having": [],
                "intersect": None,
                "limit": None,
                "orderBy": [],
                "select": [False, []],
                "union": None,
                "where": [],
            }

            # TODO fix
            parse_error = True

        kmap = self.kmaps[db_name]
        # rebuild sql for value evaluation and column evaluation
        # g_sql = rebuild_sql_val(g_sql)
        g_sql = rebuild_sql_col(schema, g_sql, kmap)
        # p_sql = rebuild_sql_val(p_sql)
        p_sql = rebuild_sql_col(schema, p_sql, kmap)
        # rebuild sql for correct table & join condition evaulation
        from_clause_semantic_equivalence = True
        if from_clause_semantic_equivalence:
            # Create primary - foreign mapping
            foreign_maps = parse_primary_foreign_relations(kmap)
            p_sql = modify_from_clause(p_sql, self.primary_keys[db_name], foreign_maps)
            g_sql = modify_from_clause(g_sql, self.primary_keys[db_name], foreign_maps)

        if self.etype in ["all", "exec"]:
            self.scores[hardness]["exec"] += eval_exec_match(
                self.db_paths[db_name],
                predicted,
                gold,
                p_sql,
                g_sql,
                db_type=self.db_type,
            )

        if self.etype in ["all", "match"]:
            partial_scores = self.eval_partial_match(p_sql, g_sql)
            exact_score = self.eval_exact_match(p_sql, g_sql, partial_scores)
            self.scores[hardness]["exact"] += exact_score
            self.scores["all"]["exact"] += exact_score
            for type_ in PARTIAL_TYPES:
                if partial_scores[type_]["pred_total"] > 0:
                    self.scores[hardness]["partial"][type_]["acc"] += partial_scores[
                        type_
                    ]["acc"]
                    self.scores[hardness]["partial"][type_]["acc_count"] += 1
                if partial_scores[type_]["label_total"] > 0:
                    self.scores[hardness]["partial"][type_]["rec"] += partial_scores[
                        type_
                    ]["rec"]
                    self.scores[hardness]["partial"][type_]["rec_count"] += 1
                self.scores[hardness]["partial"][type_]["f1"] += partial_scores[type_][
                    "f1"
                ]
                if partial_scores[type_]["pred_total"] > 0:
                    self.scores["all"]["partial"][type_]["acc"] += partial_scores[
                        type_
                    ]["acc"]
                    self.scores["all"]["partial"][type_]["acc_count"] += 1
                if partial_scores[type_]["label_total"] > 0:
                    self.scores["all"]["partial"][type_]["rec"] += partial_scores[
                        type_
                    ]["rec"]
                    self.scores["all"]["partial"][type_]["rec_count"] += 1
                self.scores["all"]["partial"][type_]["f1"] += partial_scores[type_][
                    "f1"
                ]

        return {
            "db_id": db_name,
            "predicted": predicted,
            "gold": gold,
            "predicted_parse_error": parse_error,
            "hardness": hardness,
            "exact": exact_score,
            "partial": partial_scores,
            "db_id": db_name,
        }

    def finalize(self):
        scores = self.scores
        for level in LEVELS:
            if scores[level]["count"] == 0:
                continue
            if self.etype in ["all", "exec"]:
                scores[level]["exec"] /= scores[level]["count"]

            if self.etype in ["all", "match"]:
                scores[level]["exact"] /= scores[level]["count"]
                for type_ in PARTIAL_TYPES:
                    if scores[level]["partial"][type_]["acc_count"] == 0:
                        scores[level]["partial"][type_]["acc"] = 0
                    else:
                        scores[level]["partial"][type_]["acc"] = (
                            scores[level]["partial"][type_]["acc"]
                            / scores[level]["partial"][type_]["acc_count"]
                            * 1.0
                        )
                    if scores[level]["partial"][type_]["rec_count"] == 0:
                        scores[level]["partial"][type_]["rec"] = 0
                    else:
                        scores[level]["partial"][type_]["rec"] = (
                            scores[level]["partial"][type_]["rec"]
                            / scores[level]["partial"][type_]["rec_count"]
                            * 1.0
                        )
                    if (
                        scores[level]["partial"][type_]["acc"] == 0
                        and scores[level]["partial"][type_]["rec"] == 0
                    ):
                        scores[level]["partial"][type_]["f1"] = 1
                    else:
                        scores[level]["partial"][type_]["f1"] = (
                            2.0
                            * scores[level]["partial"][type_]["acc"]
                            * scores[level]["partial"][type_]["rec"]
                            / (
                                scores[level]["partial"][type_]["rec"]
                                + scores[level]["partial"][type_]["acc"]
                            )
                        )


def isValidSQL(sql, db, db_type="sqlite"):
    conn = db_utils.connect(db, db_type)
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
    except:
        return False
    return True


def print_scores(scores, etype):
    LEVELS = ["easy", "medium", "hard", "extra", "all"]
    PARTIAL_TYPES = [
        "select",
        "select(no AGG)",
        "where",
        "where(no OP)",
        "group(no Having)",
        "group",
        "order",
        "and/or",
        "IUEN",
        "keywords",
    ]

    print("{:20} {:20} {:20} {:20} {:20} {:20}".format("", *LEVELS))
    counts = [scores[level]["count"] for level in LEVELS]
    print("{:20} {:<20d} {:<20d} {:<20d} {:<20d} {:<20d}".format("count", *counts))

    if etype in ["all", "exec"]:
        print("=====================   EXECUTION ACCURACY     =====================")
        this_scores = [scores[level]["exec"] for level in LEVELS]
        print(
            "{:20} {:<20.3f} {:<20.3f} {:<20.3f} {:<20.3f} {:<20.3f}".format(
                "execution", *this_scores
            )
        )

    if etype in ["all", "match"]:
        print("\n====================== EXACT MATCHING ACCURACY =====================")
        exact_scores = [scores[level]["exact"] for level in LEVELS]
        print(
            "{:20} {:<20.3f} {:<20.3f} {:<20.3f} {:<20.3f} {:<20.3f}".format(
                "exact match", *exact_scores
            )
        )
        print("\n---------------------PARTIAL MATCHING ACCURACY----------------------")
        for type_ in PARTIAL_TYPES:
            this_scores = [scores[level]["partial"][type_]["acc"] for level in LEVELS]
            print(
                "{:20} {:<20.3f} {:<20.3f} {:<20.3f} {:<20.3f} {:<20.3f}".format(
                    type_, *this_scores
                )
            )

        print("---------------------- PARTIAL MATCHING RECALL ----------------------")
        for type_ in PARTIAL_TYPES:
            this_scores = [scores[level]["partial"][type_]["rec"] for level in LEVELS]
            print(
                "{:20} {:<20.3f} {:<20.3f} {:<20.3f} {:<20.3f} {:<20.3f}".format(
                    type_, *this_scores
                )
            )

        print("---------------------- PARTIAL MATCHING F1 --------------------------")
        for type_ in PARTIAL_TYPES:
            this_scores = [scores[level]["partial"][type_]["f1"] for level in LEVELS]
            print(
                "{:20} {:<20.3f} {:<20.3f} {:<20.3f} {:<20.3f} {:<20.3f}".format(
                    type_, *this_scores
                )
            )


def evaluate(gold, predict, db_dir, etype, kmaps, db_type="sqlite", grammar="spider"):
    with open(gold) as f:
        glist = [l.strip().split("\t") for l in f.readlines() if len(l.strip()) > 0]

    with open(predict) as f:
        plist = [l.strip().split("\t") for l in f.readlines() if len(l.strip()) > 0]
    # plist = [("select max(Share),min(Share) from performance where Type != 'terminal'", "orchestra")]
    # glist = [("SELECT max(SHARE) ,  min(SHARE) FROM performance WHERE TYPE != 'Live final'", "orchestra")]
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


def eval_exec_match(db, p_str, g_str, pred, gold, db_type="sqlite"):
    """
    return 1 if the values between prediction and gold are matching
    in the corresponding index. Currently not support multiple col_unit(pairs).
    """
    conn = db_utils.connect(db, db_type)
    cursor = conn.cursor()
    try:
        cursor.execute(p_str)
        p_res = cursor.fetchall()
    except:
        return False

    cursor.execute(g_str)
    q_res = cursor.fetchall()

    def res_map(res, val_units):
        rmap = {}
        for idx, val_unit in enumerate(val_units):
            key = (
                tuple(val_unit[1])
                if not val_unit[2]
                else (val_unit[0], tuple(val_unit[1]), tuple(val_unit[2]))
            )
            rmap[key] = [r[idx] for r in res]
        return rmap

    p_val_units = [unit[1] for unit in pred["select"][1]]
    q_val_units = [unit[1] for unit in gold["select"][1]]
    return res_map(p_res, p_val_units) == res_map(q_res, q_val_units)


# Rebuild SQL functions for value evaluation
def rebuild_cond_unit_val(cond_unit):
    if cond_unit is None or not DISABLE_VALUE:
        return cond_unit

    not_op, op_id, val_unit, val1, val2 = cond_unit
    if type(val1) is tuple:  # Handling column
        pass
    elif type(val1) is not dict:
        val1 = None
    else:
        val1 = rebuild_sql_val(val1)
    if type(val2) is not dict:
        val2 = None
    else:
        val2 = rebuild_sql_val(val2)
    return not_op, op_id, val_unit, val1, val2


def rebuild_condition_val(condition):
    if condition is None or not DISABLE_VALUE:
        return condition

    res = []
    for idx, it in enumerate(condition):
        if idx % 2 == 0:
            res.append(rebuild_cond_unit_val(it))
        else:
            res.append(it)
    return res


def rebuild_sql_val(sql):
    if sql is None or not DISABLE_VALUE:
        return sql

    # sql['from']['conds'] = rebuild_condition_val(sql['from']['conds'],)
    sql["having"] = rebuild_condition_val(sql["having"])
    sql["where"] = rebuild_condition_val(sql["where"])
    sql["intersect"] = rebuild_sql_val(sql["intersect"])
    sql["except"] = rebuild_sql_val(sql["except"])
    sql["union"] = rebuild_sql_val(sql["union"])

    return sql


# Rebuild SQL functions for foreign key evaluation
def build_valid_col_units(table_units, schema):
    col_ids = [
        table_unit[1]
        for table_unit in table_units
        if table_unit[0] == TABLE_TYPE["table_unit"]
    ]
    prefixs = [col_id[:-2] for col_id in col_ids]
    valid_col_units = []
    for value in list(schema.idMap.values()):
        if "." in value and value[: value.rindex(".")] in prefixs:
            valid_col_units.append(value)
    return valid_col_units


def rebuild_col_unit_col(valid_col_units, col_unit, kmap, schema):
    if col_unit is None:
        return col_unit
    elif isinstance(col_unit, str) or isinstance(col_unit, float):
        return col_unit
    elif isinstance(col_unit, dict):
        # apply rebuild to nested query as well
        return rebuild_sql_col(schema, col_unit, kmap)
    elif isinstance(col_unit, int):
        return col_unit
    elif col_unit[0] == "time":
        return col_unit
    elif isinstance(col_unit[1], list):
        agg_id, _col_ids, distinct = col_unit
        col_ids = []
        for col_id in _col_ids:
            if col_id in kmap and col_id in valid_col_units:
                # Consistently use the first item that matches
                # (Not sure if this logic leads to incorrect evaluation)
                for new_col_id in kmap[col_id]:
                    if new_col_id in valid_col_units:
                        col_ids.append(col_id)
                        break
            col_ids.append(col_id)
        if DISABLE_DISTINCT:
            distinct = None
        return agg_id, col_ids, distinct
    else:
        assert False


def rebuild_val_unit_col(valid_col_units, val_unit, kmap, schema):
    if val_unit is None:
        return val_unit
    elif isinstance(val_unit, tuple):
        assert len(val_unit) == 3
        unit_op, col_unit1, col_unit2 = val_unit
        col_unit1 = rebuild_col_unit_col(valid_col_units, col_unit1, kmap, schema)
        col_unit2 = rebuild_col_unit_col(valid_col_units, col_unit2, kmap, schema)
        return unit_op, col_unit1, col_unit2
    else:
        assert False


def rebuild_table_unit_col(valid_col_units, table_unit, kmap):
    if table_unit is None:
        return table_unit

    table_type, col_unit_or_sql = table_unit
    if isinstance(col_unit_or_sql, tuple):
        col_unit_or_sql = rebuild_col_unit_col(valid_col_units, col_unit_or_sql, kmap)
    return table_type, col_unit_or_sql


def rebuild_cond_unit_col(valid_col_units, cond_unit, kmap, schema):
    if cond_unit is None:
        return cond_unit

    not_op, op_id, val_unit, val1, val2 = cond_unit
    val_unit = rebuild_val_unit_col(valid_col_units, val_unit, kmap, schema)
    val1 = rebuild_col_unit_col(valid_col_units, val1, kmap, schema)  # For column
    return not_op, op_id, val_unit, val1, val2


def rebuild_condition_col(valid_col_units, condition, kmap, schema):
    for idx in range(len(condition)):
        if idx % 2 == 0:
            condition[idx] = rebuild_cond_unit_col(
                valid_col_units, condition[idx], kmap, schema
            )
    return condition


def rebuild_select_col(valid_col_units, sel, kmap, schema):
    if sel is None:
        return sel
    distinct, _list = sel
    new_list = []
    for it in _list:
        agg_id, val_unit = it
        new_list.append(
            (agg_id, rebuild_val_unit_col(valid_col_units, val_unit, kmap, schema))
        )
    if DISABLE_DISTINCT:
        distinct = None
    return distinct, new_list


def rebuild_from_col(valid_col_units, from_, kmap):
    if from_ is None:
        return from_

    from_["table_units"] = [
        rebuild_table_unit_col(valid_col_units, table_unit, kmap)
        for table_unit in from_["table_units"]
    ]
    from_["conds"] = rebuild_condition_col(valid_col_units, from_["conds"], kmap)
    return from_


def rebuild_group_by_col(valid_col_units, group_by, kmap, schema):
    if group_by is None:
        return group_by

    return [
        rebuild_col_unit_col(valid_col_units, col_unit, kmap, schema)
        for col_unit in group_by
    ]


def rebuild_order_by_col(valid_col_units, order_by, kmap, schema):
    if order_by is None or len(order_by) == 0:
        return order_by

    direction, val_units = order_by
    new_val_units = [
        rebuild_val_unit_col(valid_col_units, val_unit, kmap, schema)
        for val_unit in val_units
    ]
    return direction, new_val_units


def rebuild_sql_col(schema, sql, kmap):
    if sql is None:
        return sql
    valid_col_units = build_valid_col_units(sql["from"]["table_units"], schema)

    sql["select"] = rebuild_select_col(valid_col_units, sql["select"], kmap, schema)
    # sql['from'] = rebuild_from_col(valid_col_units, sql['from'], kmap)
    sql["where"] = rebuild_condition_col(valid_col_units, sql["where"], kmap, schema)
    sql["groupBy"] = rebuild_group_by_col(valid_col_units, sql["groupBy"], kmap, schema)
    sql["orderBy"] = rebuild_order_by_col(valid_col_units, sql["orderBy"], kmap, schema)
    sql["having"] = rebuild_condition_col(valid_col_units, sql["having"], kmap, schema)
    sql["intersect"] = rebuild_sql_col(schema, sql["intersect"], kmap)
    sql["except"] = rebuild_sql_col(schema, sql["except"], kmap)
    sql["union"] = rebuild_sql_col(schema, sql["union"], kmap)

    return sql


def build_foreign_key_map(entry):
    cols_orig = entry["column_names_original"]
    tables_orig = entry["table_names_original"]

    # rebuild cols corresponding to idmap in Schema
    cols = []
    for col_orig in cols_orig:
        if col_orig[0] >= 0:
            t = tables_orig[col_orig[0]]
            c = col_orig[1]
            cols.append("__" + t.lower() + "." + c.lower() + "__")
        else:
            cols.append("__all__")

    def keyset_in_list(k1, k2, k_list):
        for k_set in k_list:
            if k1 in k_set or k2 in k_set:
                return k_set
        new_k_set = set()
        k_list.append(new_k_set)
        return new_k_set

    foreign_key_list = []
    foreign_keys = entry["foreign_keys"]
    for fkey in foreign_keys:
        key1, key2 = fkey
        key_set = keyset_in_list(key1, key2, foreign_key_list)
        key_set.add(key1)
        key_set.add(key2)

    # To-do: need to consider case where two different foreign keys on one primary key
    foreign_key_map = {}
    for key_set in foreign_key_list:
        sorted_list = sorted(list(key_set))
        midx = sorted_list[0]
        for idx in sorted_list:
            foreign_key_map[cols[idx]] = cols[midx]

    return foreign_key_map


def build_foreign_key_map_from_json(table):
    with open(table) as f:
        data = json.load(f)
    tables = {}
    for entry in data:
        tables[entry["db_id"]] = build_foreign_key_map(entry)
    return tables


def modify_from_clause(sql, primary_key, foreign_maps):
    def get_all_referenced_tables(json_sql):
        all_strings = get_all_string(json_sql)
        all_schema = set([item for item in all_strings if "__"])
        if any(item.count(".") == 2 for item in all_schema):
            all_used_tables = set([item for item in all_schema if item.count(".") == 1])
            all_columns = set([item for item in all_schema if item.count(".") == 2])
            all_referenced_tables = set(
                [item[: item.rindex(".")] + "__" for item in all_columns]
            )
        else:
            all_used_tables = set([item for item in all_schema if "." not in item])
            all_columns = set([item for item in all_schema if "." in item])
            all_referenced_tables = set(
                [item.split(".")[0] + "__" for item in all_columns]
            )
        if "__all__" in all_used_tables:
            all_referenced_tables.update(["__all__"])
        return all_referenced_tables

    def get_all_string(data):
        referenced_tables = []
        if type(data) is dict:
            for key, item in data.items():
                if key in ["intersect", "union", "except", "from"]:
                    continue
                referenced_tables += get_all_string(item)
        elif type(data) in [tuple, list]:
            for datum in data:
                referenced_tables += get_all_string(datum)
        elif type(data) is str:
            referenced_tables += [data]
        return referenced_tables

    def has_select_star_no_agg(sql_json):
        for item in sql_json["select"][1]:
            if item[0] == 0 and item[1][1][1] == "__all__":
                return True
        return False

    def remove_redundant_table(table_units, join_conds, used_tables):
        """
        This is dependent to remove_redundant_join. Should be called after
        """
        # Get tables from join conds
        tables_in_join = []
        for cond in join_conds:
            for tab_col in cond:
                table = tab_col[: tab_col.rindex(".")] + "__"
                tables_in_join.append(table)

        # Remove redundant ones
        new_table_units = []
        for table_unit in table_units:
            if (
                table_unit[0] == "sql"
                or table_unit[1] in used_tables
                or table_unit[1] in tables_in_join
            ):
                new_table_units.append(table_unit)
            if "__all__" in used_tables:
                new_table_units.append(table_unit)
        return new_table_units

    def remove_redundant_join(sql, join_conds, used_tables, primary_keys, foreign_maps):
        """
        Following conditions should be satisfy to remove the join condition
        1. There should be no reference to the joined table
        2. The gold SQL should not have "SELECT * ..."
           (because,then the different output due to join might have been intended)
        3. The table with no reference should be a primary key (to ensure no change in the output)
        4. The corresponding join condition should exist in the predefined primary-foreign key relation
           (to ensure no change in the output)
        """
        new_join_conds = copy.deepcopy(join_conds)
        # Requirement #2
        if "__all__" in used_tables and has_select_star_no_agg(sql):
            return new_join_conds

        # Requirment #1, #3 and #4
        for cond in join_conds:
            for tab_col in cond:
                table = tab_col[: tab_col.rindex(".")] + "__"
                if (
                    table not in used_tables
                    and tab_col in primary_keys
                    and cond in foreign_maps
                ):
                    new_join_conds.remove(cond)
                    break
        return new_join_conds

    def parse_join_conds(list_of_conds):
        tmp = []
        for idx, item in enumerate(list_of_conds):
            if idx % 2 == 0:
                interested_items = [value for value in item if type(value) is tuple]
                tmp.append(set(get_all_string(interested_items)))
        return tmp

    # Get join conditions
    join_conds = parse_join_conds(sql["from"]["conds"])
    used_tables = get_all_referenced_tables(sql)

    new_join_conds = remove_redundant_join(
        sql, join_conds, used_tables, primary_key, foreign_maps
    )
    new_table_units = remove_redundant_table(
        sql["from"]["table_units"], new_join_conds, used_tables
    )
    sql["from"]["conds"] = new_join_conds
    sql["from"]["table_units"] = new_table_units

    # Nested queries in the WHERE clause (does not support correlation)
    if sql["where"]:
        for idx, predicate in enumerate(sql["where"]):
            if idx % 2 == 0 and type(predicate[3]) == dict:
                sql["where"][idx] = (
                    predicate[0],
                    predicate[1],
                    predicate[2],
                    modify_from_clause(predicate[3], primary_key, foreign_maps),
                    predicate[4],
                )
    elif sql["from"]:
        for idx, table_unit in enumerate(sql["from"]["table_units"]):
            if table_unit[0] == "sql":
                sql["from"]["table_units"][idx] = (
                    "sql",
                    modify_from_clause(table_unit[1], primary_key, foreign_maps),
                )
    # Queries with set operations
    for keyword in ["intersect", "union", "except"]:
        if sql[keyword]:
            sql[keyword] = modify_from_clause(sql[keyword], primary_key, foreign_maps)

    return sql


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
