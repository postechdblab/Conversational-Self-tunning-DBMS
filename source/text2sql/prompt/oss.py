gpt_prompt = """You are a {dialect} data analyst. You are given a database schema below.

**Schema:**
{db_schema}

**Previous Questions:**
{history}

**Question:**
{question}

Please read and understand the database schema carefully, and generate an executable SQL query based on the user's question. Return only the SQL query wrapped in ```sql and ``` code blocks.
```sql
"""

gpt_fix_prompt = """You are a {dialect} data analyst. Verify that the generated SQL query accurately captures the semantic meaning of the natural language question.

**Schema:**
{db_schema}

**Previous Questions:**
{history}

**Question:**
{question}

**Original SQL Query:**
{original_sql}

Verify if the SQL query's semantic meaning matches the question's intent. Check for:
1. Semantic equivalence between the question and the original SQL query
2. Correct table and column names from the schema
3. Valid {dialect} syntax

If the original SQL query is correct, return it as-is. If not, generate a corrected version. Return only the SQL query wrapped in ```sql and ``` code blocks.
```sql
"""
