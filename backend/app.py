import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from core.env import load_env_from_file

env_path = os.path.join(current_dir, "env.sh")
load_env_from_file(env_path)

from agent.build_graph import graph_builder
from agent.tools.rag_tool import force_refresh_index
from core.files import DEFAULT_ALLOWED_EXTENSIONS, validate_upload_files
from core.http import (
    AppError,
    error_response,
    get_request_id,
    success_response,
    validate_identifier,
    validate_required_text,
)
from services.chat_service import build_agent_inputs, count_message_tokens, execute_agent
from services.history_service import log_to_history
from services.kb_service import KBService
from utils.security import check_input_safety, check_output_safety

SELECT_MODEL = os.environ.get("SELECT_MODEL", "gpt-4o")
MAX_INPUT_TOKENS = int(os.environ.get("MAX_INPUT_TOKENS", 10000))
MAX_FILE_PROMPT_CHARS = int(os.environ.get("MAX_FILE_PROMPT_CHARS", 10000))
FILE_CONTEXT_TAIL_CHARS = int(os.environ.get("FILE_CONTEXT_TAIL_CHARS", 3000))

agent_app = graph_builder.compile()
app = FastAPI(title="KLCLAB Backend API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HISTORY_DIR = Path(current_dir) / "history_storage"
HISTORY_DIR.mkdir(exist_ok=True)

kb_service = KBService()


def parse_users_field(users: Optional[str]) -> Optional[List[Any]]:
    if users is None:
        return None
    try:
        parsed = json.loads(users)
    except json.JSONDecodeError as exc:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_USERS_FIELD",
            "users 必须是合法的 JSON 数组字符串",
            detail={"error": str(exc)},
        ) from exc
    if not isinstance(parsed, list):
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_USERS_FIELD",
            "users 必须是 JSON 数组",
        )
    return parsed


def try_refresh_index() -> Dict[str, Any]:
    try:
        force_refresh_index()
        return {"refreshed": True, "error": None}
    except Exception as exc:
        print(f"[Index refresh error] {exc}")
        return {"refreshed": False, "error": str(exc)}


@app.middleware("http")
async def inject_request_id(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError):
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        detail=exc.detail,
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    for item in errors:
        loc = item.get("loc", ())
        msg = str(item.get("msg", ""))
        if len(loc) >= 2 and loc[0] == "body" and loc[1] == "files" and "Expected UploadFile" in msg:
            return error_response(
                request,
                status_code=status.HTTP_400_BAD_REQUEST,
                code="EMPTY_FILE_NAME",
                message="上传文件名不能为空",
                detail=errors,
            )
    return error_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="REQUEST_VALIDATION_ERROR",
        message="请求参数校验失败",
        detail=errors,
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException):
    return error_response(
        request,
        status_code=exc.status_code,
        code="HTTP_ERROR",
        message=str(exc.detail),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception):
    print(f"[Unhandled error][{get_request_id(request)}] {exc}")
    return error_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="系统内部错误",
        detail={"error": str(exc)},
    )


async def prepare_chat_inputs(
    *,
    message: str,
    files: Optional[List[UploadFile]],
    system_prompt: str,
    conversation_id: str,
    web_search: bool,
    db_version: Optional[str],
    kb_category: Optional[str],
    user_identity: Optional[str],
) -> Dict[str, Any]:
    sanitized_message_input = validate_required_text(message, "message", "EMPTY_MESSAGE")
    safe_conversation_id = validate_identifier(
        conversation_id,
        field_name="conversation_id",
        error_code="INVALID_CONVERSATION_ID",
    )
    safe_user_identity = (user_identity or "guest").strip() or "guest"
    safe_system_prompt = (system_prompt or "You are a helpful assistant").strip() or "You are a helpful assistant"
    safe_db_version = (db_version or "").strip() or None
    safe_kb_category = (kb_category or "").strip() or None

    sanitized_message, is_safe, error_msg = check_input_safety(sanitized_message_input)
    if not is_safe:
        raise AppError(status.HTTP_400_BAD_REQUEST, "INPUT_BLOCKED", error_msg)

    prepared = await build_agent_inputs(
        message=sanitized_message,
        files=files,
        system_prompt=safe_system_prompt,
        db_version=safe_db_version,
        kb_category=safe_kb_category,
        user_identity=safe_user_identity,
        web_search=web_search,
        select_model=SELECT_MODEL,
        max_input_tokens=MAX_INPUT_TOKENS,
        max_file_prompt_chars=MAX_FILE_PROMPT_CHARS,
        file_context_tail_chars=FILE_CONTEXT_TAIL_CHARS,
    )
    prepared.update(
        {
            "conversation_id": safe_conversation_id,
            "sanitized_message": sanitized_message,
            "user_identity": safe_user_identity,
        }
    )

    try:
        raw_tokens = count_message_tokens(prepared["raw_messages"])
        trimmed_tokens = count_message_tokens(prepared["trimmed_messages"])
        print(f"[Token Trim] raw={raw_tokens}, trimmed={trimmed_tokens}, max={MAX_INPUT_TOKENS}")
    except Exception as exc:
        print(f"[Token Debug Error] {exc}")

    return prepared


@app.delete("/api/chat/{conversation_id}")
async def delete_conversation(request: Request, conversation_id: str):
    safe_id = validate_identifier(
        conversation_id,
        field_name="conversation_id",
        error_code="INVALID_CONVERSATION_ID",
    )
    path = HISTORY_DIR / f"{safe_id}.json"
    if not path.exists():
        raise AppError(status.HTTP_404_NOT_FOUND, "CONVERSATION_NOT_FOUND", "对话历史不存在")
    try:
        os.remove(path)
    except Exception as exc:
        raise AppError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "DELETE_CONVERSATION_FAILED",
            "删除对话历史失败",
            detail={"error": str(exc)},
        ) from exc
    return success_response(request, message="对话历史删除成功", data={"conversation_id": safe_id})


@app.post("/api/chat")
async def chat_endpoint(
    request: Request,
    message: str = Form(...),
    files: List[UploadFile] = File(None),
    system_prompt: str = Form("You are a helpful assistant"),
    conversation_id: str = Form(...),
    web_search: bool = Form(False),
    db_version: Optional[str] = Form(None),
    kb_category: Optional[str] = Form(None),
    user_identity: Optional[str] = Form("guest"),
):
    prepared = await prepare_chat_inputs(
        message=message,
        files=files,
        system_prompt=system_prompt,
        conversation_id=conversation_id,
        web_search=web_search,
        db_version=db_version,
        kb_category=kb_category,
        user_identity=user_identity,
    )
    inputs = {
        "messages": prepared["trimmed_messages"],
        "enable_web": web_search,
        "select_model": SELECT_MODEL,
        "user_identity": prepared["user_identity"],
    }
    request_id = get_request_id(request)

    async def response_stream():
        try:
            result = await execute_agent(agent_app=agent_app, inputs=inputs, include_text_deltas=False)
            if result.full_text:
                yield result.full_text
                log_to_history(
                    HISTORY_DIR,
                    prepared["conversation_id"],
                    prepared["full_user_content"],
                    result.full_text,
                )
                out_safe, out_msg = check_output_safety(prepared["sanitized_message"], result.full_text)
                if not out_safe:
                    print(f"[Output safety warning][{request_id}] {out_msg}")
        except Exception as exc:
            print(f"[Chat stream error][{request_id}] {exc}")
            yield f"\n[系统错误][request_id={request_id}] {str(exc)}"

    return StreamingResponse(response_stream(), media_type="text/plain; charset=utf-8")


@app.post("/api/chat/events")
async def chat_events_endpoint(
    request: Request,
    message: str = Form(...),
    files: List[UploadFile] = File(None),
    system_prompt: str = Form("You are a helpful assistant"),
    conversation_id: str = Form(...),
    web_search: bool = Form(False),
    db_version: Optional[str] = Form(None),
    kb_category: Optional[str] = Form(None),
    user_identity: Optional[str] = Form("guest"),
):
    prepared = await prepare_chat_inputs(
        message=message,
        files=files,
        system_prompt=system_prompt,
        conversation_id=conversation_id,
        web_search=web_search,
        db_version=db_version,
        kb_category=kb_category,
        user_identity=user_identity,
    )
    inputs = {
        "messages": prepared["trimmed_messages"],
        "enable_web": web_search,
        "select_model": SELECT_MODEL,
        "user_identity": prepared["user_identity"],
    }
    result = await execute_agent(agent_app=agent_app, inputs=inputs, include_text_deltas=True)
    return success_response(
        request,
        message="会话事件获取成功",
        data={
            "conversation_id": prepared["conversation_id"],
            "events": result.events,
            "final_answer": result.full_text,
            "search_results": result.search_results,
        },
    )


@app.post("/api/chat/search-artifacts")
async def chat_search_artifacts_endpoint(
    request: Request,
    message: str = Form(...),
    files: List[UploadFile] = File(None),
    system_prompt: str = Form("You are a helpful assistant"),
    conversation_id: str = Form(...),
    web_search: bool = Form(True),
    db_version: Optional[str] = Form(None),
    kb_category: Optional[str] = Form(None),
    user_identity: Optional[str] = Form("guest"),
):
    prepared = await prepare_chat_inputs(
        message=message,
        files=files,
        system_prompt=system_prompt,
        conversation_id=conversation_id,
        web_search=web_search,
        db_version=db_version,
        kb_category=kb_category,
        user_identity=user_identity,
    )
    inputs = {
        "messages": prepared["trimmed_messages"],
        "enable_web": web_search,
        "select_model": SELECT_MODEL,
        "user_identity": prepared["user_identity"],
    }
    result = await execute_agent(agent_app=agent_app, inputs=inputs, include_text_deltas=False)
    return success_response(
        request,
        message="搜索抓取结果获取成功",
        data={
            "conversation_id": prepared["conversation_id"],
            "search_results": result.search_results,
            "result_count": len(result.search_results),
            "final_answer": result.full_text,
        },
    )


@app.get("/api/kb/list")
async def get_kb_list(request: Request):
    return success_response(request, data=kb_service.load_all(), message="知识库列表获取成功")


@app.get("/api/test/file_tree")
async def get_file_tree(request: Request):
    def build_tree(path: Path):
        node = {"label": path.name}
        if path.is_dir():
            children = [build_tree(p) for p in path.iterdir() if not p.name.startswith(".") and p.name != "__pycache__"]
            children.sort(key=lambda x: ("children" not in x, x["label"]))
            node["children"] = children
        return node

    docs_path = Path(current_dir).parent / "documents"
    if not docs_path.exists():
        return success_response(request, data=[], message="documents 目录不存在，返回空树")

    tree = [build_tree(p) for p in docs_path.iterdir() if not p.name.startswith(".")]
    tree.sort(key=lambda x: ("children" not in x, x["label"]))
    return success_response(request, data=tree, message="文件树获取成功")


@app.post("/api/kb/create")
async def create_kb(
    request: Request,
    name: str = Form(...),
    model: str = Form("openai"),
    category: str = Form("users/guest"),
):
    safe_name = validate_required_text(name, "name", "EMPTY_KB_NAME")
    safe_category = validate_required_text(category, "category", "EMPTY_KB_CATEGORY")
    safe_model = (model or "openai").strip() or "openai"
    kb = kb_service.create_kb(safe_name, safe_model, safe_category)
    return success_response(request, status_code=status.HTTP_201_CREATED, message="知识库创建成功", data=kb)


@app.post("/api/kb/update")
async def update_kb(
    request: Request,
    id: str = Form(...),
    name: Optional[str] = Form(None),
    remark: Optional[str] = Form(None),
    enabled: Optional[bool] = Form(None),
    users: Optional[str] = Form(None),
):
    kb_id = validate_identifier(id, field_name="id", error_code="INVALID_KB_ID")
    if not kb_service.get_kb(kb_id):
        raise AppError(status.HTTP_404_NOT_FOUND, "KB_NOT_FOUND", "知识库不存在")

    update_data: Dict[str, Any] = {}
    if name is not None:
        update_data["name"] = validate_required_text(name, "name", "EMPTY_KB_NAME")
    if remark is not None:
        update_data["remark"] = remark.strip()
    if enabled is not None:
        update_data["enabled"] = enabled

    parsed_users = parse_users_field(users)
    if parsed_users is not None:
        update_data["users"] = parsed_users
    if not update_data:
        raise AppError(status.HTTP_400_BAD_REQUEST, "EMPTY_UPDATE_PAYLOAD", "没有可更新的字段")

    result = kb_service.update_kb(kb_id, update_data)
    if not result:
        raise AppError(status.HTTP_404_NOT_FOUND, "KB_NOT_FOUND", "知识库不存在")
    return success_response(request, data=result, message="知识库更新成功")


@app.delete("/api/kb/{id}")
async def delete_kb(request: Request, id: str):
    kb_id = validate_identifier(id, field_name="id", error_code="INVALID_KB_ID")
    if not kb_service.get_kb(kb_id):
        raise AppError(status.HTTP_404_NOT_FOUND, "KB_NOT_FOUND", "知识库不存在")
    success = kb_service.delete_kb(kb_id)
    if not success:
        raise AppError(status.HTTP_500_INTERNAL_SERVER_ERROR, "DELETE_KB_FAILED", "知识库删除失败")

    refresh_state = try_refresh_index()
    message = "知识库删除成功" if refresh_state["refreshed"] else "知识库删除成功，但索引刷新失败"
    return success_response(request, message=message, data={"id": kb_id, "index_refresh": refresh_state})


@app.get("/api/kb/{id}/files")
async def get_kb_files(request: Request, id: str):
    kb_id = validate_identifier(id, field_name="id", error_code="INVALID_KB_ID")
    if not kb_service.get_kb(kb_id):
        raise AppError(status.HTTP_404_NOT_FOUND, "KB_NOT_FOUND", "知识库不存在")
    return success_response(request, data=kb_service.list_files(kb_id), message="知识库文件列表获取成功")


@app.post("/api/kb/{id}/upload")
async def upload_kb_file(request: Request, id: str, files: List[UploadFile] = File(...)):
    kb_id = validate_identifier(id, field_name="id", error_code="INVALID_KB_ID")
    if not kb_service.get_kb(kb_id):
        raise AppError(status.HTTP_404_NOT_FOUND, "KB_NOT_FOUND", "知识库不存在")

    uploads = validate_upload_files(files, field_error_code="EMPTY_FILES", allowed_extensions=DEFAULT_ALLOWED_EXTENSIONS)

    try:
        saved_names = kb_service.save_files(kb_id, uploads)
    except ValueError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, "INVALID_FILE_NAME", str(exc)) from exc
    except Exception as exc:
        raise AppError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "UPLOAD_FILE_FAILED",
            "文件上传失败",
            detail={"error": str(exc)},
        ) from exc

    refresh_state = try_refresh_index()
    message = "文件上传成功" if refresh_state["refreshed"] else "文件上传成功，但索引刷新失败"
    data = {
        "id": kb_id,
        "filenames": saved_names,
        "uploaded_count": len(saved_names),
        "index_refresh": refresh_state,
    }
    if len(saved_names) == 1:
        data["filename"] = saved_names[0]
    return success_response(request, status_code=status.HTTP_201_CREATED, message=message, data=data)


@app.post("/api/kb/{id}/delete_file")
async def delete_kb_file(request: Request, id: str, filename: str = Form(...)):
    kb_id = validate_identifier(id, field_name="id", error_code="INVALID_KB_ID")
    if not kb_service.get_kb(kb_id):
        raise AppError(status.HTTP_404_NOT_FOUND, "KB_NOT_FOUND", "知识库不存在")

    safe_filename = validate_required_text(filename, "filename", "EMPTY_FILE_NAME")
    try:
        deleted = kb_service.delete_file(kb_id, safe_filename)
    except ValueError as exc:
        raise AppError(status.HTTP_400_BAD_REQUEST, "INVALID_FILE_NAME", str(exc)) from exc
    except Exception as exc:
        raise AppError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "DELETE_FILE_FAILED",
            "文件删除失败",
            detail={"error": str(exc)},
        ) from exc
    if not deleted:
        raise AppError(status.HTTP_404_NOT_FOUND, "FILE_NOT_FOUND", "文件不存在")

    refresh_state = try_refresh_index()
    message = "文件删除成功" if refresh_state["refreshed"] else "文件删除成功，但索引刷新失败"
    return success_response(
        request,
        message=message,
        data={"id": kb_id, "filename": Path(safe_filename).name, "index_refresh": refresh_state},
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
