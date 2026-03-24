import json
import os
import sys
import shutil
from typing import List, Optional, AsyncGenerator
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, Query, Path as FastPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, AIMessageChunk, ToolMessage

# 确保 backend 目录在 sys.path 中，防止模块导入失败
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from agent.build_graph import graph_builder
from agent.tools.rag_tool import force_refresh_index 
from utils.security import check_input_safety, check_output_safety 

app = FastAPI(
    title="研发猫 AI 系统 - 后端接口服务",
    description="支持流式对话、层级 RAG 检索、对话审计及反馈处理的核心后端服务。",
    version="1.0.0"
)

# 允许跨域请求（CORS），方便前端本地调试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 物理目录路径配置
ROOT_DIR = Path(current_dir).parent
HISTORY_DIR = ROOT_DIR / "history_storage"
FEEDBACK_ROOT = ROOT_DIR / "feedbacks"
USER_JSON_PATH = ROOT_DIR / "user.json"

# 反馈收录分类目录
EXCELLENT_DIR = FEEDBACK_ROOT / "excellent_answers"
NEGATIVE_QA_DIR = FEEDBACK_ROOT / "negative_answers"

# 确保必要的存储目录存在
HISTORY_DIR.mkdir(exist_ok=True)
FEEDBACK_ROOT.mkdir(exist_ok=True)
EXCELLENT_DIR.mkdir(exist_ok=True)
NEGATIVE_QA_DIR.mkdir(exist_ok=True)

def get_logged_in_user():
    """从本地 user.json 读取当前模拟登录的用户信息"""
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

# 挂载静态资源目录，用于前端直接预览反馈截图
app.mount("/api/static/feedbacks", StaticFiles(directory=str(FEEDBACK_ROOT)), name="feedbacks")

from langgraph.checkpoint.memory import MemorySaver

# 编译 Agent 引擎 (注入 MemorySaver 实现状态检查点，支持自动上下文关联)
memory = MemorySaver()
agent_app = graph_builder.compile(checkpointer=memory) 

# ----------------------------- 
# 引导逻辑：生成推荐提问
# ----------------------------- 
async def generate_recommendations(user_msg: str, ai_msg: str) -> str:
    """根据当次对话内容，智能生成 3 个用户可能感兴趣的追问建议"""
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
# 对话接口 (Chat APIs)
# ----------------------------- 

@app.get("/api/chat/new_session", 
    summary="初始化并获取新会话 ID", 
    description="在开启一个全新的对话窗口前调用。后端生成基于时间戳的唯一标识，用于后续关联上下文记忆。",
    responses={200: {"description": "成功生成并返回唯一会话 ID"}}
)
async def create_new_session():
    new_id = f"{int(datetime.now().timestamp() * 1000)}"
    return {"conversation_id": new_id}

@app.post("/api/chat", 
    summary="AI 流式对话检索接口", 
    description="系统核心接口。支持上传附件分析、联网实时搜索、以及针对知识库的 RAG 增强检索。响应采用 HTTP Streaming 实时推送文本。",
    responses={
        200: {"description": "流式文本响应，包含 [SOURCES_JSON] 和 [RECOMMENDATIONS] 标记"}, 
        400: {"description": "安全拦截（包含违禁词）或请求参数非法"},
        422: {"description": "字段验证失败（如缺失必填参数）"}
    }
)
async def chat_endpoint(
    message: str = Form(..., description="用户输入的提问文本内容"),
    files: List[UploadFile] = File(None, description="用户上传的附件列表（可选），支持 PDF、Word、Excel、PPT、Markdown 等格式"),
    system_prompt: str = Form("You are a helpful assistant", description="AI 的人格设定或系统提示词"),
    conversation_id: str = Form(..., description="对话唯一标识。相同 ID 的连续请求将自动加载上下文记忆"),
    web_search: bool = Form(False, description="是否启用联网搜索功能以获取最新互联网资讯"),
    db_version: Optional[str] = Form(None, description="指定特定的向量数据库版本（可选）"),
    # kb_category: Optional[str] = Form(None, description="限定检索的知识库范围（如：全量、部门、或特定分类）"),
    user_identity: Optional[str] = Form("guest", description="用户身份标识，用于权限隔离和行为审计") 
):
    # 1. 基础安全校验
    sanitized_message, is_safe, error_msg = check_input_safety(message)
    if not is_safe:
        async def safety_error_stream(): yield f"⚠️ [安全拦截] {error_msg}"
        return StreamingResponse(safety_error_stream(), media_type="text/plain")

    # 2. 构造 Agent 运行参数
    inputs = {
        "messages": [SystemMessage(content=system_prompt), HumanMessage(content=sanitized_message)],
        "enable_web": web_search, 
        "select_model": "gpt-4o", 
        "user_identity": user_identity 
    }

    # 注入线程 ID 激活上下文记忆
    config = {"configurable": {"thread_id": conversation_id}}

    async def response_stream():
        full_ai_response = ""
        try:
            # 3. 调用 Agent 执行图，流式获取结果
            async for msg, metadata in agent_app.astream(inputs, config=config, stream_mode="messages"):
                node_name = metadata.get("langgraph_node", "")
                # 兼容 invoke() 产出的 AIMessage 和流式产出的 AIMessageChunk。
                if node_name in ["chatbot_web", "chatbot_local", "sql_answer"] and isinstance(msg, (AIMessageChunk, AIMessage)):
                    if msg.content:
                        yield msg.content
                        full_ai_response += msg.content
                # 处理联网搜索返回的参考链接
                elif isinstance(msg, ToolMessage) and msg.name == "tavily_search_with_summary":
                    try:
                        results = json.loads(msg.content).get("results", [])
                        clean = [{"main_title": r.get("main_title"), "url": r.get("url"), "summary": r.get("summary")} for r in results]
                        yield f"\n[SOURCES_JSON]:{json.dumps(clean, ensure_ascii=False)}\n"
                    except: pass
            
            # 4. 会话结束后的补充逻辑
            if full_ai_response:
                # 生成追问建议并推送到流末尾
                rec_json = await generate_recommendations(sanitized_message, full_ai_response)
                if rec_json and rec_json != "[]": yield f"\n[RECOMMENDATIONS]:{rec_json}\n"
                
                # 持久化保存本次对话记录到物理文件（用于审计）
                safe_id = "".join(c for c in conversation_id if c.isalnum() or c in ('-', '_'))
                path = HISTORY_DIR / f"{safe_id}.json"
                history = []
                if path.exists():
                    with open(path, "r", encoding="utf-8") as f: history = json.load(f)
                history.append({"role": "user", "content": sanitized_message})
                history.append({"role": "assistant", "content": full_ai_response})
                with open(path, "w", encoding="utf-8") as f: json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e: 
            yield f"\n[系统错误: {str(e)}]"

    return StreamingResponse(response_stream(), media_type="text/plain")

# ----------------------------- 
# 历史维护 (History APIs)
# ----------------------------- 

@app.get("/api/history/list", 
    summary="获取对话历史摘要列表", 
    description="用于管理后台。支持按关键字搜索标题或对话内容，支持按时间范围筛选。",
    responses={200: {"description": "返回历史记录数组，包含标题、消息数、更新时间等"}}
)
async def list_histories(
    search: str = Query("", description="搜索关键词，支持匹配标题及对话正文"), 
    start_time: float = Query(None, description="起始时间戳（Unix Timestamp，秒）"), 
    end_time: float = Query(None, description="结束时间戳（Unix Timestamp，秒）")
):
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

@app.delete("/api/chat/{conversation_id}", 
    summary="删除单条对话历史记录", 
    description="物理删除服务器上存储的对应 JSON 历史文件。",
    responses={200: {"description": "删除成功"}, 404: {"description": "未找到对应的历史记录"}}
)
async def delete_history(
    conversation_id: str = FastPath(..., description="要删除的会话唯一 ID")
):
    path = HISTORY_DIR / f"{conversation_id}.json"
    if path.exists(): 
        os.remove(path)
        return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "not found"})

@app.post("/api/history/batch_delete", 
    summary="批量删除对话历史", 
    description="根据传入的 ID 列表，批量清理物理历史文件。",
    responses={200: {"description": "批量删除操作完成"}, 422: {"description": "参数格式错误"}}
)
async def batch_delete_history(data: dict):
    ids = data.get("ids", [])
    for hid in ids:
        path = HISTORY_DIR / f"{hid}.json"
        if path.exists(): os.remove(path)
    return {"status": "success"}

@app.get("/api/history/{conversation_id}", 
    summary="获取指定对话的详细内容", 
    description="加载并返回该会话完整的 User 和 Assistant 消息数组。",
    responses={200: {"description": "返回消息数组"}, 404: {"description": "记录不存在"}}
)
async def get_history_detail(
    conversation_id: str = FastPath(..., description="会话 ID")
):
    path = HISTORY_DIR / f"{conversation_id}.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    return JSONResponse(status_code=404, content={"error": "not found"})

# ----------------------------- 
# 反馈维护 (Feedback APIs)
# ----------------------------- 

@app.post("/api/chat/feedback", 
    summary="提交用户反馈 (点赞/点踩)", 
    description="当用户点击点赞或点踩时触发。支持状态切换逻辑：再次点击相同类型视为取消，点击不同类型视为覆盖。操作会同步回写到对话历史 JSON 中。",
    responses={200: {"description": "反馈状态已更新并同步至历史记录"}}
)
async def save_feedback(
    conversation_id: str = Form(..., description="关联的会话 ID"),
    message_index: int = Form(..., description="反馈的消息在历史数组中的索引位置"),
    type: str = Form(..., description="反馈类型：'like'（赞）或 'dislike'（踩）"), 
    reasons: Optional[str] = Form(None, description="勾选的理由分类（JSON 字符串）"),
    comment: Optional[str] = Form(None, description="用户的详细文字评价"),
    files: List[UploadFile] = File(None, description="用户上传的反馈截图列表")
):
    user = get_logged_in_user()
    
    # 1. 核心逻辑：更新历史记录中的反馈状态
    hist_path = HISTORY_DIR / f"{conversation_id}.json"
    current_feedback_state = None
    target_question, target_answer = "未知问题", "未知回答"
    
    if hist_path.exists():
        try:
            with open(hist_path, "r", encoding="utf-8") as f:
                history = json.load(f)
            
            if 0 <= message_index < len(history):
                msg = history[message_index]
                old_feedback = msg.get("feedback")
                
                # 状态机切换
                if old_feedback == type:
                    # 再次点击相同类型 -> 取消
                    msg["feedback"] = None
                    current_feedback_state = "canceled"
                else:
                    # 不同类型或首次评价 -> 设置/覆盖
                    msg["feedback"] = type
                    current_feedback_state = type
                
                # 校验逻辑：如果是点踩且不是取消操作，必须有内容
                if current_feedback_state == 'dislike':
                    # 只要 reasons(解析后), comment, files 任意一个有值就行
                    has_reasons = False
                    if reasons:
                        try:
                            r_data = json.loads(reasons)
                            has_reasons = any(v for v in r_data.values() if v) if isinstance(r_data, dict) else bool(r_data)
                        except: has_reasons = True
                    
                    if not any([has_reasons, comment, files]):
                        return JSONResponse(
                            status_code=400, 
                            content={"error": "点踩反馈必须填写原因、描述或上传截图"}
                        )

                # 提取 QA 快照用于反馈存证
                target_answer = msg.get("content", "")
                if message_index > 0:
                    target_question = history[message_index - 1].get("content", "")
            
            # 回写历史文件
            with open(hist_path, "w", encoding="utf-8") as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error updating history feedback: {e}")

    # 2. 物理存证逻辑 (Option B: 幂等文件夹)
    # 反馈 ID 采用固定格式：fb_{会话ID}_{索引}
    feedback_id = f"fb_{conversation_id}_{message_index}"
    
    # 为了追溯，我们按首个反馈生成的日期存放，如果已存在则沿用
    today = datetime.now().strftime("%Y-%m-%d")
    # 查找是否已有该反馈的目录（可能在不同日期）
    existing_dirs = list(FEEDBACK_ROOT.glob(f"**/{feedback_id}"))
    if existing_dirs:
        target_dir = existing_dirs[0]
    else:
        target_dir = FEEDBACK_ROOT / today / feedback_id
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存/更新反馈数据
    info_path = target_dir / "feedback.json"
    image_names = []
    
    # 如果是追加图片
    if info_path.exists():
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                old_info = json.load(f)
                image_names = old_info.get("images", [])
        except: pass

    # 保存新上传的图片
    for i, f in enumerate(files or []):
        ext = os.path.splitext(f.filename)[1]
        name = f"feedback_{len(image_names) + i}{ext}"
        with open(target_dir / name, "wb") as out:
            shutil.copyfileobj(f.file, out)
        image_names.append(name)
    
    # 解析原因
    reason_list = []
    if reasons:
        try:
            r_data = json.loads(reasons)
            reason_list = [v for v in r_data.values() if v] if isinstance(r_data, dict) else r_data
        except: reason_list = [reasons]

    # 构建完整的反馈详情
    info = {
        "id": feedback_id,
        "conversation_id": conversation_id,
        "message_index": message_index,
        "type": type,
        "status": current_feedback_state, # "like", "dislike", "canceled"
        "is_canceled": current_feedback_state == "canceled",
        "target_question": target_question,
        "target_answer": target_answer,
        "contact_name": user["name"],
        "contact_phone": user["phone"],
        "enterprise": user["company"],
        "reasons": reason_list,
        "comment": comment or "",
        "images": image_names,
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "process_status": "未处理"
    }
    
    # 如果是首次创建，记录 createdAt
    if not info_path.exists():
        info["createdAt"] = info["updatedAt"]
    else:
        # 保留原有的 createdAt
        try:
            with open(info_path, "r", encoding="utf-8") as f:
                old_info = json.load(f)
                info["createdAt"] = old_info.get("createdAt", info["updatedAt"])
        except: pass

    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
        
    return {
        "status": "success", 
        "feedback_state": current_feedback_state,
        "id": feedback_id
    }

@app.get("/api/feedback/detail/{date}/{id}",
    summary="获取单条反馈详情",
    description="根据日期目录和反馈 ID 加载完整的反馈 JSON 数据。",
    responses={200: {"description": "返回反馈详情内容"}, 404: {"description": "反馈不存在"}}
)
async def get_feedback_detail(
    date: str = FastPath(..., description="反馈日期目录"), 
    id: str = FastPath(..., description="反馈唯一 ID")
):
    f_path = FEEDBACK_ROOT / date / id / "feedback.json"
    if f_path.exists():
        with open(f_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return JSONResponse(status_code=404, content={"error": "feedback record not found"})

@app.post("/api/feedback/process", 
    summary="管理端处理反馈 (审核并收录)", 
    description="对反馈进行人工审核。支持收录到优秀回答或负面案例库，并同步更新处理状态。",
    responses={200: {"description": "处理状态更新成功"}, 404: {"description": "反馈记录不存在"}}
)
async def process_feedback(data: dict):
    # 明确参数提取
    date_path = data.get("date_path")
    fid = data.get("id")
    processor = data.get("processor", "系统管理员")
    is_collect = data.get("is_collect", False) # 是否收录
    
    f_path = FEEDBACK_ROOT / date_path / fid / "feedback.json"
    if not f_path.exists(): return JSONResponse(status_code=404, content={"error": "not found"})
    
    with open(f_path, "r", encoding="utf-8") as f: info = json.load(f)
    
    # 更新基础处理状态
    info["process_status"] = "已处理"
    info["processor"] = processor
    info["processedAt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 执行收录逻辑
    if is_collect:
        # 如果是点赞则收录到优秀库，点踩收录到负面库
        target_dir = EXCELLENT_DIR if info["type"] == "like" else NEGATIVE_QA_DIR
        info["process_result"] = "已收录"
        
        collect_file = target_dir / f"{fid}.json"
        with open(collect_file, "w", encoding="utf-8") as out:
            json.dump({
                "question": info.get("target_question"),
                "answer": info.get("target_answer"),
                "feedback_id": fid,
                "original_type": info["type"],
                "collectedAt": info["processedAt"]
            }, out, ensure_ascii=False, indent=2)
    else:
        info["process_result"] = "已处理 (未收录)"

    # 回写更新后的详情
    with open(f_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
        
    return {"status": "success", "data": info}

@app.delete("/api/feedback/{date}/{id}", 
    summary="删除指定反馈记录", 
    description="删除整个反馈文件夹及其下的所有截图和 JSON 文件。",
    responses={200: {"description": "成功物理删除"}, 404: {"description": "反馈不存在"}}
)
async def delete_feedback(
    date: str = FastPath(..., description="反馈日期目录 (如 2025-03-11)"), 
    id: str = FastPath(..., description="反馈唯一 ID")
):
    target_dir = FEEDBACK_ROOT / date / id
    if target_dir.exists() and target_dir.is_dir():
        shutil.rmtree(target_dir)
        return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "not found"})

@app.get("/api/feedback/list", 
    summary="获取反馈审计全量列表", 
    description="扫描服务器反馈目录，返回结构化的反馈详情列表。",
    responses={200: {"description": "返回反馈详情数组"}}
)
async def list_feedbacks(
    name: str = Query("", description="按反馈人姓名筛选"), 
    enterprise: str = Query("", description="按所属企业筛选"), 
    type: str = Query("", description="按类型(like/dislike)筛选")
):
    results = []
    for f_json in FEEDBACK_ROOT.glob("**/feedback.json"):
        if "excellent_answers" in str(f_json) or "negative_answers" in str(f_json): continue
        try:
            with open(f_json, "r", encoding="utf-8") as f:
                d = json.load(f)
                if name and name.lower() not in d.get("contact_name", "").lower(): continue
                if enterprise and enterprise.lower() not in d.get("enterprise", "").lower(): continue
                if type and d.get("type", "") != type: continue
                results.append(d)
        except: pass
    results.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
    return results

# ----------------------------- 
# 知识库与工具 (Knowledge Base APIs)
# ----------------------------- 

from services.kb_service import KBService
kb_service = KBService()

@app.get("/api/kb/list", summary="获取所有知识库的基本信息列表")
async def get_kb_list(): return kb_service.load_all()

@app.post("/api/kb/create", 
    summary="创建一个新的知识库", 
    description="根据用户信息和所选分类，后端会自动在物理路径创建对应文件夹并初始化元数据。",
    responses={200: {"description": "知识库创建成功并已准备好接收文件"}}
)
async def create_kb(
    name: str = Form(..., description="知识库名称"), 
    category: str = Form(..., description="知识库分类（企业知识库、部门知识库、个人知识库）"),
    model: str = Form("openai", description="使用的向量 Embedding 模型（默认为 openai）")
): 
    return kb_service.create_kb(name, category=category, model=model)

@app.post("/api/kb/update", 
    summary="更新知识库元数据（含启用/禁用状态）", 
    description="支持修改名称、备注、以及开关状态。状态变更会触发 RAG 索引的实时热重载。",
    responses={200: {"description": "更新成功"}, 404: {"description": "知识库不存在"}}
)
async def update_kb(
    id: str = Form(..., description="知识库唯一 ID"),
    name: Optional[str] = Form(None, description="新的名称"),
    remark: Optional[str] = Form(None, description="新的备注说明"),
    enabled: Optional[str] = Form(None, description="是否启用 ('true'/'false')"),
    users: Optional[str] = Form(None, description="有权访问的用户列表 (JSON 数组)")
):
    update_data = {}
    if name is not None: update_data["name"] = name
    if remark is not None: update_data["remark"] = remark
    if enabled is not None: update_data["enabled"] = enabled.lower() == 'true'
    if users is not None: update_data["users"] = json.loads(users)
    
    result = kb_service.update_kb(id, update_data)
    if result: return result
    return JSONResponse(status_code=404, content={"error": "failed"})

@app.get("/api/kb/{id}/files", 
    summary="获取指定知识库下的文件清单", 
    responses={200: {"description": "返回文件详情列表，含名称、大小、上传时间等"}}
)
async def list_kb_files(id: str = FastPath(..., description="知识库 ID")):
    return kb_service.list_files(id)

@app.post("/api/kb/{id}/upload", 
    summary="向知识库上传文档并自动索引", 
    description="上传文件后，系统会自动触发文本切片及向量 Embedding，并更新 RAG 索引。",
    responses={200: {"description": "上传并索引成功"}}
)
async def upload_kb_file(
    id: str = FastPath(..., description="知识库 ID"), 
    file: UploadFile = File(..., description="要上传的物理文件")
):
    if kb_service.save_file(id, file): return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "failed"})

@app.post("/api/kb/{id}/delete_file", 
    summary="从知识库中永久删除指定文档", 
    description="删除物理文件，并同步清理向量索引中的相关数据。",
    responses={200: {"description": "删除及索引同步成功"}}
)
async def delete_kb_file(
    id: str = FastPath(..., description="知识库 ID"), 
    filename: str = Form(..., description="要删除的文件完整名称")
):
    if kb_service.delete_file(id, filename): return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "failed"})

if __name__ == "__main__":
    import uvicorn
    # 本地启动命令：pixi run python app.py
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
