

system_prompt = """
你是一个具备自主调用工具能力的AI助手, 你负责处理用户提出的问题，给出详细而完整的回答。
当你判断需要通过外部工具获得额外信息才能更好地回答用户问题时，你可以主动生成特定格式的函数调用语句，之后系统将调用沙盒进行执行，你会获得返回结果。


【工具调用规范】
当需要外部功能时，必须立即停止常规回复，改用特定格式生成工具调用指令。
当前你可以调用的函数如下：

1. SQL 查询函数：

**用途**：对结构化数据库进行查询

**调用格式**：
 ```
 <sql>
SQL查询内容的中文语言描述 (注意：你无需转换成SQL语句);
 </sql>
 ```

**调用示例和结果示例**：
 ```
<sql>
 本班级中分数大于90的学生名字;
</sql>
<result>
["Alice", "Bob"]
</result>
```


2. RAG 检索：

**用途**：对文档库中所有文档进行查询

**调用格式**：
 ```
 <RAG>
你想要查询的文本内容;
 </RAG>
 ```

**调用示例和结果示例**：
 ```
<RAG>
 研发费用加计扣除的政策。
</RAG>
<result>
研发费用加计扣除政策啊，简单来说，就是......
</result>
```


【请注意】：
> 你**无需等待用户要求你调用函数**，只要你认为有需要就可以主动发起函数调用。
> 每次调用只能生成一个工具调用结构块。
> 不要解释函数调用语法，不要在调用结构之中或之后赘述调用内容。
> 当你生成特定工具的调用结构时（例如，`<sql>...</sql>`），系统将中断你的生成并立刻调用沙盒进行执行。
> 系统会将沙盒结果通过`<result>...</result>` 返回, 此时你应继续从 `<result>` 后开始生成响应，结合调用结果继续完成对用户问题的回答。
> 你需要根据调用结果自行推断调用结构块是否正确、调用结果能否完成对用户问题的回答，若不能，你可以再次发起调用。


"""


question = "2025年二月总工时最长的人员id是什么？"
question = "研发费用加计扣除的政策是什么？"

user_prompt = f"""
【用户提问】  
> {question}

【已知资源和背景信息】
有一个RAG知识库，包含公司所有文件, 有一个SQL数据库，包含公司财务数据和员工信息。

【要求】  
请处理用户提出的问题，给出详细而完整的回答。必要时，基于工具调用规范，调用合适的工具。

"""
#请你一步一步地仔细思考：





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

from vllm import LLM, SamplingParams
from openai import OpenAI
def query_LLM_vllm(query, only_return_response=True):
    llm_path = {"base_url": "http://localhost:8000/v1", "api_key": "token-abc123", "model":"Qwen2.5-32B-Instruct"}
    model_name = llm_path.pop("model")
    client = OpenAI(**llm_path)

    outputs = client.completions.create(
        model=model_name,
        prompt=query,
        max_tokens=3096,
        stop=SUPPRESS_TOKENS,
    )
    response = outputs.choices[0].text
    #response = response.choices[0].message.content
    if only_return_response:
        return response
    else: 
        return response, query + [{"role":"assistant", "content": response}]

from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("/data1/public/models/Qwen2.5-32B-Instruct")

initial_message = [
            {"role":"system", "content": system_prompt},
            {"role":"user", "content": user_prompt},
            {"role":"assistant", "content": ""},
        ]

message = initial_message
def call_sandbox(x):
    if "研发费用加计扣除" in x: 
    #return "{'rowcount': 1, 'fields': ['employee_id', 'total_hours'], 'data': [{'employee_id': 3, 'total_hours': Decimal('8.00')}]}"
        return """研发费用加计扣除政策啊，简单来说，就是企业在进行研发新技术、新产品、新工艺时所产生的费用，在计算税款时可以多扣一些。具体来说，这个政策包括以下几个方面：

    首先，研发活动范围是指企业为获得科学与技术新知识，创造性运用科学技术新知识，或实质性改进技术、产品、工艺而持续进行的具有明确目标的系统性活动。

    其次，允许加计扣除的研发费用包括人员人工费用、直接投入费用、折旧费用、无形资产摊销、新产品设计费、新工艺规程制定费等等。这些费用在税前都可以进行加计扣除。

    不过，也有一些活动是不适用税前加计扣除政策的，比如企业产品服务的常规性升级、对某项科研成果的直接应用等。同时，像烟草制造业、住宿和餐饮业、批发和零售业等行业也是不能享受这个政策的。

    最后，这个政策适用于会计核算健全、实行查账征收并能够准确归集研发费用的居民企业。企业需要对研发支出进行会计处理，并设置辅助账来准确归集核算当年可加计扣除的各项研发费用实际发生额。

    总的来说，研发费用加计扣除政策是政府为了鼓励企业创新而出台的一项优惠政策，企业在进行新技术研发时，可以合理利用这个政策来减轻税负。
    """
    elif "总工时" in x: 
        return "{'rowcount': 1, 'fields': ['employee_id', 'total_hours'], 'data': [{'employee_id': 3, 'total_hours': Decimal('8.00')}]}"


def text_generate(message):
    while True:
        inputs = tokenizer.apply_chat_template(message, tokenize=False)
        inputs = "<|im_end|>".join(inputs.split("<|im_end|>")[:-1])
        #print("\033[31m inputs:\033[0m", inputs)
        raw_response = query_LLM_vllm(inputs, True)
        #print("\033[31m raw_response:\033[0m", raw_response)
        func_pattern = find_last_unclosed_pattern(raw_response)
        if func_pattern is None:
            yield raw_response
            break
        supress_token = func_pattern[1]
        leading_token = func_pattern[0]
        function_call_content = raw_response.split(leading_token)[-1]
        #print("\033[31m function_call_content:\033[0m", function_call_content)
        
        extended_response = raw_response + supress_token + "<result>\n" + call_sandbox(function_call_content) + "\n</result>\n```\n"
        yield extended_response
        if message[-1]["role"] == "assistant":
            message[-1]["content"] = message[-1]["content"]  +extended_response
        else:
            message = message + [{"role":"assistant", "content": extended_response}]
        #print("\033[31m message:\033[0m", message)


"""
if message[-1]["role"] == "assistant":
    message[-1]["content"] = message[-1]["content"]  +raw_response
else:
    message = message + [{"role":"assistant", "content": raw_response}]
"""
print("\033[31m message[2][content]:\033[0m", message[2]["content"])
print(len(message))

