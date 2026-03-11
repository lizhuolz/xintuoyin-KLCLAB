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
USER_JSON_PATH = ROOT_DIR / "user.json"

# 收录目录
EXCELLENT_DIR = FEEDBACK_ROOT / "excellent_answers"
NEGATIVE_QA_DIR = FEEDBACK_ROOT / "negative_answers"

HISTORY_DIR.mkdir(exist_ok=True)
FEEDBACK_ROOT.mkdir(exist_ok=True)
EXCELLENT_DIR.mkdir(exist_ok=True)
NEGATIVE_QA_DIR.mkdir(exist_ok=True)

def get_logged_in_user():
    if USER_JSON_PATH.exists():
        with open(USER_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "name": "演示用户",
        "company": "演示公司",
        "phone": "13800000000",
        "ip_address": "127.0.0.1",
        "user_id": "UID_DEMO"
    }

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
async def list_histories(search: str = "", start_time: float = None, end_time: float = None):
    user = get_logged_in_user()
    results = []
    for f in HISTORY_DIR.glob("*.json"):
        try:
            mtime = os.path.getmtime(f)
            if start_time and mtime < start_time: continue
            if end_time and mtime > end_time: continue

            with open(f, "r", encoding="utf-8") as file:
                content = json.load(file)
                if search:
                    text_blob = "".join([m.get("content", "") for m in content]).lower()
                    if search.lower() not in text_blob: continue
                results.append({
                    "id": f.stem, 
                    "title": content[0]["content"][:30] if content else "空对话", 
                    "updatedAt": mtime, 
                    "messageCount": len(content),
                    "ip_address": user["ip_address"],
                    "user_id_display": user["user_id"],
                    "record_id": f"REC_{f.stem}"
                })
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
# 反馈维护
# ----------------------------- 

@app.post("/api/chat/feedback")
async def save_feedback(
    conversation_id: str = Form(...),
    message_index: int = Form(...),
    type: str = Form(...), # 'like' or 'dislike'
    user_identity: str = Form("guest"),
    reasons: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    files: List[UploadFile] = File(None)
):
    user = get_logged_in_user()
    
    target_question = "未知问题"
    target_answer = "未知回答"
    hist_path = HISTORY_DIR / f"{conversation_id}.json"
    if hist_path.exists():
        try:
            with open(hist_path, "r", encoding="utf-8") as f:
                history = json.load(f)
                if 0 <= message_index < len(history):
                    target_answer = history[message_index].get("content", "")
                    if message_index > 0:
                        target_question = history[message_index - 1].get("content", "")
        except: pass

    today = datetime.now().strftime("%Y-%m-%d")
    feedback_id = f"{int(datetime.now().timestamp())}_{message_index}"
    target_dir = FEEDBACK_ROOT / today / feedback_id
    target_dir.mkdir(parents=True, exist_ok=True)
    
    image_names = []
    for i, f in enumerate(files or []):
        ext = os.path.splitext(f.filename)[1]
        name = f"user_{user['name']}_{i}{ext}"
        with open(target_dir / name, "wb") as out: shutil.copyfileobj(f.file, out)
        image_names.append(name)
    
    # 解析原因结构
    reason_list = []
    if reasons:
        try:
            r_data = json.loads(reasons)
            if isinstance(r_data, dict):
                for k, v in r_data.items():
                    if v: reason_list.append(v)
            else:
                reason_list = r_data
        except:
            reason_list = [reasons]

    info = {
        "id": feedback_id, 
        "date_path": today, 
        "conversation_id": conversation_id,
        "type": type,
        "target_question": target_question,
        "target_answer": target_answer,
        "contact_name": user["name"],
        "contact_phone": user["phone"],
        "enterprise": user["company"],
        "reasons": reason_list,
        "comment": comment or ("用户点赞" if type == 'like' else ""),
        "images": image_names,
        "createdAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "process_status": "未处理",
        "process_result": "",
        "processor": ""
    }
    with open(target_dir / "feedback.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    return {"status": "success", "id": feedback_id}

@app.post("/api/feedback/process")
async def process_feedback(data: dict):
    # 参数: date_path, id, processor, is_collect
    date_path = data.get("date_path")
    fid = data.get("id")
    processor = data.get("processor", "系统管理员")
    is_collect = data.get("is_collect", False)
    
    f_path = FEEDBACK_ROOT / date_path / fid / "feedback.json"
    if not f_path.exists():
        return JSONResponse(status_code=404, content={"error": "not found"})
    
    with open(f_path, "r", encoding="utf-8") as f:
        info = json.load(f)
    
    # 更新状态
    info["process_status"] = "已处理"
    info["processor"] = processor
    
    # 收录逻辑
    if is_collect:
        target_dir = EXCELLENT_DIR if info["type"] == "like" else NEGATIVE_QA_DIR
        info["process_result"] = "已收录于优秀回答" if info["type"] == "like" else "已收录于负面回答"
        # 物理保存收录文件
        collect_file = target_dir / f"{fid}.json"
        with open(collect_file, "w", encoding="utf-8") as out:
            json.dump({
                "question": info["target_question"],
                "answer": info["target_answer"],
                "feedback_id": fid,
                "collectedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }, out, ensure_ascii=False, indent=2)
    else:
        info["process_result"] = "已处理 (未收录)"

    with open(f_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
        
    return {"status": "success"}

@app.delete("/api/feedback/{date}/{id}")
async def delete_feedback(date: str, id: str):
    target_dir = FEEDBACK_ROOT / date / id
    if target_dir.exists() and target_dir.is_dir():
        shutil.rmtree(target_dir)
        parent = target_dir.parent
        if not any(parent.iterdir()):
            shutil.rmtree(parent)
        return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "not found"})

@app.post("/api/feedback/batch_delete")
async def batch_delete_feedback(data: dict):
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
async def list_feedbacks(name: str = "", enterprise: str = "", type: str = ""):
    results = []
    # 查找所有 feedback.json
    for f_json in FEEDBACK_ROOT.glob("**/feedback.json"):
        # 排除收录文件夹
        if "excellent_answers" in str(f_json) or "negative_answers" in str(f_json):
            continue
            
        try:
            with open(f_json, "r", encoding="utf-8") as f:
                d = json.load(f)
                if name and name.lower() not in d.get("contact_name", "").lower(): continue
                if enterprise and enterprise.lower() not in d.get("enterprise", "").lower(): continue
                
                # 筛选逻辑：如果传入 like/dislike 则严格按 type 过滤
                if type in ["like", "dislike"]:
                    if d.get("type", "") != type: continue
                # 如果传入的是具体理由，则在 reasons 数组中过滤
                elif type:
                    if type not in d.get("reasons", []): continue
                
                results.append(d)
        except: pass
    results.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return results

# ----------------------------- 
# 结构测试 & 知识库
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
async def create_kb(
    name: str = Form(...), 
    category: str = Form(...),
    model: str = Form("openai")
): 
    return kb_service.create_kb(name, category=category, model=model)

@app.post("/api/kb/update")
async def update_kb(
    id: str = Form(...),
    name: Optional[str] = Form(None),
    remark: Optional[str] = Form(None),
    enabled: Optional[str] = Form(None),
    users: Optional[str] = Form(None)
):
    update_data = {}
    if name is not None: update_data["name"] = name
    if remark is not None: update_data["remark"] = remark
    if enabled is not None: 
        update_data["enabled"] = enabled.lower() == 'true' or enabled is True
    if users is not None: update_data["users"] = json.loads(users)
    
    result = kb_service.update_kb(id, update_data)
    if result: return result
    return JSONResponse(status_code=404, content={"error": "failed"})

@app.delete("/api/kb/{id}")
async def delete_kb(id: str):
    if kb_service.delete_kb(id): return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "failed"})

@app.get("/api/kb/{id}/files")
async def list_kb_files(id: str):
    return kb_service.list_files(id)

@app.post("/api/kb/{id}/upload")
async def upload_kb_file(id: str, file: UploadFile = File(...)):
    if kb_service.save_file(id, file):
        return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "failed"})

@app.post("/api/kb/{id}/delete_file")
async def delete_kb_file(id: str, filename: str = Form(...)):
    if kb_service.delete_file(id, filename):
        return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "failed"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
