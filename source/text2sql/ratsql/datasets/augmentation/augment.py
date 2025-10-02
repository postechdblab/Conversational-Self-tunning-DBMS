import os
import json
import tqdm
import copy
import time
import random
import functools
import itertools

TYPES = ["integer", "double precision","numeric", "smallint", "bigint", "array", "character",
         "character varying", "text", "timestamp without time zone"]
NUMTYPES = ["integer", "double precision","numeric", "smallint", "bigint",]

def read_lines(path):
    def remove_new_line(text):
        return text.strip("\n")
    def double_to_single_space(text):
        return text.replace("  ", " ")
    def lower(text):
        return text.lower()
    with open(path, "r") as f:
        return [functools.reduce(lambda x, f: f(x), [line, lower, double_to_single_space, remove_new_line]) for line in f.readlines()]

def append_and_write_data(data, path, aux_path):
    with open(aux_path, "r") as f:
        lines = f.readlines()
    
    with open(path, "w") as f:
        for line in lines:
            f.write(line)
        for datum in data:
            f.write(f"{datum['sql']}\t{datum['question']}\n")

def replace_variables_in_text(text, variables, cache={}, is_question=False):
    """
    Input: question sentence and variable dictionary.
    Return: list of question sentences without variables in it.
    Description: Recursively replace one variable with all possible words.
    """
    new_text = text
    for key, values in variables.items():
        for key_num in range(3):
            if key_num == 0:
                key_mention = f"<{key}>"
            else:
                key_mention = f"<{key}{key_num}>"
            if key_mention in text:
                start_idx = text.index(key_mention)
                end_idx = start_idx + len(key_mention)
                # Select variable
                if key_mention.strip('<>') in cache:
                    value = cache[key_mention.strip('<>')]
                else:
                    value = random.choice(values)
                    cache[key_mention.strip('<>')] = value
                if value == 'null':
                    tmp_text = text[:start_idx] + text[end_idx:]
                else:
                    if not is_question and ('month' in key or 'day' in key):
                        value = "{:02d}".format(int(value))
                    tmp_text = text[:start_idx] + value + text[end_idx:]
                tmp_text = tmp_text.replace("  ", " ").strip(' ')
                new_text = replace_variables_in_text(tmp_text, variables, cache, is_question=is_question)
    # Return question itself if there was no variable
    return new_text

def parse_types(line, types):
    assert line.startswith("type:") and line.endswith(")"), f"Bad line: {line}"
    line = line.split(' (')[1][:-1]
    col_types = {}
    for item in line.split(','):
        name, type_name = [tmp.strip() for tmp in item.split(":")]
        if 'column' in name:
            if type_name[0] == '<'  and type_name[-1] == '>':
                assert type_name[1:-1] in types
                col_types[name] = types[type_name[1:-1]]
            else:
                assert type_name in TYPES
                col_types[name] = [type_name]
    return {"col_type": col_types}

def parse_same_table(line):
    assert line.startswith("same_table:")
    line = ":".join(line.split(':')[1:]).strip(" ")
    items = line.split(';')
    list_of_set = []
    for item in items:
        local_set = set()
        item = item.strip(" ()")
        values = item.split(',')
        for value in values:
            value = value.strip(" ")
            local_set.add(value)
        list_of_set.append(local_set)
    return {"same_table": list_of_set}

def parse_same_name(line):
    assert line.startswith("same_name:")
    line = ":".join(line.split(':')[1:]).strip(" ")
    items = line.split(';')
    list_of_set = []
    for item in items:
        local_set = set()
        item = item.strip(" ()")
        values = item.split(',')
        for value in values:
            value = value.strip(" ")
            local_set.add(value)
        list_of_set.append(local_set)
    return {"same_name": list_of_set}

def parse_set_name(line):
    assert line.startswith("set_name:")
    line = ":".join(line.split(':')[1:]).strip(" ()")
    items = line.split(',')
    dict = {}
    for item in items:
        key, value = item.split(':')
        key, value = key.strip(' '), value.strip(' ')
        dict[key] = value
    return {"set_name": dict}

def parse_set_table(line):
    assert line.startswith("set_table:")
    line = ":".join(line.split(':')[1:]).strip(" ")
    items = line.split(';')
    dict = {}
    for item in items:
        item = item.strip(" ()")
        key, values = item.split(':')
        values = values.split(',')
        for value in values:
            value = value.strip(" ")
            dict[value] = key
    return {"set_table": dict}

def read_templates(path):
    VARIABLE_DEFINE_START = "!define variable start"
    VARIABLE_DEFINE_END = "!define variable end"
    TYPE_DEFINE_START = "!define type start"
    TYPE_DEFINE_END = "!define type end"
    def is_empty(line):
        line = line.strip("\n").replace(" ", "")
        return line == ""
    def is_comment(line):
        return len(line) > 0 and line[0] == '#'
    def is_sql(line):
        return len(line) > 5 and line[:6] == "select"
    def is_special(line):
        return len(line) > 0 and line[0] == "!" and \
                    line in [VARIABLE_DEFINE_START,VARIABLE_DEFINE_END,
                            TYPE_DEFINE_START, TYPE_DEFINE_END]
    def parse_declaration(line):
        line = line.replace(" = ", "=")
        line = line.replace(" =", "=")
        line = line.replace("= ", "=")
        assert "=" in line
        key, values = line.split("=")
        assert values[0] == '[' and values[-1] == ']'
        values = values[1:-1].split('|')
        return {key: values}

    defined_types = {}
    defined_variables = {}
    templates = []
    # Read in lines
    lines = read_lines(path)
    last_sql = None
    last_question = None
    last_constraints = dict()
    is_defining_variable = False
    is_defining_type = False
    for line_num, line in enumerate(lines):
        # Skip line
        if is_comment(line):
            pass
        # Indicator line
        elif is_special(line):
            if "type" in line:
                is_defining_type = 'start' in line
            elif "variable" in line:
                is_defining_variable = 'start' in line
            else:
                raise RuntimeError(f"Bad line: {line}")
        # Read variable
        elif is_defining_variable:
            defined_variables.update(parse_declaration(line))
        elif is_defining_type:
            defined_types.update(parse_declaration(line))
        # Template
        else:
            if is_empty(line):
                if last_sql and last_question and last_constraints:
                    # Save new data
                    variation_num = 5
                    for _ in range(variation_num):
                        cache_dic = {}
                        new_question = replace_variables_in_text(last_question, defined_variables, cache_dic, is_question=True)
                        new_sql = replace_variables_in_text(last_sql, defined_variables, cache_dic, is_question=False)
                        template = {
                            "sql": new_sql,
                            "question": new_question,
                            "constraints": last_constraints
                        }
                        templates.append(template)
                    # Reset
                    last_sql = None
                    last_question = None
                    last_constraints = dict()
                else:
                    continue
            elif is_sql(line):
                assert last_sql is None, f"Bad line order at line:{line_num}"
                last_sql = line
            elif last_sql and not last_question:
                # is question
                last_question = line
            elif last_sql and last_question:
                # Read in column types
                if 'type:' in line:
                    last_constraints.update(parse_types(line, defined_types))
                elif 'set_name:' in line:
                    last_constraints.update(parse_set_name(line))
                elif 'set_table:' in line:
                    last_constraints.update(parse_set_table(line))
                elif 'same_table:' in line:
                    last_constraints.update(parse_same_table(line))
                elif 'same_name:' in line:
                    last_constraints.update(parse_same_name(line))
                else:
                    raise RuntimeError(f"Bad line: {line}")
            else:
                raise RuntimeError(f"Bad line: {line}")
    return templates

def read_schema(path):
    with open(path, 'r') as f:
        return json.load(f)

def create_data(template, schema):
    COLUMN_PREFIX = "[column"
    def sample(list):
        return random.sample(list, 1)[0]
    def find_indices_of_all_substr(text, prefix=COLUMN_PREFIX):
        index = 0
        indices = []
        while True:
            index = text.find(prefix, index)
            if index == -1:
                break
            indices.append(index)
            index += len(prefix)
        return indices
    def count_distinct_schema_entity(text, prefix=COLUMN_PREFIX):
        ids = set()
        start_indices = find_indices_of_all_substr(text, prefix=prefix)
        for start_idx in start_indices:
            id = int(text[start_idx+len(prefix):].split(".")[0])
            ids.add(id)
        return len(ids)
    def get_col_var_id(text):
        assert text.startswith("column")
        return int(text[len("column"):])
    
    def is_same_table(text1, text2):
        if '.' in text1:
            text1 = text1.split('.')[1]
        if '.' in text2:
            text2 = text2.split('.')[1]
        return text1 == text2

    def select_columns(columns, constraints, required_num=1):
        tmp = set()
        trial_num = 6
        for _ in range(trial_num):
            result = _select_columns(columns, constraints, required_num=required_num)
            if result:
                tmp.add(tuple(result))
        return list(tmp)

    def find_idx(original_list, col):
        for idx, item in enumerate(original_list):
            if item['name'] == col['name'] and item['table']['name'] == col['table']['name']:
                return idx
        raise RuntimeError("Should not be here")

    def _select_columns(columns, constraints, required_num=1):
        assert len(columns) > 0
        columns_to_be_wasted = copy.deepcopy(columns)
        selected_columns = []
        for target_id in range(1, required_num+1):
            filtered_columns = columns_to_be_wasted
            target_key = f"column{target_id}"
            # Filter by constraints
            if 'col_type' in constraints:
                possible_col_types = constraints['col_type'][target_key]
                filtered_columns = [col for col in filtered_columns if col['type'] in possible_col_types]
            if 'set_name' in constraints:
                if target_key in constraints['set_name']:
                    target_name = constraints['set_name'][target_key]
                    filtered_columns = [col for col in filtered_columns if col['name'] == target_name]
            if 'set_table' in constraints:
                if target_key in constraints['set_table']:
                    target_table = constraints['set_table'][target_key]
                    filtered_columns = [col for col in filtered_columns if is_same_table(col['table']['name'], target_table)]
            if 'same_name' in constraints:
                for col_set in constraints['same_name']:
                    if target_key in col_set:
                        related_col_var_id = sorted([get_col_var_id(c) for c in col_set if c != target_key])[0]
                        if related_col_var_id < target_id:
                            related_column = selected_columns[related_col_var_id-1]
                            filtered_columns = [col for col in filtered_columns if col['name'] == related_column['name']]
                            break
            if 'same_table' in constraints:
                for col_set in constraints['same_table']:
                    if target_key in col_set:
                        related_col_var_id = sorted([get_col_var_id(c) for c in col_set if c != target_key])[0]
                        if related_col_var_id < target_id:
                            related_column = selected_columns[related_col_var_id-1]
                            filtered_columns = [col for col in filtered_columns if is_same_table(col['table']['name'], related_column['table']['name'])]
                            break
            # Random selected from 
            if filtered_columns:
                selected_col = random.choice(filtered_columns)
                columns_to_be_wasted.remove(selected_col)
                selected_columns.append(selected_col)
            else:
                return None

        # Selected column to id
        selected_columns_as_idx = [find_idx(columns, col) for col in selected_columns]

        return selected_columns_as_idx
    def replace_column_placeholders(text, columns, sampled_col_ids, value_cache_dic, use_quotation=False):
        # Replace placeholders in query
        while True:
            start_index = text.find(COLUMN_PREFIX)
            if start_index == -1:
                break
            # Replace
            tmp = text[start_index+len(COLUMN_PREFIX):].split('.')
            col_id = sampled_col_ids[int(tmp[0])-1]
            placeholder_type = tmp[1].split("]")[0]
            if placeholder_type == 'table':
                if 'name' in tmp[2]:
                    end_idx = text.index(".table.name]") + len(".table.name]")
                    replace_string = columns[col_id]['table']['name']
                elif 'mention' in tmp[2]:
                    end_idx = text.index(".table.mention]") + len(".table.mention]")
                    replace_string = sample(columns[col_id]['table']['mentions'])
                else:
                    raise RuntimeError("Should not be here")
            elif placeholder_type == 'name':
                end_idx = text.index(".name]") + len(".name]")
                replace_string = columns[col_id]['name']
            elif placeholder_type == 'mention':
                end_idx = text.index(".mention]") + len(".mention]")
                replace_string = sample(columns[col_id]['mentions'])
            elif placeholder_type == 'value':
                end_idx = text.index(".value]") + len(".value]")
                if col_id not in value_cache_dic:
                    replace_string = sample(columns[col_id]['values'])
                    value_cache_dic[col_id] = replace_string
                else:
                    replace_string = value_cache_dic[col_id]
                if use_quotation and columns[col_id]['type'] not in NUMTYPES:
                    replace_string = f"\'{replace_string}\'"
                else:
                    replace_string
            else:
                raise RuntimeError("Should not be here")
            text = text[:start_index] + replace_string + text[end_idx:]
        return text
    # Begin
    query, question, constraints = template['sql'], template['question'], template['constraints']
    # Count distinct columns, tables
    distinct_col_num = count_distinct_schema_entity(query, COLUMN_PREFIX)
    distinct_col_num_ = count_distinct_schema_entity(question, COLUMN_PREFIX)
    distinct_col_num = max(distinct_col_num, distinct_col_num_)
    
    # Append table to columns
    for table in schema['tables']:
        for col in table['columns']:
            col['table'] = table

    final_data = []
    # Use multiple tables
    if len(constraints) > 1:
        columns = list(itertools.chain(*[table['columns'] for table in schema['tables']]))
        if len(columns) >= distinct_col_num and distinct_col_num > 0:
                col_pairs = select_columns(columns, constraints, distinct_col_num) 
                for col_pair in col_pairs:
                    value_cache_dic = {}
                    new_query = replace_column_placeholders(query, columns, col_pair, value_cache_dic, use_quotation=True)
                    new_question = replace_column_placeholders(question, columns, col_pair, value_cache_dic, use_quotation=False)
                    new_data = {'sql': new_query, 'question': new_question}
                    if new_data not in final_data:
                        final_data.append({'sql': new_query, 'question': new_question})
    # Use single table
    else:
        for table in schema['tables']:
            columns = table['columns']
            if len(columns) >= distinct_col_num and distinct_col_num > 0:
                col_pairs = select_columns(columns, constraints, distinct_col_num) 
                for col_pair in col_pairs:
                    value_cache_dic = {}
                    new_query = replace_column_placeholders(query, columns, col_pair, value_cache_dic, use_quotation=True)
                    new_question = replace_column_placeholders(question, columns, col_pair, value_cache_dic, use_quotation=False)
                    new_data = {'sql': new_query, 'question': new_question}
                    if new_data not in final_data:
                        final_data.append({'sql': new_query, 'question': new_question})
    return final_data

def augmentation(templates, schema):
    final_data = []
    for idx, template in enumerate(tqdm.tqdm(templates)):
        new_data = create_data(template, schema)
        final_data += new_data
        # print(f"idx:{idx} new_data:{len(new_data)} total:{len(final_data)}")
    print(f"Total generated data: {len(final_data)}")
    return final_data

def filter_repeated_templates(templates):
    def template_key(template):
        return f"sql:{template['sql']}_question:{template['question']}"
    cache = set()
    unique_templates = []
    for template in templates:
        key = template_key(template)
        if key not in cache:
            unique_templates.append(template)
            cache.add(key)
    print(f"Filtering templates {len(templates)} -> {len(unique_templates)}")
    return unique_templates


if __name__ == "__main__":
    random.seed(0)
    # Paths
    workspaceFolder = "/data/hkkang/NL2QGM"
    template_path = os.path.join("ratsql/datasets/augmentation/template.txt")
    schema_path = os.path.join("ratsql/datasets/augmentation/schema.txt")
    
    aux_path = os.path.join(workspaceFolder, "data/samsung-addop-hkkang/all_original.tsv")
    outpath = os.path.join("all.tsv")

    # Load information
    templates = read_templates(template_path)
    templates = filter_repeated_templates(templates)
    schema = read_schema(schema_path)

    # Create All Possible Data
    data = augmentation(templates, schema)

    # # Dump data
    append_and_write_data(data, outpath, aux_path)

    print("Done!")
