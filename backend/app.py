import json
import asyncio
import base64
import io
import csv
import mimetypes
import os
import re
import sys
import shutil
import zipfile
import subprocess
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Dict, List, Literal, Optional
from xml.etree import ElementTree as ET

from fastapi import Body, Depends, FastAPI, File, Form, Header, Query, Request, UploadFile
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile as StarletteUploadFile

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage

# 确保 backend 目录在 sys.path 中，防止模块导入失败
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from agent.build_graph import graph_builder
from services.kb_service import KBService
from services.storage_service import storage_service
from utils.DB_vllm_32B import DB as DatabaseSelector

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

app = FastAPI(
    title="研发猫 AI 系统 - 后端接口服务",
    description="支持对话、历史、反馈、知识库管理的后端服务。所有接口通过 header `accessToken` 识别用户身份。",
    version="2.0.0",
    openapi_url=None,
    openapi_tags=[
        {"name": "AI对话/对话", "description": "会话创建、对话交互、思考过程、系统配置。"},
        {"name": "AI对话/对话日志", "description": "企业端：用户查看和删除自己的对话历史。"},
        {"name": "AI对话/反馈", "description": "点赞点踩反馈提交。"},
        {"name": "AI对话/知识库", "description": "知识库创建、更新、文件管理、使用人选择与删除。"},
        {"name": "AI对话/文件上传", "description": "统一文件上传接口，返回临时 file_id，供其他业务接口引用。"},
        {"name": "管理端/对话日志", "description": "管理端：查看所有用户的对话历史、导出、删除。"},
        {"name": "管理端/反馈", "description": "管理端：反馈列表查看、处理、导出、删除。"},
        {"name": "管理端/数据库", "description": "管理端：数据库连接管理。"},
        {"name": "管理端/知识库", "description": "管理端：知识库全权限管理。"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Stream-Id"],
)

from services.user_auth import get_user_by_token, set_current_user, make_guest_user


async def _resolve_user(request: Request):
    """FastAPI 依赖：从 header 解析用户身份并设置到 contextvars。
    作为全局依赖自动注入所有接口，无需手动声明。"""
    token = request.headers.get("accesstoken") or request.query_params.get("accessToken") or ""
    ip = request.client.host if request.client else ""
    if token:
        user = get_user_by_token(token)
        if user:
            user["access_token"] = token
            user["ip_address"] = ip
            set_current_user(user)
            return
    guest = make_guest_user(ip)
    guest["access_token"] = ""
    set_current_user(guest)


# 全局依赖：每个请求自动执行用户解析
app.router.dependencies.append(Depends(_resolve_user))

from config import PROJECT_ROOT as ROOT_DIR, DATA_DIR, USER_JSON_FILE as USER_JSON_PATH, now_ms, now_display

HISTORY_MINIO_PREFIX = "history"

from services import db_registry  # noqa: E402  路由层依赖

agent_app = graph_builder.compile()


@app.on_event("startup")
async def on_startup():
    """启动时清理超过1小时的 staging 文件，并初始化数据库注册表。"""
    try:
        storage_service.ensure_ready()
        one_hour_ago = datetime.now() - timedelta(hours=1)
        for obj in storage_service.client.list_objects(storage_service.bucket_name, prefix="staging/", recursive=True):
            if obj.last_modified and obj.last_modified.replace(tzinfo=None) < one_hour_ago:
                storage_service.client.remove_object(storage_service.bucket_name, obj.object_name)
    except Exception:
        pass
    try:
        db_registry.initialize_on_startup()
    except Exception as exc:
        print(f"[startup] db_registry 初始化失败: {exc}")


kb_service = KBService()
VALID_FEEDBACK_TYPES = {"like", "dislike"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def new_conversation_id() -> str:
    return f"{now_ms()}-{uuid.uuid4().hex[:8]}"


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def normalize_db_version(value: Optional[str]) -> Optional[str]:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    mapping = {
        "v0": "1",
        "0": "1",
        "1": "1",
        "v1": "2",
        "2": "2",
    }
    return mapping.get(lowered, text)


def _fill_openapi_schema_descriptions(schema: dict):
    components = schema.get("components", {}).get("schemas", {})

    def resolve_schema(node):
        if not isinstance(node, dict):
            return None
        ref = node.get("$ref")
        if ref and ref.startswith("#/components/schemas/"):
            return components.get(ref.rsplit("/", 1)[-1], {})
        return node

    def fill_schema(node):
        node = resolve_schema(node)
        if not isinstance(node, dict):
            return
        properties = node.get("properties", {})
        for prop_name, prop_schema in properties.items():
            if isinstance(prop_schema, dict):
                prop_schema.setdefault("description", f"{prop_name} 字段")
                fill_schema(prop_schema)
        items = node.get("items")
        if isinstance(items, dict):
            fill_schema(items)
        for group_name in ("allOf", "anyOf", "oneOf"):
            for group_item in node.get(group_name, []) or []:
                fill_schema(group_item)

    for component_schema in components.values():
        fill_schema(component_schema)

    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for parameter in operation.get("parameters", []) or []:
                if isinstance(parameter, dict):
                    parameter.setdefault("description", f"{parameter.get('name', 'parameter')} 参数")
            request_body = operation.get("requestBody")
            if isinstance(request_body, dict):
                request_body.setdefault("description", "请求体参数")
                for media in request_body.get("content", {}).values():
                    media_schema = media.get("schema")
                    fill_schema(media_schema)


def custom_openapi_schema():
    if app.openapi_schema:
        return app.openapi_schema
    app.openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    _fill_openapi_schema_descriptions(app.openapi_schema)
    # 给企业端接口注入 accessToken header（管理端 /api/admin/ 不需要）
    access_token_param = {
        "name": "accessToken",
        "in": "header",
        "required": False,
        "schema": {"type": "string"},
        "description": "用户登录 token。无 token 视为游客；不同 token 对应不同权限（普通用户/企业管理员）。",
    }
    # 不需要显示 accessToken 的路由
    no_token_paths = {"/api/upload", "/api/config/enums"}
    for path, path_item in app.openapi_schema.get("paths", {}).items():
        if "/admin/" in path or path in no_token_paths:
            continue
        for operation in path_item.values():
            if isinstance(operation, dict):
                params = operation.setdefault("parameters", [])
                if not any(p.get("name") == "accessToken" for p in params):
                    params.insert(0, access_token_param)
    return app.openapi_schema


@app.get("/openapi.json", include_in_schema=False)
async def openapi_json():
    schema = custom_openapi_schema()
    return JSONResponse(content=schema, media_type="application/json; charset=utf-8")


def success_response(msg: str, data=None):
    return {"code": 0, "msg": msg, "data": data if data is not None else {}}


def error_response(msg: str, data=None, status_code: int = 400):
    return JSONResponse(
        status_code=status_code,
        content={"code": 1, "msg": msg, "data": data if data is not None else {}}
    )


def read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return default


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def cleanup_empty_parents(path: Path, stop_at: Path):
    current = path.parent
    while current != stop_at and current.exists():
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def parse_optional_millis(value: Optional[str], field_name: str) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} 必须是毫秒时间戳字符串或整数")


def adjust_end_of_day(end_ms: Optional[int]) -> Optional[int]:
    """前端只传日期（当天 00:00:00 本地时区的毫秒时间戳），需要补齐到 23:59:59.999 才能包含当天数据。"""
    if end_ms is None:
        return None
    dt = datetime.fromtimestamp(end_ms / 1000)
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        next_day_start = (dt + timedelta(days=1)).timestamp() * 1000
        return int(next_day_start) - 1
    return end_ms


def ensure_id_list(data: dict, *keys: str) -> list[str]:
    for key in keys:
        value = data.get(key)
        if value in (None, ""):
            continue
        if not isinstance(value, list):
            raise ValueError(f"{key} 必须是列表")
        return [str(item) for item in value if str(item).strip()]
    return []


def validate_feedback_type(value: str) -> str:
    if value not in VALID_FEEDBACK_TYPES:
        raise ValueError("type 仅支持 like 或 dislike")
    return value


def safe_segment(value: str) -> str:
    safe = "".join(c for c in str(value) if c.isalnum() or c in ("-", "_", "."))
    return safe or now_ms()


def resolve_user_id(user: Optional[dict]) -> str:
    user = user or {}
    return str(user.get("user_id") or user.get("userId") or user.get("UID") or "UID_DEMO")


def resolve_record_id(conversation_id: Optional[str], payload: Optional[dict] = None) -> str:
    if conversation_id not in (None, ""):
        return str(conversation_id)
    payload = payload or {}
    return str(payload.get("record_id") or payload.get("recordId") or payload.get("RecordID") or "")


def get_logged_in_user(access_token: Optional[str] = None):
    """获取当前请求的登录用户。中间件已通过 accessToken 设置了上下文。"""
    from services.user_auth import get_current_user
    return get_current_user()


def require_role(min_role: str):
    """权限检查。通过返回 None；不通过返回 error_response。
    用法：err = require_role("user"); if err: return err
    """
    from services.user_auth import check_role
    result = check_role(min_role)
    if result is None:
        return None
    msg, status_code = result
    return error_response(msg, {"reason": "权限不足"}, status_code)


def _kb_has_user(kb: dict, staff_id) -> bool:
    """检查知识库的使用人列表中是否包含该 staffId。"""
    if not staff_id:
        return False
    sid = str(staff_id)
    for u in kb.get("users", []):
        if isinstance(u, dict):
            u_sid = str(u.get("staffId") or u.get("staff_id") or "")
        else:
            u_sid = str(u)
        if u_sid == sid:
            return True
    return False


def _require_kb_access(kb_id: str):
    """企业端接口鉴权：
    - KB 不存在 → 404
    - 普通 KB 的 tenant_id 与当前用户不匹配 → 404（防止信息泄露，对外装作不存在）
    - 普通用户还要求在 users 列表里（操作权限）
    - 企业管理员在本租户内直接放行
    - 基础知识库：任何登录用户可读，但 users 列表约束仍生效（普通用户默认没权编辑基础库）
    返回 None 表示通过。"""
    from services.user_auth import current_role, ROLE_USER
    detail = kb_service.get_kb_detail(kb_id)
    if not detail:
        return error_response("知识库不存在", {"id": kb_id}, 404)
    user = get_logged_in_user()
    my_tenant = user.get("tenant_id")
    # 非基础知识库：tenant 不匹配直接 404（不泄露其他企业 KB 的存在）
    if detail.get("category") != "基础知识库":
        kb_tenant = detail.get("tenant_id")
        if my_tenant is None or str(kb_tenant or "") != str(my_tenant):
            return error_response("知识库不存在", {"id": kb_id}, 404)
    if current_role() != ROLE_USER:
        return None
    my_staff_id = user.get("staff_id") or user.get("staffId")
    if not _kb_has_user(detail, my_staff_id):
        return error_response("无权操作该知识库", {"reason": "您不在该知识库的使用人列表中"}, 403)
    return None


def build_user_brief(user: dict, conversation_id: Optional[str] = None):
    return {
        "name": user.get("name", ""),
        "phone": user.get("phone", ""),
        "categoryName": user.get("company", ""),
        "user_id": resolve_user_id(user),
        "record_id": resolve_record_id(conversation_id, user),
        "ip_address": user.get("ip_address", ""),
    }


def build_user_payload(user: dict, conversation_id: Optional[str] = None):
    return {
        "name": user.get("name", ""),
        "enterprise": user.get("company", ""),
        "phone": user.get("phone", ""),
        "department": user.get("department", ""),
        "user_id": resolve_user_id(user),
        "record_id": resolve_record_id(conversation_id, user),
        "ip_address": user.get("ip_address", ""),
    }


def normalize_page_size(page: int, size: int) -> tuple[int, int]:
    safe_page = max(1, int(page or 1))
    safe_size = max(1, min(100, int(size or 10)))
    return safe_page, safe_size


def paginate_payload(items: list, page: int, size: int) -> dict:
    page, size = normalize_page_size(page, size)
    total = len(items)
    start = (page - 1) * size
    end = start + size
    total_pages = (total + size - 1) // size if size else 0
    return {
        "list": items[start:end],
        "total": total,
        "page": page,
        "size": size,
        "total_pages": total_pages,
    }


def _extract_snippet(text: str, keyword: str, context: int = 20) -> str:
    """从文本中提取关键词周围的上下文片段，用于前端展示命中位置。"""
    if not text or not keyword:
        return ""
    lower = text.lower()
    pos = lower.find(keyword.lower())
    if pos < 0:
        return ""
    start = max(0, pos - context)
    end = min(len(text), pos + len(keyword) + context)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def build_history_list_item(record: dict) -> dict:
    messages = record.get("messages", []) or []
    last_message = messages[-1] if messages else {}
    user = record.get("user") or {}
    item = {
        "conversation_id": record.get("conversation_id"),
        "title": record.get("title", ""),
        "updated_at": record.get("updated_at", ""),
        "updatedAt": record.get("updatedAt", ""),
        "message_count": record.get("message_count", 0),
        "last_user_input": last_message.get("question", ""),
        "last_answer": last_message.get("answer", ""),
        "user": {
            "name": user.get("name", ""),
            "phone": user.get("phone", ""),
            "categoryName": user.get("categoryName", ""),
            "user_id": user.get("user_id") or "",
            "record_id": user.get("record_id") or record.get("conversation_id", ""),
            "ip_address": user.get("ip_address", ""),
        },
    }
    # 命中搜索时附带命中轮次信息，前端可跳转高亮
    if "_matched_field" in record:
        item["matched_field"] = record.get("_matched_field")
        item["matched_message_index"] = record.get("_matched_message_index")
        item["matched_snippet"] = record.get("_matched_snippet") or ""
    return item


def build_feedback_type_meta(info: dict) -> dict:
    raw_type = info.get("type")
    primary = "点赞" if raw_type == "like" else "点踩" if raw_type == "dislike" else ""
    scenes = derive_feedback_scenes(info)
    # 点踩有子分类时只显示子分类，不显示"点踩"
    if scenes:
        labels = list(scenes)
    elif primary:
        labels = [primary]
    else:
        labels = []
    return {
        "primary": primary,
        "labels": labels,
    }


def build_feedback_user(info: dict) -> dict:
    user = info.get("user") if isinstance(info.get("user"), dict) else {}
    return {
        "name": user.get("name") or info.get("name", ""),
        "enterprise": user.get("enterprise") or info.get("enterprise", ""),
        "phone": user.get("phone") or info.get("phone", ""),
        "user_id": user.get("user_id") or info.get("user_id", ""),
        "record_id": user.get("record_id") or info.get("record_id") or info.get("conversation_id", ""),
        "ip_address": user.get("ip_address") or info.get("ip_address", ""),
    }


def match_feedback_type(info: dict, feedback_type: str) -> bool:
    if not feedback_type or feedback_type == "全部":
        return True
    meta = build_feedback_type_meta(info)
    if feedback_type in meta.get("labels", []):
        return True
    if feedback_type == info.get("type") or feedback_type == info.get("state"):
        return True
    return False


def build_question_keywords(question: str) -> list[str]:
    text = str(question or "").strip()
    if not text:
        return []
    keywords = set()
    for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9_]+", text):
        token = token.strip()
        if len(token) >= 2:
            keywords.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            for size in (2, 3, 4):
                if len(token) >= size:
                    for idx in range(len(token) - size + 1):
                        keywords.add(token[idx:idx + size])
    return sorted(keywords, key=len, reverse=True)


def fallback_select_tables(question: str, detailed: dict, limit: int = 8) -> list[str]:
    keywords = build_question_keywords(question)
    if not keywords:
        return []
    scored = []
    for table_name, info in (detailed or {}).items():
        haystack = " ".join([
            str(table_name or ""),
            str(info.get("table_comment") or ""),
            " ".join(str(item) for item in (info.get("column_comments") or [])),
        ]).lower()
        score = 0
        for keyword in keywords:
            lowered = keyword.lower()
            if lowered and lowered in haystack:
                score += max(1, len(keyword))
        if score > 0:
            scored.append((score, table_name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [table_name for _, table_name in scored[:limit]]


def list_history_objects():
    return storage_service.list_files(f"{HISTORY_MINIO_PREFIX}/")


def resolve_history_path(conversation_id: str) -> Optional[str]:
    safe_id = safe_segment(conversation_id)
    candidates = sorted(
        (
            item for item in list_history_objects()
            if item.get("object_name", "").endswith(f"/{safe_id}.json")
        ),
        key=lambda item: item.get("last_modified"),
        reverse=True,
    )
    if candidates:
        return candidates[0]["object_name"]
    return None


def build_history_path(conversation_id: str, date_str: Optional[str] = None) -> str:
    return f"{HISTORY_MINIO_PREFIX}/{date_str or today_str()}/{safe_segment(conversation_id)}.json"


def empty_history_record(conversation_id: str, user: Optional[dict] = None):
    user = user or get_logged_in_user()
    timestamp = now_ms()
    display = now_display()
    return {
        "conversation_id": conversation_id,
        "title": "",
        "created_at": timestamp,
        "updated_at": timestamp,
        "createdAt": display,
        "updatedAt": display,
        "message_count": 0,
        "user": build_user_brief(user, conversation_id),
        "messages": []
    }


def normalize_legacy_history(conversation_id: str, payload, user: Optional[dict] = None):
    if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        record = payload
        record.setdefault("conversation_id", conversation_id)
        record.setdefault("title", record.get("messages", [{}])[0].get("question", "") if record.get("messages") else "")
        record.setdefault("message_count", len(record.get("messages", [])))
        record.setdefault("created_at", now_ms())
        record.setdefault("updated_at", record.get("created_at", now_ms()))
        record.setdefault("createdAt", now_display())
        record.setdefault("updatedAt", record.get("createdAt", now_display()))
        current_user = dict(record.get("user") or {})
        fallback_user = user or get_logged_in_user()
        current_user.setdefault("name", fallback_user.get("name", ""))
        current_user.setdefault("phone", fallback_user.get("phone", ""))
        current_user.setdefault("categoryName", fallback_user.get("company", ""))
        current_user.setdefault("ip_address", fallback_user.get("ip_address", ""))
        current_user["user_id"] = current_user.get("user_id") or resolve_user_id(fallback_user)
        current_user["record_id"] = conversation_id
        record["user"] = current_user
        return record

    record = empty_history_record(conversation_id, user)
    legacy_messages = payload if isinstance(payload, list) else []
    round_index = 0
    i = 0
    while i < len(legacy_messages):
        current = legacy_messages[i] if isinstance(legacy_messages[i], dict) else {}
        if current.get("role") == "user":
            assistant = {}
            if i + 1 < len(legacy_messages) and isinstance(legacy_messages[i + 1], dict) and legacy_messages[i + 1].get("role") == "assistant":
                assistant = legacy_messages[i + 1]
                i += 1
            message = {
                "message_index": round_index,
                "question": current.get("content", ""),
                "files": current.get("files", []),
                "uploaded_files": current.get("uploaded_files", []),
                "web_search": bool(current.get("web_search", False)),
                "db_version": current.get("db_version"),
                "answer": assistant.get("content", ""),
                "resource": assistant.get("resource", []),
                "recommend_answer": assistant.get("recommend_answer", []),
                "feedback": assistant.get("feedback"),
                "thinking_text": assistant.get("thinking_text"),
                "thinking_steps": assistant.get("thinking_steps", []),
                "created_at": assistant.get("created_at") or current.get("created_at") or now_ms(),
                "updated_at": assistant.get("updated_at") or current.get("updated_at") or now_ms(),
                "createdAt": assistant.get("createdAt") or current.get("createdAt") or now_display(),
                "updatedAt": assistant.get("updatedAt") or current.get("updatedAt") or now_display()
            }
            record["messages"].append(message)
            round_index += 1
        i += 1
    record["message_count"] = len(record["messages"])
    record["title"] = record["messages"][0]["question"] if record["messages"] else ""
    return record


def load_history_record(conversation_id: str, user: Optional[dict] = None):
    object_name = resolve_history_path(conversation_id)
    if not object_name:
        return empty_history_record(conversation_id, user), build_history_path(conversation_id)
    raw = storage_service.read_file_bytes(object_name)
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        payload = {}
    return normalize_legacy_history(conversation_id, payload, user), object_name


def save_history_record(record: dict, path: Optional[str] = None):
    record["title"] = record.get("messages", [{}])[0].get("question", "") if record.get("messages") else ""
    record["message_count"] = len(record.get("messages", []))
    record["updated_at"] = now_ms()
    record["updatedAt"] = now_display()
    target_path = path or resolve_history_path(record["conversation_id"]) or build_history_path(record["conversation_id"])
    data = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
    if not storage_service.upload_file_obj(io.BytesIO(data), target_path, "application/json"):
        raise RuntimeError(f"保存历史记录失败: {record['conversation_id']}")
    return target_path


def list_history_records():
    records_by_id = {}
    for item in list_history_objects():
        try:
            object_name = item.get("object_name", "")
            if not object_name.endswith(".json"):
                continue
            conversation_id = Path(object_name).stem
            raw = storage_service.read_file_bytes(object_name)
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            record = normalize_legacy_history(conversation_id, payload)
            record["storage_date"] = Path(object_name).parent.name
            records_by_id[conversation_id] = record
        except Exception:
            continue
    return list(records_by_id.values())


def filter_history_records(
    *,
    ids: Optional[list[str]] = None,
    search: str = "",
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
):
    end_ms = adjust_end_of_day(end_ms)
    id_set = {str(item) for item in (ids or []) if str(item).strip()}
    results = []
    for record in list_history_records():
        if id_set and str(record.get("conversation_id")) not in id_set:
            continue
        updated_at = int(record.get("updated_at") or 0)
        if start_ms is not None and updated_at < start_ms:
            continue
        if end_ms is not None and updated_at > end_ms:
            continue
        if search:
            keyword = search.lower()
            user = record.get("user") or {}
            # 先匹配元信息（标题/IP/userId/recordId）
            meta_fields = {
                "title": record.get("title") or "",
                "ip_address": user.get("ip_address") or "",
                "user_id": user.get("user_id") or "",
                "record_id": user.get("record_id") or str(record.get("conversation_id") or ""),
            }
            matched_field = None
            matched_index = None
            matched_snippet = None
            for field, val in meta_fields.items():
                if val and keyword in val.lower():
                    matched_field = "title" if field == "title" else "user"
                    matched_snippet = _extract_snippet(val, keyword)
                    break
            # 未命中元信息则按轮次扫描 question/answer，取第一个命中
            if matched_field is None:
                for idx, msg in enumerate(record.get("messages") or []):
                    q = msg.get("question") or ""
                    a = msg.get("answer") or ""
                    if keyword in q.lower():
                        matched_field = "question"
                        matched_index = idx
                        matched_snippet = _extract_snippet(q, keyword)
                        break
                    if keyword in a.lower():
                        matched_field = "answer"
                        matched_index = idx
                        matched_snippet = _extract_snippet(a, keyword)
                        break
            if matched_field is None:
                continue
            record = dict(record)
            record["_matched_field"] = matched_field
            record["_matched_message_index"] = matched_index
            record["_matched_snippet"] = matched_snippet
        results.append(record)
    results.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return results


def build_history_export_text(record: dict) -> bytes:
    lines = []
    title = record.get("title") or "未命名对话"
    user = record.get("user") or {}
    lines.append(f"对话标题：{title}")
    if user.get("name"):
        lines.append(f"用户：{user.get('name')}")
    lines.append(f"导出时间：{now_display()}")
    lines.append("")

    messages = record.get("messages", []) or []
    for index, item in enumerate(messages, start=1):
        lines.append(f"第{index}轮")
        lines.append("问：")
        lines.append(str(item.get("question") or ""))
        uploaded_files = item.get("uploaded_files") or []
        if uploaded_files:
            filenames = [str(file_item.get("filename") or "") for file_item in uploaded_files if str(file_item.get("filename") or "").strip()]
            if filenames:
                lines.append(f"附件：{'、'.join(filenames)}")
        lines.append("答：")
        lines.append(str(item.get("answer") or ""))
        sources = item.get("resource") or []
        if sources:
            lines.append("参考链接：")
            for source in sources:
                title_text = str(source.get("title") or "未命名来源")
                link_text = str(source.get("link") or "")
                if link_text:
                    lines.append(f"- {title_text}：{link_text}")
        lines.append("")
    return "\n".join(lines).encode("utf-8-sig")


def format_qa_content(messages: list) -> str:
    """将问答列表格式化为'问：xxx\\n答：xxx'的多行字符串，一条问答一组。"""
    lines = []
    for item in messages or []:
        question = str(item.get("question") or "").strip()
        answer = str(item.get("answer") or "").strip()
        if question:
            lines.append(f"问：{question}")
        if answer:
            lines.append(f"答：{answer}")
    return "\n".join(lines)


def build_xlsx_bytes(headers: list, rows: list) -> bytes:
    """构建 xlsx 文件字节流。headers 为表头列表，rows 为每行数据（与 headers 对齐的列表）。"""
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in rows:
        ws.append(row)
    # 设置所有单元格自动换行，居中对齐
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    # 设置列宽
    for col_idx, _ in enumerate(headers, start=1):
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = 24
    # 问答列更宽
    if "问答" in headers or "反馈对象" in headers:
        last_col = ws.cell(row=1, column=len(headers)).column_letter
        ws.column_dimensions[last_col].width = 60
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def find_uploaded_file(conversation_id: str, message_index: int, file_id: str):
    history_record, _ = load_history_record(conversation_id)
    target = next((item for item in history_record.get("messages", []) if item.get("message_index") == message_index), None)
    if not target:
        return None
    for file_item in target.get("uploaded_files", []) or []:
        if str(file_item.get("file_id") or "") == str(file_id):
            return file_item
    return None



MAX_FILE_TEXT_CHARS = env_int("CHAT_FILE_TEXT_MAX_CHARS", 12000)
MAX_HISTORY_ROUNDS = env_int("CHAT_HISTORY_MAX_ROUNDS", 6)
FILE_HISTORY_SNIPPET_CHARS = env_int("CHAT_FILE_HISTORY_SNIPPET_CHARS", 3000)


def _compact_text(text: str, limit: int = MAX_FILE_TEXT_CHARS) -> str:
    # 保留换行结构（表格/PDF 分行），只压缩行内多余空白
    src = str(text or "")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in src.splitlines()]
    compact = "\n".join(line for line in lines if line)
    if len(compact) <= limit:
        return compact
    return compact[:limit] + " ...(已截断)"


def _extract_pdf_text(path: Path) -> str:
    parts = []
    if PdfReader is not None:
        try:
            reader = PdfReader(str(path))
            for page in reader.pages:
                parts.append(page.extract_text() or "")
        except Exception:
            parts = []
    if not ''.join(parts).strip():
        try:
            result = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, check=True)
            return _compact_text(result.stdout)
        except Exception:
            return ""
    return _compact_text('\n'.join(parts))


def _extract_text_nodes_from_xml(xml_bytes: bytes) -> list[str]:
    try:
        root = ET.fromstring(xml_bytes)
    except Exception:
        return []
    texts = []
    for elem in root.iter():
        if elem.tag.endswith('}t') or elem.tag == 't':
            if elem.text and elem.text.strip():
                texts.append(elem.text.strip())
    return texts


def _extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            data = zf.read('word/document.xml')
    except Exception:
        return ''
    return _compact_text('\n'.join(_extract_text_nodes_from_xml(data)))


def _extract_pptx_text(path: Path) -> str:
    texts = []
    try:
        with zipfile.ZipFile(path) as zf:
            for name in sorted(zf.namelist()):
                if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
                    texts.extend(_extract_text_nodes_from_xml(zf.read(name)))
    except Exception:
        return ''
    return _compact_text('\n'.join(texts))


def _extract_xlsx_text(path: Path) -> str:
    """按行读取 xlsx，每行一条，保留行列结构，方便模型理解表格。"""
    try:
        from openpyxl import load_workbook
    except Exception:
        return ''
    try:
        wb = load_workbook(str(path), data_only=True, read_only=True)
    except Exception:
        return ''
    parts: list[str] = []
    try:
        for sheet in wb.worksheets:
            parts.append(f'【Sheet: {sheet.title}】')
            for row in sheet.iter_rows(values_only=True):
                cells = ['' if v is None else str(v).strip() for v in row]
                # 跳过整行全空
                if not any(cells):
                    continue
                parts.append(' | '.join(cells))
    finally:
        wb.close()
    return _compact_text('\n'.join(parts))


def extract_uploaded_file_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    try:
        if suffix in {'.txt', '.md', '.csv', '.json', '.py', '.log'}:
            return _compact_text(file_path.read_text(encoding='utf-8', errors='ignore'))
        if suffix == '.pdf':
            return _extract_pdf_text(file_path)
        if suffix == '.docx':
            return _extract_docx_text(file_path)
        if suffix == '.pptx':
            return _extract_pptx_text(file_path)
        if suffix == '.xlsx':
            return _extract_xlsx_text(file_path)
        if suffix in {'.doc', '.xls', '.ppt'}:
            # 用 LibreOffice 转换成新版 OOXML 再走现有解析
            from services.kb_file_parser import (
                convert_legacy_office,
                LEGACY_OFFICE_TARGETS,
            )
            target_ext = LEGACY_OFFICE_TARGETS[suffix]
            converted = convert_legacy_office(file_path, target_ext)
            if not converted:
                return '该文件为旧版 Office 格式，服务器未能成功转换，请手动转换为 docx/xlsx/pptx 后重试。'
            try:
                if target_ext == 'docx':
                    return _extract_docx_text(converted)
                if target_ext == 'xlsx':
                    return _extract_xlsx_text(converted)
                if target_ext == 'pptx':
                    return _extract_pptx_text(converted)
            finally:
                import shutil
                shutil.rmtree(converted.parent, ignore_errors=True)
        return '该文件类型暂不支持正文抽取，但文件已上传保存。'
    except Exception as exc:
        return f'文件解析失败：{exc}'


import tempfile
import uuid

IMAGE_SUFFIXES_CHAT = {'.png', '.jpg', '.jpeg', '.bmp', '.gif'}


def build_uploaded_file_contexts(uploaded_files: List[dict]) -> list[dict]:
    """返回结构：
    - 文本类文件: {filename, kind:'text', text}
    - 图片文件:   {filename, kind:'image', data_url}  —— 供当轮 multimodal 输入
    """
    import base64, mimetypes
    contexts = []
    for item in uploaded_files or []:
        object_name = item.get('object_name') or item.get('relative_path')
        if not object_name:
            continue
        filename = item.get('filename') or Path(object_name).name
        suffix = Path(filename).suffix.lower()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / filename
            if not storage_service.download_file(object_name, str(tmp_path)):
                continue
            if suffix in IMAGE_SUFFIXES_CHAT:
                mime, _ = mimetypes.guess_type(filename)
                if not mime or not mime.startswith('image/'):
                    mime = 'image/jpeg'
                try:
                    b64 = base64.b64encode(tmp_path.read_bytes()).decode('ascii')
                    contexts.append({
                        'filename': filename,
                        'kind': 'image',
                        'data_url': f'data:{mime};base64,{b64}',
                    })
                except Exception:
                    continue
            else:
                extracted_text = extract_uploaded_file_text(tmp_path)
                contexts.append({
                    'filename': filename,
                    'kind': 'text',
                    'text': extracted_text,
                })
    return contexts


def _strip_rag_sources(text: str) -> str:
    """从历史回答中移除 RAG 来源引用块，避免模型从历史上下文中直接引用已关闭的知识库内容。"""
    if not text:
        return text
    return re.sub(r"【来源:.*?】\n?", "", text).strip()


def compose_chat_prompt(current_message: str, history_record: dict, file_contexts: Optional[list[dict]] = None) -> str:
    parts = []
    history_messages = history_record.get('messages', [])[-MAX_HISTORY_ROUNDS:]
    if history_messages:
        history_lines = ['【历史对话上下文】']
        for idx, item in enumerate(history_messages, start=1):
            question = (item.get('question') or '').strip()
            answer = _strip_rag_sources((item.get('answer') or '').strip())
            if question:
                history_lines.append(f'第{idx}轮用户：{question}')
            prior_file_contexts = item.get('file_contexts') or []
            for file_item in prior_file_contexts:
                filename = file_item.get('filename', '未命名文件')
                text = _compact_text(file_item.get('text', ''), FILE_HISTORY_SNIPPET_CHARS)
                if text:
                    history_lines.append(f'第{idx}轮附件《{filename}》内容摘要：{text}')
            if answer:
                history_lines.append(f'第{idx}轮助手：{answer}')
        parts.append('\n'.join(history_lines))

    current_file_contexts = file_contexts or []
    # 文本类文件：拼进 prompt；图片单独通过 multimodal 输入传给模型，这里只提个醒
    text_contexts = [c for c in current_file_contexts if c.get('kind', 'text') != 'image']
    image_contexts = [c for c in current_file_contexts if c.get('kind') == 'image']
    if text_contexts:
        file_lines = ['【本轮上传文件内容】']
        for idx, item in enumerate(text_contexts, start=1):
            file_lines.append(f'文件{idx}：{item.get("filename", "未命名文件")}')
            file_lines.append(item.get('text') or '文件内容为空，或暂未成功解析。')
        parts.append('\n'.join(file_lines))
    if image_contexts:
        names = '、'.join(c.get('filename', '未命名图片') for c in image_contexts)
        parts.append(f'【本轮附带图片】{names}（图片内容已随本轮一并传给模型，请结合图片作答）')

    parts.append(f'【当前用户提问（请务必针对此问题回答）】\n{current_message}')
    if current_file_contexts:
        parts.append('注意：上面的文件内容已由系统成功读取，直接基于文件内容回答即可，不要说无法读取。')
    return '\n\n'.join(part for part in parts if part.strip())


# ─────────────────────────────────────────────────────────
# 反馈元数据存储：MinIO（feedback/<日期>/<feedback_id>/feedback.json）
# 截图也在同前缀下（png/jpg）。日期分组从 MinIO 反查现有对象。
# ─────────────────────────────────────────────────────────
FEEDBACK_PREFIX = "feedback"


def _feedback_object_root(feedback_id: str, date_str: str) -> str:
    return f"{FEEDBACK_PREFIX}/{date_str}/{feedback_id}"


def _resolve_feedback_object_root(feedback_id: str) -> Optional[str]:
    """根据 feedback_id 在 MinIO 中找到它实际所在的日期分组前缀。
    返回如 'feedback/2026-04-23/fb_xxx'，找不到返回 None。
    """
    target = f"/{feedback_id}/"
    candidates = []
    for entry in storage_service.list_files(f"{FEEDBACK_PREFIX}/"):
        object_name = entry.get("object_name") if isinstance(entry, dict) else entry
        if not object_name:
            continue
        if target in f"/{object_name}":
            parts = object_name.split("/")
            try:
                idx = parts.index(feedback_id)
            except ValueError:
                continue
            candidates.append("/".join(parts[: idx + 1]))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0]


def _load_feedback_info(feedback_id: str) -> dict:
    """从 MinIO 读 feedback.json，找不到返回 {}。"""
    root = _resolve_feedback_object_root(feedback_id)
    if not root:
        return {}
    raw = storage_service.read_file_bytes(f"{root}/feedback.json")
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _save_feedback_info(feedback_id: str, info: dict, date_str: Optional[str] = None) -> str:
    """把 feedback dict 写到 MinIO；若已有同 fb_id 对象则原地覆盖（保持原日期分组）。
    返回写入对象的对象前缀（如 'feedback/2026-04-23/fb_xxx'）。
    """
    root = _resolve_feedback_object_root(feedback_id)
    if not root:
        root = _feedback_object_root(feedback_id, date_str or today_str())
    object_name = f"{root}/feedback.json"
    payload = json.dumps(info, ensure_ascii=False, indent=2).encode("utf-8")
    import io as _io
    storage_service.upload_file_obj(_io.BytesIO(payload), object_name, content_type="application/json")
    return root


def _delete_feedback_all(feedback_id: str) -> bool:
    """删 MinIO 里 feedback/<date>/<fb_id>/* 整个前缀（含 JSON + 图片）。"""
    root = _resolve_feedback_object_root(feedback_id)
    if not root:
        return False
    storage_service.delete_files_by_prefix(f"{root}/")
    return True


FEEDBACK_REASON_GROUPS = {
    "question_issues": {
        "scene_label": "针对问题",
        "options": {
            "notUnderstand": "不理解问题",
            "missingContext": "遗忘上下文",
            "notMeetRequirements": "未遵循要求",
        },
    },
    "answer_effects": {
        "scene_label": "针对回答效果",
        "options": {
            "wrongAnswer": "回答错误",
            "confuseLogic": "逻辑混乱",
            "timeMismatch": "时效性差",
            "readabilityPoor": "可读性差",
            "incompleteAnswer": "回答不完整",
            "processUnprofessional": "回答笼统不专业",
        },
    },
    "report_reasons": {
        "scene_label": "举报",
        "options": {
            "porn": "色情低俗",
            "politics": "政治敏感",
            "illegal": "违法犯罪",
            "privacy": "侵犯隐私",
            "copyright": "内容侵权",
            "discrimination": "歧视或偏见回答",
        },
    },
}

FEEDBACK_REASON_FIELDS = tuple(
    (field, cfg["scene_label"]) for field, cfg in FEEDBACK_REASON_GROUPS.items()
)


def normalize_reason_keys(raw, field_name: str) -> list[str]:
    """把请求里单个分组字段规范成 key 数组。非法 key 抛 ValueError。"""
    if raw is None or raw == "" or (isinstance(raw, (list, dict)) and not raw):
        return []
    valid_keys = FEEDBACK_REASON_GROUPS.get(field_name, {}).get("options", {})
    keys: list[str] = []
    items = raw if isinstance(raw, list) else list(raw.keys()) if isinstance(raw, dict) else None
    if items is None:
        raise ValueError(f"{field_name} 必须是 key 数组")
    for item in items:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} 元素必须是字符串")
        key = item.strip()
        if not key:
            continue
        if key not in valid_keys:
            raise ValueError(f"{field_name} 包含非法 key: {key}")
        if key not in keys:
            keys.append(key)
    return keys


def coerce_reason_keys_for_read(value, field_name: str) -> list[str]:
    """读侧防御：把磁盘上历史形态（key 数组 / dict / 中文 label 数组）统一成 key 数组。"""
    options = FEEDBACK_REASON_GROUPS.get(field_name, {}).get("options", {})
    if not options:
        return []
    label_to_key = {label: key for key, label in options.items()}
    result: list[str] = []
    items: list = []
    if isinstance(value, dict):
        items = list(value.keys())
    elif isinstance(value, list):
        items = value
    else:
        return []
    for item in items:
        if not isinstance(item, str):
            continue
        if item in options and item not in result:
            result.append(item)
        elif item in label_to_key and label_to_key[item] not in result:
            result.append(label_to_key[item])
    return result


def derive_feedback_scenes(info: dict) -> list[str]:
    """根据三个分组字典里哪些非空，派生分类标签。"""
    return [label for field, label in FEEDBACK_REASON_FIELDS if info.get(field)]


def update_message_feedback(conversation_id: str, message_index: int, feedback_state):
    record, path = load_history_record(conversation_id)
    if 0 <= message_index < len(record.get("messages", [])):
        record["messages"][message_index]["feedback"] = feedback_state
        record["messages"][message_index]["updated_at"] = now_ms()
        record["messages"][message_index]["updatedAt"] = now_display()
        save_history_record(record, path)
        return record["messages"][message_index], record, path
    return None, record, path


def build_feedback_summary(info: dict):
    return {
        "id": info.get("id"),
        "conversation_id": info.get("conversation_id"),
        "message_index": info.get("message_index"),
        "type": info.get("type"),
        "active": info.get("active", True),
        "feedback_type": build_feedback_type_meta(info),
        "question_issues": coerce_reason_keys_for_read(info.get("question_issues"), "question_issues"),
        "answer_effects": coerce_reason_keys_for_read(info.get("answer_effects"), "answer_effects"),
        "report_reasons": coerce_reason_keys_for_read(info.get("report_reasons"), "report_reasons"),
        "comment": info.get("comment", ""),
        "user": build_feedback_user(info),
        "createdAt": info.get("createdAt", ""),
        "updatedAt": info.get("updatedAt", ""),
        "process_status": info.get("process_status", "未处理"),
        "process_result": info.get("process_result", ""),
        "processor": info.get("processor", ""),
    }


def iter_feedback_infos():
    """从 MinIO 列举所有反馈 feedback.json，逐个读出。
    第二个返回值保留为对象路径（字符串而非 Path），方便上层做参考；新代码不应依赖它。
    """
    for entry in storage_service.list_files(f"{FEEDBACK_PREFIX}/"):
        object_name = entry.get("object_name") if isinstance(entry, dict) else entry
        if not object_name or not object_name.endswith("/feedback.json"):
            continue
        try:
            raw = storage_service.read_file_bytes(object_name)
            if not raw:
                continue
            info = json.loads(raw.decode("utf-8"))
        except Exception:
            continue
        yield info, object_name


def collect_feedback_summaries(
    search: str = "",
    type: str = "",
    feedback_type: str = "全部",
    process_status: str = "",
    process_result: str = "",
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
    processed_start_ms: Optional[int] = None,
    processed_end_ms: Optional[int] = None,
):
    end_ms = adjust_end_of_day(end_ms)
    processed_end_ms = adjust_end_of_day(processed_end_ms)
    keyword = search.lower().strip()
    results = []
    for info, _ in iter_feedback_infos():
        if keyword:
            user = build_feedback_user(info)
            name = user.get("name", "").lower()
            phone = user.get("phone", "").lower()
            enterprise = user.get("enterprise", "").lower()
            if keyword not in name and keyword not in phone and keyword not in enterprise:
                continue
        if type and info.get("type") != type:
            continue
        if not match_feedback_type(info, feedback_type):
            continue
        if process_status:
            status = info.get("process_status") or "未处理"
            if process_status != status:
                continue
        if process_result and info.get("process_result", "") != process_result:
            continue
        update_time = int(info.get("update_time") or 0)
        if start_ms is not None and update_time < start_ms:
            continue
        if end_ms is not None and update_time > end_ms:
            continue
        if processed_start_ms is not None or processed_end_ms is not None:
            processed_at = int(info.get("processed_at") or 0)
            if processed_start_ms is not None and processed_at < processed_start_ms:
                continue
            if processed_end_ms is not None and processed_at > processed_end_ms:
                continue
        summary = build_feedback_summary(info)
        summary["_sort_time"] = info.get("update_time") or info.get("time") or "0"
        results.append(summary)
    results.sort(key=lambda item: item.pop("_sort_time", "0"), reverse=True)
    return results


def collect_history_records(ids: Optional[list[str]] = None):
    if ids:
        return filter_history_records(ids=ids)
    return filter_history_records()


async def generate_recommendations(user_msg: str, ai_msg: str) -> List[str]:
    import re
    limit = env_int("CHAT_RECOMMENDATION_COUNT", 3)

    def fallback_questions() -> List[str]:
        cleaned_user = re.sub(r"\s+", " ", str(user_msg or "")).strip("？?。！!，, ")
        if cleaned_user:
            return [
                f"{cleaned_user}的关键点有哪些？",
                f"{cleaned_user}有没有具体例子？",
                f"{cleaned_user}还需要注意什么？",
            ][:limit]
        return [
            "能展开说说吗？",
            "有哪些关键点？",
            "还有什么需要注意？",
        ][:limit]

    if not str(user_msg or "").strip():
        return fallback_questions()

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=os.getenv("CHAT_MODEL_NAME", "gpt-4o"),
            temperature=0,
            max_tokens=256,
            timeout=min(env_float("CHAT_MODEL_TIMEOUT", 120), 60),
            model_kwargs={"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}},
        )
        prompt = f"""你是一个对话引导助手。
根据以下对话内容，预测用户接下来最感兴趣、最可能追问的3个问题。
要求：1. 每个问题不超过20个字。2. 必须以纯JSON字符串数组格式返回。3. 不要包含任何多余解释。4. 必须返回恰好3个问题。
用户问题: {user_msg}
AI回答: {ai_msg[:env_int("CHAT_RECOMMENDATION_INPUT_LIMIT", 500)]}"""
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        text = str(getattr(response, "content", "") or "").strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return fallback_questions()
        parsed = json.loads(match.group(0))
        if not isinstance(parsed, list):
            return fallback_questions()
        normalized = [
            str(item).strip()
            for item in parsed
            if str(item).strip()
        ]
        if not normalized:
            return fallback_questions()
        limit = env_int("CHAT_RECOMMENDATION_COUNT", 3)
        while len(normalized) < limit:
            for item in fallback_questions():
                if item not in normalized:
                    normalized.append(item)
                if len(normalized) >= limit:
                    break
        return normalized[:limit]
    except Exception as exc:
        print(f"[recommendations] failed: {exc}", file=sys.stderr)
        return fallback_questions()


def _compact_preview(value, limit: int = 240) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False)
    else:
        text = str(value or "")
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def _format_tool_result_preview(tool_name: str, content) -> str:
    if tool_name == "tavily_search_with_summary":
        try:
            results = json.loads(content).get("results", [])
            titles = [item.get("main_title") or item.get("url") for item in results[:2] if item.get("main_title") or item.get("url")]
            summary = f"检索到 {len(results)} 条结果"
            if titles:
                summary += "：" + "；".join(titles)
            return summary
        except Exception:
            pass
    return _compact_preview(content)


def _tool_trace_event(kind: str, node_name: str, tool_name: str, preview: str, tool_call_id: Optional[str] = None) -> dict:
    return {
        "kind": kind,
        "node_name": node_name,
        "tool_name": tool_name,
        "preview": preview,
        "tool_call_id": tool_call_id,
    }


def _tool_trace_thinking_delta(kind: str, tool_name: str, preview: str) -> str:
    if kind == "call":
        text = f"\n[工具调用] {tool_name}"
        if preview:
            text += f"\n输入参数：{preview}"
        text += "\n正在执行，请稍候...\n"
        return text
    text = f"\n[工具返回] {tool_name}"
    if preview:
        text += f"\n结果摘要：{preview}"
    text += "\n"
    return text


def _format_thinking_text(events: List[dict]) -> str:
    if not events:
        return ""

    lines = ["在正式回答前，我先做了几步准备："]
    call_map = {}
    step_no = 1

    for event in events:
        kind = event.get("kind")
        tool_name = event.get("tool_name", "工具")
        preview = event.get("preview", "")
        tool_call_id = event.get("tool_call_id")

        if kind == "call":
            line = f"{step_no}. 我调用了 {tool_name}"
            if preview:
                line += f"，输入大致是：{preview}"
            line += "。"
            lines.append(line)
            if tool_call_id:
                call_map[tool_call_id] = step_no
            step_no += 1
        elif kind == "result":
            linked_step = call_map.get(tool_call_id)
            prefix = f"对应上面第 {linked_step} 步，" if linked_step else f"{step_no}. "
            line = f"{prefix}{tool_name} 返回了这样的关键信息：{preview or '已完成处理。'}"
            if not line.endswith("。"):
                line += "。"
            lines.append(line)
            if linked_step is None:
                step_no += 1

    lines.append("整理完这些信息后，我再把最终答案组织成对你更自然的回复。")
    return "\n".join(lines)


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_comment(text: str) -> str:
    safe_text = " ".join(str(text or "").splitlines()).strip() or "keepalive"
    return f": {safe_text}\n\n"


# ────────────────────────────────────────────────
# 活跃流式注册表：{conversation_id: {"stream_id": str, "abort": asyncio.Event}}
# - 同一 conversation 只能有一个流式在跑（防止 message_index 并发错乱）
# - 前端可通过 /api/chat/abort 主动中断
# ────────────────────────────────────────────────
_active_streams: Dict[str, Dict[str, Any]] = {}


def _register_stream(conversation_id: str) -> Optional[Dict[str, Any]]:
    """注册新流式。若同 conv 已在流式中，返回 None；否则返回 {stream_id, abort}。"""
    if conversation_id in _active_streams:
        return None
    entry = {
        "stream_id": uuid.uuid4().hex,
        "abort": asyncio.Event(),
        "started_at": now_ms(),
    }
    _active_streams[conversation_id] = entry
    return entry


def _unregister_stream(conversation_id: str, stream_id: str) -> None:
    """注销流式。仅当 stream_id 匹配时才移除，避免误删后来者。"""
    entry = _active_streams.get(conversation_id)
    if entry and entry.get("stream_id") == stream_id:
        _active_streams.pop(conversation_id, None)


def _abort_stream(conversation_id: str) -> Optional[Dict[str, Any]]:
    entry = _active_streams.get(conversation_id)
    if entry is None:
        return None
    entry["abort"].set()
    return entry


def _iter_text_event_chunks(event_type: str, text: str) -> List[dict]:
    content = str(text or "")
    if not content:
        return []
    chunk_size = max(env_int("CHAT_STREAM_DELTA_CHARS", 1), 1)
    return [
        {"type": event_type, "delta": content[index:index + chunk_size]}
        for index in range(0, len(content), chunk_size)
    ]


async def _yield_text_events(event_type: str, text: str) -> AsyncIterator[str]:
    delay_ms = max(env_int("CHAT_STREAM_CHAR_DELAY_MS", 15), 0)
    for chunk_event in _iter_text_event_chunks(event_type, text):
        yield _sse_event(chunk_event)
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000)


def _strip_think_blocks(text: str) -> str:
    """移除 content 中的 <think>、<tool_call> 等模型内部标签。"""
    if not text:
        return ""
    # 1) 完整的标签对
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<tool_call>.*?</tool_call>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    # 2) <function=xxx>...</function> 格式
    cleaned = re.sub(r"<function=[^>]*>.*?</function>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    # 3) <parameter=xxx>...</parameter> 格式
    cleaned = re.sub(r"<parameter=[^>]*>.*?</parameter>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    # 4) 残留的单独标签（未闭合的）
    cleaned = re.sub(r"</?(?:think|tool_call|function|parameter)(?:=[^>]*)?>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


class ThinkSplitter:
    """
    流式 </think> 分割器。

    Qwen3.5 的 chat_template 在 assistant 开头注入 <think>，
    模型生成的 content 格式为：思考内容</think>回答内容
    （开头没有 <think>，因为那是 template 注入的，不在生成内容里）

    只需找 </think> 这一个分割点：之前是思考，之后是回答。
    """
    CLOSE_TAG = "</think>"

    def __init__(self):
        self.done = False
        self.buffer = ""

    def feed(self, text: str) -> tuple[str, str]:
        if self.done:
            return "", text
        self.buffer += text
        idx = self.buffer.lower().find(self.CLOSE_TAG)
        if idx != -1:
            thinking = self.buffer[:idx]
            answer = self.buffer[idx + len(self.CLOSE_TAG):]
            self.buffer = ""
            self.done = True
            return thinking, answer.lstrip()
        keep = len(self.CLOSE_TAG)
        if len(self.buffer) > keep:
            thinking = self.buffer[:-keep]
            self.buffer = self.buffer[-keep:]
            return thinking, ""
        return "", ""

    def flush(self) -> tuple[str, str]:
        remaining = self.buffer
        self.buffer = ""
        if self.done:
            return "", remaining
        return remaining, ""



def _resolve_saved_thinking_text(message_item: dict) -> str:
    thinking_steps = message_item.get("thinking_steps") or []
    if thinking_steps:
        return _format_thinking_text(thinking_steps)
    if message_item.get("model_think_text"):
        return str(message_item.get("model_think_text"))
    return ""


def _build_chat_done_payload(message_item: dict) -> dict:
    payload = dict(message_item)
    payload.pop("raw_answer", None)
    payload.pop("model_think_text", None)
    payload.pop("thinking_text", None)
    payload.pop("thinking_steps", None)
    return payload


async def _get_request_payload(request: Request) -> dict:
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return payload
    form = await request.form()
    return dict(form)



async def iterate_chat_events(message, conversation_id: str, web_search: bool, user_identity: str, *, raw_user_message: str = "", enable_thinking: bool = False):
    # message 支持 str 或 multimodal list（[{"type":"text",...}, {"type":"image_url",...}]）
    inputs = {
        "messages": [HumanMessage(content=message)],
        "enable_web": web_search,
        "select_model": os.getenv("CHAT_MODEL_NAME", "gpt-4o"),
        "user_identity": user_identity,
        "enable_thinking": enable_thinking,
    }
    config = {"configurable": {"thread_id": f"{conversation_id}_{now_ms()}"}}

    last_chatbot_content = ""
    sources = []
    tool_trace_events = []
    emitted_trace_keys = set()
    stream_buf = ""
    # enable_thinking=true 时，模型输出默认就是思考内容，直到遇到 </think> 才切换到回答
    # （vLLM 会吞掉 <think> 开标签，但保留 </think> 闭标签）
    in_think_block = enable_thinking

    async for msg, metadata in agent_app.astream(inputs, config=config, stream_mode="messages"):
        node_name = metadata.get("langgraph_node", "")

        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for idx, tool_call in enumerate(msg.tool_calls):
                tool_name = tool_call.get("name") or "unknown_tool"
                tool_call_id = tool_call.get("id") or f"{node_name}:{tool_name}:{idx}"
                trace_key = f"call:{tool_call_id}"
                if trace_key not in emitted_trace_keys:
                    emitted_trace_keys.add(trace_key)
                    preview = _compact_preview(tool_call.get("args", {}))
                    tool_trace_events.append(_tool_trace_event(
                        "call",
                        node_name,
                        tool_name,
                        preview,
                        tool_call_id,
                    ))
                    yield {"type": "thinking_delta", "delta": _tool_trace_thinking_delta("call", tool_name, preview)}
                    yield {"type": "progress", "message": f"tool_call {tool_name}"}
        if isinstance(msg, ToolMessage):
            tool_name = msg.name or "unknown_tool"
            tool_call_id = getattr(msg, "tool_call_id", None)
            trace_key = f"result:{tool_call_id or node_name}:{tool_name}:{_compact_preview(msg.content, 80)}"
            if trace_key not in emitted_trace_keys:
                emitted_trace_keys.add(trace_key)
                preview = _format_tool_result_preview(tool_name, msg.content)
                tool_trace_events.append(_tool_trace_event(
                    "result",
                    node_name,
                    tool_name,
                    preview,
                    tool_call_id,
                ))
                yield {"type": "thinking_delta", "delta": _tool_trace_thinking_delta("result", tool_name, preview)}
                yield {"type": "progress", "message": f"tool_result {tool_name}"}
                # 工具结果返回后，清空之前的 chatbot 中间输出，之后的 chatbot 才是最终回答
                last_chatbot_content = ""
                stream_buf = ""
                in_think_block = False
                if tool_name == "tavily_search_with_summary":
                    try:
                        results = json.loads(msg.content).get("results", [])
                        sources = [
                            {
                                "link": item.get("url", ""),
                                "title": item.get("main_title", ""),
                                "content": item.get("summary", ""),
                            }
                            for item in results
                        ]
                    except Exception:
                        pass
        if node_name in ["chatbot_web", "chatbot_local", "sql_answer"] and isinstance(msg, (AIMessageChunk, AIMessage)):
            has_tc = getattr(msg, "tool_calls", None)
            if isinstance(msg, AIMessage) and has_tc:
                continue
            text = msg.content or ""
            if text:
                last_chatbot_content += text
                # ── 实时流式输出 thinking / answer ──
                stream_buf += text
                if in_think_block:
                    # 正在 <think> 块内，检查是否遇到 </think>
                    close_pos = stream_buf.lower().find("</think>")
                    if close_pos != -1:
                        # 思考结束，输出剩余思考内容 + 切换到回答
                        thinking_part = stream_buf[:close_pos]
                        answer_part = stream_buf[close_pos + 8:]
                        if thinking_part:
                            yield {"type": "thinking_delta", "delta": thinking_part}
                        in_think_block = False
                        stream_buf = ""
                        if answer_part:
                            yield {"type": "answer_delta", "delta": answer_part}
                    else:
                        # 还在思考中，流式输出（保留末尾防止 tag 跨 chunk）
                        safe_len = max(0, len(stream_buf) - 10)
                        if safe_len > 0:
                            yield {"type": "thinking_delta", "delta": stream_buf[:safe_len]}
                            stream_buf = stream_buf[safe_len:]
                else:
                    # 不在 <think> 块内
                    open_pos = stream_buf.lower().find("<think>")
                    if open_pos != -1:
                        # 遇到 <think> 开始
                        before = stream_buf[:open_pos]
                        if before.strip():
                            yield {"type": "answer_delta", "delta": _strip_think_blocks(before)}
                        in_think_block = True
                        stream_buf = stream_buf[open_pos + 7:]  # 跳过 <think>
                        # 检查同一 chunk 里是否也有 </think>
                        close_pos = stream_buf.lower().find("</think>")
                        if close_pos != -1:
                            thinking_part = stream_buf[:close_pos]
                            answer_part = stream_buf[close_pos + 8:]
                            if thinking_part:
                                yield {"type": "thinking_delta", "delta": thinking_part}
                            in_think_block = False
                            stream_buf = ""
                            if answer_part:
                                yield {"type": "answer_delta", "delta": _strip_think_blocks(answer_part)}
                    else:
                        # 检查是否包含 <tool_call> 等标签块
                        tc_open = stream_buf.lower().find("<tool_call>")
                        if tc_open != -1:
                            tc_close = stream_buf.lower().find("</tool_call>")
                            if tc_close != -1:
                                # 完整标签块在 buffer 中，剥离并输出剩余
                                before = stream_buf[:tc_open]
                                after = stream_buf[tc_close + 12:]
                                if before.strip():
                                    yield {"type": "answer_delta", "delta": before}
                                stream_buf = after
                            else:
                                # 标签块未闭合，输出标签前的内容，保留标签部分等后续 chunk
                                before = stream_buf[:tc_open]
                                if before.strip():
                                    yield {"type": "answer_delta", "delta": before}
                                stream_buf = stream_buf[tc_open:]
                        else:
                            # 普通回答文本，直接输出（保留末尾防止标签跨 chunk）
                            safe_len = max(0, len(stream_buf) - 15)
                            if safe_len > 0:
                                yield {"type": "answer_delta", "delta": stream_buf[:safe_len]}
                                stream_buf = stream_buf[safe_len:]

    # ── 流式循环结束后，刷出剩余 buffer ──
    if stream_buf.strip():
        if in_think_block:
            yield {"type": "thinking_delta", "delta": stream_buf}
        else:
            yield {"type": "answer_delta", "delta": _strip_think_blocks(stream_buf)}

    # 从完整文本提取最终 answer（用于保存历史）
    close_tag = "</think>"
    last_close = last_chatbot_content.lower().rfind(close_tag)
    if last_close != -1:
        full_thinking = last_chatbot_content[:last_close].strip()
        full_answer = last_chatbot_content[last_close + len(close_tag):].strip()
    else:
        full_thinking = ""
        full_answer = last_chatbot_content.strip()

    checked_answer = _strip_think_blocks(full_answer)

    # 兜底：strip 后 answer 全空时，可能是模型只输出了被清理的 <tool_call> XML 等
    # （比如工具调用被路由截断的场景），给用户一个明确提示而不是空白
    if not checked_answer.strip():
        fallback_lines = ["抱歉，本次回答未能完整生成。"]
        # 尝试从模型推理文本中截取末尾片段，至少让用户看到模型的思考脉络
        think_tail = (full_thinking or "").strip()
        if think_tail:
            tail_excerpt = think_tail[-300:].strip()
            fallback_lines.append("")
            fallback_lines.append(f"模型推理片段：{tail_excerpt}")
        # 如果有工具调用过，提示一下
        if tool_trace_events:
            tool_names = sorted({e.get("tool_name") or "" for e in tool_trace_events if e.get("tool_name")})
            if tool_names:
                fallback_lines.append("")
                fallback_lines.append(f"已调用工具：{', '.join(tool_names)}（可能未取得有效结果）。")
        fallback_lines.append("")
        fallback_lines.append("建议换个问法或提供更多上下文重试。")
        checked_answer = "\n".join(fallback_lines)

    yield {
        "type": "complete",
        "result": {
            "answer": checked_answer,
            "raw_answer": full_answer,
            "model_think_text": full_thinking,
            "sources": sources,
            "thinking_steps": list(tool_trace_events),
        }
    }


async def _thinking_text_stream(text: str, chunk_size: Optional[int] = None) -> AsyncIterator[str]:
    content = text or ""
    chunk_size = chunk_size or env_int("CHAT_THINKING_CHUNK_SIZE", 48)
    for index in range(0, len(content), chunk_size):
        yield content[index:index + chunk_size]


@app.get("/api/chat/new_session", tags=["AI对话/对话"], summary="创建新会话", description="创建一个新的对话会话并返回 conversation_id。")
async def create_new_session():
    conversation_id = new_conversation_id()
    return success_response("新建对话成功", {"conversation_id": conversation_id})


@app.post(
    "/api/chat/abort",
    tags=["AI对话/对话"],
    summary="中断当前会话的流式回复",
    description=(
        "前端在流式回答过程中主动调用本接口。传入 `conversation_id` 即可；"
        "若传 `stream_id` 会做一致性校验，不传则兜底按会话维度中断。"
        "接口立即返回；原 /api/chat 的流式连接会收到 `aborted` 事件并关闭。"
    ),
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["conversation_id"],
                        "properties": {
                            "conversation_id": {"type": "string"},
                            "stream_id": {"type": "string", "description": "可选，/api/chat 首个 event stream_open 里返回的 stream_id"},
                        },
                        "example": {"conversation_id": "c_xxx", "stream_id": "abc123"},
                    }
                }
            }
        }
    },
)
async def abort_chat(data: dict = Body(...)):
    conversation_id = str(data.get("conversation_id") or "").strip()
    if not conversation_id:
        return error_response("中断失败", {"reason": "conversation_id 不能为空"}, 400)
    stream_id = str(data.get("stream_id") or "").strip()
    entry = _active_streams.get(conversation_id)
    if entry is None:
        return error_response("当前会话没有正在进行的回答", {"conversation_id": conversation_id}, 404)
    if stream_id and entry.get("stream_id") != stream_id:
        return error_response("stream_id 不匹配，可能回答已结束或已被替换", {"conversation_id": conversation_id}, 409)
    _abort_stream(conversation_id)
    return success_response("已发送中断信号", {"conversation_id": conversation_id, "stream_id": entry.get("stream_id")})


@app.post(
    "/api/chat",
    tags=["AI对话/对话"],
    summary="发送对话消息",
    description=(
        "提交用户问题、附件和对话参数，仅以 SSE 流式输出模型可见答案。"
        "调用约定：无文件上传时使用 application/json；有文件上传时使用 multipart/form-data，并通过 files 字段传递一个或多个附件。"
    ),
    response_class=StreamingResponse,
    openapi_extra={
        "requestBody": {
            "description": "支持两种请求方式：1) 无文件上传时使用 application/json；2) 有文件上传时使用 multipart/form-data，并通过 files 字段上传附件。",
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["message", "conversation_id"],
                        "properties": {
                            "message": {"type": "string", "description": "用户输入"},
                            "conversation_id": {"type": "string", "description": "会话 ID"},
                            "web_search": {"type": "boolean", "description": "是否启用联网搜索"},
                            "enable_thinking": {"type": "boolean", "description": "是否启用深度思考"},
                            "db_version": {"type": "string", "description": "数据库版本标记"},
                            "user_identity": {"type": "string", "description": "用户身份"},
                            "file_ids": {"type": "array", "items": {"type": "string"}, "description": "通过 /api/upload 上传后获得的临时文件 ID 列表"},
                        },
                    },
                    "examples": {
                        "json_without_files": {
                            "summary": "无附件对话请求",
                            "value": {
                                "message": "你好",
                                "conversation_id": "1775641095726-184c395e",
                                "web_search": False,
                                "user_identity": "guest"
                            }
                        }
                    }
                },
            },
        }
    },
    responses={
        200: {
            "description": "SSE 流式回答",
            "content": {
                "text/event-stream": {
                    "schema": {"type": "string"}
                }
            },
        }
    },
)
async def chat_endpoint(
    request: Request,
):
    try:
        payload = await _get_request_payload(request)
    except ValueError as exc:
        return error_response("发送对话失败", {"reason": str(exc)}, 400)

    message = str(payload.get("message") or "").strip()
    conversation_id = str(payload.get("conversation_id") or "").strip()
    web_search = str(payload.get("web_search", "false")).lower() in {"1", "true", "yes", "on"}
    enable_thinking = str(payload.get("enable_thinking", "false")).lower() in {"1", "true", "yes", "on"}
    db_version = normalize_db_version(payload.get("db_version"))
    user_identity = str(payload.get("user_identity") or "guest")

    if not message:
        return error_response("发送对话失败", {"reason": "message 不能为空"}, 400)
    if not conversation_id:
        return error_response("发送对话失败", {"reason": "conversation_id 不能为空"}, 400)

    # 串行锁：同一会话正在流式中时直接拒绝，防止 message_index 并发错乱
    stream_entry = _register_stream(conversation_id)
    if stream_entry is None:
        return error_response("该会话正在回复中，请等待当前回答完成或主动中断后再发送。", {"conversation_id": conversation_id}, 409)
    stream_id = stream_entry["stream_id"]
    abort_event: asyncio.Event = stream_entry["abort"]

    sanitized_message = message

    user = get_logged_in_user()
    history_record, history_path = load_history_record(conversation_id, user)
    message_index = len(history_record.get("messages", []))
    file_ids = payload.get("file_ids") or []
    staging_files = resolve_staging_files(file_ids)
    uploaded_files = []
    for sf in staging_files:
        dest = f"chat/{today_str()}/{safe_segment(conversation_id)}/{message_index}/{sf['filename']}"
        if move_staging_to_dest(sf["staging_object"], dest):
            uploaded_files.append({
                "file_id": sf["file_id"],
                "filename": sf["filename"],
                "url": storage_service.get_presigned_url(dest),
                "relative_path": dest,
                "object_name": dest,
            })
    file_contexts = build_uploaded_file_contexts(uploaded_files)
    model_message_text = compose_chat_prompt(sanitized_message, history_record, file_contexts)
    # 本轮若带图片，构造 multimodal 消息，让 Qwen3.5 原生看图作答
    image_ctxs = [c for c in file_contexts if c.get('kind') == 'image']
    if image_ctxs:
        model_message = [{"type": "text", "text": model_message_text}]
        for c in image_ctxs:
            model_message.append({"type": "image_url", "image_url": {"url": c['data_url']}})
    else:
        model_message = model_message_text

    async def event_stream():
        latest_answer = ""
        latest_thinking_text = ""
        latest_raw_answer = ""
        latest_model_think_text = ""
        latest_sources = []
        latest_thinking_steps = []
        completed = False
        interrupted = False

        def _build_interrupted_item() -> dict:
            return {
                "message_index": message_index,
                "question": sanitized_message,
                "files": [item["filename"] for item in uploaded_files],
                "uploaded_files": uploaded_files,
                "file_contexts": file_contexts,
                "web_search": bool(web_search),
                "db_version": db_version,
                "answer": latest_answer,
                "raw_answer": latest_raw_answer,
                "resource": latest_sources,
                "recommend_answer": [],
                "feedback": None,
                "interrupted": True,
                "thinking_text": (_format_thinking_text(latest_thinking_steps) or latest_thinking_text or latest_model_think_text) if enable_thinking else "",
                "model_think_text": latest_model_think_text,
                "thinking_steps": latest_thinking_steps,
                "created_at": now_ms(),
                "updated_at": now_ms(),
                "createdAt": now_display(),
                "updatedAt": now_display(),
            }

        def _persist_interrupted() -> dict:
            """保存中断时的半截答案并返回 message_item。"""
            item = _build_interrupted_item()
            try:
                history_record["user"] = build_user_brief(user, conversation_id)
                history_record.setdefault("messages", []).append(item)
                save_history_record(history_record, history_path)
            except Exception:
                pass
            return item

        _saved_interrupted = False

        async def _iter_or_abort(iterator):
            """让 LLM 事件获取与 abort 信号并发竞争：abort 优先，可立即打断阻塞的 await。"""
            next_task: Optional[asyncio.Task] = None
            try:
                while True:
                    if next_task is None:
                        next_task = asyncio.ensure_future(iterator.__anext__())
                    abort_task = asyncio.ensure_future(abort_event.wait())
                    done_set, _ = await asyncio.wait(
                        {next_task, abort_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if abort_task in done_set and not next_task.done():
                        next_task.cancel()
                        try:
                            await next_task
                        except (asyncio.CancelledError, Exception):
                            pass
                        next_task = None
                        return  # 中断
                    if not abort_task.done():
                        abort_task.cancel()
                        try:
                            await abort_task
                        except (asyncio.CancelledError, Exception):
                            pass
                    try:
                        ev = next_task.result()
                    except StopAsyncIteration:
                        next_task = None
                        return
                    next_task = None
                    yield ev
            finally:
                if next_task is not None and not next_task.done():
                    next_task.cancel()
                    try:
                        await next_task
                    except (asyncio.CancelledError, Exception):
                        pass

        try:
            # 首个事件把 stream_id 推给前端，用于后续 abort 接口引用
            yield _sse_event({"type": "stream_open", "stream_id": stream_id})
            chat_iter = iterate_chat_events(
                model_message,
                conversation_id,
                web_search,
                user_identity or "guest",
                raw_user_message=sanitized_message,
                enable_thinking=enable_thinking,
            )
            async for event in _iter_or_abort(chat_iter.__aiter__()):
                # 每处理一个 event 先检查中断（兜底）
                if abort_event.is_set():
                    interrupted = True
                    item = _persist_interrupted()
                    _saved_interrupted = True
                    print(f"[chat] aborted conv={conversation_id} stream={stream_id} ans_len={len(latest_answer)} ts={now_ms()}", file=sys.stderr)
                    yield _sse_event({"type": "aborted", "data": _build_chat_done_payload(item)})
                    return
                event_type = event.get("type")
                if event_type == "progress":
                    yield _sse_comment(event.get("message") or "progress")
                    continue
                if event_type == "thinking_delta":
                    delta_text = event.get("delta", "")
                    if enable_thinking:
                        delay_ms = max(env_int("CHAT_STREAM_CHAR_DELAY_MS", 15), 0)
                        for chunk_event in _iter_text_event_chunks("thinking_delta", delta_text):
                            if abort_event.is_set():
                                interrupted = True
                                break
                            yield _sse_event(chunk_event)
                            # yield 成功后才把这一块累加进"前端已收到"的状态
                            latest_thinking_text += chunk_event.get("delta", "")
                            if delay_ms > 0:
                                await asyncio.sleep(delay_ms / 1000)
                    else:
                        # 不启用思考流时，前端不会看到 thinking 内容，但仍累计供后续保存
                        latest_thinking_text += delta_text
                    if interrupted:
                        break
                    continue
                if event_type == "answer_delta":
                    delta_text = event.get("delta", "")
                    delay_ms = max(env_int("CHAT_STREAM_CHAR_DELAY_MS", 15), 0)
                    for chunk_event in _iter_text_event_chunks("answer_delta", delta_text):
                        if abort_event.is_set():
                            interrupted = True
                            break
                        yield _sse_event(chunk_event)
                        # 真正发到前端后才累加，保证 abort 时 latest_answer == 前端实际看到的
                        latest_answer += chunk_event.get("delta", "")
                        if delay_ms > 0:
                            await asyncio.sleep(delay_ms / 1000)
                    if interrupted:
                        break
                elif event_type == "answer_replace":
                    latest_answer = event.get("content", "")
                    yield _sse_event(event)
                elif event_type == "complete":
                    result = event.get("result", {})
                    latest_answer = result.get("answer", latest_answer)
                    latest_raw_answer = result.get("raw_answer", latest_raw_answer)
                    latest_model_think_text = result.get("model_think_text", latest_model_think_text)
                    latest_sources = result.get("sources", latest_sources)
                    latest_thinking_steps = result.get("thinking_steps", latest_thinking_steps)
                    recommend_answer = await generate_recommendations(sanitized_message, latest_answer)
                    message_item = {
                        "message_index": message_index,
                        "question": sanitized_message,
                        "files": [item["filename"] for item in uploaded_files],
                        "uploaded_files": uploaded_files,
                        "file_contexts": file_contexts,
                        "web_search": bool(web_search),
                        "db_version": db_version,
                        "answer": latest_answer,
                        "raw_answer": latest_raw_answer,
                        "resource": latest_sources,
                        "recommend_answer": recommend_answer,
                        "feedback": None,
                        "thinking_text": (_format_thinking_text(latest_thinking_steps) or latest_thinking_text or latest_model_think_text) if enable_thinking else "",
                        "model_think_text": latest_model_think_text,
                        "thinking_steps": latest_thinking_steps,
                        "created_at": now_ms(),
                        "updated_at": now_ms(),
                        "createdAt": now_display(),
                        "updatedAt": now_display(),
                    }
                    history_record["user"] = build_user_brief(user, conversation_id)
                    history_record.setdefault("messages", []).append(message_item)
                    save_history_record(history_record, history_path)
                    completed = True
                    print(f"[chat] done conv={conversation_id} stream={stream_id} ts={now_ms()}", file=sys.stderr)
                    yield _sse_event({"type": "done", "data": _build_chat_done_payload(message_item)})
                    return
            # _iter_or_abort 因为 abort 信号提前 return 时，走到这里补发 aborted
            if abort_event.is_set() and not completed and not _saved_interrupted:
                interrupted = True
                item = _persist_interrupted()
                _saved_interrupted = True
                print(f"[chat] aborted conv={conversation_id} stream={stream_id} ans_len={len(latest_answer)} ts={now_ms()}", file=sys.stderr)
                yield _sse_event({"type": "aborted", "data": _build_chat_done_payload(item)})
        except asyncio.CancelledError:
            # 客户端主动断开 SSE 连接（浏览器 AbortController / 网络断线）
            # 此时不能再 yield，只能保存半截答案后 re-raise
            if not completed and not _saved_interrupted:
                _persist_interrupted()
            raise
        except Exception as exc:
            yield _sse_event({"type": "error", "message": str(exc)})
        finally:
            _unregister_stream(conversation_id, stream_id)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "X-Stream-Id": stream_id,  # 前端可从 response header 读，后续调 /api/chat/abort 时携带
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


STAGING_PREFIX = "staging"
GRAPH_LOCAL_FILE_ID_PREFIX = "graph_local"
GRAPH_LOCAL_OBJECT_PREFIX = "graph-local://"
GRAPH_LOCAL_UPLOAD_DIRS = {
    "internal_binding": ROOT_DIR / "graph" / "runtime" / "internal_binding_workspace" / "uploads",
    "external": ROOT_DIR / "graph" / "runtime" / "external_workspace" / "uploads",
}


def _decode_graph_local_file_id(file_id: str) -> Optional[dict]:
    raw = str(file_id or "").strip()
    parts = raw.split(":", 2)
    if len(parts) != 3 or parts[0] != GRAPH_LOCAL_FILE_ID_PREFIX:
        return None

    scope, encoded_name = parts[1], parts[2]
    upload_dir = GRAPH_LOCAL_UPLOAD_DIRS.get(scope)
    if upload_dir is None:
        return None
    try:
        padding = "=" * (-len(encoded_name) % 4)
        filename = base64.urlsafe_b64decode(f"{encoded_name}{padding}").decode("utf-8")
    except Exception:
        return None

    filename = Path(filename).name
    if not filename:
        return None
    local_path = (upload_dir / filename).resolve()
    try:
        local_path.relative_to(upload_dir.resolve())
    except ValueError:
        return None
    if not local_path.is_file():
        return None
    try:
        size = local_path.stat().st_size
    except OSError:
        size = 0
    return {"filename": filename, "local_path": local_path, "size": size}


@app.post(
    "/api/upload",
    tags=["AI对话/文件上传"],
    summary="上传文件（支持多文件）",
    description=(
        "统一文件上传接口。multipart/form-data 表单字段名固定为 `files`，可携带一个或多个文件。"
        "每个文件暂存到 staging 目录并分配独立 file_id，响应按上传顺序返回 `files` 数组。"
        "业务接口（如 /api/chat.file_ids、/api/chat/feedback.picture_ids、/api/kb/update.add_file_ids）通过这些 file_id 引用文件。"
        "未被业务接口关联的 staging 文件会在服务启动时自动清理。"
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["files"],
                        "properties": {
                            "files": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"},
                                "description": "一个或多个文件。即便只传一个也请用 `files` 字段。",
                            },
                        },
                    }
                }
            },
        },
        "responses": {
            "200": {
                "description": "上传成功。",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "integer", "example": 0},
                                "msg": {"type": "string", "example": "上传成功"},
                                "data": {
                                    "type": "object",
                                    "properties": {
                                        "files": {
                                            "type": "array",
                                            "description": "按上传顺序返回的文件元信息数组。",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "file_id": {"type": "string", "example": "f_1775641095726_ab12cd34"},
                                                    "filename": {"type": "string", "example": "合同.pdf"},
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        }
                    }
                },
            }
        },
    },
)
async def upload_file(files: list[UploadFile] = File(..., description="一个或多个文件，字段名固定为 files")):
    if not files:
        return error_response("上传失败", {"reason": "files 不能为空"}, 400)

    uploaded: list[dict] = []
    for upload in files:
        if not upload.filename:
            return error_response("上传失败", {"reason": "文件名不能为空"}, 400)
        file_id = f"f_{now_ms()}_{uuid.uuid4().hex[:8]}"
        filename = Path(upload.filename).name
        object_name = f"{STAGING_PREFIX}/{file_id}/{filename}"
        content_type = getattr(upload, "content_type", "application/octet-stream")
        if not storage_service.upload_file_obj(upload.file, object_name, content_type):
            return error_response("上传失败", {"reason": f"文件存储失败: {filename}"}, 500)
        uploaded.append({"file_id": file_id, "filename": filename})

    return success_response("上传成功", {"files": uploaded})


def resolve_staging_files(file_ids: list) -> list:
    """从 staging 目录查找 file_id 对应的文件信息。"""
    results = []
    for fid in (file_ids or []):
        if not fid:
            continue
        graph_local_file = _decode_graph_local_file_id(fid)
        if graph_local_file:
            results.append({
                "file_id": fid,
                "filename": graph_local_file["filename"],
                "staging_object": f"{GRAPH_LOCAL_OBJECT_PREFIX}{graph_local_file['local_path']}",
                "size": graph_local_file.get("size", 0),
            })
            continue
        prefix = f"{STAGING_PREFIX}/{fid}/"
        objects = storage_service.list_files(prefix)
        if objects:
            obj = objects[0]
            filename = obj["object_name"].rsplit("/", 1)[-1]
            results.append({
                "file_id": fid,
                "filename": filename,
                "staging_object": obj["object_name"],
                "size": obj.get("size", 0),
            })
    return results


def move_staging_to_dest(staging_object: str, dest_object: str) -> bool:
    """将 staging 文件移动到正式目录。"""
    if str(staging_object or "").startswith(GRAPH_LOCAL_OBJECT_PREFIX):
        local_path = Path(str(staging_object)[len(GRAPH_LOCAL_OBJECT_PREFIX):])
        allowed = False
        try:
            resolved_path = local_path.resolve()
        except OSError:
            return False
        for upload_dir in GRAPH_LOCAL_UPLOAD_DIRS.values():
            try:
                resolved_path.relative_to(upload_dir.resolve())
                allowed = True
                break
            except ValueError:
                continue
        if not allowed or not resolved_path.is_file():
            return False
        content_type = mimetypes.guess_type(resolved_path.name)[0] or "application/octet-stream"
        with open(resolved_path, "rb") as file_obj:
            return storage_service.upload_file_obj(file_obj, dest_object, content_type)
    return storage_service.move_object(staging_object, dest_object)


@app.get("/api/history/list", tags=["AI对话/对话日志"], summary="查询历史记录列表", description="按关键词、时间范围和分页参数筛选历史对话列表。")
async def list_histories(
    search: str = Query("", description="历史记录关键词，可匹配标题、问题和回答。"),
    start_time: Optional[str] = Query(None, description="开始时间，毫秒时间戳。"),
    end_time: Optional[str] = Query(None, description="结束时间，毫秒时间戳。"),
    page: int = Query(1, description="页码，从 1 开始。"),
    size: int = Query(10, description="每页数量，默认 10。"),
):
    try:
        start_ms = parse_optional_millis(start_time, "start_time")
        end_ms = parse_optional_millis(end_time, "end_time")
        page, size = normalize_page_size(page, size)
    except ValueError as exc:
        return error_response("获取历史记录失败", {"reason": str(exc)}, 400)
    records = filter_history_records(search=search, start_ms=start_ms, end_ms=end_ms)
    # 企业端：每个人只看自己的历史记录
    user = get_logged_in_user()
    my_name = user.get("name", "")
    if my_name:
        records = [r for r in records if (r.get("user") or {}).get("name") == my_name]
    results = [build_history_list_item(record) for record in records]
    return success_response("获取历史记录成功", paginate_payload(results, page, size))


@app.get("/api/history/{conversation_id}", tags=["AI对话/对话日志"], summary="获取历史记录详情", description="返回指定 conversation_id 的完整历史对话内容。")
async def get_history_detail(conversation_id: str):
    history_record, _ = load_history_record(conversation_id)
    if not history_record.get("messages"):
        return error_response("获取历史详情失败", {"conversation_id": conversation_id}, 404)
    return success_response("获取历史详情成功", history_record)


@app.delete("/api/chat/{conversation_id}", tags=["AI对话/对话日志"], summary="删除单条历史记录", description="删除指定会话的历史记录文件，并清理空目录。")
async def delete_history(conversation_id: str):
    object_name = resolve_history_path(conversation_id)
    if not object_name:
        return error_response("删除历史对话失败", {"conversation_id": conversation_id}, 404)
    if not storage_service.delete_file(object_name):
        return error_response("删除历史对话失败", {"reason": "删除 MinIO 历史文件失败"}, 500)
    return success_response("删除历史对话成功", {"conversation_id": conversation_id})


@app.post("/api/history/batch_delete", tags=["AI对话/对话日志"], summary="批量删除历史记录", description="根据传入的会话 ID 列表批量删除历史对话。")
async def batch_delete_history(data: dict = Body(..., example={"ids": ["conversation_id_1"]})):
    try:
        ids = ensure_id_list(data, "ids")
    except ValueError as exc:
        return error_response("批量删除历史对话失败", {"reason": str(exc)}, 400)
    if not ids:
        return error_response("批量删除历史对话失败", {"reason": "ids 不能为空"}, 400)
    deleted = []
    for conversation_id in ids:
        object_name = resolve_history_path(conversation_id)
        if object_name and storage_service.delete_file(object_name):
            deleted.append(conversation_id)
    return success_response("批量删除历史对话成功", {"deleted_ids": deleted})


@app.post(
    "/api/history/export",
    tags=["AI对话/对话日志"],
    summary="导出历史详情",
    description="导出选中的会话历史详情为 xlsx 文件；传 `ids` 时导出指定记录，不传时按 `search/start_time/end_time` 过滤并导出全部。",
    openapi_extra={
        "requestBody": {
            "description": "可选：传 ids 指定导出范围；或传 search/start_time/end_time 过滤条件；都不传则导出全部历史。",
            "required": False,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "要导出的 conversation_id 列表。",
                            },
                            "search": {"type": "string", "description": "仅当 ids 未传时生效；关键词模糊匹配标题/问题/回答。"},
                            "start_time": {"type": "string", "description": "仅当 ids 未传时生效；开始时间（毫秒时间戳）。"},
                            "end_time": {"type": "string", "description": "仅当 ids 未传时生效；结束时间（毫秒时间戳）。"},
                        },
                        "example": {"ids": ["1775641095726-184c395e"]},
                    }
                }
            },
        },
        "responses": {
            "200": {
                "description": "成功导出；响应为 xlsx 二进制流，文件名通过 Content-Disposition 回传（RFC 5987 UTF-8 编码）。",
                "content": {
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                        "schema": {"type": "string", "format": "binary"},
                    },
                },
            }
        },
    },
)
async def export_history_detail(data: Optional[dict] = Body(None)):
    return error_response("该接口仅限管理端访问", {"reason": "请使用 /api/admin/ 路由"}, 401)
    payload = data or {}
    try:
        ids = ensure_id_list(payload, "ids")
    except ValueError as exc:
        return error_response("导出历史记录失败", {"reason": str(exc)}, 400)

    if ids:
        records = collect_history_records(ids)
    else:
        search = str(payload.get("search") or "")
        start_time = payload.get("start_time")
        end_time = payload.get("end_time")
        start_ms = parse_optional_millis(start_time, "start_time") if start_time else None
        end_ms = parse_optional_millis(end_time, "end_time") if end_time else None
        filtered = filter_history_records(search=search, start_ms=start_ms, end_ms=end_ms)
        record_ids = [r.get("conversation_id") for r in filtered if r.get("conversation_id")]
        records = collect_history_records(record_ids or None)
    if not records:
        return error_response("导出历史记录失败", {"reason": "没有可导出的历史记录"}, 404)

    table_headers = ["序号", "IP地址", "用户ID", "RecordID", "问答"]
    rows = []
    for idx, record in enumerate(records, start=1):
        user = record.get("user") or {}
        rows.append([
            idx,
            user.get("ip_address", ""),
            user.get("user_id", ""),
            user.get("record_id", "") or record.get("conversation_id", ""),
            format_qa_content(record.get("messages", [])),
        ])
    content = build_xlsx_bytes(table_headers, rows)
    filename = f"对话日志_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    from urllib.parse import quote
    response_headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(io.BytesIO(content), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=response_headers)


@app.get("/api/history/{conversation_id}/messages/{message_index}/files/{file_id}/download", tags=["AI对话/对话日志"], summary="下载会话上传文件", description="下载某一轮提问中上传的原始附件文件。")
async def download_history_uploaded_file(conversation_id: str, message_index: int, file_id: str):
    file_item = find_uploaded_file(conversation_id, message_index, file_id)
    if not file_item:
        return error_response("下载附件失败", {"conversation_id": conversation_id, "message_index": message_index, "file_id": file_id}, 404)
    object_name = file_item.get("object_name") or file_item.get("relative_path")
    if not object_name:
        return error_response("下载附件失败", {"reason": "附件对象路径不存在"}, 404)
    content = storage_service.read_file_bytes(object_name)
    if not content:
        return error_response("下载附件失败", {"reason": "从 MinIO 读取附件失败"}, 500)
    filename = Path(file_item.get("filename") or object_name.rsplit("/", 1)[-1]).name
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(io.BytesIO(content), media_type="application/octet-stream", headers=headers)


@app.get(
    "/api/chat/{conversation_id}/thinking",
    tags=["AI对话/对话"],
    summary="获取思考过程",
    description="仅以文本流返回指定会话某一轮消息的工具调用过程；若无工具过程，则回退到模型 <think> 内容。",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "文本流式思考过程",
            "content": {
                "text/plain": {
                    "schema": {"type": "string"}
                }
            },
        }
    },
)
async def get_chat_thinking(
    conversation_id: str,
    message_index: Optional[int] = Query(None),
):
    history_record, _ = load_history_record(conversation_id)
    messages = history_record.get("messages", [])
    if not messages:
        return error_response("获取思考过程失败", {"conversation_id": conversation_id}, 404)
    target = messages[-1] if message_index is None else next((item for item in messages if item.get("message_index") == message_index), None)
    if not target:
        return error_response("获取思考过程失败", {"conversation_id": conversation_id, "message_index": message_index}, 404)
    thinking_text = _resolve_saved_thinking_text(target)
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(_thinking_text_stream(thinking_text), media_type="text/plain; charset=utf-8", headers=headers)


@app.post(
    "/api/chat/feedback",
    tags=["AI对话/反馈"],
    summary="提交对话反馈",
    description="对指定消息提交点赞或点踩反馈，并可附带原因、文字说明和图片。",
    openapi_extra={
        "requestBody": {
            "description": "通过 application/json 提交反馈，图片引用通过 /api/upload 预上传后获得的 ID。",
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["conversation_id", "message_index", "type"],
                        "properties": {
                            "conversation_id": {"type": "string", "description": "会话 ID"},
                            "message_index": {"type": "integer", "description": "消息轮次，从 0 开始"},
                            "type": {"type": "string", "enum": ["like", "dislike"], "description": "反馈类型：点赞或点踩"},
                            "question_issues": {
                                "type": "array",
                                "items": {"type": "string", "enum": ["notUnderstand", "missingContext", "notMeetRequirements"]},
                                "description": "【针对问题】勾选的原因 key 数组。空数组表示未选。key 含义见 GET /api/feedback/reason_options。",
                            },
                            "answer_effects": {
                                "type": "array",
                                "items": {"type": "string", "enum": ["wrongAnswer", "confuseLogic", "timeMismatch", "readabilityPoor", "incompleteAnswer", "processUnprofessional"]},
                                "description": "【针对回答效果】勾选的原因 key 数组。空数组表示未选。",
                            },
                            "report_reasons": {
                                "type": "array",
                                "items": {"type": "string", "enum": ["porn", "politics", "illegal", "privacy", "copyright", "discrimination"]},
                                "description": "【举报】勾选的原因 key 数组。空数组表示未选。",
                            },
                            "comment": {"type": "string", "description": "补充说明"},
                            "picture_ids": {"type": "array", "items": {"type": "string"}, "description": "通过 /api/upload 上传后获得的图片文件 ID 列表"},
                        },
                    },
                    "examples": {
                        "like_feedback": {
                            "summary": "点赞反馈",
                            "value": {
                                "conversation_id": "1775641095726-184c395e",
                                "message_index": 0,
                                "type": "like",
                            },
                        },
                        "dislike_feedback": {
                            "summary": "点踩反馈",
                            "value": {
                                "conversation_id": "1775641095726-184c395e",
                                "message_index": 0,
                                "type": "dislike",
                                "question_issues": [],
                                "answer_effects": ["wrongAnswer", "incompleteAnswer"],
                                "report_reasons": [],
                                "comment": "答案需要补充数据来源",
                            },
                        },
                    },
                },
            },
        }
    },
)
async def save_feedback(
    request: Request,
):
    try:
        payload = await _get_request_payload(request)
    except ValueError as exc:
        return error_response("提交反馈失败", {"reason": str(exc)}, 400)

    conversation_id = str(payload.get("conversation_id") or "").strip()
    fb_type = str(payload.get("type") or "").strip()
    comment = str(payload.get("comment") or "")
    if not conversation_id:
        return error_response("提交反馈失败", {"reason": "conversation_id 不能为空"}, 400)
    try:
        message_index = int(payload.get("message_index"))
    except Exception:
        return error_response("提交反馈失败", {"reason": "message_index 必须是整数"}, 400)
    if fb_type not in ("like", "dislike"):
        return error_response("提交反馈失败", {"reason": "type 必须是 like 或 dislike"}, 400)
    if message_index < 0:
        return error_response("提交反馈失败", {"reason": "message_index 不能为负数"}, 400)

    try:
        question_issues = normalize_reason_keys(payload.get("question_issues"), "question_issues")
        answer_effects = normalize_reason_keys(payload.get("answer_effects"), "answer_effects")
        report_reasons = normalize_reason_keys(payload.get("report_reasons"), "report_reasons")
    except ValueError as exc:
        return error_response("提交反馈失败", {"reason": str(exc)}, 400)

    user = get_logged_in_user()
    history_record, history_path = load_history_record(conversation_id)
    messages = history_record.get("messages", [])
    if not (0 <= message_index < len(messages)):
        return error_response("提交反馈失败", {"conversation_id": conversation_id, "message_index": message_index}, 404)

    target_message = messages[message_index]

    # 同类型点两次 = 取消；不同类型 = 新建当前类型 + 取消对方
    feedback_id = f"fb_{conversation_id}_{message_index}_{fb_type}"
    opposite_type = "dislike" if fb_type == "like" else "like"
    opposite_id = f"fb_{conversation_id}_{message_index}_{opposite_type}"

    # 检查当前类型的已有记录
    cur_existing = _load_feedback_info(feedback_id)
    was_active = cur_existing.get("active", False)

    if was_active:
        # 同类型再点 = 取消
        new_feedback = "none"
        active = False
    else:
        new_feedback = fb_type
        active = True

    # 点踩需要理由
    picture_ids = payload.get("picture_ids") or []
    has_reason = bool(question_issues or answer_effects or report_reasons)
    if new_feedback == "dislike" and not any([has_reason, comment, picture_ids]):
        return error_response("提交反馈失败", {"reason": "点踩反馈必须填写原因、描述或上传截图"}, 400)

    # 如果激活当前类型，把对方设为 inactive
    if active:
        opp_info = _load_feedback_info(opposite_id)
        if opp_info.get("active", False):
            opp_info["active"] = False
            opp_info["update_time"] = now_ms()
            opp_info["updatedAt"] = now_display()
            _save_feedback_info(opposite_id, opp_info)

    # 更新历史记录中的 feedback 状态（保留最新激活的类型）
    target_message["feedback"] = new_feedback if active else None
    target_message["updated_at"] = now_ms()
    target_message["updatedAt"] = now_display()
    save_history_record(history_record, history_path)

    existing = cur_existing

    # 处理图片：从 staging 移动到正式目录
    pictures_list = []
    picture_names = []
    if new_feedback == "dislike" and picture_ids:
        staging_pics = resolve_staging_files(picture_ids)
        for sf in staging_pics:
            dest = f"feedback/{today_str()}/{feedback_id}/{sf['filename']}"
            if move_staging_to_dest(sf["staging_object"], dest):
                pictures_list.append({"filename": sf["filename"], "object_name": dest, "url": storage_service.get_presigned_url(dest)})
                picture_names.append(sf["filename"])

    current_time = now_ms()
    question = target_message.get("question", "")
    answer = target_message.get("answer", "")
    feedback_info = {
        "id": feedback_id,
        "conversation_id": conversation_id,
        "message_index": message_index,
        "type": new_feedback,
        "active": active,
        "time": existing.get("time") or current_time,
        "update_time": current_time,
        "createdAt": existing.get("createdAt") or now_display(),
        "updatedAt": now_display(),
        "question_issues": question_issues if new_feedback == "dislike" else [],
        "answer_effects": answer_effects if new_feedback == "dislike" else [],
        "report_reasons": report_reasons if new_feedback == "dislike" else [],
        "comment": comment if new_feedback == "dislike" else "",
        "pictures": picture_names,
        "pictures_list": pictures_list,
        "user": build_user_payload(user, conversation_id),
        "name": user.get("name", ""),
        "enterprise": user.get("company", ""),
        "phone": user.get("phone", ""),
        "user_id": resolve_user_id(user),
        "record_id": conversation_id,
        "ip_address": user.get("ip_address", ""),
        "question": question,
        "answer": answer,
        "process_status": existing.get("process_status", "未处理"),
        "process_result": existing.get("process_result", ""),
    }
    _save_feedback_info(feedback_id, feedback_info)
    return success_response("提交反馈成功", {"feedback": new_feedback, "active": active})


@app.get(
    "/api/feedback/reason_options",
    tags=["AI对话/反馈"],
    summary="获取反馈原因选项",
    description=(
        "返回点踩反馈的三组原因选项。每个分组内部直接是 `{key: 中文}` 字典，"
        "前端用中文展示、把勾选的 key 回填到 /api/chat/feedback 的 `question_issues / answer_effects / report_reasons` 字段（同样是 `{key: 中文}` 字典格式）。"
    ),
    openapi_extra={
        "responses": {
            "200": {
                "description": "三组反馈原因选项。",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "integer", "example": 0},
                                "msg": {"type": "string", "example": "获取反馈原因选项成功"},
                                "data": {
                                    "type": "object",
                                    "properties": {
                                        "question_issues": {
                                            "type": "object",
                                            "description": "【针对问题】分组可选原因，key→中文 label",
                                            "additionalProperties": {"type": "string"},
                                            "example": {
                                                "notUnderstand": "不理解问题",
                                                "missingContext": "遗忘上下文",
                                                "notMeetRequirements": "未遵循要求",
                                            },
                                        },
                                        "answer_effects": {
                                            "type": "object",
                                            "description": "【针对回答效果】分组可选原因，key→中文 label",
                                            "additionalProperties": {"type": "string"},
                                            "example": {
                                                "wrongAnswer": "回答错误",
                                                "confuseLogic": "逻辑混乱",
                                                "timeMismatch": "时效性差",
                                                "readabilityPoor": "可读性差",
                                                "incompleteAnswer": "回答不完整",
                                                "processUnprofessional": "回答笼统不专业",
                                            },
                                        },
                                        "report_reasons": {
                                            "type": "object",
                                            "description": "【举报】分组可选原因，key→中文 label",
                                            "additionalProperties": {"type": "string"},
                                            "example": {
                                                "porn": "色情低俗",
                                                "politics": "政治敏感",
                                                "illegal": "违法犯罪",
                                                "privacy": "侵犯隐私",
                                                "copyright": "内容侵权",
                                                "discrimination": "歧视或偏见回答",
                                            },
                                        },
                                    },
                                },
                            },
                        }
                    }
                },
            }
        }
    },
)
async def get_feedback_reason_options():
    return success_response(
        "获取反馈原因选项成功",
        {
            **{field: dict(cfg["options"]) for field, cfg in FEEDBACK_REASON_GROUPS.items()},
            "type_options": [
                {"label": "全部", "value": "全部"},
                {"label": "点赞", "value": "点赞"},
                {"label": "点踩", "value": "点踩"},
                {"label": "针对问题", "value": "针对问题"},
                {"label": "针对回答效果", "value": "针对回答效果"},
                {"label": "举报", "value": "举报"},
            ],
            "status_options": [
                {"label": "全部", "value": ""},
                {"label": "已处理", "value": "已处理"},
                {"label": "未处理", "value": "未处理"},
            ],
            "process_results": [
                {"label": "录入良好回答", "value": "录入良好回答"},
                {"label": "录入待优化回答", "value": "录入待优化回答"},
            ],
        },
    )


@app.get(
    "/api/feedback/list",
    tags=["AI对话/反馈"],
    summary="查询反馈列表",
    description="按姓名、企业、反馈类型、时间范围和分页参数筛选反馈记录，可用于反馈列表、待优化回答、良好回答等页面。",
    openapi_extra={
        "responses": {
            "200": {
                "description": "反馈列表分页结果。",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "integer", "example": 0},
                                "msg": {"type": "string", "example": "获取反馈列表成功"},
                                "data": {
                                    "type": "object",
                                    "properties": {
                                        "list": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "id": {"type": "string"},
                                                    "conversation_id": {"type": "string"},
                                                    "message_index": {"type": "integer"},
                                                    "type": {"type": "string", "description": "点赞 like / 点踩 dislike。"},
                                                    "feedback_type": {
                                                        "type": "object",
                                                        "properties": {
                                                            "primary": {"type": "string", "description": "点赞/点踩"},
                                                            "labels": {"type": "array", "items": {"type": "string"}, "description": "细分标签：点踩有子分类时为子分类数组，否则为 [primary]"},
                                                        },
                                                    },
                                                    "question_issues": {"type": "array", "items": {"type": "string"}, "description": "【针对问题】勾选的原因 key 数组", "example": ["notUnderstand"]},
                                                    "answer_effects": {"type": "array", "items": {"type": "string"}, "description": "【针对回答效果】勾选的原因 key 数组", "example": ["wrongAnswer"]},
                                                    "report_reasons": {"type": "array", "items": {"type": "string"}, "description": "【举报】勾选的原因 key 数组", "example": []},
                                                    "comment": {"type": "string"},
                                                    "process_status": {"type": "string", "example": "未处理"},
                                                    "process_result": {"type": "string", "example": "已录入回答良好"},
                                                    "processor": {"type": "string", "description": "处理人（暂无认证体系，当前恒为空字符串）"},
                                                    "user": {
                                                        "type": "object",
                                                        "properties": {
                                                            "name": {"type": "string"},
                                                            "enterprise": {"type": "string"},
                                                            "phone": {"type": "string"},
                                                        },
                                                    },
                                                    "createdAt": {"type": "string"},
                                                    "updatedAt": {"type": "string"},
                                                    "active": {"type": "boolean"},
                                                },
                                            },
                                        },
                                        "total": {"type": "integer"},
                                        "page": {"type": "integer"},
                                        "size": {"type": "integer"},
                                        "total_pages": {"type": "integer"},
                                    },
                                },
                            },
                        }
                    }
                },
            }
        }
    },
)
async def list_feedbacks(
    search: str = Query("", description="综合搜索，匹配反馈人姓名、手机号、所属企业。"),
    type: Optional[Literal["like", "dislike"]] = Query(None, description="主类型筛选：`dislike` 表示待优化回答，`like` 表示良好回答；不传表示全部。"),
    feedback_type: Literal["全部", "针对问题", "针对回答效果", "举报", "点赞", "点踩"] = Query("全部", description="反馈细分类型筛选。"),
    process_status: str = Query("", description="处理状态筛选：已处理、未处理，不传表示全部。"),
    process_result: str = Query("", description="处理结果筛选：录入待优化回答、录入良好回答，不传表示全部。"),
    start_time: Optional[str] = Query(None, description="反馈提交开始时间，毫秒时间戳。"),
    end_time: Optional[str] = Query(None, description="反馈提交结束时间，毫秒时间戳。"),
    processed_start_time: Optional[str] = Query(None, description="处理开始时间，毫秒时间戳。"),
    processed_end_time: Optional[str] = Query(None, description="处理结束时间，毫秒时间戳。"),
    page: int = Query(1, description="页码，从 1 开始。"),
    size: int = Query(10, description="每页数量，默认 10。"),
):
    return error_response("该接口仅限管理端访问", {"reason": "请使用 /api/admin/ 路由"}, 401)
    try:
        start_ms = parse_optional_millis(start_time, "start_time")
        end_ms = parse_optional_millis(end_time, "end_time")
        processed_start_ms = parse_optional_millis(processed_start_time, "processed_start_time")
        processed_end_ms = parse_optional_millis(processed_end_time, "processed_end_time")
        page, size = normalize_page_size(page, size)
    except ValueError as exc:
        return error_response("获取反馈列表失败", {"reason": str(exc)}, 400)
    results = collect_feedback_summaries(
        search=search,
        type=type or "",
        feedback_type=feedback_type,
        process_status=process_status,
        process_result=process_result,
        start_ms=start_ms,
        end_ms=end_ms,
        processed_start_ms=processed_start_ms,
        processed_end_ms=processed_end_ms,
    )
    return success_response("获取反馈列表成功", paginate_payload(results, page, size))


@app.post(
    "/api/feedback/export",
    tags=["AI对话/反馈"],
    summary="导出反馈列表",
    description="传 ids 导出勾选条目；不传 ids 则按检索参数导出全部。返回 CSV 文件。",
)
async def export_feedbacks(data: Optional[dict] = Body(None)):
    return error_response("该接口仅限管理端访问", {"reason": "请使用 /api/admin/ 路由"}, 401)
    payload = data or {}
    ids = payload.get("ids") or []
    search = str(payload.get("search") or "")
    fb_type = str(payload.get("type") or "")
    feedback_type = str(payload.get("feedback_type") or "全部")
    process_status = str(payload.get("process_status") or "")
    process_result_filter = str(payload.get("process_result") or "")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")

    try:
        start_ms = parse_optional_millis(start_time, "start_time") if start_time else None
        end_ms = parse_optional_millis(end_time, "end_time") if end_time else None
    except ValueError as exc:
        return error_response("导出反馈列表失败", {"reason": str(exc)}, 400)

    rows = collect_feedback_summaries(
        search=search, type=fb_type, feedback_type=feedback_type,
        process_status=process_status, process_result=process_result_filter,
        start_ms=start_ms, end_ms=end_ms,
    )
    if ids:
        id_set = set(str(i) for i in ids)
        rows = [r for r in rows if str(r.get("id", "")) in id_set]
    if not rows:
        return error_response("导出反馈列表失败", {"reason": "没有可导出的反馈记录"}, 404)

    # 根据 process_result 参数区分三种模板：反馈列表 / 待优化 / 良好
    is_filtered_view = bool(process_result_filter)  # 待优化或良好
    if is_filtered_view:
        table_headers = ["序号", "反馈人", "联系方式", "所属企业", "反馈类型", "提交时间", "处理人", "反馈对象"]
    else:
        table_headers = ["序号", "反馈人", "联系方式", "所属企业", "反馈类型", "提交时间", "处理状态", "处理结果", "反馈对象"]

    table_rows = []
    for idx, item in enumerate(rows, start=1):
        user = item.get("user") or {}
        labels = (item.get("feedback_type") or {}).get("labels") or []
        fb_type_label = " / ".join(labels) if labels else ("点踩" if item.get("type") == "dislike" else "点赞")
        # 反馈对象：取对应的问答
        qa_content = ""
        conv_id = item.get("conversation_id")
        msg_idx = item.get("message_index")
        if conv_id and msg_idx is not None:
            try:
                history_record, _ = load_history_record(conv_id)
                target = next((m for m in history_record.get("messages", []) if m.get("message_index") == msg_idx), None)
                if target:
                    qa_content = format_qa_content([target])
            except Exception:
                pass
        base_row = [
            idx, user.get("name", ""), user.get("phone", ""), user.get("enterprise", ""),
            fb_type_label, item.get("createdAt", ""),
        ]
        if is_filtered_view:
            base_row += [item.get("processor") or "", qa_content]
        else:
            base_row += [item.get("process_status") or "未处理", item.get("process_result") or "", qa_content]
        table_rows.append(base_row)

    content = build_xlsx_bytes(table_headers, table_rows)
    if process_result_filter == "录入待优化回答":
        fname_prefix = "待优化回答"
    elif process_result_filter == "录入良好回答":
        fname_prefix = "回答良好"
    else:
        fname_prefix = "反馈列表"
    filename = f"{fname_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    from urllib.parse import quote
    resp_headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(io.BytesIO(content), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=resp_headers)


@app.get(
    "/api/feedback/{feedback_id}",
    tags=["AI对话/反馈"],
    summary="通过反馈 ID 获取详情",
    description="根据反馈 ID 返回对应的反馈详情，包含反馈类型、原因、补充描述、处理结果、处理人和原始提问附件信息。",
    openapi_extra={
        "responses": {
            "200": {
                "description": "反馈详情。",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "integer", "example": 0},
                                "msg": {"type": "string", "example": "获取反馈详情成功"},
                                "data": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "conversation_id": {"type": "string"},
                                        "message_index": {"type": "integer"},
                                        "type": {"type": "string"},
                                        "feedback_type": {
                                            "type": "object",
                                            "properties": {
                                                "primary": {"type": "string", "description": "点赞/点踩"},
                                                "labels": {"type": "array", "items": {"type": "string"}},
                                            },
                                        },
                                        "question_issues": {"type": "object", "additionalProperties": {"type": "string"}, "description": "【针对问题】分组勾选的原因 `{key: 中文}` 字典", "example": {"notUnderstand": "不理解问题"}},
                                        "answer_effects": {"type": "object", "additionalProperties": {"type": "string"}, "description": "【针对回答效果】分组勾选的原因 `{key: 中文}` 字典", "example": {"wrongAnswer": "回答错误"}},
                                        "report_reasons": {"type": "object", "additionalProperties": {"type": "string"}, "description": "【举报】分组勾选的原因 `{key: 中文}` 字典", "example": {}},
                                        "comment": {"type": "string"},
                                        "pictures": {"type": "array", "items": {"type": "string"}, "description": "图片文件名数组"},
                                        "picture_urls": {"type": "array", "items": {"type": "string"}, "description": "图片直接访问 URL 数组，与 pictures 顺序对应"},
                                        "uploaded_files": {"type": "array", "items": {"type": "object"}, "description": "原始提问附件列表"},
                                        "user": {"type": "object", "description": "反馈人信息：name/enterprise/phone"},
                                        "createdAt": {"type": "string", "description": "反馈提交时间（展示串）"},
                                        "updatedAt": {"type": "string", "description": "反馈最后更新时间（展示串）"},
                                        "question": {"type": "string"},
                                        "answer": {"type": "string"},
                                        "active": {"type": "boolean", "description": "反馈是否有效（false 表示已取消）"},
                                        "process_status": {"type": "string", "example": "未处理"},
                                        "process_result": {"type": "string", "example": "录入待优化回答"},
                                        "processor": {"type": "string", "description": "处理人（暂无认证体系，当前恒为空字符串）"},
                                    },
                                },
                            },
                        }
                    }
                },
            }
        }
    },
)
async def get_feedback_detail_by_id(feedback_id: str):
    info = _load_feedback_info(feedback_id)
    if not info:
        return error_response("获取反馈详情失败", {"id": feedback_id}, 404)
    # 详情比列表多返回 question/answer/pictures/comment
    detail = build_feedback_summary(info)
    detail["question"] = info.get("question", "")
    detail["answer"] = info.get("answer", "")
    detail["comment"] = info.get("comment", "")
    detail["pictures"] = info.get("pictures", [])
    detail["picture_urls"] = [
        f"/api/feedback/{feedback_id}/pictures/{p.get('filename', '')}"
        for p in info.get("pictures_list", [])
        if isinstance(p, dict) and p.get("filename")
    ]
    # 原始提问附件
    uploaded_files = []
    try:
        conv_id = str(info.get("conversation_id") or "")
        msg_idx = info.get("message_index")
        if conv_id and msg_idx is not None:
            history_record, _ = load_history_record(conv_id)
            target = next((m for m in history_record.get("messages", []) if m.get("message_index") == msg_idx), None)
            if target:
                uploaded_files = target.get("uploaded_files", []) or []
    except Exception:
        pass
    detail["uploaded_files"] = uploaded_files
    return success_response("获取反馈详情成功", detail)


@app.get("/api/feedback/{feedback_id}/pictures/{filename}", tags=["AI对话/反馈"], summary="预览反馈截图", description="通过后端代理返回反馈截图，前端直接用 img src 显示。")
async def preview_feedback_picture(feedback_id: str, filename: str):
    info = _load_feedback_info(feedback_id)
    if not info:
        return error_response("获取图片失败", {"id": feedback_id}, 404)
    pictures_list = info.get("pictures_list") or []
    target = next((p for p in pictures_list if p.get("filename") == filename), None)
    if not target:
        return error_response("获取图片失败", {"reason": f"图片 {filename} 不存在"}, 404)
    object_name = target.get("object_name", "")
    if not object_name:
        return error_response("获取图片失败", {"reason": "图片路径为空"}, 404)
    content = storage_service.read_file_bytes(object_name)
    if content is None:
        return error_response("获取图片失败", {"reason": "文件不存在"}, 404)
    import mimetypes
    content_type = mimetypes.guess_type(filename)[0] or "image/png"
    return StreamingResponse(io.BytesIO(content), media_type=content_type)


@app.post(
    "/api/feedback/process",
    tags=["AI对话/反馈"],
    summary="处理反馈",
    description="将反馈标记为已处理，并可选择收录到优秀问答或负向问答库。",
    openapi_extra={
        "requestBody": {
            "description": "处理反馈请求体。",
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["id", "process_result"],
                        "properties": {
                            "id": {"type": "string", "description": "反馈 ID。"},
                            "process_result": {"type": "string", "description": "处理结果文案，例如 `录入待优化回答` / `录入良好回答`。"},
                        },
                        "example": {"id": "fb_1775641095726-184c395e_0", "process_result": "录入良好回答"},
                    }
                }
            },
        }
    },
)
async def process_feedback(
    data: dict = Body(..., example={"id": "fb_xxx", "process_result": "录入待优化回答"}),
):
    return error_response("该接口仅限管理端访问", {"reason": "请使用 /api/admin/ 路由"}, 401)
    feedback_id = str(data.get("id") or "").strip()
    if not feedback_id:
        return error_response("处理反馈失败", {"reason": "id 不能为空"}, 400)
    process_result = str(data.get("process_result") or "").strip()
    if not process_result:
        return error_response("处理反馈失败", {"reason": "process_result 不能为空"}, 400)

    info = _load_feedback_info(feedback_id)
    if not info:
        return error_response("处理反馈失败", {"id": feedback_id}, 404)

    # 从 token 获取处理人姓名
    admin = get_logged_in_user()
    processor_name = admin.get("name") or ""

    info["process_status"] = "已处理"
    info["process_result"] = process_result
    info["processor"] = processor_name
    info["processed_at"] = now_ms()
    info["processedAt"] = now_display()
    _save_feedback_info(feedback_id, info)
    return success_response("处理反馈成功", build_feedback_summary(info))


@app.post("/api/feedback/batch_delete", tags=["AI对话/反馈"], summary="批量删除反馈", description="根据反馈 ID 列表批量删除反馈目录。")
async def batch_delete_feedback(data: dict = Body(..., example={"ids": ["fb_xxx"]})):
    return error_response("该接口仅限管理端访问", {"reason": "请使用 /api/admin/ 路由"}, 401)
    try:
        ids = ensure_id_list(data, "ids")
    except ValueError as exc:
        return error_response("批量删除反馈失败", {"reason": str(exc)}, 400)
    if not ids:
        return error_response("批量删除反馈失败", {"reason": "ids 不能为空"}, 400)
    deleted = []
    for feedback_id in ids:
        if _delete_feedback_all(feedback_id):
            deleted.append(feedback_id)
    return success_response("批量删除反馈成功", {"deleted_ids": deleted})


KB_TYPE_MAP = {"base": "基础知识库", "user": "知识库"}


def resolve_kb_category(kb_type: Optional[str]) -> Optional[str]:
    if not kb_type:
        return None
    return KB_TYPE_MAP.get(kb_type.strip().lower())


@app.get(
    "/api/department_users",
    tags=["AI对话/知识库"],
    summary="获取部门人员列表",
    description=(
        "根据当前登录用户的租户 ID，从数据库查询同租户在职员工并按部门分组。"
        "需要在 header 传 accessToken。未传 token 或 token 无效时返回空列表。"
    ),
)
async def get_department_users():
    auth_err = require_role("user")
    if auth_err:
        return auth_err
    from services.user_auth import get_current_user, get_department_users as query_dept_users
    user = get_current_user()
    if not user.get("tenant_id"):
        return success_response("获取部门人员成功", [])
    try:
        data = query_dept_users(user["tenant_id"])
    except Exception as exc:
        return error_response("获取部门人员失败", {"reason": str(exc)}, 500)
    return success_response("获取部门人员成功", data)


@app.post("/api/kb/toggle_enabled", tags=["AI对话/知识库"], summary="切换知识库启用状态", description="轻量切换，同步更新向量库的 enabled 字段，不重建向量。")
async def toggle_kb_enabled(data: dict = Body(..., example={"id": "kb_xxx", "enabled": True})):
    auth_err = require_role("user")
    if auth_err:
        return auth_err
    kb_id = str(data.get("id") or "").strip()
    if not kb_id:
        return error_response("切换状态失败", {"reason": "id 不能为空"}, 400)
    kb_err = _require_kb_access(kb_id)
    if kb_err:
        return kb_err
    enabled = str(data.get("enabled", "true")).lower() in {"1", "true", "yes", "on"}
    result = kb_service.toggle_enabled(kb_id, enabled)
    if not result:
        return error_response("切换状态失败", {"id": kb_id}, 404)
    return success_response("切换状态成功", result)


@app.get("/api/kb/list", tags=["AI对话/知识库"], summary="获取知识库列表", description="返回当前所有知识库的基础信息列表，支持分页和类型过滤。")
async def get_kb_list(
    page: int = Query(1, description="页码，从 1 开始。"),
    size: int = Query(10, description="每页数量，默认 10。"),
    type: Optional[str] = Query(None, description="知识库类型: base=基础知识库, user=用户知识库，不传则返回全部。"),
):
    auth_err = require_role("user")
    if auth_err:
        return auth_err
    page, size = normalize_page_size(page, size)
    category = resolve_kb_category(type)
    # 企业端按当前用户 tenant_id 过滤：基础知识库全部返回，普通 KB 仅同租户
    user = get_logged_in_user()
    my_tenant = user.get("tenant_id")
    items = kb_service.load_all(category=category, tenant_id=my_tenant)

    # 普通用户对"使用人不含自己"的 KB 无编辑权限
    from services.user_auth import current_role, ROLE_USER
    role = current_role()
    my_staff_id = user.get("staff_id") if role == ROLE_USER else None
    for kb in items:
        if role == ROLE_USER:
            kb["can_edit"] = _kb_has_user(kb, my_staff_id)
        else:
            kb["can_edit"] = True

    return success_response("获取知识库列表成功", paginate_payload(items, page, size))


@app.get("/api/kb/{id}", tags=["AI对话/知识库"], summary="获取知识库详情", description="根据知识库 ID 返回知识库详情。")
async def get_kb_detail(id: str):
    auth_err = require_role("user")
    if auth_err:
        return auth_err
    detail = kb_service.get_kb_detail(id)
    if not detail:
        return error_response("获取知识库详情失败", {"id": id}, 404)
    # 跨企业隔离：非基础知识库，KB 的 tenant_id 必须匹配当前用户
    if detail.get("category") != "基础知识库":
        user = get_logged_in_user()
        my_tenant = user.get("tenant_id")
        if my_tenant is None or str(detail.get("tenant_id") or "") != str(my_tenant):
            return error_response("获取知识库详情失败", {"id": id}, 404)
    # 标注 can_edit，方便前端统一用
    from services.user_auth import current_role, ROLE_USER
    if current_role() == ROLE_USER:
        my_staff_id = get_logged_in_user().get("staff_id")
        detail["can_edit"] = _kb_has_user(detail, my_staff_id)
    else:
        detail["can_edit"] = True
    return success_response("获取知识库详情成功", detail)


@app.post(
    "/api/kb/create",
    tags=["AI对话/知识库"],
    summary="创建知识库",
    description=(
        "创建一个知识库。通过 `type` 区分两类：`user`（普通知识库，按使用人授权可见）、"
        "`base`（基础知识库，对所有用户可见）；不传 `type` 时按 `user` 处理。"
    ),
    openapi_extra={
        "requestBody": {
            "description": "JSON 请求体。",
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string", "description": "知识库名称"},
                            "type": {
                                "type": "string",
                                "enum": ["user", "base"],
                                "description": "知识库类型：`user` 普通（默认）/ `base` 基础（对所有人可见）",
                                "default": "user",
                            },
                        },
                    },
                    "examples": {
                        "create_user_kb": {
                            "summary": "创建普通知识库",
                            "value": {"name": "新知识库", "type": "user"},
                        },
                        "create_base_kb": {
                            "summary": "创建基础知识库",
                            "value": {"name": "全员知识库", "type": "base"},
                        },
                    },
                }
            },
        }
    },
)
async def create_kb(request: Request):
    auth_err = require_role("user")
    if auth_err:
        return auth_err
    try:
        payload = await _get_request_payload(request)
    except ValueError as exc:
        return error_response("创建知识库失败", {"reason": str(exc)}, 400)
    name = str(payload.get("name") or "").strip()
    model = str(payload.get("model") or "openai").strip() or "openai"
    kb_type = str(payload.get("type") or "user").strip().lower()
    if not name:
        return error_response("创建知识库失败", {"reason": "name 不能为空"}, 400)
    category = resolve_kb_category(kb_type) or "知识库"
    user = get_logged_in_user()
    created = kb_service.create_kb(name=name, model=model, user=user, category=category)
    return success_response("创建知识库成功", created)


@app.post(
    "/api/kb/update",
    tags=["AI对话/知识库"],
    summary="更新知识库",
    description="更新知识库名称、备注、启用状态、授权用户，并支持在一次请求中预览或确认文件上传和删除。",
    openapi_extra={
        "requestBody": {
            "description": "application/json 知识库更新请求。",
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {
                            "id": {"type": "string", "description": "知识库 ID"},
                            "name": {"type": "string", "description": "知识库名称"},
                            "remark": {"type": "string", "description": "备注"},
                            "enabled": {"type": "boolean", "description": "是否启用"},
                            "users": {
                                "type": "array",
                                "description": "使用人列表，每个元素必须包含 staffId 和 name。staffId 来自 /api/department_users 返回的 members[].staffId。",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "staffId": {"type": "integer", "description": "员工唯一 ID（来自 /api/department_users）"},
                                        "name": {"type": "string", "description": "员工姓名"},
                                    },
                                    "required": ["staffId", "name"],
                                },
                            },
                            "delete_files": {
                                "type": "array",
                                "description": "待删除文件的 `file_id` 列表（来自 `/api/kb/{id}/files` 响应里的 `file_id` 字段，形如 `kb_123:old.txt`）。",
                                "items": {"type": "string"},
                            },
                            "confirm": {"type": "boolean", "description": "是否确认提交，false 为预览"},
                            "add_file_ids": {"type": "array", "items": {"type": "string"}, "description": "通过 /api/upload 上传后获得的文件 ID 列表"},
                        },
                    },
                    "examples": {
                        "update_kb_json": {
                            "summary": "无文件更新知识库",
                            "value": {
                                "id": "kb_1",
                                "name": "更新后的知识库",
                                "remark": "补充备注",
                                "enabled": True,
                                "users": [{"name": "张三", "staffId": 527}, {"name": "李四", "staffId": 528}],
                                "delete_files": ["kb_1:old.txt"],
                                "confirm": True,
                            },
                        }
                    },
                },
            },
        }
    },
)
async def update_kb(
    request: Request,
):
    auth_err = require_role("user")
    if auth_err:
        return auth_err
    try:
        payload = await _get_request_payload(request)
    except ValueError as exc:
        return error_response("更新知识库失败", {"reason": str(exc)}, 400)

    id = str(payload.get("id") or "").strip()
    if id:
        kb_err = _require_kb_access(id)
        if kb_err:
            return kb_err
    name = payload.get("name")
    remark = payload.get("remark")
    enabled = payload.get("enabled")
    users = payload.get("users")
    delete_files = payload.get("delete_files")
    confirm_raw = payload.get("confirm")
    if confirm_raw is None or str(confirm_raw).strip() == "":
        confirm = True
    else:
        confirm = str(confirm_raw).lower() in {"1", "true", "yes", "on"}
    if not id:
        return error_response("更新知识库失败", {"reason": "id 不能为空"}, 400)

    update_data = {}
    if name is not None and str(name).strip() != "":
        update_data["name"] = name
    if remark is not None and str(remark).strip() != "":
        update_data["remark"] = remark
    if enabled is not None and str(enabled).strip() != "":
        update_data["enabled"] = str(enabled).lower() in {"1", "true", "yes", "on"}
    if users is not None and users != "" and users != []:
        if isinstance(users, list):
            parsed_users = users
        else:
            try:
                parsed_users = json.loads(users)
            except Exception:
                return error_response("更新知识库失败", {"reason": "users 字段不是合法 JSON"}, 400)
        if not isinstance(parsed_users, list):
            return error_response("更新知识库失败", {"reason": "users 必须是数组"}, 400)
        cleaned_users = [u for u in parsed_users if u not in (None, "", {})]
        if cleaned_users:
            # 普通用户不能把自己从使用人中移除
            from services.user_auth import current_role, ROLE_USER
            if current_role() == ROLE_USER:
                my_staff_id = str(get_logged_in_user().get("staff_id") or "")
                if my_staff_id and not any(
                    str(u.get("staffId") or u.get("staff_id") or "") == my_staff_id
                    if isinstance(u, dict) else False
                    for u in cleaned_users
                ):
                    return error_response("更新知识库失败", {"reason": "不能将自己从使用人中移除"}, 400)
            update_data["users"] = cleaned_users
    delete_filenames = []
    if delete_files:
        if isinstance(delete_files, list):
            loaded = delete_files
        else:
            try:
                loaded = json.loads(delete_files)
            except Exception:
                return error_response("更新知识库失败", {"reason": "delete_files 字段不是合法 JSON"}, 400)
        if not isinstance(loaded, list):
            return error_response("更新知识库失败", {"reason": "delete_files 必须是数组"}, 400)
        for item in loaded:
            raw = str(item or "").strip()
            if not raw:
                continue
            if ":" in raw:
                _, _, filename_part = raw.partition(":")
                filename_part = filename_part.strip()
                if filename_part:
                    delete_filenames.append(filename_part)
                    continue
            delete_filenames.append(raw)
    add_file_ids = payload.get("add_file_ids") or []
    staging_files = resolve_staging_files(add_file_ids)
    try:
        updated = kb_service.update_kb(id, update_data, new_file_infos=staging_files, delete_filenames=delete_filenames, confirm=confirm)
    except Exception as exc:
        return error_response("更新知识库失败", {"reason": str(exc)}, 500)
    if not updated:
        return error_response("更新知识库失败", {"id": id}, 404)
    msg = "预览知识库更新成功" if updated.get("preview") else "更新知识库成功"
    return success_response(msg, updated)


@app.delete("/api/kb/{id}", tags=["AI对话/知识库"], summary="删除知识库", description="删除指定知识库及其元数据。")
async def delete_kb(id: str):
    auth_err = require_role("user")
    if auth_err:
        return auth_err
    kb_err = _require_kb_access(id)
    if kb_err:
        return kb_err
    try:
        deleted = kb_service.delete_kb(id)
    except Exception as exc:
        return error_response("删除知识库失败", {"reason": str(exc)}, 500)
    if not deleted:
        return error_response("删除知识库失败", {"id": id}, 404)
    return success_response("删除知识库成功", deleted)


@app.get("/api/kb/{id}/files", tags=["AI对话/知识库"], summary="获取知识库文件列表", description="返回指定知识库关联的文件列表和访问地址。")
async def list_kb_files(id: str):
    auth_err = require_role("user")
    if auth_err:
        return auth_err
    detail = kb_service.get_kb_detail(id)
    if not detail:
        return error_response("获取知识库文件失败", {"id": id}, 404)
    # 跨企业隔离
    if detail.get("category") != "基础知识库":
        user = get_logged_in_user()
        my_tenant = user.get("tenant_id")
        if my_tenant is None or str(detail.get("tenant_id") or "") != str(my_tenant):
            return error_response("获取知识库文件失败", {"id": id}, 404)
    return success_response("获取知识库文件成功", {
        "id": id,
        "url": detail.get("url", ""),
        "files": detail.get("files", []),
    })


def _resolve_kb_file_object(kb_id: str, file_id: str) -> Optional[dict]:
    """根据 kb_id 和 file_id (形如 `{kb_id}:{filename}`) 反查 MinIO object_name。"""
    kb = kb_service.get_kb(kb_id)
    if not kb:
        return None
    raw = str(file_id or "").strip()
    if not raw:
        return None
    # 兼容：完整 file_id（含 kb_id 前缀）或仅 filename 都接受
    if ":" in raw:
        _, _, filename = raw.partition(":")
    else:
        filename = raw
    filename = Path(filename.strip()).name
    if not filename:
        return None
    for item in kb_service._current_file_items(kb):
        if item["name"] == filename:
            return {"object_name": item["object_name"], "filename": filename}
    return None


@app.get(
    "/api/kb/{id}/files/{file_id}/download",
    tags=["AI对话/知识库"],
    summary="下载知识库文件",
    description="下载指定知识库中的单个文件。file_id 格式：`{kb_id}:{filename}`（来自 /api/kb/{id}/files 返回）。",
)
async def download_kb_file(id: str, file_id: str):
    auth_err = require_role("user")
    if auth_err:
        return auth_err
    kb_err = _require_kb_access(id)
    if kb_err:
        return kb_err
    target = _resolve_kb_file_object(id, file_id)
    if not target:
        return error_response("下载文件失败", {"id": id, "file_id": file_id}, 404)
    content = storage_service.read_file_bytes(target["object_name"])
    if not content:
        return error_response("下载文件失败", {"reason": "从 MinIO 读取文件失败"}, 500)
    from urllib.parse import quote
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(target['filename'])}"}
    return StreamingResponse(io.BytesIO(content), media_type="application/octet-stream", headers=headers)


@app.get(
    "/api/db/options",
    tags=["AI对话/数据库"],
    summary="获取数据库选项",
    description=(
        "返回所有已配置的数据库连接信息（不含密码）以及当前活跃 ID。"
        "前端用 `databases[].label` 在下拉中显示，用户选择后调用 /api/db/select 切换。"
    ),
    openapi_extra={
        "responses": {
            "200": {
                "description": "数据库下拉选项。",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "integer", "example": 0},
                                "msg": {"type": "string", "example": "获取数据库选项成功"},
                                "data": {
                                    "type": "object",
                                    "properties": {
                                        "databases": {
                                            "type": "array",
                                            "description": "全部已配置的数据库连接（密码不返回）",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "id": {"type": "string", "example": "db_default"},
                                                    "name": {"type": "string", "description": "MySQL schema 名", "example": "r_d_test"},
                                                    "host": {"type": "string", "example": "183.69.138.62"},
                                                    "port": {"type": "integer", "example": 33666},
                                                    "user": {"type": "string", "example": "hagongda"},
                                                    "label": {"type": "string", "description": "下拉显示用，后端拼好（name@host:port）", "example": "r_d_test@183.69.138.62:33666"},
                                                },
                                            },
                                        },
                                        "active_id": {"type": "string", "example": "db_default", "description": "当前生效的数据库 ID"},
                                    },
                                },
                            },
                        }
                    }
                },
            }
        }
    },
)
async def get_db_options():
    return error_response("该接口仅限管理端访问", {"reason": "请使用 /api/admin/ 路由"}, 401)
    return success_response("获取数据库选项成功", db_registry.list_options())


@app.post(
    "/api/db/select",
    tags=["AI对话/数据库"],
    summary="切换当前数据库",
    description=(
        "把指定 ID 设为当前活跃数据库；服务端会立刻刷新 sql_tool 的连接配置，"
        "之后所有 /api/chat 中需要查数据库的请求都会用这个新连接。"
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {
                            "id": {"type": "string", "description": "数据库 ID（对应 /api/db/options 的 databases[].id）"},
                        },
                    },
                    "examples": {
                        "default": {"summary": "切到默认库", "value": {"id": "db_default"}},
                    },
                }
            },
        },
        "responses": {
            "200": {
                "description": "切换成功。",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "integer", "example": 0},
                                "msg": {"type": "string", "example": "切换数据库成功"},
                                "data": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "name": {"type": "string"},
                                        "host": {"type": "string"},
                                        "port": {"type": "integer"},
                                        "user": {"type": "string"},
                                        "label": {"type": "string"},
                                    },
                                },
                            },
                        }
                    }
                },
            }
        },
    },
)
async def select_db(data: dict = Body(..., example={"id": "db_default"})):
    return error_response("该接口仅限管理端访问", {"reason": "请使用 /api/admin/ 路由"}, 401)
    try:
        result = db_registry.select(str(data.get("id") or ""))
    except ValueError as exc:
        return error_response("切换数据库失败", {"reason": str(exc)}, 400)
    return success_response("切换数据库成功", result)


@app.post(
    "/api/db/add",
    tags=["AI对话/数据库"],
    summary="新增数据库连接",
    description=(
        "新增一条 MySQL 连接配置：后端会立刻试连一次（5 秒超时），"
        "**只有连得通才会写入**并出现在 /api/db/options 的下拉里；连不通直接 400 + 具体原因。"
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["name", "host", "port", "user", "password"],
                        "properties": {
                            "name": {"type": "string", "description": "MySQL schema 名（即 `pymysql.connect(db=...)`）", "example": "r_d_test"},
                            "host": {"type": "string", "example": "183.69.138.62"},
                            "port": {"type": "integer", "example": 33666},
                            "user": {"type": "string", "example": "hagongda"},
                            "password": {"type": "string", "example": "********"},
                        },
                    },
                    "examples": {
                        "default": {
                            "summary": "新增一条",
                            "value": {
                                "name": "r_d_test",
                                "host": "183.69.138.62",
                                "port": 33666,
                                "user": "hagongda",
                                "password": "your_password",
                            },
                        },
                    },
                }
            },
        },
        "responses": {
            "200": {
                "description": "新增成功，返回不含密码的完整条目。",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "code": {"type": "integer", "example": 0},
                                "msg": {"type": "string", "example": "新增数据库成功"},
                                "data": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "name": {"type": "string"},
                                        "host": {"type": "string"},
                                        "port": {"type": "integer"},
                                        "user": {"type": "string"},
                                        "label": {"type": "string"},
                                    },
                                },
                            },
                        }
                    }
                },
            },
            "400": {
                "description": "校验失败 / 重复 / 连接失败（具体原因在 data.reason）。",
            },
        },
    },
)
async def add_db(data: dict = Body(...)):
    return error_response("该接口仅限管理端访问", {"reason": "请使用 /api/admin/ 路由"}, 401)
    try:
        entry = db_registry.add(data or {})
    except ValueError as exc:
        return error_response("新增数据库失败", {"reason": str(exc)}, 400)
    return success_response("新增数据库成功", entry)


@app.get("/api/config/enums", summary="获取系统枚举配置", tags=["AI对话/对话"], description="返回前端所需的枚举配置，包括反馈选项、上传文件类型、数据库选项等。")
async def get_system_enums():
    """返回前端需要的所有枚举值和配置项，前端不应硬编码这些值。"""
    return {
        "code": 0,
        "msg": "ok",
        "data": {
            "allowed_upload_extensions": ["pdf", "doc", "docx", "ppt", "pptx", "txt", "md", "xls", "xlsx", "csv"],
        },
    }


# ═══════════════════════════════════════════════════════════════
# 管理端路由 /api/admin/
# 甲方内部管理系统调用，不经过 token 认证。
# Handler 直接复用企业端的业务逻辑函数，只是跳过权限检查。
# ═══════════════════════════════════════════════════════════════
from fastapi import APIRouter

admin_router = APIRouter(prefix="/api/admin")


# ── 对话日志 ──
@admin_router.get("/history/list", tags=["管理端/对话日志"], summary="[管理端] 查询历史记录列表")
async def admin_list_histories(
    search: str = Query(""),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    page: int = Query(1),
    size: int = Query(10),
):
    page, size = normalize_page_size(page, size)
    start_ms = parse_optional_millis(start_time, "start_time") if start_time else None
    end_ms = parse_optional_millis(end_time, "end_time") if end_time else None
    records = filter_history_records(search=search, start_ms=start_ms, end_ms=end_ms)
    results = [build_history_list_item(record) for record in records]
    return success_response("获取历史记录成功", paginate_payload(results, page, size))


@admin_router.get("/history/{conversation_id}", tags=["管理端/对话日志"], summary="[管理端] 获取历史记录详情")
async def admin_get_history_detail(conversation_id: str):
    history_record, _ = load_history_record(conversation_id)
    return success_response("获取历史详情成功", history_record)


@admin_router.delete("/history/{conversation_id}", tags=["管理端/对话日志"], summary="[管理端] 删除单条历史记录")
async def admin_delete_history(conversation_id: str):
    return await delete_history(conversation_id)


@admin_router.post("/history/batch_delete", tags=["管理端/对话日志"], summary="[管理端] 批量删除历史记录")
async def admin_batch_delete_history(data: dict = Body(...)):
    ids = ensure_id_list(data, "ids")
    if not ids:
        return error_response("批量删除失败", {"reason": "ids 不能为空"}, 400)
    deleted = []
    for cid in ids:
        if delete_history_record(cid):
            deleted.append(cid)
    return success_response("批量删除成功", {"deleted_ids": deleted})


@admin_router.post("/history/export", tags=["管理端/对话日志"], summary="[管理端] 导出历史详情")
async def admin_export_history(data: Optional[dict] = Body(None)):
    payload = data or {}
    try:
        ids = ensure_id_list(payload, "ids")
    except ValueError as exc:
        return error_response("导出失败", {"reason": str(exc)}, 400)
    if ids:
        records = collect_history_records(ids)
    else:
        search = str(payload.get("search") or "")
        start_time = payload.get("start_time")
        end_time = payload.get("end_time")
        start_ms = parse_optional_millis(start_time, "start_time") if start_time else None
        end_ms = parse_optional_millis(end_time, "end_time") if end_time else None
        filtered = filter_history_records(search=search, start_ms=start_ms, end_ms=end_ms)
        record_ids = [r.get("conversation_id") for r in filtered if r.get("conversation_id")]
        records = collect_history_records(record_ids or None)
    if not records:
        return error_response("导出失败", {"reason": "没有可导出的历史记录"}, 404)
    table_headers = ["序号", "IP地址", "用户ID", "RecordID", "问答"]
    rows = []
    for idx, record in enumerate(records, start=1):
        user = record.get("user") or {}
        rows.append([idx, user.get("ip_address", ""), user.get("user_id", ""), user.get("record_id", "") or record.get("conversation_id", ""), format_qa_content(record.get("messages", []))])
    content = build_xlsx_bytes(table_headers, rows)
    filename = f"对话日志_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    from urllib.parse import quote
    resp_headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(io.BytesIO(content), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=resp_headers)


# ── 反馈管理 ──
@admin_router.get("/feedback/list", tags=["管理端/反馈"], summary="[管理端] 查询反馈列表")
async def admin_list_feedbacks(
    search: str = Query(""),
    type: Optional[str] = Query(None),
    feedback_type: str = Query("全部"),
    process_status: str = Query(""),
    process_result: str = Query(""),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    processed_start_time: Optional[str] = Query(None),
    processed_end_time: Optional[str] = Query(None),
    page: int = Query(1),
    size: int = Query(10),
):
    page, size = normalize_page_size(page, size)
    start_ms = parse_optional_millis(start_time, "start_time") if start_time else None
    end_ms = parse_optional_millis(end_time, "end_time") if end_time else None
    results = collect_feedback_summaries(
        search=search, type=type, feedback_type=feedback_type,
        process_status=process_status, process_result=process_result,
        start_ms=start_ms, end_ms=end_ms,
    )
    return success_response("获取反馈列表成功", paginate_payload(results, page, size))


@admin_router.post("/feedback/export", tags=["管理端/反馈"], summary="[管理端] 导出反馈列表")
async def admin_export_feedbacks(data: Optional[dict] = Body(None)):
    payload = data or {}
    ids = payload.get("ids")
    search = str(payload.get("search") or "")
    fb_type = payload.get("type")
    feedback_type = str(payload.get("feedback_type") or "全部")
    process_status = str(payload.get("process_status") or "")
    process_result_filter = str(payload.get("process_result") or "")
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    start_ms = parse_optional_millis(start_time, "start_time") if start_time else None
    end_ms = parse_optional_millis(end_time, "end_time") if end_time else None
    rows = collect_feedback_summaries(
        search=search, type=fb_type, feedback_type=feedback_type,
        process_status=process_status, process_result=process_result_filter,
        start_ms=start_ms, end_ms=end_ms,
    )
    if ids:
        id_set = set(str(i) for i in ids)
        rows = [r for r in rows if str(r.get("id", "")) in id_set]
    if not rows:
        return error_response("导出失败", {"reason": "没有可导出的反馈记录"}, 404)
    is_filtered_view = bool(process_result_filter)
    if is_filtered_view:
        table_headers = ["序号", "反馈人", "联系方式", "所属企业", "反馈类型", "提交时间", "处理人", "反馈对象"]
    else:
        table_headers = ["序号", "反馈人", "联系方式", "所属企业", "反馈类型", "提交时间", "处理状态", "处理结果", "反馈对象"]
    table_rows = []
    for idx, item in enumerate(rows, start=1):
        user = item.get("user") or {}
        labels = (item.get("feedback_type") or {}).get("labels") or []
        fb_type_label = " / ".join(labels) if labels else ("点踩" if item.get("type") == "dislike" else "点赞")
        qa_content = ""
        conv_id = item.get("conversation_id")
        msg_idx = item.get("message_index")
        if conv_id and msg_idx is not None:
            try:
                history_record, _ = load_history_record(conv_id)
                target = next((m for m in history_record.get("messages", []) if m.get("message_index") == msg_idx), None)
                if target:
                    qa_content = format_qa_content([target])
            except Exception:
                pass
        if is_filtered_view:
            table_rows.append([idx, user.get("name", ""), user.get("phone", ""), user.get("enterprise", ""), fb_type_label, item.get("createdAt", ""), item.get("processor", ""), qa_content])
        else:
            table_rows.append([idx, user.get("name", ""), user.get("phone", ""), user.get("enterprise", ""), fb_type_label, item.get("createdAt", ""), item.get("process_status", "未处理"), item.get("process_result", ""), qa_content])
    content = build_xlsx_bytes(table_headers, table_rows)
    fname_prefix = "待优化回答" if process_result_filter == "录入待优化回答" else "回答良好" if process_result_filter == "录入良好回答" else "反馈列表"
    filename = f"{fname_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    from urllib.parse import quote
    resp_headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(io.BytesIO(content), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=resp_headers)


@admin_router.get("/feedback/reason_options", tags=["管理端/反馈"], summary="[管理端] 获取反馈原因选项")
async def admin_get_feedback_reason_options():
    return await get_feedback_reason_options()


@admin_router.get("/feedback/{feedback_id}", tags=["管理端/反馈"], summary="[管理端] 获取反馈详情")
async def admin_get_feedback_detail(feedback_id: str):
    info = _load_feedback_info(feedback_id)
    if not info:
        return error_response("获取反馈详情失败", {"id": feedback_id}, 404)
    detail = build_feedback_summary(info)
    detail["question"] = info.get("question", "")
    detail["answer"] = info.get("answer", "")
    detail["comment"] = info.get("comment", "")
    detail["pictures"] = info.get("pictures", [])
    # 管理端用代理预览 URL（MinIO 内网地址外部访问不了）
    detail["picture_urls"] = [
        f"/api/admin/feedback/{feedback_id}/pictures/{p.get('filename', '')}"
        for p in info.get("pictures_list", [])
        if isinstance(p, dict) and p.get("filename")
    ]
    uploaded_files = []
    try:
        conv_id = str(info.get("conversation_id") or "")
        msg_idx = info.get("message_index")
        if conv_id and msg_idx is not None:
            history_record, _ = load_history_record(conv_id)
            target = next((m for m in history_record.get("messages", []) if m.get("message_index") == msg_idx), None)
            if target:
                uploaded_files = target.get("uploaded_files", []) or []
    except Exception:
        pass
    detail["uploaded_files"] = uploaded_files
    return success_response("获取反馈详情成功", detail)


@admin_router.post("/feedback/process", tags=["管理端/反馈"], summary="[管理端] 处理反馈")
async def admin_process_feedback(data: dict = Body(...)):
    feedback_id = str(data.get("id") or "").strip()
    if not feedback_id:
        return error_response("处理反馈失败", {"reason": "id 不能为空"}, 400)
    process_result = str(data.get("process_result") or "").strip()
    if not process_result:
        return error_response("处理反馈失败", {"reason": "process_result 不能为空"}, 400)
    info = _load_feedback_info(feedback_id)
    if not info:
        return error_response("处理反馈失败", {"id": feedback_id}, 404)
    info["process_status"] = "已处理"
    info["process_result"] = process_result
    info["processor"] = data.get("processor") or ""
    info["processed_at"] = now_ms()
    info["processedAt"] = now_display()
    _save_feedback_info(feedback_id, info)
    return success_response("处理反馈成功", build_feedback_summary(info))


@admin_router.post("/feedback/batch_delete", tags=["管理端/反馈"], summary="[管理端] 批量删除反馈")
async def admin_batch_delete_feedback(data: dict = Body(...)):
    try:
        ids = ensure_id_list(data, "ids")
    except ValueError as exc:
        return error_response("批量删除失败", {"reason": str(exc)}, 400)
    if not ids:
        return error_response("批量删除失败", {"reason": "ids 不能为空"}, 400)
    deleted = []
    for fid in ids:
        info = _load_feedback_info(fid)
        if not info:
            continue
        # 删前先同步清理历史消息的 feedback 字段
        try:
            conv_id = info.get("conversation_id")
            msg_idx = info.get("message_index")
            fb_type = info.get("type")
            if conv_id and msg_idx is not None and fb_type in ("like", "dislike"):
                rec, path = load_history_record(conv_id)
                msgs = rec.get("messages", [])
                if 0 <= int(msg_idx) < len(msgs) and msgs[int(msg_idx)].get("feedback") == fb_type:
                    msgs[int(msg_idx)]["feedback"] = None
                    msgs[int(msg_idx)]["updated_at"] = now_ms()
                    msgs[int(msg_idx)]["updatedAt"] = now_display()
                    save_history_record(rec, path)
        except Exception:
            pass
        if _delete_feedback_all(fid):
            deleted.append(fid)
    return success_response("批量删除成功", {"deleted_ids": deleted})


# ── 数据库管理 ──
@admin_router.get("/db/options", tags=["管理端/数据库"], summary="[管理端] 获取数据库选项")
async def admin_get_db_options():
    return success_response("获取数据库选项成功", db_registry.list_options())


@admin_router.post("/db/select", tags=["管理端/数据库"], summary="[管理端] 切换当前数据库")
async def admin_select_db(data: dict = Body(...)):
    try:
        result = db_registry.select(str(data.get("id") or ""))
    except ValueError as exc:
        return error_response("切换数据库失败", {"reason": str(exc)}, 400)
    return success_response("切换数据库成功", result)


@admin_router.post("/db/add", tags=["管理端/数据库"], summary="[管理端] 新增数据库连接")
async def admin_add_db(data: dict = Body(...)):
    try:
        entry = db_registry.add(data or {})
    except ValueError as exc:
        return error_response("新增数据库失败", {"reason": str(exc)}, 400)
    return success_response("新增数据库成功", entry)


# ── 知识库管理 ──
@admin_router.get("/kb/list", tags=["管理端/知识库"], summary="[管理端] 获取知识库列表")
async def admin_get_kb_list(
    page: int = Query(1),
    size: int = Query(10),
    type: Optional[str] = Query(None),
):
    page, size = normalize_page_size(page, size)
    category = resolve_kb_category(type)
    items = kb_service.load_all(category=category)
    for kb in items:
        kb["can_edit"] = True
    return success_response("获取知识库列表成功", paginate_payload(items, page, size))


@admin_router.get("/kb/{id}", tags=["管理端/知识库"], summary="[管理端] 获取知识库详情")
async def admin_get_kb_detail(id: str):
    detail = kb_service.get_kb_detail(id)
    if not detail:
        return error_response("获取知识库详情失败", {"id": id}, 404)
    return success_response("获取知识库详情成功", detail)


@admin_router.post("/kb/create", tags=["管理端/知识库"], summary="[管理端] 创建知识库")
async def admin_create_kb(request: Request):
    try:
        payload = await _get_request_payload(request)
    except ValueError as exc:
        return error_response("创建知识库失败", {"reason": str(exc)}, 400)
    name = str(payload.get("name") or "").strip()
    model = str(payload.get("model") or "openai").strip() or "openai"
    kb_type = str(payload.get("type") or "user").strip().lower()
    if not name:
        return error_response("创建知识库失败", {"reason": "name 不能为空"}, 400)
    category = resolve_kb_category(kb_type) or "知识库"
    user = get_logged_in_user()
    created = kb_service.create_kb(name=name, model=model, user=user, category=category)
    return success_response("创建知识库成功", created)


@admin_router.post("/kb/update", tags=["管理端/知识库"], summary="[管理端] 更新知识库")
async def admin_update_kb(request: Request):
    try:
        payload = await _get_request_payload(request)
    except ValueError as exc:
        return error_response("更新知识库失败", {"reason": str(exc)}, 400)
    id = str(payload.get("id") or "").strip()
    if not id:
        return error_response("更新知识库失败", {"reason": "id 不能为空"}, 400)
    update_data = {}
    for key in ("name", "remark"):
        val = payload.get(key)
        if val is not None and str(val).strip():
            update_data[key] = val
    enabled = payload.get("enabled")
    if enabled is not None and str(enabled).strip():
        update_data["enabled"] = str(enabled).lower() in {"1", "true", "yes", "on"}
    users = payload.get("users")
    if users is not None and users != "" and users != []:
        if isinstance(users, list):
            parsed_users = users
        else:
            try:
                parsed_users = json.loads(users)
            except Exception:
                return error_response("更新知识库失败", {"reason": "users 不是合法 JSON"}, 400)
        cleaned = [u for u in parsed_users if u not in (None, "", {})]
        if cleaned:
            update_data["users"] = cleaned
    delete_files = payload.get("delete_files")
    delete_filenames = []
    if delete_files:
        loaded = delete_files if isinstance(delete_files, list) else json.loads(delete_files)
        for item in loaded:
            raw = str(item or "").strip()
            if not raw:
                continue
            if ":" in raw:
                _, _, fn = raw.partition(":")
                fn = fn.strip()
                if fn:
                    delete_filenames.append(fn)
                    continue
            delete_filenames.append(raw)
    add_file_ids = payload.get("add_file_ids") or []
    staging_files = resolve_staging_files(add_file_ids)
    confirm_raw = payload.get("confirm")
    confirm = True if confirm_raw is None or str(confirm_raw).strip() == "" else str(confirm_raw).lower() in {"1", "true", "yes", "on"}
    try:
        updated = kb_service.update_kb(id, update_data, new_file_infos=staging_files, delete_filenames=delete_filenames, confirm=confirm)
    except Exception as exc:
        return error_response("更新知识库失败", {"reason": str(exc)}, 500)
    if not updated:
        return error_response("更新知识库失败", {"id": id}, 404)
    return success_response("预览知识库更新成功" if updated.get("preview") else "更新知识库成功", updated)


@admin_router.delete("/kb/{id}", tags=["管理端/知识库"], summary="[管理端] 删除知识库")
async def admin_delete_kb(id: str):
    try:
        deleted = kb_service.delete_kb(id)
    except Exception as exc:
        return error_response("删除知识库失败", {"reason": str(exc)}, 500)
    if not deleted:
        return error_response("删除知识库失败", {"id": id}, 404)
    return success_response("删除知识库成功", deleted)


@admin_router.get("/kb/{id}/files", tags=["管理端/知识库"], summary="[管理端] 获取知识库文件列表")
async def admin_list_kb_files(id: str):
    detail = kb_service.get_kb_detail(id)
    if not detail:
        return error_response("获取知识库文件失败", {"id": id}, 404)
    return success_response("获取知识库文件成功", {"id": id, "files": detail.get("files", [])})


@admin_router.get("/kb/{id}/files/{file_id}/download", tags=["管理端/知识库"], summary="[管理端] 下载知识库文件")
async def admin_download_kb_file(id: str, file_id: str):
    target = _resolve_kb_file_object(id, file_id)
    if not target:
        return error_response("下载文件失败", {"id": id, "file_id": file_id}, 404)
    content = storage_service.read_file_bytes(target["object_name"])
    if not content:
        return error_response("下载文件失败", {"reason": "从 MinIO 读取文件失败"}, 500)
    from urllib.parse import quote
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(target['filename'])}"}
    return StreamingResponse(io.BytesIO(content), media_type="application/octet-stream", headers=headers)


@admin_router.post("/kb/toggle_enabled", tags=["管理端/知识库"], summary="[管理端] 切换知识库启用状态")
async def admin_toggle_kb_enabled(data: dict = Body(...)):
    kb_id = str(data.get("id") or "").strip()
    if not kb_id:
        return error_response("切换状态失败", {"reason": "id 不能为空"}, 400)
    enabled = str(data.get("enabled", "true")).lower() in {"1", "true", "yes", "on"}
    result = kb_service.toggle_enabled(kb_id, enabled)
    if not result:
        return error_response("切换状态失败", {"id": kb_id}, 404)
    return success_response("切换状态成功", result)


# ── 文件上传 ──
@admin_router.post("/upload", tags=["管理端/文件上传"], summary="[管理端] 上传文件")
async def admin_upload_file(files: list[UploadFile] = File(...)):
    return await upload_file(files)


# ── 文件下载 ──
@admin_router.get("/history/{conversation_id}/messages/{message_index}/files/{file_id}/download", tags=["管理端/对话日志"], summary="[管理端] 下载历史对话附件")
async def admin_download_history_file(conversation_id: str, message_index: int, file_id: str):
    return await download_history_uploaded_file(conversation_id, message_index, file_id)


@admin_router.get("/feedback/{feedback_id}/files/{file_id}/download", tags=["管理端/反馈"], summary="[管理端] 下载反馈中的原始提问附件")
async def admin_download_feedback_file(feedback_id: str, file_id: str):
    info = _load_feedback_info(feedback_id)
    if not info:
        return error_response("下载失败", {"id": feedback_id}, 404)
    conversation_id = str(info.get("conversation_id") or "").strip()
    message_index = info.get("message_index")
    if not conversation_id or message_index is None:
        return error_response("下载失败", {"reason": "反馈记录缺少 conversation_id 或 message_index"}, 404)
    return await download_history_uploaded_file(conversation_id, int(message_index), file_id)


@admin_router.get(
    "/feedback/{feedback_id}/pictures/{filename}", tags=["管理端/反馈"],
    summary="[管理端] 预览反馈截图",
    description="通过后端代理返回反馈截图（避免前端直连 MinIO 内网地址）。直接在浏览器中预览，不触发下载。",
)
async def admin_preview_feedback_picture(feedback_id: str, filename: str):
    info = _load_feedback_info(feedback_id)
    if not info:
        return error_response("获取图片失败", {"id": feedback_id}, 404)
    pictures_list = info.get("pictures_list") or []
    target = next((p for p in pictures_list if p.get("filename") == filename), None)
    if not target:
        return error_response("获取图片失败", {"reason": f"图片 {filename} 不存在"}, 404)
    object_name = target.get("object_name", "")
    if not object_name:
        return error_response("获取图片失败", {"reason": "图片路径为空"}, 404)
    content = storage_service.read_file_bytes(object_name)
    if content is None:
        return error_response("获取图片失败", {"reason": "文件不存在"}, 404)
    import mimetypes
    content_type = mimetypes.guess_type(filename)[0] or "image/png"
    return StreamingResponse(io.BytesIO(content), media_type=content_type)


# ── 部门人员 ──
@admin_router.get("/department_users", tags=["管理端/知识库"], summary="[管理端] 获取部门人员列表")
async def admin_get_department_users():
    from services.user_auth import get_current_user, get_department_users as query_dept_users
    user = get_current_user()
    if not user.get("tenant_id"):
        # 管理端无 token 时返回全部租户的人员（或返回空）
        return success_response("获取部门人员成功", [])
    try:
        data = query_dept_users(user["tenant_id"])
    except Exception as exc:
        return error_response("获取部门人员失败", {"reason": str(exc)}, 500)
    return success_response("获取部门人员成功", data)


app.include_router(admin_router)


# ─────────────────────────────────────────────────────────────────
# 挂载知识图谱 Flask 应用（xty-graph）到同进程下
# 前端走 8000 端口访问图谱原路径（/upload、/get_graph、/graph/* 等），
# 路径完全不变，xty-graph 代码也无需改动。
# 必须在所有 FastAPI 路由注册之后挂载，让显式路由优先匹配。
# ─────────────────────────────────────────────────────────────────
def _mount_graph_app(fastapi_app):
    import importlib.util
    from pathlib import Path
    from a2wsgi import WSGIMiddleware

    graph_root = Path(__file__).resolve().parent.parent / "graph"
    if not (graph_root / "app.py").exists():
        print(f"[graph] skip mount: {graph_root}/app.py not found", file=sys.stderr)
        return

    # 用 append 而非 insert(0)，避免 graph/app.py 抢占 'app' 名字解析
    # 让 graph/ 仅作为后备路径供 graph 自己的子包 import 用
    if str(graph_root) not in sys.path:
        sys.path.append(str(graph_root))

    spec = importlib.util.spec_from_file_location("xty_graph_flask_app", graph_root / "app.py")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        print(f"[graph] mount failed: {exc}", file=sys.stderr)
        return

    fastapi_app.mount("/", WSGIMiddleware(mod.app))
    route_count = len(list(mod.app.url_map.iter_rules()))
    print(f"[graph] Flask app mounted, {route_count} routes available", file=sys.stderr)


_mount_graph_app(app)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
