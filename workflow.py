from utils.prompts import task_classify_prompt, \
function_mapping_prompt, \
planning_prompt_system, \
planning_prompt_user, \
planning_prompt_system_multi_step, \
planning_prompt_user_multi_step, \
RAG_QA_conservative_prompt, \
RAG_QA_radical_prompt, \
transform_prompt

#from utils.functions import query_LLM, general_task_classify, RAG, execute_sql, compute, text2sql, TEXT2SQL, query_LLM_wrapped
from utils.functions import general_task_classify, RAG, compute, text2sql, query_LLM
from utils.query_backend import query_LLM_backend
from utils.DB import DB

import warnings
warnings.filterwarnings("ignore")



# 假设你已经有以下动作映射表
ACTION_FUNCTION_MAP = {
    "RAG": "RAG",
    "query LLM": "query_LLM",
    "execute SQL": "execute_sql_wrapped",
    "compute": "compute"
    # ... 其他动作
}


# 执行器上下文：用于存储中间变量


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
        self.history = []  # [(user_msg, agent_msg), ...]
        self.ctx = {}
    
    def handle_message(self, query):
        agent = Agent()  # 始终调用唯一的Agent实例
        response, steps = agent.solve(self, query)
        self.history.append({
            "user": query,
            "planning": steps,
            "assistant": response,
        })
        return response
    

class Agent:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Agent, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        #self.ctx = {}
        self.func_mapping_LLM = "weak-LLM"
        self.planning_LLM = "NLP-LLM"

        ### 定义数据库
        self.db = DB(init_llm=True)
        global global_db
        global_db = self.db 
    
    def solve(self, conver: Conversation, query):
        steps = self.planning(conver, query)
        result = self.execute(conver, query, steps)
        response = query_LLM_backend(llm_name="NLP-LLM", query=transform_prompt.format(user_prompt=query, final_result=result))   ### todo
        return response, steps
        
    
    def function_mapping(self, raw_query, step, allowed_args, ctx_var):
        message = [ {"role":"user", "content": 
                     function_mapping_prompt.format(用户原始问题=raw_query, 当前步骤=step, context_vars=ctx_var, allowed_args=allowed_args)              
                    }]
        response = query_LLM_backend(llm_name=self.func_mapping_LLM, query=message)
        #print(message[-1]["content"])
        #print(response)
        return eval(response.split("```json")[1].split("```")[0].replace("null", "None"))
    
    def planning(self, conver: Conversation, query):
        if len(conver.history)==0:
            message = [
                {"role":"system", "content": planning_prompt_system},
                {"role":"user", "content": planning_prompt_user.format(用户提问=query)},
                ]
        else:
            ctx_var = [{'name':name, 'comment': value["comment"]}  for name, value in conver.ctx.items()]
            message = [
                {"role":"system", "content": planning_prompt_system_multi_step},
                {"role":"user", "content": planning_prompt_user_multi_step.format(用户提问=query, 历史对话=conver.history, context_vars=ctx_var)},
                ]
        response = query_LLM_backend(llm_name=self.planning_LLM, query=message)
        #print(message[-1]["content"])
        #print(response)

        return eval(response.split("```json")[1].split("```")[0].replace("null", "\"null\""))

    def execute(self, conver: Conversation, query, steps):
        ctx = conver.ctx
        for step in steps:
            action = step["action"]
            raw_args = step["args"]
            raw_input = step["input"]
            output_name = step["output"]

            # 替换 input 中引用的变量（如果是已有中间结果）
            """
            input_value = raw_input
            for var_name in self.ctx:
                if var_name in raw_input:
                    input_value = input_value.replace(var_name, str(self.ctx[var_name]))
            """
            # 取得函数名
            func_name = ACTION_FUNCTION_MAP[action]
            func = globals()[func_name]
            func_allowed_args = func.allowed_args
            func_description = None

            # 获得环境变量名及其注释
            ctx_var = []
            for name, value in conver.ctx.items():
                ctx_var.append({'name':name, 'comment': value["comment"]})
            
            mapping_step = self.function_mapping(query, step, func_allowed_args, ctx_var)
            
            args = None if mapping_step['args'] is not None and "None" in mapping_step['args'] else mapping_step['args']
            input = mapping_step['input']
            if input in conver.ctx.keys():
                input_value = conver.ctx[input]['content']
            else: 
                input_value = raw_input
            output_comment = mapping_step['output_comment']

            # 执行函数
            #print("input_value", input_value)
            result = func(args=args, input=input_value)

            # 存储结果到上下文，供后续步骤引用
            conver.ctx[output_name] = {'content': result, 'comment': output_comment}

            print(f"[STEP {step['step']}] {output_name} = {func_name}(args={args}, input={input_value})\n")
        return result

