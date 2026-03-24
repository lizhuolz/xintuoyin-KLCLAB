import json
import os
import sys
from typing import List, Optional
from pathlib import Path

import tiktoken
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import os
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    AIMessageChunk,
    trim_messages,
)

# 确保 backend 目录在 sys.path 中，以便正确导入 agent 包
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from agent.build_graph import graph_builder
from agent.tools.rag_tool import force_refresh_index
from utils.security import check_input_safety, check_output_safety
from services.kb_service import KBService
SELECT_MODEL = os.environ.get("SELECT_MODEL", "gpt-4o")
MAX_INPUT_TOKENS = int(os.environ.get("MAX_INPUT_TOKENS", 10000)) # 增加长度限定


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

kb_service = KBService()

# -----------------------------
# 2. Token 计数与消息裁剪
# -----------------------------

def get_token_encoder():
    """
    优先按 gpt-4o 编码；失败时回退到 cl100k_base。
    """
    try:
        return tiktoken.encoding_for_model("gpt-4o")
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def count_message_tokens(messages) -> int:
    """
    粗略统计消息总 token 数。
    """
    enc = get_token_encoder()
    total = 0

    for msg in messages:
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            total += len(enc.encode(content))
        else:
            total += len(enc.encode(str(content)))

        # 给角色/消息结构增加一点保守余量，避免低估
        total += 8

    return total


def trim_input_messages(messages, max_tokens: int = MAX_INPUT_TOKENS):
    """
    保留 system prompt，并将 messages 裁到 max_tokens 以内。
    """
    try:
        trimmed = trim_messages(
            messages,
            max_tokens=max_tokens,
            token_counter=count_message_tokens,
            strategy="last",
            include_system=True,
            start_on="human",
            allow_partial=False,
        )
        return trimmed
    except Exception as e:
        print(f"[Trim messages failed] {e}")
        return messages


# -----------------------------
# 3. 后端存档逻辑（静默记录）
# -----------------------------
def log_to_history(conv_id: str, user_msg: str, ai_msg: str):
    """
    仅在后端磁盘记录对话内容，不参与 Agent 的 prompt 计算
    """
    safe_id = "".join(c for c in conv_id if c.isalnum() or c in ("-", "_"))
    path = HISTORY_DIR / f"{safe_id}.json"

    history = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []

    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": ai_msg})

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Logging Error] {e}")


# -----------------------------
# 4. 文件解析
# -----------------------------
async def extract_file_text(files: Optional[List[UploadFile]]) -> str:
    """
    解析上传文件内容并拼成上下文。
    """
    file_context = ""

    for f in files or []:
        try:
            filename = (f.filename or "").lower()
            content = await f.read()
            text = ""

            if filename.endswith(".pdf"):
                from pypdf import PdfReader
                import io

                reader = PdfReader(io.BytesIO(content))
                pages = []
                for page in reader.pages:
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            pages.append(page_text)
                    except Exception:
                        pass
                text = "\n".join(pages)

            elif filename.endswith(".docx"):
                import docx2txt
                import io
                text = docx2txt.process(io.BytesIO(content))

            elif filename.endswith(".xlsx") or filename.endswith(".xls"):
                import pandas as pd
                import io

                df = pd.read_excel(io.BytesIO(content))
                text = df.to_string()

            else:
                text = content.decode("utf-8", errors="ignore")

            if text:
                # 避免附件内容过大，先做一次截断
                file_context += f"\n文件 {f.filename} 内容:\n{text[:10000]}"

        except Exception as e:
            print(f"[File parsing error] ({getattr(f, 'filename', 'unknown')}): {e}")
    print("[DEBUG] file_context:", file_context)
    return file_context


# -----------------------------
# 5. API 接口
# -----------------------------
@app.delete("/api/chat/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    物理删除后端存储的该轮对话 JSON 记录
    """
    safe_id = "".join(c for c in conversation_id if c.isalnum() or c in ("-", "_"))
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
    user_identity: Optional[str] = Form("guest"),
):
    # --- 安全检查 ---
    sanitized_message, is_safe, error_msg = check_input_safety(message)
    if not is_safe:
        async def safety_error_stream():
            yield f"⚠️ [安全拦截] {error_msg}"

        return StreamingResponse(safety_error_stream(), media_type="text/plain")

    # 解析上传文件
    file_context = await extract_file_text(files)

    # 构造用户完整输入
    full_user_content = sanitized_message
    if db_version:
        full_user_content = f"从数据库{db_version}中 {full_user_content}"
    if file_context:
        full_user_content += f"\n\n--- 附件内容 ---\n{file_context}"

    # 构造 system prompt
    current_system_prompt = system_prompt
    current_system_prompt += "\n\n【重要上下文】"
    current_system_prompt += f"\n- 当前用户身份: {user_identity}"
    current_system_prompt += (
        "\n- 你的任务: 优先通过调用 `rag_tool` 检索内部知识库。"
        "如果检索到内容，请务必【直接引用原文】或基于原文精准回答，严禁产生幻觉。"
        "如果未搜到内容，请如实告知。"
    )

    if kb_category:
        current_system_prompt += (
            f"\n- 用户偏好: 已指定分类 '{kb_category}'。"
            "请在调用 `rag_tool` 时参考此分类。"
        )

    # 原始消息
    raw_messages = [
        SystemMessage(content=current_system_prompt),
        HumanMessage(content=full_user_content),
    ]

    # 裁剪
    trimmed_messages = trim_input_messages(raw_messages, MAX_INPUT_TOKENS)

    try:
        raw_tokens = count_message_tokens(raw_messages)
        trimmed_tokens = count_message_tokens(trimmed_messages)
        print(f"[Token Trim] raw={raw_tokens}, trimmed={trimmed_tokens}, max={MAX_INPUT_TOKENS}")
    except Exception as e:
        print(f"[Token Debug Error] {e}")

    # Agent 输入
    inputs = {
        "messages": trimmed_messages,
        "enable_web": web_search,
        "select_model": SELECT_MODEL,
        "user_identity": user_identity,
    }

    async def response_stream():
        full_ai_response = ""
        try:
            # 不带 thread_id，确保不触发 LangGraph 的持久化记忆逻辑
            async for msg, metadata in agent_app.astream(inputs, stream_mode="messages"):
                node_name = metadata.get("langgraph_node", "")

                # 只输出最终回答节点
                if node_name in ["chatbot_web", "chatbot_local"] and isinstance(msg, AIMessageChunk):
                    if msg.content:
                        yield msg.content
                        full_ai_response += msg.content

            # 结束后静默存档
            if full_ai_response:
                log_to_history(conversation_id, full_user_content, full_ai_response)

                # 输出审计（仅记录风险，不拦截）
                out_safe, out_msg = check_output_safety(sanitized_message, full_ai_response)
                if not out_safe:
                    print(f"⚠️ [输出风险警告] {out_msg}")

        except Exception as e:
            yield f"\n[系统错误: {str(e)}]"

    return StreamingResponse(response_stream(), media_type="text/plain")


# -----------------------------
# 6. KB Management API
# -----------------------------
@app.get("/api/kb/list")
async def get_kb_list():
    return kb_service.load_all()


@app.get("/api/test/file_tree")
async def get_file_tree():
    """
    返回 documents 目录的物理树形结构
    """
    def build_tree(path: Path):
        node = {"label": path.name}
        if path.is_dir():
            children = [
                build_tree(p)
                for p in path.iterdir()
                if not p.name.startswith(".") and p.name != "__pycache__"
            ]
            children.sort(key=lambda x: ("children" not in x, x["label"]))
            node["children"] = children
        return node

    docs_path = Path(current_dir).parent / "documents"
    if not docs_path.exists():
        return []

    tree = [
        build_tree(p)
        for p in docs_path.iterdir()
        if not p.name.startswith(".")
    ]
    return tree


@app.post("/api/kb/create")
async def create_kb(
    name: str = Form(...),
    model: str = Form("openai"),
    category: str = Form("users/guest"),
):
    return kb_service.create_kb(name, model, category)


@app.post("/api/kb/update")
async def update_kb(
    id: str = Form(...),
    name: Optional[str] = Form(None),
    remark: Optional[str] = Form(None),
    enabled: Optional[bool] = Form(None),
    users: Optional[str] = Form(None),  # JSON string
):
    update_data = {}
    if name is not None:
        update_data["name"] = name
    if remark is not None:
        update_data["remark"] = remark
    if enabled is not None:
        update_data["enabled"] = enabled
    if users is not None:
        update_data["users"] = json.loads(users)

    result = kb_service.update_kb(id, update_data)
    if result:
        return result
    return JSONResponse(status_code=404, content={"error": "KB not found"})


@app.delete("/api/kb/{id}")
async def delete_kb(id: str):
    success = kb_service.delete_kb(id)
    if success:
        return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "KB not found"})


@app.get("/api/kb/{id}/files")
async def get_kb_files(id: str):
    return kb_service.list_files(id)


@app.post("/api/kb/{id}/upload")
async def upload_kb_file(id: str, file: UploadFile = File(...)):
    success = kb_service.save_file(id, file)
    if success:
        force_refresh_index()
        return {"status": "success"}
    return JSONResponse(status_code=500, content={"error": "Upload failed"})


@app.post("/api/kb/{id}/delete_file")
async def delete_kb_file(id: str, filename: str = Form(...)):
    success = kb_service.delete_file(id, filename)
    if success:
        force_refresh_index()
        return {"status": "success"}
    return JSONResponse(status_code=404, content={"error": "File not found"})


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)