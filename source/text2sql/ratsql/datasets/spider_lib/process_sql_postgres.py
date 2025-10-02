################################
# Assumptions:
#   1. sql is correct
#   2. only table name has alias
#   3. only one intersect/union/except
#
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

import json
import re
import sqlite3
from nltk import word_tokenize
from source.text2sql.ratsql.datasets.spider_lib.process_sql_spider import (
    Schema,
    get_schema,
    get_schema_from_json,
)

Schema, get_schema, get_schema_from_json = Schema, get_schema, get_schema_from_json

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
AS = ("as",)

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
UNNEST = ("unnest",)
ARRLEN = ("array_length",)
CONCAT = ("||",)
UNIT_OPS = ("none", "unnest", "array_length", "-", "+", "*", "/", "||")
AGG_OPS = ("none", "max", "min", "count", "sum", "avg")
TABLE_TYPE = {
    "sql": "sql",
    "table_unit": "table_unit",
}

COND_OPS = ("and", "or")
SQL_OPS = ("intersect", "union", "except")
ORDER_OPS = ("desc", "asc")


def tokenize(string):
    string = str(string)
    string = string.replace(
        "'", '"'
    )  # ensures all string values wrapped by "" problem??
    string = string.replace("\\", "")
    quote_idxs = [idx for idx, char in enumerate(string) if char == '"']
    assert len(quote_idxs) % 2 == 0, "Unexpected quote"

    # keep string value as token
    vals = {}
    for i in range(len(quote_idxs) - 1, -1, -2):
        qidx1 = quote_idxs[i - 1]
        qidx2 = quote_idxs[i]
        val = string[qidx1 : qidx2 + 1]
        key = "__val_{}_{}__".format(qidx1, qidx2)
        string = string[:qidx1] + key + string[qidx2 + 1 :]
        vals[key] = val

    toks = [word.lower() for word in word_tokenize(string)]

    # find if there exists !=, >=, <=
    eq_idxs = [idx for idx, tok in enumerate(toks) if tok == "="]
    eq_idxs.reverse()
    prefix = ("!", ">", "<")
    for eq_idx in eq_idxs:
        pre_tok = toks[eq_idx - 1]
        if pre_tok in prefix:
            toks = toks[: eq_idx - 1] + [pre_tok + "="] + toks[eq_idx + 1 :]

    concat_idxs = [idx for idx, tok in enumerate(toks) if "||" in tok]
    concat_idxs.reverse()
    for concat_idx in concat_idxs:
        _splitted_toks = toks[concat_idx].split("||")
        splitted_toks = []
        for tok in _splitted_toks:
            splitted_toks.append(tok)
            splitted_toks.append("||")
        toks = toks[:concat_idx] + splitted_toks[:-1] + toks[concat_idx + 1 :]

    concat_idxs = [idx for idx, tok in enumerate(toks) if "," in tok]
    concat_idxs.reverse()
    for concat_idx in concat_idxs:
        if toks[concat_idx] == ",":
            continue
        _splitted_toks = toks[concat_idx].split(",")
        splitted_toks = []
        for tok in _splitted_toks:
            splitted_toks.append(tok)
            splitted_toks.append(",")
        toks = toks[:concat_idx] + splitted_toks[:-1] + toks[concat_idx + 1 :]

    # replace with string value token
    for i in range(len(toks)):
        if toks[i] in vals:
            toks[i] = vals[toks[i]]

    return toks


def scan_alias(toks):
    """Scan the index of 'as' and build the map for all alias"""
    as_idxs = [idx for idx, tok in enumerate(toks) if tok == "as"]
    alias = {}
    for idx in as_idxs:
        alias[toks[idx + 1]] = toks[idx - 1]
    return alias


def get_tables_with_alias(schema, toks):
    tables = scan_alias(toks)
    for key in schema:
        assert key not in tables, "Alias {} has the same name in table".format(key)
        tables[key] = key
        if "quality." or "master." in key:
            new_key = key.replace("master.", "").replace("quality.", "")
            tables[new_key] = key
    return tables


def _parse_col(toks, start_idx, tables_with_alias, schema, default_tables=None):
    """
    :returns next idx, column id
    """
    tok = toks[start_idx]
    if re.search("__val_\d+_\d+__", tok):
        return start_idx + 1, -1

    if tok == "*":
        return start_idx + 1, schema.idMap[tok]

    if "." in tok:  # if token is a composite
        _splitted_tok = tok.split(".")
        alias, col = ".".join(_splitted_tok[:-1]), _splitted_tok[-1]
        key = tables_with_alias[alias] + "." + col
        return start_idx + 1, schema.idMap[key]

    assert (
        default_tables is not None and len(default_tables) > 0
    ), "Default tables should not be None or empty"

    for alias in default_tables:
        table = tables_with_alias[alias]
        if tok in schema.schema[table]:
            key = table + "." + tok
            return start_idx + 1, schema.idMap[key]

    assert False, "Error col: {}".format(tok)


def parse_col(toks, start_idx, tables_with_alias, schema, default_tables=None):
    """
    :returns next idx, column id
    """
    idx = start_idx
    len_ = len(toks)
    isBlock = False
    if toks[idx] == "(":
        isBlock = True
        idx += 1

    idx, col_id = _parse_col(toks, idx, tables_with_alias, schema, default_tables)
    col_ids = []
    if col_id != -1:
        col_ids.append(col_id)
    while idx < len_ and toks[idx] in CONCAT:
        idx += 1
        idx, col_id = _parse_col(toks, idx, tables_with_alias, schema, default_tables)
        if col_id != -1:
            col_ids.append(col_id)

    if isBlock:
        assert toks[idx] == ")"
        idx += 1  # skip ')'
    return idx, col_ids


def parse_col_unit(toks, start_idx, tables_with_alias, schema, default_tables=None):
    """
    :returns next idx, (agg_op id, col_id)
    """
    idx = start_idx
    len_ = len(toks)
    isBlock = False
    isDistinct = False
    if toks[idx] == "(":
        isBlock = True
        idx += 1

    if toks[idx] in AGG_OPS:
        agg_id = AGG_OPS.index(toks[idx])
        idx += 1
        assert idx < len_ and toks[idx] == "("
        idx += 1
        if toks[idx] == "distinct":
            idx += 1
            isDistinct = True
        idx, col_ids = parse_col(toks, idx, tables_with_alias, schema, default_tables)
        assert idx < len_ and toks[idx] == ")"
        idx += 1
        return idx, (agg_id, col_ids, isDistinct)

    if toks[idx] == "distinct":
        idx += 1
        isDistinct = True
    agg_id = AGG_OPS.index("none")
    idx, col_ids = parse_col(toks, idx, tables_with_alias, schema, default_tables)

    if isBlock:
        assert toks[idx] == ")"
        idx += 1  # skip ')'

    return idx, (agg_id, col_ids, isDistinct)


def parse_val_unit(toks, start_idx, tables_with_alias, schema, default_tables=None):
    idx = start_idx
    len_ = len(toks)
    isBlock = False
    if toks[idx] == "(":
        isBlock = True
        idx += 1

    col_unit1 = None
    col_unit2 = None
    unit_op = UNIT_OPS.index("none")

    if idx < len_ and toks[idx] in UNNEST:
        unit_op = UNIT_OPS.index(toks[idx])
        idx += 1
        idx, col_unit1 = parse_col_unit(
            toks, idx, tables_with_alias, schema, default_tables
        )

    elif idx < len_ and toks[idx] in ARRLEN:
        unit_op = UNIT_OPS.index(toks[idx])
        idx += 1
        assert toks[idx] == "("
        idx += 1

        idx, col_unit1 = parse_col_unit(
            toks, idx, tables_with_alias, schema, default_tables
        )
        assert toks[idx] == ","
        idx += 1

        col_unit2 = int(toks[idx])
        idx += 1

        assert toks[idx] == ")"
        idx += 1

    else:
        idx, col_unit1 = parse_col_unit(
            toks, idx, tables_with_alias, schema, default_tables
        )
        if idx < len_ and toks[idx] in UNIT_OPS:
            unit_op = UNIT_OPS.index(toks[idx])
            idx += 1
            idx, col_unit2 = parse_col_unit(
                toks, idx, tables_with_alias, schema, default_tables
            )

    if isBlock:
        assert toks[idx] == ")"
        idx += 1  # skip ')'

    return idx, (unit_op, col_unit1, col_unit2)


def parse_table_unit(toks, start_idx, tables_with_alias, schema):
    """
    :returns next idx, table id, table name
    """
    idx = start_idx
    len_ = len(toks)
    key = tables_with_alias[toks[idx]]

    if idx + 1 < len_ and toks[idx + 1] == "as":
        idx += 3
    else:
        idx += 1

    return idx, schema.idMap[key], key


def parse_value(toks, start_idx, tables_with_alias, schema, default_tables=None):
    idx = start_idx
    len_ = len(toks)

    isBlock = False
    if toks[idx] == "(":
        isBlock = True
        idx += 1
        if toks[idx] != "select":
            raise ValueError(
                "error in right operand of IN operation\n" + " ".join(toks)
            )

    if toks[idx] == "select":
        idx, val = parse_sql(toks, idx, tables_with_alias, schema)
    elif toks[idx] in {"current_timestamp", "current_date"}:
        idx += 2
        if toks[idx] == "interval":
            idx += 1
        val = ("time", toks[idx])
        idx += 1
    elif '"' in toks[idx]:  # token is a string value
        val = toks[idx]
        idx += 1
    elif toks[idx] == "null":
        val = "null"
        idx += 1
    else:
        try:
            val = float(toks[idx])
            idx += 1
        except:
            end_idx = idx
            while (
                end_idx < len_
                and toks[end_idx] != ","
                and toks[end_idx] != ")"
                and toks[end_idx] != "and"
                and toks[end_idx] not in CLAUSE_KEYWORDS
                and toks[end_idx] not in JOIN_KEYWORDS
            ):
                end_idx += 1

            idx, val = parse_col_unit(
                toks[start_idx:end_idx], 0, tables_with_alias, schema, default_tables
            )
            idx = end_idx

    if isBlock:
        if toks[idx] == ",":
            end_idx = toks[idx:].index(")")
            tmp = [val]
            for item in toks[idx + 1 : idx + end_idx]:
                if item == ",":
                    continue
                if type(item) == str:
                    if item.isnumeric():
                        item = int(item)
                    else:
                        try:
                            item = float(item)
                        except:
                            pass
                tmp += [item]
            idx += end_idx
        assert toks[idx] == ")"
        idx += 1

    return idx, val


def parse_condition(toks, start_idx, tables_with_alias, schema, default_tables=None):
    idx = start_idx
    len_ = len(toks)
    conds = []

    while idx < len_:
        idx, val_unit = parse_val_unit(
            toks, idx, tables_with_alias, schema, default_tables
        )
        not_op = False
        if toks[idx] == "not":
            not_op = True
            idx += 1

        assert (
            idx < len_ and toks[idx] in WHERE_OPS
        ), "Error condition: idx: {}, tok: {}".format(idx, toks[idx])
        op_id = WHERE_OPS.index(toks[idx])
        idx += 1
        val1 = val2 = None
        if op_id == WHERE_OPS.index(
            "between"
        ):  # between..and... special case: dual values
            idx, val1 = parse_value(
                toks, idx, tables_with_alias, schema, default_tables
            )
            assert toks[idx] == "and"
            idx += 1
            idx, val2 = parse_value(
                toks, idx, tables_with_alias, schema, default_tables
            )
        elif op_id == WHERE_OPS.index("is"):
            if toks[idx] == "not":
                not_op = True
                idx += 1
            idx, val1 = parse_value(
                toks, idx, tables_with_alias, schema, default_tables
            )
            val2 = None
        else:  # normal case: single value
            idx, val1 = parse_value(
                toks, idx, tables_with_alias, schema, default_tables
            )
            val2 = None

        conds.append((not_op, op_id, val_unit, val1, val2))

        if idx < len_ and (
            toks[idx] in CLAUSE_KEYWORDS
            or toks[idx] in (")", ";")
            or toks[idx] in JOIN_KEYWORDS
        ):
            break

        if idx < len_ and toks[idx] in COND_OPS:
            conds.append(toks[idx])
            idx += 1  # skip and/or

    return idx, conds


def parse_select(toks, start_idx, tables_with_alias, schema, default_tables=None):
    idx = start_idx
    len_ = len(toks)

    assert toks[idx] == "select", "'select' not found"
    idx += 1
    isDistinct = False
    if idx < len_ and toks[idx] == "distinct":
        idx += 1
        isDistinct = True
    val_units = []

    while idx < len_ and toks[idx] not in CLAUSE_KEYWORDS:
        agg_id = AGG_OPS.index("none")
        if toks[idx] in AGG_OPS:
            agg_id = AGG_OPS.index(toks[idx])
            idx += 1
        idx, val_unit = parse_val_unit(
            toks, idx, tables_with_alias, schema, default_tables
        )
        val_units.append((agg_id, val_unit))

        if (idx < len_) and (toks[idx] == ":") and (":" in toks[idx + 1]):
            idx += 2

        if toks[idx] in AS:
            idx += 1
            col_alias = toks[idx]
            idx += 1

        if idx + 1 < len_ and (toks[idx + 1] in {",", "from"}):
            col_alias = toks[idx]
            idx += 1

        if idx < len_ and toks[idx] == ",":
            idx += 1  # skip ','

    return idx, (isDistinct, val_units)


def parse_from(toks, start_idx, tables_with_alias, schema):
    """
    Assume in the from clause, all table units are combined with join
    """
    assert "from" in toks[start_idx:], "'from' not found"

    len_ = len(toks)
    idx = toks.index("from", start_idx) + 1
    default_tables = []
    table_units = []
    conds = []

    while idx < len_:
        isBlock = False
        if toks[idx] == "(":
            isBlock = True
            idx += 1

        if toks[idx] == "select":
            idx, sql = parse_sql(toks, idx, tables_with_alias, schema)
            table_units.append((TABLE_TYPE["sql"], sql))
        else:
            if idx < len_ and toks[idx] == "join":
                idx += 1  # skip join
            idx, table_unit, table_name = parse_table_unit(
                toks, idx, tables_with_alias, schema
            )
            table_units.append((TABLE_TYPE["table_unit"], table_unit))
            default_tables.append(table_name)
        if idx < len_ and toks[idx] == "on":
            idx += 1  # skip on
            idx, this_conds = parse_condition(
                toks, idx, tables_with_alias, schema, default_tables
            )
            if len(conds) > 0:
                conds.append("and")
            conds.extend(this_conds)

        if isBlock:
            assert toks[idx] == ")"
            idx += 1
        if idx < len_ and (toks[idx] in CLAUSE_KEYWORDS or toks[idx] in (")", ";")):
            break

    return idx, table_units, conds, default_tables


def parse_where(toks, start_idx, tables_with_alias, schema, default_tables):
    idx = start_idx
    len_ = len(toks)

    if idx >= len_ or toks[idx] != "where":
        return idx, []

    idx += 1
    idx, conds = parse_condition(toks, idx, tables_with_alias, schema, default_tables)
    return idx, conds


def parse_group_by(toks, start_idx, tables_with_alias, schema, default_tables):
    idx = start_idx
    len_ = len(toks)
    col_units = []

    if idx >= len_ or toks[idx] != "group":
        return idx, col_units

    idx += 1
    assert toks[idx] == "by"
    idx += 1

    while idx < len_ and not (toks[idx] in CLAUSE_KEYWORDS or toks[idx] in (")", ";")):
        idx, col_unit = parse_col_unit(
            toks, idx, tables_with_alias, schema, default_tables
        )
        col_units.append(col_unit)
        if idx < len_ and toks[idx] == ",":
            idx += 1  # skip ','
        else:
            break

    return idx, col_units


def parse_order_by(toks, start_idx, tables_with_alias, schema, default_tables):
    idx = start_idx
    len_ = len(toks)
    val_units = []
    order_type = "asc"  # default type is 'asc'

    if idx >= len_ or toks[idx] != "order":
        return idx, val_units

    idx += 1
    assert toks[idx] == "by"
    idx += 1

    while idx < len_ and not (toks[idx] in CLAUSE_KEYWORDS or toks[idx] in (")", ";")):
        idx, val_unit = parse_val_unit(
            toks, idx, tables_with_alias, schema, default_tables
        )
        val_units.append(val_unit)
        if idx < len_ and toks[idx] in ORDER_OPS:
            order_type = toks[idx]
            idx += 1
        if idx < len_ and toks[idx] == ",":
            idx += 1  # skip ','
        else:
            break

    return idx, (order_type, val_units)


def parse_having(toks, start_idx, tables_with_alias, schema, default_tables):
    idx = start_idx
    len_ = len(toks)

    if idx >= len_ or toks[idx] != "having":
        return idx, []

    idx += 1
    idx, conds = parse_condition(toks, idx, tables_with_alias, schema, default_tables)
    return idx, conds


def parse_limit(toks, start_idx):
    idx = start_idx
    len_ = len(toks)

    if idx < len_ and toks[idx] == "limit":
        idx += 2
        return idx, int(toks[idx - 1])

    return idx, None


def parse_sql(toks, start_idx, tables_with_alias, schema):
    isBlock = False  # indicate whether this is a block of sql/sub-sql
    len_ = len(toks)
    idx = start_idx

    sql = {}
    if toks[idx] == "(":
        isBlock = True
        idx += 1

    # parse from clause in order to get default tables
    from_end_idx, table_units, conds, default_tables = parse_from(
        toks, start_idx, tables_with_alias, schema
    )
    sql["from"] = {"table_units": table_units, "conds": conds}
    # select clause
    _, select_col_units = parse_select(
        toks, idx, tables_with_alias, schema, default_tables
    )
    idx = from_end_idx
    sql["select"] = select_col_units
    # where clause
    idx, where_conds = parse_where(toks, idx, tables_with_alias, schema, default_tables)
    sql["where"] = where_conds
    # group by clause
    idx, group_col_units = parse_group_by(
        toks, idx, tables_with_alias, schema, default_tables
    )
    sql["groupBy"] = group_col_units
    # having clause
    idx, having_conds = parse_having(
        toks, idx, tables_with_alias, schema, default_tables
    )
    sql["having"] = having_conds
    # order by clause
    idx, order_col_units = parse_order_by(
        toks, idx, tables_with_alias, schema, default_tables
    )
    sql["orderBy"] = order_col_units
    # limit clause
    idx, limit_val = parse_limit(toks, idx)
    sql["limit"] = limit_val

    idx = skip_semicolon(toks, idx)
    if isBlock:
        assert toks[idx] == ")"
        idx += 1  # skip ')'
    idx = skip_semicolon(toks, idx)

    # intersect/union/except clause
    for op in SQL_OPS:  # initialize IUE
        sql[op] = None
    if idx < len_ and toks[idx] in SQL_OPS:
        sql_op = toks[idx]
        idx += 1
        idx, IUE_sql = parse_sql(toks, idx, tables_with_alias, schema)
        sql[sql_op] = IUE_sql
    return idx, sql


def load_data(fpath):
    with open(fpath) as f:
        data = json.load(f)
    return data


def get_sql(schema, query):
    toks = tokenize(query)
    tables_with_alias = get_tables_with_alias(schema.schema, toks)
    _, sql = parse_sql(toks, 0, tables_with_alias, schema)

    return sql


def skip_semicolon(toks, start_idx):
    idx = start_idx
    while idx < len(toks) and toks[idx] == ";":
        idx += 1
    return idx
