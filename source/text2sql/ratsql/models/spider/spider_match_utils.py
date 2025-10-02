import re
import string

import nltk.corpus
try:
    STOPWORDS = set(nltk.corpus.stopwords.words('english'))
except:
    import nltk
    nltk.download("stopwords")
    nltk.download('punkt')
    STOPWORDS = set(nltk.corpus.stopwords.words('english'))

PUNKS = set(a for a in string.punctuation)


def is_int(text):
    try:
        int(text)
        return True
    except:
        return False


def assert_idx(str_idx, col_len, row_len):
    str_idx_split = str_idx.split(',')
    assert len(str_idx_split) == 2
    assert is_int(str_idx_split[0])
    assert is_int(str_idx_split[1])
    assert int(str_idx_split[0]) < col_len
    assert int(str_idx_split[1]) < row_len


# schema linking, similar to IRNet
def compute_schema_linking(question, column, table, manual_linking_info=None):
    def partial_match(x_list, y_list):
        x_str = " ".join(x_list)
        y_str = " ".join(y_list)
        if x_str in STOPWORDS or x_str in PUNKS:
            return False
        if re.match(rf"\b{re.escape(x_str)}\b", y_str):
            assert x_str in y_str
            return True
        else:
            return False

    def exact_match(x_list, y_list):
        x_str = " ".join(x_list)
        y_str = " ".join(y_list)
        if x_str == y_str:
            return True
        else:
            return False

    q_col_match = dict()
    q_tab_match = dict()

    col_id2list = dict()
    for col_id, col_item in enumerate(column):
        if col_id == 0:
            continue
        col_id2list[col_id] = col_item

    tab_id2list = dict()
    for tab_id, tab_item in enumerate(table):
        tab_id2list[tab_id] = tab_item

    new_question = []
    for q in question:
        if q.upper() != q.lower():
            new_question.append(q)
    question = new_question

    # 5-gram
    n = 5
    while n > 0:
        for i in range(len(question) - n + 1):
            n_gram_list = question[i:i + n]
            n_gram = " ".join(n_gram_list)
            if len(n_gram.strip()) == 0:
                continue
            # exact match case
            for col_id in col_id2list:
                if exact_match(n_gram_list, col_id2list[col_id]):
                    for q_id in range(i, i + n):
                        q_col_match[f"{q_id},{col_id}"] = "CEM"
            for tab_id in tab_id2list:
                if exact_match(n_gram_list, tab_id2list[tab_id]):
                    for q_id in range(i, i + n):
                        q_tab_match[f"{q_id},{tab_id}"] = "TEM"

            # partial match case
            for col_id in col_id2list:
                if partial_match(n_gram_list, col_id2list[col_id]):
                    for q_id in range(i, i + n):
                        if f"{q_id},{col_id}" not in q_col_match:
                            q_col_match[f"{q_id},{col_id}"] = "CPM"
            for tab_id in tab_id2list:
                if partial_match(n_gram_list, tab_id2list[tab_id]):
                    for q_id in range(i, i + n):
                        if f"{q_id},{tab_id}" not in q_tab_match:
                            q_tab_match[f"{q_id},{tab_id}"] = "TPM"
        n -= 1
    if manual_linking_info:
        for idx_str in manual_linking_info['CEM']:
            assert_idx(idx_str, len(question), len(column))
            q_col_match[idx_str] = 'CEM'
        for idx_str in manual_linking_info['CPM']:
            assert_idx(idx_str, len(question), len(column))
            q_col_match[idx_str] = 'CPM'
        for idx_str in manual_linking_info['TEM']:
            assert_idx(idx_str, len(question), len(table))
            q_tab_match[idx_str] = 'TEM'
        for idx_str in manual_linking_info['TPM']:
            assert_idx(idx_str, len(question), len(table))
            q_tab_match[idx_str] = 'TPM'
        # Exclude
        for idx_str in manual_linking_info['CEM_exclude']:
            assert_idx(idx_str, len(question), len(column))
            assert q_col_match[idx_str] == 'CEM'
            del q_col_match[idx_str]
        for idx_str in manual_linking_info['CPM_exclude']:
            assert_idx(idx_str, len(question), len(column))
            assert q_col_match[idx_str] == 'CPM'
            del q_col_match[idx_str]
        for idx_str in manual_linking_info['TEM_exclude']:
            assert_idx(idx_str, len(question), len(table))
            assert q_tab_match[idx_str] == 'TEM'
            del q_tab_match[idx_str]
        for idx_str in manual_linking_info['TPM_exclude']:
            assert_idx(idx_str, len(question), len(table))
            assert q_tab_match[idx_str] == 'TPM'
            del q_tab_match[idx_str]
            
    return {"q_col_match": q_col_match, "q_tab_match": q_tab_match}


def compute_cell_value_linking(tokens, schema, manual_linking_info=None):
    def isnumber(word):
        try:
            float(word)
            return True
        except:
            return False

    def db_word_match(word, column, table, db_utils, column_type='text'):
        def is_number(word):
            try:
                float(word)
                return True
            except:
                return False

        if db_utils is None:
            return False
        
        cursor = db_utils.cursor()
        word = word.strip("'")
        if column_type in ['ARRAY', 'timestamp without time zone']:
            return False
        elif column_type in ['numeric', 'integer', 'double precision', 'bigint', 'smallint']:
            if not is_number(word):
                return False
            p_str = f"select \"{column}\" from {table} where \"{column}\" = {word} limit 1"
        else:
            # Here we handle all column types in sqlite system
            p_str = f"select \"{column}\" from {table} where \"{column}\" like '{word} %' or \"{column}\" like '% {word}' or " \
                    f"\"{column}\" like '% {word} %' or \"{column}\" like '{word}' limit 1"
        # For debugging purpose: avoid catching exceptions
        try:
            cursor.execute(p_str)
            p_res = cursor.fetchall()
            if len(p_res) == 0:
                return False
            else:
                return p_res
        except Exception as e:
            return False

    num_date_match = {}
    cell_match = {}

    for q_id, word in enumerate(tokens):
        if len(word.strip()) == 0:
            continue
        if word in STOPWORDS or word in PUNKS:
            continue
        if word.upper() == word.lower():
            continue

        num_flag = isnumber(word)

        CELL_MATCH_FLAG = "CELLMATCH"

        for col_id, column in enumerate(schema.columns):
            if col_id == 0:
                assert column.orig_name == "*"
                continue

            # word is number 
            if num_flag:
                if column.type in ["number", "time"]:  # TODO fine-grained date
                    num_date_match[f"{q_id},{col_id}"] = column.type.upper()
            else:
                ret = db_word_match(word, column.orig_name, column.table.orig_name, schema.connection, column_type=column.type)
                if ret:
                    # print(word, ret)
                    cell_match[f"{q_id},{col_id}"] = CELL_MATCH_FLAG

    if manual_linking_info:
        for idx_str in manual_linking_info['CM']:
            assert_idx(idx_str, len(tokens), len(schema.columns))
            cell_match[idx_str] = 'CELLMATCH'
        for idx_str in manual_linking_info['NM']:
            assert_idx(idx_str, len(tokens), len(schema.columns))
            num_date_match[idx_str] = 'NUMBER'
        for idx_str in manual_linking_info['DM']:
            assert_idx(idx_str, len(tokens), len(schema.columns))
            num_date_match[idx_str] = 'TIME'
        # Exclude
        for idx_str in manual_linking_info['CM_exclude']:
            assert_idx(idx_str, len(tokens), len(schema.columns))
            assert cell_match[idx_str] == 'CELLMATCH'
            del cell_match[idx_str]
        for idx_str in manual_linking_info['NM_exclude']:
            assert_idx(idx_str, len(tokens), len(schema.columns))
            assert num_date_match[idx_str] == 'NUMBER'
            del num_date_match[idx_str]
        for idx_str in manual_linking_info['DM_exclude']:
            assert_idx(idx_str, len(tokens), len(schema.columns))
            assert num_date_match[idx_str] == 'TIME'
            del num_date_match[idx_str]

    cv_link = {"num_date_match": num_date_match, "cell_match": cell_match}
    return cv_link
