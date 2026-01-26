import pymysql
import sqlparse
import copy
import re
from openai import OpenAI

# MySQL Info
HOST = '183.69.138.62'
PORT = 33666
USER = '严丹丹'
PASSWD = '123456789'
DB_NAME = 'r_d_test'

MAX_REVISE_ROUND = 4

REVISE_PROMPT ='''
以下是一个在MySQL上执行的语句：
{wrong_sql}

发生报错：{error}

请你修改给出正确的SQL语句，用<SQL>xxx</SQL>形式给出修改后的SQL语句。
'''.strip()

# Selector Prompt (保持不变)
SELECT_PROMPT="""
以下是数据库的所有表和字段信息：
{database_information}
以下是一个关于该数据库的问题：
{question}
请你根据这个问题从以上所有表中选出最相关至多8个表，并且返回表的英文名，用<RES>table_name1, table_name2, ...</RES> （用逗号分隔每个table_name，整体结果包裹在<RES></RES>之间）的形式给出结果。
"""

# SQL Generation Prompt (针对 Qwen Chat 优化)
# 我们不再使用续写模式，而是使用指令模式
SQL_SYSTEM_PROMPT = """You are an expert in MySQL. 
Please generate a valid SQL query to answer the user's question based on the provided database schema.

Requirements:
1. Output **only** the SQL query. Do not add any explanations, markdown formatting (like ```sql), or conversational text.
2. If you cannot answer, return 'I do not know'.
"""

SQL_USER_TEMPLATE = """### Database Schema
{schema}

### Question
{question}
"""

class DB:
    def __init__(self, 
                 base_url='https://api.claudeshop.top/v1', 
                 model_name='gpt-4o' ,
                 api_key = "sk-pMyKRA0l2LRns2k0BuBipp1gDmI2HG98ZXATEyOS0MMAJNJH"
                 ):
        
        # init MySQL
        self.conn = None
        self.cur = None
        self.host = HOST
        self.port = PORT
        self.user = USER
        self.passwd = PASSWD
        self.db_name = DB_NAME
        self._init_mysql()
        
        # Cache comments
        self.detailed_comments = None
        self.table_comments = None
        self.detailed_comments = self._extract_all_table_detailed_comments()
        self.table_comments = copy.deepcopy(self.detailed_comments)
        if self.table_comments:
            for k, v in self.table_comments.items():
                if 'column_comments' in v:
                    del v['column_comments']
        
        # Init OpenAI Client (Unified)
        # Selector 和 SQLCoder 使用同一个客户端和模型
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        self.model_name = model_name
        
        print(f"DB initialized. All-in-Qwen Mode @ {base_url} (model='{model_name}')")

    def _init_mysql(self):
        self.conn = pymysql.connect(host=self.host, port=self.port, user=self.user, passwd=self.passwd, db=self.db_name, charset='utf8')
        self.cur = self.conn.cursor()

    # --- Schema Helpers (Unchanged) ---
    def _format_schema(self, table_names):
        schema = ''
        for table in table_names:
            schema += self._get_create_statement(table) + '\n\n'
        return schema

    def _get_all_tables(self):
        """返回当前数据库中所有表名"""
        if self.detailed_comments is not None:
            return self.detailed_comments.keys()
        
        self.cur.execute("SHOW TABLES")
        tables = [row[0] for row in self.cur.fetchall()]
        return tables

    def _get_create_statement(self, table_name):
        """返回指定表的 CREATE TABLE 语句"""
        self.cur.execute(f"SHOW CREATE TABLE `{table_name}`")
        result = self.cur.fetchone()
        return result[1] if result else None
    
    def _extract_all_table_comments(self):
        """
        返回值:
            dict : {表名: 注释} 的字典映射
        """
        if self.table_comments is not None:
            return self.table_comments
        
        sql = """
        SELECT table_name, table_comment
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
        """
        result = self.execute_sql(sql)
        # print(result)
        if "data" in result:
            return {row["TABLE_NAME"]: row["TABLE_COMMENT"] for row in result["data"]}
            # return {row["table_name"]: row["table_comment"] for row in result["data"]}
        else:
            return {}
        
    def _extract_column_comments(self, table_name: str):
        """
        返回值:
            List[dict] : 每个字段一条记录，包含字段名、类型、注释，例如：
                [
                    {"column_name": "id", "column_type": "bigint(20)", "column_comment": "id"},
                    {"column_name": "group_name", "column_type": "varchar(128)", "column_comment": "考勤组名字"},
                    ...
                ]
        """
        sql = f"""
        SELECT column_name, column_type, column_comment
        FROM information_schema.columns
        WHERE table_schema = DATABASE() AND table_name = '{table_name}'
        """
        result = self.execute_sql(sql)
        return result.get("data", [])
    
    def _extract_all_table_detailed_comments(self):
        """
        返回值:
            dict: 每张表对应的注释信息结构如下：
            {
                'table_name': {
                    'table_comment': '表的注释',
                    'column_comments': [
                        '字段1注释',
                        '字段2注释',
                        ...
                    ]
                },
                ...
            }
        """
        
        if self.detailed_comments is not None:
            return self.detailed_comments
        
        table_comments = self._extract_all_table_comments()
        result = {}

        for table_name, table_comment in table_comments.items():
            columns = self._extract_column_comments(table_name)
            # column_comments = [col["column_comment"] for col in columns]
            column_comments = [col["COLUMN_COMMENT"] for col in columns]
            result[table_name] = {
                "table_comment": table_comment,
                "column_comments": column_comments
            }

        return result
    
    def get_database_comments(self) -> str:
        """
        获取数据库所有表的信息

        返回:
            str: 每个表一行的字符串形式，便于语言模型理解和快速处理。
            每一行形如table_name (表注释): [字段注释1, 字段注释2, ...]
        """
        table_comments = self._extract_all_table_detailed_comments()
        lines = []
        
        # detailed version
        for table_name, info in table_comments.items():
            table_comment = info.get("table_comment", "")
            column_comments = info.get("column_comments", [])
            column_str = ", ".join(column_comments)
            line = f"{table_name} ({table_comment}): [{column_str}]"
            lines.append(line)
        return "\n\n".join(lines)

    # --- Core Logic ---

    def select_table(self, question, error_context=None):
        '''
        Task 1: Select Tables using Qwen Chat
        Args:
            error_context (str): 之前失败的错误信息上下文
        '''
        # 如果有错误历史，将其加入到问题描述中，提示模型避坑
        current_question = question
        if error_context:
            current_question += f"\n\n[Important Reference - Previous Failed Attempts]:\nWe tried to generate SQL previously but failed. Here is the error history:\n{error_context}\nPlease re-evaluate the table selection based on this error."

        query = SELECT_PROMPT.format(database_information=self.get_database_comments(), question=current_question)
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant specialized in database schema selection."},
            {"role": "user", "content": query}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1, 
                max_tokens=1024,
                stop=["</RES>"] 
            )
            
            content = response.choices[0].message.content
            if not content.strip().endswith("</RES>"):
                 content += "</RES>"

            print(f"[Selector Output]: {content}")

            match = re.search(r"<RES>(.*?)</RES>", content, re.DOTALL)
            if match:
                table_str = match.group(1)
                selected_raw = [t.strip() for t in table_str.split(",") if t.strip()]
                
                # --- 新增：硬过滤 ---
                # 获取真实存在的所有表名
                all_real_tables = self.detailed_comments.keys() if self.detailed_comments else []
                # 只保留真实存在的表
                selected_table_name = [t for t in selected_raw if t in all_real_tables]
                
                # 如果过滤后发现有被剔除的表，打印个警告方便调试
                if len(selected_raw) != len(selected_table_name):
                    print(f"Warning: Hallucinated tables removed: {set(selected_raw) - set(selected_table_name)}")
                # ------------------
            else:
                selected_table_name = []
            
            return selected_table_name

        except Exception as e:
            print(f"Error in select_table: {e}")
            return []

    def generate_sql(self, selected_table_name, question, error_context=None):
        '''
        Task 2: Generate SQL using Qwen Chat (Updated)
        '''
        schema = self._format_schema(selected_table_name)
        
        # 如果有错误历史，加入 Prompt
        current_question = question
        if error_context:
            current_question += f"\n\n[Previous Failed Attempts & Errors]:\n{error_context}\nPlease avoid these errors and generate a correct SQL."

        # 组装 User Message
        user_content = SQL_USER_TEMPLATE.format(schema=schema, question=current_question)
        
        messages = [
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.0,
                max_tokens=1024,
            )
            
            raw_output = response.choices[0].message.content
            print(f"[SQLCoder Output]: {raw_output}")
            
            sql_code = raw_output.strip()
            # 提取 SQL (兼容 Markdown 和纯文本)
            match = re.search(r"```sql(.*?)```", sql_code, re.DOTALL)
            if match:
                sql_code = match.group(1).strip()
            else:
                match_generic = re.search(r"```(.*?)```", sql_code, re.DOTALL)
                if match_generic:
                    sql_code = match_generic.group(1).strip()
            
            sql_code = sqlparse.format(sql_code, reindent=True)
            return sql_code

        except Exception as e:
            print(f"Error in generate_sql: {e}")
            return ""

    def revise_sql(self, wrong_sql, res):
        # 依然可以用 Qwen 自己来修，或者保持原有的 reasoning-LLM
        # 这里演示如何用当前的 Qwen 来修
        prompt = REVISE_PROMPT.format(wrong_sql=wrong_sql, error=res['error'])
        messages = [
             {"role": "system", "content": "You are a SQL debugging expert. Output only the corrected SQL wrapped in <SQL> tags."},
             {"role": "user", "content": prompt}
        ]
        try:
             response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.0
            )
             content = response.choices[0].message.content
             match = re.search(r"<SQL>(.*?)</SQL>", content, re.DOTALL)
             if match:
                 return match.group(1).strip()
             return wrong_sql
        except:
             return wrong_sql

    def execute_sql(self, sql):
        # ... (保持不变) ...
        try:
            self.conn.ping(reconnect=True)
            self.cur = self.conn.cursor()
            count = self.cur.execute(sql)
            if sql.strip().lower().startswith("select"):
                rows = self.cur.fetchall()
                if self.cur.description:
                    fields = [desc[0] for desc in self.cur.description]
                    data = [dict(zip(fields, row)) for row in rows]
                else:
                    fields = []; data = []
                return {"rowcount": count, "fields": fields, "data": data}
            else:
                self.conn.commit()
                return {"rowcount": count, "message": "Success"}
        except Exception as e:
            return {"error": str(e)}

    def query_db(self, text_query):
        """
        全链路重试机制：
        Attempt 1: 正常流程
        If Error: 收集错误 -> 添加到 Context -> 重新 Select Table -> 重新 Generate SQL
        """
        error_history = ""
        last_error_msg = ""
        
        # 这里的 MAX_REVISE_ROUND 现在代表“整个流程重试的次数”
        for attempt in range(MAX_REVISE_ROUND):
            print(f"--- Pipeline Execution Round {attempt + 1} ---")
            
            try:
                # 1. 选表 (带入之前的错误上下文)
                selected = self.select_table(text_query, error_context=error_history)
                print(f"Selected Tables: {selected}")
                
                if not selected:
                    # 如果选不出表，记录错误并continue，看看下次能不能选出来
                    current_error = "Error: No tables were selected."
                    error_history += f"Round {attempt+1} Failed: {current_error}\n"
                    print(current_error)
                    continue
                
                # 2. 生成 SQL (带入之前的错误上下文)
                sql = self.generate_sql(selected, text_query, error_context=error_history)
                print(f"Generated SQL: {sql}")
                
                # 3. 执行 SQL
                res = self.execute_sql(sql)
                
                # 4. 检查结果
                if 'error' in res:
                    print(f"Execution Error: {res['error']}")
                    # 记录错误信息，供下一轮循环使用
                    last_error_msg = res['error']
                    # 格式化错误记录：记录是哪条SQL导致了什么错
                    error_history += f"Round {attempt+1} SQL:\n{sql}\nError:\n{res['error']}\n----------------\n"
                    continue # 进入下一轮重试
                else:
                    # 成功！直接返回结果
                    print("SQL Executed Successfully.")
                    return res
                    
            except Exception as e:
                # 捕获 Pipeline 内部的其他异常
                print(f"Pipeline Exception: {e}")
                error_history += f"Round {attempt+1} Exception: {str(e)}\n"
                last_error_msg = str(e)
                continue

        # 如果循环结束还没有返回，说明彻底失败
        raise RuntimeError(f"Database query failed after {MAX_REVISE_ROUND} attempts. Last Error: {last_error_msg}")

if __name__ == "__main__":
    db = DB()