import json
import os
import sys
from typing import List, Optional, AsyncGenerator
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk

# 确保 backend 目录在 sys.path 中，以便正确导入 agent 包
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from agent.build_graph import graph_builder
from agent.tools.rag_tool import force_refresh_index # 新增导入

# ----------------------------- 
# 1. 环境与配置加载
# ----------------------------- 
env_path = os.path.join(current_dir, "env.sh")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("export "):
                content = line[7:].strip()
                if "=" in content:
                    key, value = content.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if " # " in value:
                        value = value.split(" # ")[0].strip()
                    os.environ[key] = value

# 编译 Agent：不使用 MemorySaver，确保 Agent 每次调用都是独立的，不带历史记忆
agent_app = graph_builder.compile() 

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HISTORY_DIR = Path("history_storage")
HISTORY_DIR.mkdir(exist_ok=True)

# ----------------------------- 
# 2. 后端存档逻辑 (静默记录)
# ----------------------------- 
def log_to_history(conv_id: str, user_msg: str, ai_msg: str):
    """仅在后端磁盘记录对话内容，不参与 Agent 的 prompt 计算"""
    safe_id = "".join(c for c in conv_id if c.isalnum() or c in ('-', '_'))
    path = HISTORY_DIR / f"{safe_id}.json"
    
    history = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except:
            pass
    
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": ai_msg})
    
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Logging Error: {e}")

# ----------------------------- 
# 3. API 接口
# ----------------------------- 

@app.delete("/api/chat/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """物理删除后端存储的该轮对话 JSON 记录"""
    safe_id = "".join(c for c in conversation_id if c.isalnum() or c in ('-', '_'))
    path = HISTORY_DIR / f"{safe_id}.json"
    if path.exists():
        try:
            os.remove(path)
            return {"status": "success", "message": f"History for {conversation_id} deleted."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "ignored", "message": "Not found."}

@app.post("/api/chat")
async def chat_endpoint(
    message: str = Form(...),
    files: List[UploadFile] = File(None),
    system_prompt: str = Form("You are a helpful assistant"),
    conversation_id: str = Form(...),
    web_search: bool = Form(False),
    db_version: Optional[str] = Form(None),
    kb_category: Optional[str] = Form(None),
    user_identity: Optional[str] = Form("guest") # 新增: 用户身份模拟
):
    # 处理上传文件内容
    file_context = ""
    for f in files or []:
        try:
            content = await f.read()
            text = content.decode("utf-8", errors="ignore")
            file_context += f"\n文件 {f.filename} 内容:\n{text[:5000]}"
        except:
            pass

    # 构造当前请求的完整内容
    full_user_content = message
    if db_version:
        full_user_content = f"从数据库{db_version}中 {full_user_content}"
    if file_context:
        full_user_content += f"\n\n--- 附件内容 ---\n{file_context}"

    # Agent 输入
    current_system_prompt = system_prompt
    if kb_category:
        instruction = (
            f"\n\n【重要指令】用户已选择在知识库分类 '{kb_category}' 中查询。"
            f"如果你需要检索内部文档，请务必调用 rag_tool 并将参数 category 设置为 '{kb_category}'。"
        )
        current_system_prompt += instruction

    inputs = {
        "messages": [
            SystemMessage(content=current_system_prompt),
            HumanMessage(content=full_user_content)
        ],
        "enable_web": web_search,
        "select_model": "gpt-4o",
        "user_identity": user_identity # 传入身份
    }

    async def response_stream():
        full_ai_response = ""
        try:
            # astream 运行不带 thread_id，确保不触发 LangGraph 的持久化记忆逻辑
            async for msg, metadata in agent_app.astream(inputs, stream_mode="messages"):
                node_name = metadata.get("langgraph_node", "")
                
                # 过滤输出节点：只显示最终回答的内容
                if node_name in ["chatbot_web", "chatbot_local"] and isinstance(msg, AIMessageChunk):
                    if msg.content:
                        yield msg.content
                        full_ai_response += msg.content
            
            # 流式结束后，静默存入后端磁盘
            if full_ai_response:
                log_to_history(conversation_id, full_user_content, full_ai_response)
                
        except Exception as e:
            yield f"\n[系统错误: {str(e)}]"

    return StreamingResponse(response_stream(), media_type="text/plain")

from services.kb_service import KBService

kb_service = KBService()

# --- KB Management API ---

@app.get("/api/kb/list")
async def get_kb_list():
    return kb_service.load_all()

@app.post("/api/kb/create")
async def create_kb(
    name: str = Form(...),
    model: str = Form("openai"),
    category: str = Form("users/guest")
):
    return kb_service.create_kb(name, model, category)

@app.post("/api/kb/update")
async def update_kb(
    id: str = Form(...),
    name: Optional[str] = Form(None),
    remark: Optional[str] = Form(None),
    enabled: Optional[bool] = Form(None),
    users: Optional[str] = Form(None) # JSON string
):
    update_data = {}
    if name is not None: update_data["name"] = name
    if remark is not None: update_data["remark"] = remark
    if enabled is not None: update_data["enabled"] = enabled
    if users is not None: update_data["users"] = json.loads(users)
    
    result = kb_service.update_kb(id, update_data)
    if result: return result
    return JSONResponse(status_code=404, content={"error": "KB not found"})

@app.delete("/api/kb/{id}")
async def delete_kb(id: str):
    success = kb_service.delete_kb(id)
    if success: return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "KB not found"})

@app.get("/api/kb/{id}/files")
async def get_kb_files(id: str):
    return kb_service.list_files(id)

@app.post("/api/kb/{id}/upload")
async def upload_kb_file(id: str, file: UploadFile = File(...)):
    success = kb_service.save_file(id, file)
    if success:
        force_refresh_index() # 刷新索引
        return {"status": "success"}
    return JSONResponse(status_code=500, content={"error": "Upload failed"})

@app.post("/api/kb/{id}/delete_file")
async def delete_kb_file(id: str, filename: str = Form(...)):
    success = kb_service.delete_file(id, filename)
    if success:
        force_refresh_index() # 刷新索引
        return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "File not found"})


if __name__ == "__main__":
    import uvicorn
    # 获取环境变量中的端口，默认 8000
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)