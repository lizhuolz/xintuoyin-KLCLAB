from utils.prompts import task_classify_prompt, \
function_mapping_prompt, \
planning_prompt_system, \
planning_prompt_user, \
planning_prompt_system_multi_step, \
planning_prompt_user_multi_step, \
RAG_QA_conservative_prompt, \
RAG_QA_radical_prompt, \
transform_prompt, \
function_calling_prompt_system,\
function_calling_prompt_user

#from utils.functions import query_LLM, general_task_classify, RAG, execute_sql, compute, text2sql, TEXT2SQL, query_LLM_wrapped
from utils.functions import general_task_classify, RAG, compute, text2sql, query_LLM
from utils.query_backend import function_calling_query_vllm
from utils.DB import DB
from transformers import AutoTokenizer
import warnings
warnings.filterwarnings("ignore")



# 假设你已经有以下动作映射表
ACTION_FUNCTION_MAP = {
    "<RAG>": "RAG",
    "<query>": "query_LLM",
    "<sql>": "execute_sql_wrapped",
    "compute": "compute"
    # ... 其他动作
}

# 首次生成（到特定token停止）
SUPPRESS_TOKENS = ["</sql>", "</RAG>"]  # 您的特定停止标记
PATTERNS = [
    ("<sql>", "</sql>"),
    ("<RAG>", "</RAG>"),
]

def find_last_unclosed_pattern(long_string, patterns=PATTERNS):
    """
    从后往前查找最后一个未闭合的模式。
    
    Args:
        long_string (str): 要搜索的长字符串。
        patterns (list of tuple): 模式列表，每个模式是 (发语词, 结束词) 的元组，如 ("<sql>", "</sql>")。
        
    Returns:
        tuple or None: 返回最后一个未闭合的 (发语词, 结束词)，如果没有未闭合的模式则返回 None。
    """
    last_unclosed = None
    last_unclosed_pos = -1  # 记录未闭合模式的最晚出现位置
    
    for start_tag, end_tag in patterns:
        # 从后往前找最后一个 start_tag
        last_start_pos = long_string.rfind(start_tag)
        
        if last_start_pos == -1:
            continue  # 该模式未出现，跳过
        
        # 检查 start_tag 后面是否有对应的 end_tag
        substring_after_start = long_string[last_start_pos:]
        if end_tag not in substring_after_start:
            # 如果未闭合，检查是否是最晚出现的未闭合模式
            if last_start_pos > last_unclosed_pos:
                last_unclosed_pos = last_start_pos
                last_unclosed = (start_tag, end_tag)
    
    return last_unclosed


global_db = None
class execute_sql_wrapped:
    allowed_args = text2sql.allowed_args
    func_description = text2sql.func_description

    def __new__(cls, args, input):
        # 注意：这里是运行时读取全局变量 db0，而不是类定义时就绑定了它的值
        return text2sql(input=input, args=global_db)


class User:
    def __init__(self, user_id):
        self.user_id = user_id
        self.conversations = {}

    def start_conversation(self, conv_id):
        conv = Conversation(conv_id)
        self.conversations[conv_id] = conv
        return conv

    def get_conversation(self, conv_id):
        return self.conversations.get(conv_id)

class Conversation: 
    def __init__(self, conv_id):
        self.conv_id = conv_id
        self.history = [
            {"role":"system", "content": function_calling_prompt_system},
        ]
    def handle_message(self, query):
        agent = Agent()  # 始终调用唯一的Agent实例

        self.history = self.history + [
            {"role":"user", "content": function_calling_prompt_user.format(question=query)},
            {"role":"assistant", "content": ""},
        ]
    
        messages = agent.solve(self.history, query)
        assert len(self.history) == len(messages)
        self.history = messages
        return self.extract_response(messages)
    
    def extract_response(messages):
        return messages[-1]["content"]

    

class Agent:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Agent, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        #self.func_mapping_LLM = "weak-LLM"
        #self.planning_LLM = "NLP-LLM"
        self.tokenizer = AutoTokenizer.from_pretrained("/data1/public/models/Qwen2.5-32B-Instruct")
        self.MAX_ITERATION = 8

        ### 定义数据库
        self.db = DB(init_llm=True)
        global global_db
        global_db = self.db 
    
    def solve(self, message: list, query):
        for i in range(self.MAX_ITERATION):
            inputs = self.tokenizer.apply_chat_template(message, tokenize=False)
            inputs = "<|im_end|>".join(inputs.split("<|im_end|>")[:-1])
            #print("\033[31m inputs:\033[0m", inputs)
            raw_response = function_calling_query_vllm(inputs, SUPPRESS_TOKENS)
            #print("\033[31m raw_response:\033[0m", raw_response)
            func_pattern = find_last_unclosed_pattern(raw_response)
            if func_pattern is None:
                break
            supress_token = func_pattern[1]
            leading_token = func_pattern[0]
            function_call_content = raw_response.split(leading_token)[-1]
            #print("\033[31m function_call_content:\033[0m", function_call_content)

            func_name = ACTION_FUNCTION_MAP[leading_token]
            func = globals()[func_name]
            sandbox_result = func(args=None, input=function_call_content)
            
            extended_response = raw_response + supress_token + "<result>\n" + sandbox_result + "\n</result>\n```\n"
            if message[-1]["role"] == "assistant":
                message[-1]["content"] = message[-1]["content"]  + extended_response
            else:
                message = message + [{"role":"assistant", "content": extended_response}]
            #print("\033[31m message:\033[0m", message)

        if message[-1]["role"] == "assistant":
            message[-1]["content"] = message[-1]["content"]  +raw_response
        else:
            message = message + [{"role":"assistant", "content": raw_response}]
        #response = query_LLM_backend(llm_name="NLP-LLM", query=transform_prompt.format(user_prompt=query, final_result=result))   ### todo
        return message
        