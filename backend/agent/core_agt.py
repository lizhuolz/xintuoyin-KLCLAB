# agent_cli.py / core_agt.py
import operator as op
import openai # 引入 openai 以捕获 Azure 错误
from typing import Any, Dict

# LangChain/LangGraph 组件
from langchain_core.messages import AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver
# 替换成你实际的 import 路径
from agent.build_graph import graph_builder 

# ==========================================
# 🔥 安全防火墙配置
# ==========================================
from llm_guard.vault import Vault
from llm_guard import scan_prompt, scan_output
# 注意：这里不再从 input_scanners 引入 BanTopics
from llm_guard.input_scanners import (
    Anonymize, BanSubstrings, Gibberish, InvisibleText, 
    PromptInjection, Secrets, TokenLimit, Toxicity
)
from llm_guard.output_scanners import NoRefusal, Deanonymize, BanTopics

# 1. 初始化
print("正在初始化安全防火墙...")
vault = Vault()

# 2. 定义输入防御层 (Input Scanners)
# ❌ 已移除 BanTopics (它会导致报错)
# ✅ 保留 BanSubstrings (它负责拦截炸弹、制毒等关键词)
input_scanners = [
    # 核心拦截：只要出现这些词，直接拒绝
    BanSubstrings(
        substrings=[
            "炸弹", "爆炸物", "生化武器", "制毒", "杀人", 
            "自杀", "核武器", "枪支", "火药", "硝酸铵",
            "ignore previous instructions", "system prompt"
        ],
        match_type="str",
        case_sensitive=False
    ),
    PromptInjection(threshold=0.5),
    InvisibleText(),
    Secrets(redact_mode="partial"),
    Anonymize(vault=vault),
    TokenLimit(limit=2000),
    Toxicity(threshold=0.5),
    Gibberish(threshold=0.5),
]

# 3. 定义输出防御层 (Output Scanners)
# 这里可以放 BanTopics，用来检查生成的结果是否包含危险话题
output_scanners = [
    NoRefusal(),
    # 如果之前 BanTopics 在输出端也报错，可以先注释掉下面这行，确保程序跑通
    BanTopics(topics=["explosives", "weapons"], threshold=0.6), 
    Deanonymize(vault=vault)
]
print("✅ 防火墙加载完毕")

# 编译 Graph
checkpointer = MemorySaver()
app = graph_builder.compile(checkpointer=checkpointer)

def main():
    print("LangGraph Agent (Secure Mode) 已启动。输入 exit 退出。")
    thread_id = "demo-thread-secure"

    while True:
        try:
            user_text = input("\nYou: ").strip()
        except EOFError:
            break

        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit"):
            break

        # ==========================================
        # 🔥 1. 本地防火墙检查 (Input)
        # ==========================================
        try:
            # 这里调用 input_scanners，里面已经没有 BanTopics 了，不会再报错
            sanitized_prompt, results_valid, results_score = scan_prompt(input_scanners, user_text)
            
            if any(not is_valid for is_valid in results_valid.values()):
                print("\n🛑 [本地拦截] 输入被防火墙拒绝：") # [OUTPUT]
                for scanner_name, is_valid in results_valid.items():
                    if not is_valid:
                        score = results_score.get(scanner_name, 0)
                        # 如果是 BanSubstrings 拦截的，说明命中了炸弹等关键词
                        print(f"   ❌ {scanner_name} (分值: {score})")
                continue
        except Exception as e:
            print(f"本地防火墙出错: {e}")


        # ==========================================
        # 2. 执行 Agent
        # ==========================================
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {
            "messages": [("user", sanitized_prompt)],
            "enable_web": True,
            "select_model": "gpt-4o"
        }

        print("Agent: ", end="", flush=True)
        full_response_text = ""

        try:
            for msg, metadata in app.stream(inputs, config, stream_mode="messages"):
                node_name = metadata.get("langgraph_node", "unknown")
                if isinstance(msg, AIMessageChunk) and msg.content and node_name in ["chatbot_web","chatbot_local"]:
                    print(msg.content, end="", flush=True)
                    full_response_text += msg.content
        
        except openai.BadRequestError as e:
            if e.code == 'content_filter':
                print("\n\n🛡️ [Azure 云端拦截] 内容违反了 Azure 安全策略 (暴力/仇恨/越狱)。")
            else:
                print(f"\n\n❌ OpenAI 请求错误: {e}")
        except Exception as e:
            print(f"\n\n❌ 系统运行错误: {e}")

        print("") 

        # ==========================================
        # 3. 输出审计 (Output)
        # ==========================================
        if full_response_text:
            try:
                # BanTopics 在这里（output_scanners）才是合法的
                _, out_valid, _ = scan_output(output_scanners, sanitized_prompt, full_response_text)
                if any(not is_valid for is_valid in out_valid.values()):
                     print("\n⚠️ [内容警告] 回复内容可能违反安全策略") # [OUTPUT]  full_response_text += "\n[内容警告] 回复内容可能违反安全策略"
                     for k, v in out_valid.items():
                         if not v: print(f"   - {k} 违规")
            except Exception as e:
                # 即使输出检查出错，也不要让程序崩溃，打印日志即可
                print(f"[审计跳过] 输出检查出错: {e}")

if __name__ == "__main__":
    main()