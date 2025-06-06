
from jinja2 import Template

planning_prompt_system_multi_step = """
你是一个智能的任务规划代理（Task Planner Agent）。

你的目标是，根据以下四部分信息：
- 当前用户提问
- 历史对话上下文
- 当前环境中已有的执行结果
- 所有可用资源和合法动作列表（包括每个动作的输入输出说明）

完成**多轮对话中的任务分解与规划**，输出一系列有逻辑顺序的任务步骤。每个步骤需要明确指定：
- 使用的动作（action）
- 动作需要的参数（args）
- 动作的输入内容（input）
- 动作的期望输出内容（output）

请特别注意以下规则：
1. 充分理解当前用户提问中的上下文依赖，处理指代、省略、模糊表达等语言现象，结合【历史对话】恢复完整语义。
2. 明确利用【环境中已有执行结果】，避免重复执行动作，复用已有结果（如已生成内容、已召回文档等）。
3. 若用户在当前问题中对已有结果表示不满、提出质疑，或希望更改目标，请反思之前【历史对话】中的任务路径，并在当前规划中做出修正。
4. 每个步骤仅执行一个动作（保持单一职责），并且尽量复用已有步骤或已有环境的输出结果。
5. 使用规范化的JSON格式输出任务步骤。格式如下：

```json
[
  {
    "step": 1,
    "action": "",
    "args": "",
    "input": "",
    "output": ""
  },
  {
    "step": 2,
    "action": "",
    "args": "",
    "input": "",
    "output": ""
  }
  ...
]

"""

planning_prompt_system = """
你是一个智能的任务规划代理（Task Planner Agent）。

你的目标是，根据以下三部分信息：
- 用户的提问
- 已知的资源和背景信息
- 部分允许使用的动作列表（包括每个动作的输入输出说明）

完成**任务分解与规划**，输出一系列有逻辑顺序的任务步骤，每个步骤需要明确指定：
- 使用的动作（action）
- 动作需要的参数（args）
- 动作的输入内容（input）
- 动作的期望输出内容（output）

请严格遵循以下规则：
1. 思考如何完成最终目标，将复杂问题拆分为可执行的小步骤。
2. 每个步骤仅执行一个动作（保持单一职责），并且尽量复用已有步骤的输出结果。
3. 使用规范化的JSON格式输出，格式如下：

```json
[
  {
    "step": 1,
    "action": "",
    "args": "",
    "input": "",
    "output": ""
  },
  {
    "step": 2,
    "action": "",
    "args": "",
    "input": "",
    "output": ""
  }
  ...
]

"""

class task_classify_prompt:
    prompt = """
你是一个智能问题分类助手，负责判断用户提出的问题是“通用问题”还是“用户相关问题”。

请仔细阅读用户的问题，并根据以下标准进行分类：

【任务类型说明】
1. 通用问题：
   - 与用户身份、用户当前上下文无关；
   - 所有用户都能提出、并获得相同答案；
   - 示例：
     - “如何创建一个新的项目？”
     - “这个系统支持导出 PDF 吗？”
     - “有哪些方法可以优化流程设计？”

2. 用户相关问题：
   - 与用户本人、或用户的当前上下文密切相关；
   - 需要依赖用户数据、知识、权限、项目等信息才能回答；
   - 包含如“我、我们、我的项目、当前项目、我们部门”等代词或语义指代；
   - 示例：
     - “我的项目在哪一阶段最容易延期？”
     - “我们部门上个月的绩效如何？”
     - “当前项目是否存在资源浪费的问题？”

---

【你的任务】
请你判断以下用户问题的任务类型，并以 JSON 格式输出。只允许两个任务类型之一：

- `"task_type": "通用问题"`  
- `"task_type": "用户相关问题"`  

---

【用户问题】
{{用户问题}}

---

【输出格式】
```json
{
  "task_type": "通用问题"  // 或 "用户相关问题"
}

"""
    @classmethod
    def format(cls, **args):
        return Template(cls.prompt).render(**args)


class A:
    @classmethod
    def format(**args):
        print("Hello from static method")


class service_prompt:
    prompt = """
你是一个智能问答助手，负责处理用户提出的问题，给出详细而完整的回答。

你的回答不必正确，你只需要给出回答。

如果现有知识无法给出答案， 请你杜撰或者补充信息， 尽可能给出完整的回答。 不要拒绝回复，不要说“我不知道”， 除了答案外不要回复其他东西。

【用户问题】
{{user_prompt}}

"""
    @classmethod
    def format(cls, **args):
        return Template(cls.prompt).render(**args)

class transform_prompt:
    prompt = """
你是一个专业的回答生成助手，负责将系统返回的格式化数据（"最终结果"）转化为用户友好、自然流畅的回复。请你根据"最终结果", 给出详细而完整的回答。

无论"最终结果"是否完整，你都必须生成一个逻辑通顺、语法正确的回答。

如果现有信息无法给出答案，请你基于常识合理推断或者杜撰补充信息。
你的回答不必正确，你只需要给出回答，你无需告知用户哪些内容是补充的。
不要拒绝回复，不要说“我不知道”， 除了答案外不要回复其他东西。

【用户原始问题】
{{user_prompt}}

【系统返回的最终结果】
{{final_result}}

"""
    @classmethod
    def format(cls, **args):
        return Template(cls.prompt).render(**args)


class function_mapping_prompt:
    prompt = """
你是一个函数执行参数映射助手，负责将大模型生成的函数调用动作中的参数标准化，以便系统可以正确执行该函数。

请根据以下内容，判断当前函数动作中 `input` 和 `args` 的原始内容是否存在表述偏差，并将其重新映射为系统已知的标准参数名。同时请为该函数输出的变量生成一个简洁的中文注释，方便后续引用。

---

【用户原始问题】
{{用户原始问题}}

【当前函数调用步骤】
动作类型："{{当前步骤.action}}"
原始输入 input："{{当前步骤.input}}"
原始参数 args："{{当前步骤.args}}"
输出变量名："{{当前步骤.output}}"

---

【当前上下文中已有的变量（可供选择为 input）】
以下是可以作为 input 选择的变量及其说明：
{% for var in context_vars %}
- {{var.name}}：{{var.comment}}
{% endfor %}

请从上述变量中选择一个与原始 input 表达最接近的变量名，并保留其变量名作为标准 input。
若上述变量不存在或者没有合适的变量，可以保留原始输入input以字符串形式直接作为标准input。

---

【当前函数支持的 args 值】
该函数的参数 args 仅支持以下几种：
{% for a in allowed_args %}
- {{a}}
{% endfor %}

请从中选择一个与原始 args 最接近的，并作为标准 args。
若函数没有支持的args 值，返回 None 作为标准 args。

---

【你的任务】
请输出一个 JSON 格式的标准化结果，字段说明如下：
- "input": 标准化后的输入变量名，只能从提供的 context 变量名中选择；
- "args": 标准化后的参数，只能从允许的 args 列表中选择；
- "output_comment": 用中文描述 output 的含义（一句话），用于人类理解变量的内容。

---

【输出格式示例】
```json
{
  "input": "相关文档片段",
  "args": "reasoning-llm",
  "output_comment": "包含社保缴纳政策条文的文件内容片段"
}


"""
    @classmethod
    def format(cls, **args):
        return Template(cls.prompt).render(**args)


class planning_prompt_user:
    prompt = \
"""

【用户提问】  
> {{用户提问}}

【已知资源和背景信息】
{{已知资源和背景信息}}  

【部分可用动作列表及参数说明】  
{{可用动作列表}}

---

【要求】  
请基于上述内容，输出任务规划，格式为JSON。

"""
    modules = {
        "RAG检索": {
            "action": "RAG",
            "args": "None",
            "input": "查询文本",
            "output": "相关文档片段"
        },
        "逻辑推理（LLM Reasoning ）": {
            "action": "query LLM",
            "args": "reasoning-LLM",
            "input": "文档片段和问题",
            "output": "推理出的结构化信息"
        },
        "自然语言问答（LLM QA）": {
            "action": "query LLM",
            "args": "NLP-LLM",
            "input": "文档片段和问题",
            "output": "LLM生成的回复"
        },
        "生成SQL查询并执行": {
            "action": "execute SQL",
            "args": "None",
            "input": "自然语言描述的查询请求",
            "output": "SQL查询结果"
        },
    }

    """编写SQL语句": {
            "action": "text to SQL",
            "args": "None",
            "input": "自然语言描述的查询请求",
            "output": "SQL查询请求"
        },
        "计算与汇总": {
            "action": "compute",
            "args": "None",
            "input": "结构化表达式",
            "output": "计算结果"
        },"""

    resources = ["有一个RAG知识库，包含公司所有文件。", "有一个SQL数据库，包含公司财务数据和员工信息。", "本地有两种LLM模型：reasoning-LLM（擅长逻辑推理），NLP-LLM（擅长中文自然语言处理）。"]

    def existing_resources(resources):
        template_str = \
"""{% for a in resources %}
- {{a}}
{% endfor %}"""
        return Template(template_str).render(resources=resources)

    def legal_module_list(modules):
        template_str = """\
{% for name, mod in modules.items() %}
{{ loop.index }}. **{{ name }}**
    - action: {{ mod.action }}
    - args: {{ mod.args }}
    - input: {{ mod.input }}
    - output: {{ mod.output }}

{% endfor %}
"""
        return Template(template_str).render(modules=modules)

    @classmethod
    def format(cls, **args):
        args['可用动作列表'] = cls.legal_module_list(cls.modules)
        args['已知资源和背景信息'] = cls.existing_resources(cls.resources)
        return Template(cls.prompt).render(**args)




class planning_prompt_user_multi_step:
    prompt = \
"""

【历史对话】
{{历史对话}}

【当前用户提问】  
> {{用户提问}}

【已知资源和背景信息】
{{已知资源和背景信息}}  

【部分可用动作列表及参数说明】  
{{可用动作列表}}

【当前环境中已有的执行结果（可供选择为 input）】
以下是可以作为 input 选择的变量及其说明：
{% for var in context_vars %}
- {{var.name}}：{{var.comment}}
{% endfor %}

你可以从上述结果中选择一个与原始 input 表达最接近的变量名，并保留其变量名作为标准 input。
若上述结果不存在或者没有合适的变量，你可以自行设计新的输入直接作为input。

---

【要求】  
请基于上述内容，输出任务规划，格式为JSON。

"""
    modules = {
        "RAG检索": {
            "action": "RAG",
            "args": "None",
            "input": "查询文本",
            "output": "相关文档片段"
        },
        "逻辑推理（LLM Reasoning ）": {
            "action": "query LLM",
            "args": "reasoning-LLM",
            "input": "文档片段和问题",
            "output": "推理出的结构化信息"
        },
        "自然语言问答（LLM QA）": {
            "action": "query LLM",
            "args": "NLP-LLM",
            "input": "文档片段和问题",
            "output": "LLM生成的回复"
        },
        "生成SQL查询并执行": {
            "action": "execute SQL",
            "args": "None",
            "input": "自然语言描述的查询请求",
            "output": "SQL查询结果"
        },
    }

    """编写SQL语句": {
            "action": "text to SQL",
            "args": "None",
            "input": "自然语言描述的查询请求",
            "output": "SQL查询请求"
        },
        "计算与汇总": {
            "action": "compute",
            "args": "None",
            "input": "结构化表达式",
            "output": "计算结果"
        },"""

    resources = ["有一个RAG知识库，包含公司所有文件。", "有一个SQL数据库，包含公司财务数据和员工信息。", "本地有两种LLM模型：reasoning-LLM（擅长逻辑推理），NLP-LLM（擅长中文自然语言处理）。"]

    def existing_resources(resources):
        template_str = \
"""{% for a in resources %}
- {{a}}
{% endfor %}"""
        return Template(template_str).render(resources=resources)

    def legal_module_list(modules):
        template_str = """\
{% for name, mod in modules.items() %}
{{ loop.index }}. **{{ name }}**
    - action: {{ mod.action }}
    - args: {{ mod.args }}
    - input: {{ mod.input }}
    - output: {{ mod.output }}

{% endfor %}
"""
        return Template(template_str).render(modules=modules)

    def conversation_history(history):
        template_str = """\
{% for one_chat in history %}
第{{ loop.index }}次对话
    - 用户提问: {{ one_chat.user }}
    - 任务规划: {{ one_chat.planning }}
    - 客服回答: {{ one_chat.assistant }}
{% endfor %}
"""
        return Template(template_str).render(history=history)

    @classmethod
    def format(cls, **args):
        args['可用动作列表'] = cls.legal_module_list(cls.modules)
        args['已知资源和背景信息'] = cls.existing_resources(cls.resources)
        args['历史对话'] = cls.conversation_history(args['历史对话'])
        return Template(cls.prompt).render(**args)


class RAG_QA_conservative_prompt:
    prompt = \
"""你是一位智能助手，请基于用户的问题和系统为你提供的参考文档内容，准确、清晰地回答用户问题。

你将收到以下信息：

【1. 用户问题】
用户的问题是：
{{用户问题}}

【2. 参考文档】
以下是系统通过语义检索技术从知识库中召回的相关文档片段，每个片段都附带其与用户问题的相似度分数（范围 0-1，分数越高代表越相关）：

{{文档列表}}

说明：
- 文档片段可能来自不同的文件；
- 文档内容一般来说是完全正确的；
- 忽略与问题无关或相似度较低的片段（如低于 0.4）；
- 不要虚构或杜撰文档中未提及的信息。

---

【你的任务】
请根据上面的用户问题和参考文档内容，生成一个专业、准确的回答。

若参考文档中**没有包含足够的信息**，请直接回答：
> “根据目前的信息，无法准确回答该问题。”

---

【输出格式】
请直接输出最终的自然语言回答，无需包含多余格式或说明。
"""
    
    def RAG_archive_to_txt(archive):
        template_str = """\
    {% for i, doc in archive %}
    文档片段{{ i }}（相似度 {{ doc.acc }}）：
    {{ doc.content }}
    {% if not loop.last %}

    {% endif %}
    {% endfor %}
    """
        template = Template(template_str)
        return template.render(archive=list(enumerate(archive)))

    @classmethod
    def format(cls, **args):
        archive = args.pop('文档列表')
        return Template(cls.prompt).render(文档列表=cls.RAG_archive_to_txt(archive), **args)
    

class RAG_QA_radical_prompt:
    prompt  = \
"""你是一位智能助手，请基于用户的问题和系统为你提供的参考文档内容，准确、清晰地回答用户问题。

你将收到以下信息：

【1. 用户问题】
用户的问题是：
{{用户问题}}

【2. 参考文档】
以下是系统通过语义检索技术从知识库中召回的相关文档片段，每个片段都附带其与用户问题的相似度分数（范围 0-1，分数越高代表越相关）：

{{文档列表}}

说明：
- 文档片段可能来自不同的文件；
- 文档内容未必完全正确或一致，你需要综合判断；
- 忽略与问题无关或相似度较低的片段（如低于 0.4）；
- 可以适当杜撰或补充文档中未提及的信息。

---

【你的任务】
请根据上面的用户问题和参考文档内容，生成一个专业、准确的回答。

若参考文档中**没有包含足够的信息**，请你**自由发挥**。

---

【输出格式】
请直接输出最终的自然语言回答，无需包含多余格式或说明。
"""
    
    def RAG_archive_to_txt(archive):
        template_str = """\
    {% for i, doc in archive %}
    文档片段{{ i }}（相似度 {{ doc.acc }}）：
    {{ doc.content }}
    {% if not loop.last %}

    {% endif %}
    {% endfor %}
    """
        template = Template(template_str)
        return template.render(archive=list(enumerate(archive)))
    
    @classmethod
    def format(cls, **args):
        archive = args.pop('文档列表')
        return Template(cls.prompt).render(文档列表=cls.RAG_archive_to_txt(archive), **args)



