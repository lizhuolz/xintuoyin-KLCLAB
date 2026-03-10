import json
import os
import sys
import shutil
from typing import List, Optional, AsyncGenerator
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk, ToolMessage

# 确保 backend 目录在 sys.path 中
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from agent.build_graph import graph_builder
from agent.tools.rag_tool import force_refresh_index 
from utils.security import check_input_safety, check_output_safety 

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 目录配置
ROOT_DIR = Path(current_dir).parent
HISTORY_DIR = ROOT_DIR / "history_storage"
FEEDBACK_ROOT = ROOT_DIR / "feedbacks"

HISTORY_DIR.mkdir(exist_ok=True)
FEEDBACK_ROOT.mkdir(exist_ok=True)

app.mount("/api/static/feedbacks", StaticFiles(directory=str(FEEDBACK_ROOT)), name="feedbacks")

# 编译 Agent
agent_app = graph_builder.compile() 

# ----------------------------- 
# 引导逻辑：生成推荐提问
# ----------------------------- 
async def generate_recommendations(user_msg: str, ai_msg: str) -> str:
    try:
        from llama_index.core import Settings
        import re
        llm = Settings.llm 
        prompt = f"""你是一个对话引导助手。
根据以下对话内容，预测用户接下来最感兴趣、最可能追问的3个问题。
要求：1. 每个问题不超过20个字。2. 必须以纯JSON字符串数组格式返回。3. 不要包含任何多余解释。
用户问题: {user_msg}
AI回答: {ai_msg[:500]}"""
        response = await llm.acomplete(prompt)
        text = str(response).strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        return match.group(0) if match else "[]"
    except: return "[]"

# ----------------------------- 
# 对话接口
# ----------------------------- 

@app.post("/api/chat")
async def chat_endpoint(
    message: str = Form(...),
    files: List[UploadFile] = File(None),
    system_prompt: str = Form("You are a helpful assistant"),
    conversation_id: str = Form(...),
    web_search: bool = Form(False),
    db_version: Optional[str] = Form(None),
    kb_category: Optional[str] = Form(None),
    user_identity: Optional[str] = Form("guest") 
):
    sanitized_message, is_safe, error_msg = check_input_safety(message)
    if not is_safe:
        async def safety_error_stream(): yield f"⚠️ [安全拦截] {error_msg}"
        return StreamingResponse(safety_error_stream(), media_type="text/plain")

    inputs = {
        "messages": [SystemMessage(content=system_prompt), HumanMessage(content=sanitized_message)],
        "enable_web": web_search, "select_model": "gpt-4o", "user_identity": user_identity 
    }

    async def response_stream():
        full_ai_response = ""
        try:
            async for msg, metadata in agent_app.astream(inputs, stream_mode="messages"):
                node_name = metadata.get("langgraph_node", "")
                if node_name in ["chatbot_web", "chatbot_local"] and isinstance(msg, AIMessageChunk):
                    if msg.content:
                        yield msg.content
                        full_ai_response += msg.content
                elif isinstance(msg, ToolMessage) and msg.name == "tavily_search_with_summary":
                    try:
                        results = json.loads(msg.content).get("results", [])
                        clean = [{"main_title": r.get("main_title"), "sub_title": r.get("sub_title"), "summary": r.get("summary"), "url": r.get("url")} for r in results]
                        yield f"\n[SOURCES_JSON]:{json.dumps(clean, ensure_ascii=False)}\n"
                    except: pass
            
            if full_ai_response:
                rec_json = await generate_recommendations(sanitized_message, full_ai_response)
                if rec_json and rec_json != "[]": yield f"\n[RECOMMENDATIONS]:{rec_json}\n"
                
                safe_id = "".join(c for c in conversation_id if c.isalnum() or c in ('-', '_'))
                path = HISTORY_DIR / f"{safe_id}.json"
                history = []
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f: history = json.load(f)
                history.append({"role": "user", "content": sanitized_message})
                history.append({"role": "assistant", "content": full_ai_response})
                with open(path, "w", encoding="utf-8") as f: json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e: yield f"\n[系统错误: {str(e)}]"

    return StreamingResponse(response_stream(), media_type="text/plain")

# ----------------------------- 
# 历史维护 (支持内容检索)
# ----------------------------- 

@app.get("/api/history/list")
async def list_histories(search: str = ""):
    results = []
    for f in HISTORY_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as file:
                content = json.load(file)
                if search:
                    text_blob = "".join([m.get("content", "") for m in content]).lower()
                    if search.lower() not in text_blob: continue
                results.append({"id": f.stem, "title": content[0]["content"][:30] if content else "空对话", "updatedAt": os.path.getmtime(f), "messageCount": len(content)})
        except: pass
    results.sort(key=lambda x: x["updatedAt"], reverse=True)
    return results

@app.delete("/api/chat/{conversation_id}")
async def delete_history(conversation_id: str):
    path = HISTORY_DIR / f"{conversation_id}.json"
    if path.exists(): 
        os.remove(path)
        return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "not found"})

@app.post("/api/history/batch_delete")
async def batch_delete_history(data: dict):
    ids = data.get("ids", [])
    for hid in ids:
        path = HISTORY_DIR / f"{hid}.json"
        if path.exists(): os.remove(path)
    return {"status": "success"}

@app.get("/api/history/{conversation_id}")
async def get_history_detail(conversation_id: str):
    path = HISTORY_DIR / f"{conversation_id}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    return JSONResponse(status_code=404, content={"error": "not found"})

# ----------------------------- 
# 反馈维护 (点踩专用)
# ----------------------------- 

@app.post("/api/chat/feedback")
async def save_feedback(
    conversation_id: str = Form(...),
    message_index: int = Form(...),
    type: str = Form(...), # 'like' or 'dislike'
    user_identity: str = Form("guest"),
    contact_name: Optional[str] = Form(None),
    contact_phone: Optional[str] = Form(None),
    enterprise: Optional[str] = Form(None),
    reasons: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    files: List[UploadFile] = File(None)
):
    # 不需要记录点赞
    if type == 'like':
        return {"status": "success", "info": "like ignored"}

    today = datetime.now().strftime("%Y-%m-%d")
    feedback_id = f"{int(datetime.now().timestamp())}_{message_index}"
    target_dir = FEEDBACK_ROOT / today / feedback_id
    target_dir.mkdir(parents=True, exist_ok=True)
    
    image_names = []
    for i, f in enumerate(files or []):
        ext = os.path.splitext(f.filename)[1]
        name = f"user_{contact_name or 'unnamed'}_{i}{ext}"
        with open(target_dir / name, "wb") as out: shutil.copyfileobj(f.file, out)
        image_names.append(name)
    
    info = {
        "id": feedback_id, "date_path": today, "conversation_id": conversation_id,
        "contact_name": contact_name or user_identity, "contact_phone": contact_phone,
        "enterprise": enterprise, "type": type, "reasons": json.loads(reasons) if reasons else [],
        "comment": comment, "images": image_names, "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(target_dir / "feedback.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    return {"status": "success", "id": feedback_id}

@app.delete("/api/feedback/{date}/{id}")
async def delete_feedback(date: str, id: str):
    target_dir = FEEDBACK_ROOT / date / id
    if target_dir.exists() and target_dir.is_dir():
        shutil.rmtree(target_dir)
        # 如果日期文件夹空了，也删掉
        parent = target_dir.parent
        if not any(parent.iterdir()):
            shutil.rmtree(parent)
        return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "not found"})

@app.post("/api/feedback/batch_delete")
async def batch_delete_feedback(data: dict):
    # 期望数据格式: [{"date": "2024-03-10", "id": "123_4"}, ...]
    items = data.get("items", [])
    for item in items:
        date = item.get("date")
        fid = item.get("id")
        if date and fid:
            target_dir = FEEDBACK_ROOT / date / fid
            if target_dir.exists():
                shutil.rmtree(target_dir)
                parent = target_dir.parent
                if parent.exists() and not any(parent.iterdir()):
                    shutil.rmtree(parent)
    return {"status": "success"}

@app.get("/api/feedback/list")
async def list_feedbacks(name: str = "", enterprise: str = "", reason: str = ""):
    results = []
    for f_json in FEEDBACK_ROOT.glob("**/feedback.json"):
        try:
            with open(f_json, "r", encoding="utf-8") as f:
                d = json.load(f)
                if name and name.lower() not in d.get("contact_name", "").lower(): continue
                if enterprise and enterprise.lower() not in d.get("enterprise", "").lower(): continue
                if reason and reason not in d.get("reasons", []): continue
                results.append(d)
        except: pass
    results.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return results

# ----------------------------- 
# 结构测试 & 知识库 (略)
# ----------------------------- 
@app.get("/api/test/file_tree")
async def get_file_tree():
    def build_tree(path: Path):
        node = {"label": path.name}
        if path.is_dir():
            node["children"] = [build_tree(p) for p in sorted(path.iterdir()) if not p.name.startswith(".")]
        return node
    docs_root = ROOT_DIR / "documents"
    return [build_tree(docs_root)] if docs_root.exists() else []

from services.kb_service import KBService
kb_service = KBService()
@app.get("/api/kb/list")
async def get_kb_list(): return kb_service.load_all()
@app.post("/api/kb/create")
async def create_kb(name: str = Form(...), category: str = Form(...)): return kb_service.create_kb(name, category=category)
@app.delete("/api/kb/{id}")
async def delete_kb(id: str):
    if kb_service.delete_kb(id): return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "failed"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
