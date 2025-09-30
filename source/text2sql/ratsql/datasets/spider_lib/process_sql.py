from source.text2sql.ratsql.datasets.spider_lib import (
    process_sql_postgres,
    process_sql_spider,
)
from source.text2sql.ratsql.datasets.spider_lib.process_sql_spider import *
from source.text2sql.ratsql.grammars.postgres import POSTGRES_GRAMMAR_IDENTIFIERS
from source.text2sql.ratsql.grammars.spider import SPIDER_GRAMMAR_IDENTIFIERS


""" jjkim - Nov 16, 2021
change original process_sql.py to process_sql_spider.py and
package two process_sql_*.py files with this file.
if an outside code references a function that is not revised in this file,
it would be linked to process_sql_spider (from process_sql_spider import *)
"""


def tokenize(string, grammar="spider"):
    if grammar in SPIDER_GRAMMAR_IDENTIFIERS:
        return process_sql_spider.tokenize(string)
    elif grammar in POSTGRES_GRAMMAR_IDENTIFIERS:
        return process_sql_postgres.tokenize(string)
    else:
        raise KeyError(f"no such grammar: {grammar}")


def get_sql(schema, query, grammar="spider"):
    if grammar in SPIDER_GRAMMAR_IDENTIFIERS:
        return process_sql_spider.get_sql(schema, query)
    elif grammar in POSTGRES_GRAMMAR_IDENTIFIERS:
        return process_sql_postgres.get_sql(schema, query)
    else:
        raise KeyError(f"no such grammar: {grammar}")
