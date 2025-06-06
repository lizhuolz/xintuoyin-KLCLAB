
from .prompts import task_classify_prompt, \
function_mapping_prompt, \
planning_prompt_system, \
planning_prompt_user, \
RAG_QA_conservative_prompt, \
RAG_QA_radical_prompt, \
transform_prompt
from .query_backend import query_LLM_backend
from .RAG_backend import RAG_backend


import torch

class A:
    allowed_args = []
    func_description = []

    @classmethod
    def func_call(cls, input):
        print(f"Called from {input}")
    
    def __new__(cls, args, input):
        cls.func_call(input=args)


class query_LLM:
    allowed_args = ["weak-LLM", "NLP-LLM", "reasoning-LLM", "SQL-LLM"]
    func_description = []

    @classmethod
    def func_call(cls, llm_name, query, only_return_response=True):
        return query_LLM_backend(llm_name, query, only_return_response)
    
    def __new__(cls, args, input):
        return cls.func_call(llm_name=args, query=input)



def general_task_classify(query):
    if "研发猫" in query:
        return True
    
    message = [ {"role":"user", "content": task_classify_prompt.format(用户问题=query)}, ]
    response = query_LLM(llm_name=None, query=message)
    
    json = eval(response.split("```json")[1].split("```")[0])
    if json["task_type"] == "通用问题":
        return True
    elif json["task_type"] == "用户相关问题":
        return False
    else:
        return False

def post_processing(query, result):
    prompt = transform_prompt.format(
        user_prompt=query, final_result=result
        )
    return query_LLM(llm_name="NLP-LLM", query=prompt)


def function_mapping(query, step, context_vars, allowed_args):
    prompt = function_mapping_prompt.format(
        用户原始问题=query, 当前步骤=step, context_vars=context_vars, allowed_args=allowed_args
        )
    message = [ {"role":"user", "content": prompt}, ]
    response = query_LLM(llm_name=None, query=message)
    return eval(response.split("```json")[1].split("```")[0])

   
class RAG:
    allowed_args = []
    func_description = []

    @classmethod
    def func_call(cls, repo, query):
        # 模拟知识库检索
        return RAG_backend(query)
    
    def __new__(cls, args, input):
        return cls.func_call(repo=args, query=input)



class execute_sql:
    allowed_args = []
    func_description = []

    @classmethod
    def func_call(cls, database, query):
        # 模拟SQL查询
        return f"<查询 {database} 数据库，语句为：{query}>"
    
    def __new__(cls, input, args=None):
        return cls.func_call(database=args, query=input)

class compute:
    allowed_args = []
    func_description = []

    @classmethod
    def func_call(cls, expression):
        # 模拟计算
        return f"<计算数学表达式，语句为：{expression}>"
    
    def __new__(cls, input, args=None):
        return cls.func_call(expression=input)

    

from .DB import DB

class text2sql:
    allowed_args = []
    func_description = ["""
    将自然语言问题转换为对应的 MySQL 查询语句，并提供模型的解释或注释说明

    输入参数:
        question (str): 用户用自然语言描述的数据库访问请求
                        例如："列出所有注册用户的姓名和注册时间"。

    返回值:
        dict:
            {
                'sql': str,          # 转换后的 MySQL 查询语句
                'comment': str       # Text2SQL 模型对 SQL 的解释或转换逻辑说明
            }

    函数作用:
        使用 Text-to-SQL 模型（如 Codex、ChatGPT 等）将自然语言意图转换为结构化 SQL 查询语句，
        并生成附加注释帮助理解 SQL 的结构和意图。

    注意事项:
        实现依赖于集成的 NLP 模型或 API，应确保语义解析的准确性。
    """]

    @classmethod
    def func_call(self, database: DB, question: str) -> dict:
        return database.query_db(question)
    
    def __new__(cls, input, args):
        return cls.func_call(database=args, question=input)

    