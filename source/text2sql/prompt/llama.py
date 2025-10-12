llama_prompt = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are now a {dialect} data analyst, and you are given a database schema as follows:<|eot_id|><|start_header_id|>user<|end_header_id|>

【Schema】
{db_schema}

【Previous Questions】
{history}

【Question】
{question}

Please read and understand the database schema carefully, and generate an executable SQL based on the user's question. The generated SQL is protected by ```sql and ```.<|eot_id|><|start_header_id|>assistant<|end_header_id|>
```sql
"""

llama_fix_prompt = """<|begin_of_text|><|start_header_id|>system<|end_header_id|>

You are now a {dialect} data analyst. Verify that the generated SQL query accurately captures the semantic meaning of the natural language question.<|eot_id|><|start_header_id|>user<|end_header_id|>

【Schema】
{db_schema}

【Previous Questions】
{history}

【Question】
{question}

【Original SQL Query】
{original_sql}

Verify if the SQL query's semantic meaning matches the question's intent. Check for:
1. Semantic equivalence between the question and the original SQL query
2. Correct table and column names from the schema
3. Valid {dialect} syntax

If the original SQL query is correct, return it as-is. If not, generate a corrected version.

The SQL query is protected by ```sql and ```.<|eot_id|><|start_header_id|>assistant<|end_header_id|>
```sql
"""
