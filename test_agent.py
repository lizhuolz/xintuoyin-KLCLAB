from utils.DB_vllm_32B import DB
from utils.functions import *
from transformers import AutoTokenizer, AutoModelForCausalLM

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "5,6,7"
# LLM_path = "../../../../LLM/llama-3-sqlcoder-8b"
# db = DB(init_llm=True)
db = DB()
# print(db.get_database_comments())
question = "本年可享受研发加计扣除项目数量，其中人员人工费用是多少？"
answer=db.query_db(text_query=question)
print(answer)