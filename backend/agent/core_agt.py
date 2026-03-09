# core_agt.py
import operator as op
import openai
from typing import Any, Dict
import json
from langchain_core.messages import AIMessageChunk
from langgraph.checkpoint.memory import MemorySaver
from agent.build_graph import graph_builder
from utils.security import check_input_safety, check_output_safety
from langchain_core.messages import AIMessageChunk, ToolMessage

# 编译 Graph
checkpointer = MemorySaver()
app = graph_builder.compile(checkpointer=checkpointer)

def main():
    print("==================================================")
    print("🛡️  LangGraph Agent (Secure CLI Mode) 已启动")
    print("   防火墙已加载：输入、输出均受 LLM Guard 保护")
    print("   输入 'exit' 或 'quit' 退出。")
    print("==================================================")
    
    thread_id = "cli-demo-thread"

    while True:
        try:
            user_text = input("\nYou: ").strip()
        except EOFError:
            break

        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit"):
            break

        # --- 🛡️ 1. 输入防火墙检查 ---
        sanitized_prompt, is_safe, error_msg = check_input_safety(user_text)
        if not is_safe:
            print(f"\n🛑 [本地拦截] {error_msg}")
            continue

        # --- 2. 执行 Agent ---
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {
            "messages": [("user", sanitized_prompt)],
            "enable_web": True,
            "select_model": "gpt-4o",
            "user_identity": "admin" # CLI 默认管理员权限
        }

        print("Agent: ", end="", flush=True)
        full_response_text = ""

        try:
            # 流式输出
            for msg, metadata in app.stream(inputs, config, stream_mode="messages"):
                node_name = metadata.get("langgraph_node", "unknown")
                if isinstance(msg, AIMessageChunk) and msg.content and node_name in ["chatbot_web","chatbot_local"]:
                    print(msg.content, end="", flush=True)
                    full_response_text += msg.content
        
        
                elif isinstance(msg, ToolMessage):
                    if msg.name == "tavily_search_with_summary":
                        try:
                            search_data = json.loads(msg.content)
                            results = search_data.get("results", [])
                            
                            print("\n\n" + "="*55)
                            print("🔍 [后台 AI 搜索与网页抓取完毕]")
                            
                            for idx, item in enumerate(results):
                                raw_len = len(item.get("raw_content", ""))
                                print(f"\n📄 来源 {idx + 1}:")
                                print(f"  🔹 【大标题】: {item.get('main_title', '无')}")
                                print(f"  🔸 【小标题】: {item.get('sub_title', '无')}")
                                print(f"  📝 【摘  要】: {item.get('summary', '无')}")
                                print(f"  🔗 【链  接】: {item.get('url', '无')}")
                                # 在终端里我们只提示抓取了多少字，不全部打印出来刷屏
                                print(f"  📦 【原  文】: [已加载完整原文，共 {raw_len} 字符送入 Agent 大脑]")
                                
                            print("="*55 + "\n")
                            print("Agent: ", end="", flush=True) 
                            
                        except json.JSONDecodeError:
                            print("\n[系统提示: 工具返回了非标准 JSON，跳过解析]\n")
                            print("Agent: ", end="", flush=True)
        
        
        
        except openai.BadRequestError as e:
            if e.code == 'content_filter':
                print("\n\n🛡️ [Azure/Cloud 拦截] 内容违反了云端安全策略。" )
            else:
                print(f"\n\n❌ API 错误: {e}")
        except Exception as e:
            print(f"\n\n❌ 系统运行错误: {e}")

        print("") 

        # --- 🛡️ 3. 输出防火墙审计 ---
        if full_response_text:
            out_safe, out_msg = check_output_safety(sanitized_prompt, full_response_text)
            if not out_safe:
                print(f"⚠️ [内容警告] {out_msg}")

if __name__ == "__main__":
    main()
