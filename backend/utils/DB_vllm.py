import pymysql
import sqlparse
import copy
import re
from openai import OpenAI
from utils.functions import query_LLM_ollama

# predefined info
HOST = '183.69.138.62'
PORT = 33666
USER = '严丹丹'
PASSWD = '123456789'
DB_NAME = 'r_d_test'

TEMPLATE = """### Task
Generate a SQL query to answer [QUESTION]{question}[/QUESTION]

### Instructions
- If you cannot answer the question with the available database schema, return 'I do not know'
- Remember that revenue is price multiplied by quantity
- Remember that cost is supply_price multiplied by quantity

### Database Schema
{schema}

### Answer
Given the database schema, here is the SQL query that answers [QUESTION]{question}[/QUESTION]
[SQL]
"""

MAX_REVISE_ROUND = 5

REVISE_PROMPT ='''
以下是一个在MySQL上执行的语句：
{wrong_sql}

发生报错：{error}

请你修改给出正确的SQL语句，用<SQL>xxx</SQL>形式给出修改后的SQL语句。
'''.strip()

SELECT_PROMPT="""
以下是数据库的所有表和字段信息：
{database_information}
以下是一个关于该数据库的问题：
{question}
请你根据这个问题从以上所有表中选出最相关的至多3个表，并且返回表的英文名，用<RES>table_name1, table_name2, ...</RES> （用逗号分隔每个table_name，整体结果包裹在<RES></RES>之间）的形式给出结果。
"""

class DB:
    def __init__(self, 
                 # 修改这里：将默认值改为 'default'
                 sqlcoder_base_url='http://localhost:35000/v1', 
                 sqlcoder_model_name='default', 
                 
                 # 修改这里：将默认值改为 'default'
                 selector_base_url='http://localhost:35000/v1', 
                 selector_model_name='default'
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
        for k, v in self.table_comments.items():
            if 'column_comments' in v:
                del v['column_comments']
        
        # init vLLM OpenAI Clients
        self.template = TEMPLATE
        
        # 1. SQLCoder Client (通常是一个补全模型)
        self.sqlcoder_client = OpenAI(
            base_url=sqlcoder_base_url,
            api_key="EMPTY" # vLLM 本地部署通常不需要 Key
        )
        self.sqlcoder_model_name = sqlcoder_model_name
        
        # 2. Selector Client (通常是一个 Chat 模型)
        self.selector_client = OpenAI(
            base_url=selector_base_url,
            api_key="EMPTY"
        )
        self.selector_model_name = selector_model_name
        
        print(f"DB initialized. Selector: {selector_model_name} @ {selector_base_url}, SQLCoder: {sqlcoder_model_name} @ {sqlcoder_base_url}")

    def _init_mysql(self):
        self.conn = pymysql.connect(host=self.host, port=self.port, user=self.user, passwd=self.passwd, db=self.db_name, charset='utf8')
        self.cur = self.conn.cursor()

    # ... [保留原有的 _format_schema, _get_all_tables, _get_create_statement, _extract... 等辅助函数不变] ...
    # 为了节省篇幅，这里假设 _extract_all_table_detailed_comments, get_database_comments 等方法与原代码一致
    # 只要确保它们被包含在类中即可。
    
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
    
        # concise version: w/o column comments
        # for table_name, info in table_comments.items():
        #     table_comment = info.get("table_comment", "")
        #     line = f"{table_name}: {table_comment}"
        #     lines.append(line)
        # return "\n\n".join(lines)

    # ================= 核心修改部分 =================

    def select_table(self, question):
        '''
        使用 vLLM (Qwen @ 35000) 进行选表
        '''
        query = SELECT_PROMPT.format(database_information=self.get_database_comments(), question=question)
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant specialized in database schema selection."},
            {"role": "user", "content": query}
        ]
        
        try:
            # Qwen 是 Chat 模型，使用 chat.completions
            response = self.selector_client.chat.completions.create(
                model=self.selector_model_name, # "default"
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
                selected_table_name = [t.strip() for t in table_str.split(",") if t.strip()]
            else:
                # 备用方案：如果没有标签，尝试找逗号分隔的表名
                print("Warning: No <RES> tags found, trying lenient parsing.")
                selected_table_name = []
            
            return selected_table_name

        except Exception as e:
            print(f"Error in select_table: {e}")
            return []

    def generate_sql(self, selected_table_name, question):
        '''
        使用 vLLM (SQLCoder @ 36000) 生成 SQL
        '''
        schema = self._format_schema(selected_table_name)
        prompt = self.template.format(question=question, schema=schema)
        
        try:
            print("SQLCoder prompt: \n", prompt)
            # SQLCoder 适合 Text Completion，使用 completions 接口
            response = self.sqlcoder_client.completions.create(
                model=self.sqlcoder_model_name, # "default"
                prompt=prompt,
                temperature=1.0,
                max_tokens=512,
                stop=["```", ";", "assistant"] 
            )
            
            raw_output = response.choices[0].text
            print(f"[SQLCoder Output]: {raw_output}")
            
            sql_code = raw_output.strip()
            # 移除 Markdown 标记
            sql_code = sql_code.replace("```sql", "").replace("```", "").strip()
            
            # 格式化
            sql_code = sqlparse.format(sql_code, reindent=True)
            return sql_code

        except Exception as e:
            print(f"Error in generate_sql: {e}")
            return ""

    def revise_sql(self, wrong_sql, res):
        # 保持原样，调用外部 ollama 或其他逻辑
        response = query_LLM_ollama(llm_name='reasoning-LLM', query=REVISE_PROMPT.format(wrong_sql=wrong_sql, error=res['error']))
        
        def extract_sql(text):
            match = re.search(r"<SQL>(.*?)</SQL>", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            return None
            
        new_sql_code = extract_sql(response)
        return new_sql_code if new_sql_code else wrong_sql

    def execute_sql(self, sql):
        try:
            # 防止连接断开
            self.conn.ping(reconnect=True)
            self.cur = self.conn.cursor()
            
            count = self.cur.execute(sql)
            if sql.strip().lower().startswith("select"):
                rows = self.cur.fetchall()
                if self.cur.description:
                    fields = [desc[0] for desc in self.cur.description]
                    data = [dict(zip(fields, row)) for row in rows]
                else:
                    fields = []
                    data = []
                return {
                    "rowcount": count,
                    "fields": fields,
                    "data": data
                }
            else:
                self.conn.commit()
                return {
                    "rowcount": count,
                    "message": "Executed successfully."
                }
        except Exception as e:
            return {
                "error": str(e)
            }

    def query_db(self, text_query):
        try:
            selected_table_name = self.select_table(question=text_query.strip())
            print(f"Selected Tables: {selected_table_name}")
            
            if not selected_table_name:
                raise RuntimeError("No tables selected.")

            sql_code = self.generate_sql(selected_table_name=selected_table_name, question=text_query.strip()).strip()
            print(f"Generated SQL: {sql_code}")
            
            res = self.execute_sql(sql_code)
            
            cnt = 0
            while 'error' in res and cnt < MAX_REVISE_ROUND:
                print(f"SQL Execution Error: {res['error']}")
                sql_code = self.revise_sql(wrong_sql=sql_code, res=res).strip()
                print(f"Revised SQL: {sql_code}")
                res = self.execute_sql(sql_code)
                cnt += 1
                
            if 'error' in res:
                raise RuntimeError(f"Database query failed. Final SQL: {sql_code}\nError: {res['error']}")
            else:
                return res
                
        except Exception as e:
            raise RuntimeError(f"Pipeline Failed: {e}")