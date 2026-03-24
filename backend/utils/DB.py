import pymysql
import os
import sqlparse

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

import copy
import re
from utils.functions import query_LLM_ollama
# predefined info
HOST = '183.69.138.62'
PORT = 33666
USER = 'hagongda'
PASSWD = 'ha.G/o[tEst]n%gD*a'
DB_NAME = 'r_d_test'
print('😊😊😊😊😊😊')
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
请你根据这个问题从以上所有表中选出最相关的15-20个表，并且返回表的英文名，用<RES>table_name1, table_name2, ...</RES> （用逗号分隔每个table_name，整体结果包裹在<RES></RES>之间）的形式给出结果。
"""


# TODO: 
# - 把selector改为ollama接入？
# - 需要等待ollama部署后才能测试

class DB:

    def __init__(self, sqlcoder_path = '/data1/public/models/llama-3-sqlcoder-8b/', init_llm=False, selector_path = '/data1/public/models/Qwen2.5-32B-Instruct/'): # L20-old
        # init MySQL
        self.conn = None
        self.cur = None
        self.host = HOST
        self.port = PORT
        self.user = USER
        self.passwd = PASSWD
        self.db_name = DB_NAME
        self._init_mysql()
        
        # TODO: 单次连接只能访问一次？
        self.detailed_comments = None
        self.table_comments = None
        self.detailed_comments = self._extract_all_table_detailed_comments()
        self.table_comments = copy.deepcopy(self.detailed_comments)
        for k, v in self.table_comments.items():
            del v['column_comments']
        
        # init text2sql model
        self.sqlcoder = None
        self.tokenizer = None
        self.template = TEMPLATE
        if init_llm:
            self._init_sqlcoder(sqlcoder_path)
            self._init_selector(selector_path)
        
        
    def _init_mysql(self):
        self.conn = pymysql.connect(host=self.host, port=self.port, user=self.user, passwd=self.passwd, db=self.db_name, charset='utf8')
        self.cur = self.conn.cursor()
        # self.cur = self.conn.cursor(pymysql.cursors.DictCursor)
        
    def _init_sqlcoder(self, path):
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.sqlcoder = AutoModelForCausalLM.from_pretrained(
            path,
            trust_remote_code=True,
            torch_dtype=torch.float16,
            device_map='auto'
            # device_map={"": int(os.environ.get("LOCAL_RANK") or 0)}
        )
        
    def _init_selector(self, path):
        self.tokenizer_selector = AutoTokenizer.from_pretrained(path)
        self.selector = AutoModelForCausalLM.from_pretrained(
            path,
            trust_remote_code=True,
            torch_dtype=torch.float16,
            device_map='auto'
            # device_map={"": int(os.environ.get("LOCAL_RANK") or 0)}
        )
        
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
        
    def select_table(self,question):
        '''
        依据question和所有的表的名字和列的介绍，生成候选表
        输入：
            question：需要查询的问题
        返回：
            selected_table_name：List形式组织的各个表名，[table_name1, table_name2,...]
        '''
        
        query=SELECT_PROMPT.format(database_information=self.get_database_comments(), question=question)
        
        prompt = query
        messages = [
            {"role": "system", "content": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
        text = self.tokenizer_selector.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        model_inputs = self.tokenizer_selector([text], return_tensors="pt").to(self.selector.device)

        generated_ids = self.selector.generate(
            **model_inputs,
            max_new_tokens=1024
        )
        generated_ids = [
            output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]

        response = self.tokenizer_selector.batch_decode(generated_ids, skip_special_tokens=True)[0]
    
        print(response)
        
        import re

        # 从 outputs 中提取 <RES> 标签之间的内容
        match = re.search(r"<RES>(.*?)</RES>", response, re.DOTALL)
        if match:
            table_str = match.group(1)
            # 按逗号分隔，去除前后空格
            selected_table_name = [t.strip() for t in table_str.split(",") if t.strip()]
        else:
            selected_table_name = []

        
        return selected_table_name
    
    def generate_sql(self, selected_table_name, question):
        '''
        依据question和选取好的table_name，生成对应的SQL语句
        输入：
            selected_table_name：List形式组织的各个表名，[table_name1, table_name2,...]
            question：需要查询的问题
        返回：
            返回值：SQL语句（str类型）
        '''
        schema = self._format_schema(selected_table_name)
        updated_prompt = self.template.format(question=question, schema=schema)
        inputs = self.tokenizer(updated_prompt, return_tensors="pt").to(self.sqlcoder.device)
        generated_ids = self.sqlcoder.generate(
            **inputs,
            num_return_sequences=1,
            eos_token_id=self.tokenizer.eos_token_id,
            pad_token_id=self.tokenizer.eos_token_id,
            max_new_tokens=400,
            do_sample=False,
            num_beams=1,
        )
        outputs = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)
        sql_output = sqlparse.format(outputs[0].split("[SQL]")[-1], reindent=True)
        sql_code = sql_output.split('assistant')[0].strip()
        
        # TODO: comment的内容是什么意思
        comment = sql_output.split('assistant')[1].strip()
        
        return sql_code
    
    
    def revise_sql(self, wrong_sql, res):
        response = query_LLM_ollama(llm_name='reasoning-LLM', query=REVISE_PROMPT.format(wrong_sql=wrong_sql, error=res['error']))
        def extract_sql(text):
            # 使用正则表达式提取 <SQL> 和 </SQL> 之间的内容
            match = re.search(r"<SQL>(.*?)</SQL>", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            return None
        new_sql_code = extract_sql(response).strip()
        return new_sql_code
    
    def execute_sql(self, sql):
        """
        执行任意SQL语句，若正确执行，返回结果（SELECT 结果为 dict）：
            dcit['rowcount']：返回的结果行数
            dict['fields']：返回结果表的列信息
            dict['data']：list形式的每一行数据，每一行数据由字典形式组成：[{field1: xxx, field2: xxxx}, ...]
        
        若执行出现错误返回：
            字典形式的error信息：{'error': 错误信息}
        """
        try:
            count = self.cur.execute(sql)
            if sql.strip().lower().startswith("select"):
                rows = self.cur.fetchall()
                fields = [desc[0] for desc in self.cur.description]
                data = [dict(zip(fields, row)) for row in rows]
                return {
                    "rowcount": count,
                    "fields": fields,
                    "data": data
                }
            # TODO: 非Select语句的结果
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
        """
        输入针对数据库的文本形式问题，查询数据库数据，若正确执行，返回结果（SELECT 结果为 dict）：
            dcit['rowcount']：返回的结果行数
            dict['fields']：返回结果表的列信息
            dict['data']：list形式的每一行数据，每一行数据由字典形式组成：[{field1: xxx, field2: xxxx}, ...]
        
        若执行出现错误抛出错误信息：
            raise RuntimeError(f"An error occurred while executing the database query: {e}")
        """
        
        try:
            # TODO: table_name
            selected_table_name = self.select_table(question=text_query.strip())
            sql_code = self.generate_sql(selected_table_name = selected_table_name, question=text_query.strip()).strip()
            res = self.execute_sql(sql_code)
            cnt = 0
            while 'error' in res and cnt < MAX_REVISE_ROUND:
                sql_code = self.revise_sql(wrong_sql=sql_code, res=res).strip()
                print(f"Round: {cnt}")
                res = self.execute_sql(sql_code)
                print(res)
                cnt += 1
            if 'error' in res:
                # print('Failed!')
                raise RuntimeError(f"Database query failed after {cnt} attempts. Final SQL: {sql_code}\nError: {res['error']}")
            else:
                print(sql_code)
                return res
                
        except Exception as e:
            raise RuntimeError(f"An error occurred while executing the database query: {e}")