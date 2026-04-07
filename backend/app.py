import json
import asyncio
import os
import re
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import AsyncIterator, List, Optional
from xml.etree import ElementTree as ET

from fastapi import Body, FastAPI, File, Form, Header, Query, Request, UploadFile
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
from utils.security import check_input_safety, check_output_safety
from services.kb_service import KBService
from services.storage_service import storage_service
from utils.DB_vllm_32B import DB as DatabaseSelector

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

app = FastAPI(
    title="研发猫 AI 系统 - 后端接口服务",
    description="支持对话、历史、反馈、知识库管理的后端服务。",
    version="2.0.0",
    openapi_url=None,
    openapi_tags=[
        {"name": "对话", "description": "会话创建、对话交互、思考过程与附件上传接口。"},
        {"name": "历史记录", "description": "历史对话的查询、详情查看与删除接口。"},
        {"name": "反馈", "description": "点赞点踩反馈、截图上传、反馈处理与删除接口。"},
        {"name": "知识库", "description": "知识库创建、更新、文件管理与删除接口。"},
        {"name": "数据库", "description": "数据库表字段选择与显式配置相关接口。"},
    ]
)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.ngrok-free\.dev",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_DIR = Path(current_dir).parent
HISTORY_ROOT = ROOT_DIR / "history_storage"
FEEDBACK_ROOT = ROOT_DIR / "feedbacks"
CHAT_UPLOAD_ROOT = ROOT_DIR / "uploads" / "chat"
USER_JSON_PATH = ROOT_DIR / "user.json"
EXCELLENT_DIR = FEEDBACK_ROOT / "excellent_answers"
NEGATIVE_QA_DIR = FEEDBACK_ROOT / "negative_answers"

for path in [HISTORY_ROOT, FEEDBACK_ROOT, CHAT_UPLOAD_ROOT, EXCELLENT_DIR, NEGATIVE_QA_DIR]:
    path.mkdir(parents=True, exist_ok=True)

app.mount("/api/static/feedbacks", StaticFiles(directory=str(FEEDBACK_ROOT)), name="feedbacks")
app.mount("/api/static/chat_uploads", StaticFiles(directory=str(CHAT_UPLOAD_ROOT)), name="chat_uploads")

agent_app = graph_builder.compile()
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


def now_ms() -> str:
    return str(int(datetime.now().timestamp() * 1000))


def now_display() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


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


def get_logged_in_user(access_token: Optional[str] = None):
    if USER_JSON_PATH.exists():
        try:
            with open(USER_JSON_PATH, "r", encoding="utf-8") as f:
                user = json.load(f)
                return {
                    "name": user.get("name", "演示用户"),
                    "company": user.get("company", "演示公司"),
                    "phone": user.get("phone", ""),
                    "department": user.get("department", ""),
                    "ip_address": user.get("ip_address") or user.get("ip") or "127.0.0.1",
                    "user_id": user.get("user_id", "UID_DEMO"),
                    "record_id": user.get("record_id") or user.get("recordId") or user.get("RecordID") or user.get("user_id", "UID_DEMO"),
                    "access_token": access_token or ""
                }
        except Exception:
            pass
    return {
        "name": "演示用户",
        "company": "演示公司",
        "phone": "13800000000",
        "department": "",
        "ip_address": "127.0.0.1",
        "user_id": "UID_DEMO",
        "record_id": "UID_DEMO",
        "access_token": access_token or ""
    }


def build_user_brief(user: dict):
    return {
        "name": user.get("name", ""),
        "phone": user.get("phone", ""),
        "categoryName": user.get("company", ""),
        "record_id": user.get("record_id") or user.get("user_id", ""),
        "ip_address": user.get("ip_address", ""),
    }


def build_user_payload(user: dict):
    return {
        "name": user.get("name", ""),
        "enterprise": user.get("company", ""),
        "phone": user.get("phone", ""),
        "department": user.get("department", ""),
        "record_id": user.get("record_id") or user.get("user_id", ""),
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


def build_history_list_item(record: dict) -> dict:
    messages = record.get("messages", []) or []
    last_message = messages[-1] if messages else {}
    user = record.get("user") or {}
    return {
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
            "record_id": user.get("record_id") or user.get("user_id", ""),
            "ip_address": user.get("ip_address", ""),
        },
    }


def build_feedback_type_meta(info: dict) -> dict:
    raw_type = info.get("type")
    primary = "点赞" if raw_type == "like" else "点踩" if raw_type == "dislike" else ""
    labels = []
    if primary:
        labels.append(primary)
    scene = info.get("feedback_scene") or "针对回答效果"
    labels.append(scene)
    text_blob = " ".join(str(item) for item in (info.get("reasons") or [])) + " " + str(info.get("comment") or "")
    if any(keyword in text_blob for keyword in ["举报", "违规", "违法", "投诉"]):
        labels.append("举报")
    if any(keyword in text_blob for keyword in ["问题", "提问", "question"]):
        labels.append("针对问题")
    labels = list(dict.fromkeys([item for item in labels if item]))
    return {
        "primary": primary,
        "scene": scene,
        "labels": labels,
        "options": ["全部", "针对问题", "针对回答效果", "举报", "点赞", "点踩"],
    }


def build_feedback_user(info: dict) -> dict:
    user = info.get("user") if isinstance(info.get("user"), dict) else {}
    return {
        "name": user.get("name") or info.get("name", ""),
        "enterprise": user.get("enterprise") or info.get("enterprise", ""),
        "phone": user.get("phone") or info.get("phone", ""),
        "record_id": user.get("record_id") or info.get("record_id", ""),
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


def iter_history_paths():
    for path in HISTORY_ROOT.rglob("*.json"):
        yield path


def resolve_history_path(conversation_id: str) -> Optional[Path]:
    safe_id = safe_segment(conversation_id)
    direct = HISTORY_ROOT / f"{safe_id}.json"
    if direct.exists():
        return direct
    dated = sorted(HISTORY_ROOT.glob(f"*/{safe_id}.json"), reverse=True)
    if dated:
        return dated[0]
    return None


def build_history_path(conversation_id: str, date_str: Optional[str] = None) -> Path:
    return HISTORY_ROOT / (date_str or today_str()) / f"{safe_segment(conversation_id)}.json"


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
        "user": build_user_brief(user),
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
        record.setdefault("user", build_user_brief(user or get_logged_in_user()))
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
    path = resolve_history_path(conversation_id)
    if not path:
        return empty_history_record(conversation_id, user), build_history_path(conversation_id)
    payload = read_json(path, {})
    return normalize_legacy_history(conversation_id, payload, user), path


def save_history_record(record: dict, path: Optional[Path] = None):
    record["title"] = record.get("messages", [{}])[0].get("question", "") if record.get("messages") else ""
    record["message_count"] = len(record.get("messages", []))
    record["updated_at"] = now_ms()
    record["updatedAt"] = now_display()
    target_path = path or resolve_history_path(record["conversation_id"]) or build_history_path(record["conversation_id"])
    write_json(target_path, record)
    return target_path


def list_history_records():
    records = []
    for path in iter_history_paths():
        try:
            payload = read_json(path, {})
            conversation_id = path.stem
            record = normalize_legacy_history(conversation_id, payload)
            record["storage_date"] = path.parent.name if path.parent != HISTORY_ROOT else ""
            records.append(record)
        except Exception:
            continue
    return records


def save_chat_uploads(conversation_id: str, message_index: int, files: List[UploadFile]):
    saved = []
    if not files:
        return saved
    prefix = f"chat/{today_str()}/{safe_segment(conversation_id)}/{message_index}"
    existing_names = {
        item["object_name"].rsplit("/", 1)[-1]
        for item in storage_service.list_files(prefix + "/")
    }
    for upload in files:
        original_name = Path(upload.filename or "unnamed_file").name
        stem = Path(original_name).stem
        suffix = Path(original_name).suffix
        final_name = original_name
        counter = 1
        while final_name in existing_names:
            final_name = f"{stem}_{counter}{suffix}"
            counter += 1
        existing_names.add(final_name)
        object_name = f"{prefix}/{final_name}"

        # 直接流式上传到 MinIO
        if storage_service.upload_file_obj(upload.file, object_name, getattr(upload, 'content_type', 'application/octet-stream')):
            saved.append({
                "file_id": f"file_{now_ms()}_{len(saved)}",
                "filename": final_name,
                "url": storage_service.get_presigned_url(object_name),
                "relative_path": object_name,
                "object_name": object_name
            })
    return saved


MAX_FILE_TEXT_CHARS = env_int("CHAT_FILE_TEXT_MAX_CHARS", 12000)
MAX_HISTORY_ROUNDS = env_int("CHAT_HISTORY_MAX_ROUNDS", 6)
FILE_HISTORY_SNIPPET_CHARS = env_int("CHAT_FILE_HISTORY_SNIPPET_CHARS", 3000)


def _compact_text(text: str, limit: int = MAX_FILE_TEXT_CHARS) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
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
    try:
        with zipfile.ZipFile(path) as zf:
            shared_strings = []
            if 'xl/sharedStrings.xml' in zf.namelist():
                shared_strings = _extract_text_nodes_from_xml(zf.read('xl/sharedStrings.xml'))
            parts = []
            for name in sorted(zf.namelist()):
                if not (name.startswith('xl/worksheets/sheet') and name.endswith('.xml')):
                    continue
                try:
                    root = ET.fromstring(zf.read(name))
                except Exception:
                    continue
                sheet_rows = []
                for cell in root.iter():
                    if not cell.tag.endswith('}c'):
                        continue
                    value = ''
                    cell_type = cell.attrib.get('t')
                    value_node = next((child for child in cell if child.tag.endswith('}v')), None)
                    if value_node is None or value_node.text is None:
                        continue
                    raw = value_node.text.strip()
                    if cell_type == 's' and raw.isdigit():
                        idx = int(raw)
                        if 0 <= idx < len(shared_strings):
                            value = shared_strings[idx]
                    else:
                        value = raw
                    if value:
                        sheet_rows.append(value)
                if sheet_rows:
                    parts.append(' | '.join(sheet_rows))
    except Exception:
        return ''
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
            return '该文件为旧版 Office 二进制格式，当前服务暂不支持直接抽取正文，请转换为 docx/xlsx/pptx 后重试。'
        return '该文件类型暂不支持正文抽取，但文件已上传保存。'
    except Exception as exc:
        return f'文件解析失败：{exc}'


import tempfile
import uuid

def build_uploaded_file_contexts(uploaded_files: List[dict]) -> list[dict]:
    contexts = []
    for item in uploaded_files or []:
        object_name = item.get('object_name') or item.get('relative_path')
        if not object_name:
            continue

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / item.get('filename', f"tmp_{uuid.uuid4().hex}")
            # 从 MinIO 下载到临时文件进行正文抽取
            if storage_service.download_file(object_name, str(tmp_path)):
                extracted_text = extract_uploaded_file_text(tmp_path)
                contexts.append({
                    'filename': item.get('filename', tmp_path.name),
                    'text': extracted_text,
                })
    return contexts


def compose_chat_prompt(current_message: str, history_record: dict, file_contexts: Optional[list[dict]] = None) -> str:
    parts = []
    history_messages = history_record.get('messages', [])[-MAX_HISTORY_ROUNDS:]
    if history_messages:
        history_lines = ['【历史对话上下文】']
        for idx, item in enumerate(history_messages, start=1):
            question = (item.get('question') or '').strip()
            answer = (item.get('answer') or '').strip()
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
    if current_file_contexts:
        file_lines = ['【本轮上传文件内容】']
        for idx, item in enumerate(current_file_contexts, start=1):
            file_lines.append(f'文件{idx}：{item.get("filename", "未命名文件")}')
            file_lines.append(item.get('text') or '文件内容为空，或暂未成功解析。')
        parts.append('\n'.join(file_lines))

    parts.append(
        '【当前用户问题】\n'
        f'{current_message}\n\n'
        '【回答要求】\n'
        '1. 必须同时结合历史对话、本轮问题和上传文件内容进行回答。\n'
        '2. 如果上面已经给出了上传文件正文或摘要，说明系统已经成功读取文件；此时不要再说“无法读取附件”或类似表述。\n'
        '3. 如果上传文件中有可用信息，优先基于文件内容回答，并明确提到文件名。\n'
        '4. 如果文件未解析成功或内容不足，请明确说明，不要假装已经读到。\n'
        '5. 不要忽略用户本轮输入的文字问题。'
    )
    return '\n\n'.join(part for part in parts if part.strip())


def find_feedback_dir(feedback_id: str) -> Optional[Path]:
    matches = sorted(FEEDBACK_ROOT.glob(f"*/{feedback_id}"), reverse=True)
    return matches[0] if matches else None


def get_feedback_dir(feedback_id: str) -> Path:
    existing = find_feedback_dir(feedback_id)
    if existing:
        return existing
    return FEEDBACK_ROOT / today_str() / feedback_id


def parse_reasons(raw_reasons):
    if raw_reasons in (None, "", []):
        return []
    if isinstance(raw_reasons, list):
        return raw_reasons
    if isinstance(raw_reasons, dict):
        return [value for value in raw_reasons.values() if value]
    try:
        parsed = json.loads(raw_reasons)
        if isinstance(parsed, dict):
            return [value for value in parsed.values() if value]
        if isinstance(parsed, list):
            return parsed
        return [parsed]
    except Exception:
        return [raw_reasons]


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
        "state": info.get("state"),
        "feedback_type": build_feedback_type_meta(info),
        "reasons": info.get("reasons", []),
        "comment": info.get("comment", ""),
        "pictures": info.get("pictures", []),
        "pictures_list": info.get("pictures_list", []),
        "user": build_feedback_user(info),
        "time": info.get("time", ""),
        "update_time": info.get("update_time", ""),
        "processed_at": info.get("processed_at", ""),
        "createdAt": info.get("createdAt", ""),
        "updatedAt": info.get("updatedAt", ""),
        "processedAt": info.get("processedAt", ""),
        "times": {
            "submit_time": info.get("time", ""),
            "update_time": info.get("update_time", ""),
            "processed_at": info.get("processed_at", ""),
            "createdAt": info.get("createdAt", ""),
            "updatedAt": info.get("updatedAt", ""),
            "processedAt": info.get("processedAt", ""),
        },
        "question": info.get("question", ""),
        "answer": info.get("answer", ""),
        "process_status": info.get("process_status", "未处理"),
        "process_result": info.get("process_result", ""),
    }


async def generate_recommendations(user_msg: str, ai_msg: str) -> List[str]:
    import re

    def fallback_questions() -> List[str]:
        generic = [
            "能展开说说吗？",
            "有哪些关键点？",
            "还有什么需要注意？",
        ]
        cleaned_user = re.sub(r"\s+", " ", str(user_msg or "")).strip("？?。！!，, ")
        if cleaned_user:
            generic = [
                f"{cleaned_user}的关键点有哪些？",
                f"{cleaned_user}有没有具体例子？",
                f"{cleaned_user}还需要注意什么？",
            ]
        return generic[:env_int("CHAT_RECOMMENDATION_COUNT", 3)]

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


THINK_OPEN_TAG = "<think>"
THINK_CLOSE_TAG = "</think>"


def _extract_think_content(text: str) -> str:
    if not text:
        return ""
    matches = re.findall(r"<think>(.*?)</think>", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = [item.strip() for item in matches if str(item).strip()]
    if cleaned:
        return "\n\n".join(cleaned)
    close_index = text.lower().find(THINK_CLOSE_TAG)
    if close_index != -1:
        prefix = text[:close_index]
        prefix = re.sub(r"^\s*<think>\s*", "", prefix, flags=re.IGNORECASE)
        return prefix.strip()
    return ""


def _strip_think_blocks(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    if cleaned != text:
        return cleaned.strip()
    close_index = text.lower().find(THINK_CLOSE_TAG)
    if close_index != -1:
        return text[close_index + len(THINK_CLOSE_TAG):].strip()
    return cleaned.strip()


def _new_chat_stream_state() -> dict:
    return {
        "buffer": "",
        "mode": "visible",
        "started_visible": False,
        "visible_buffer": "",
        "thinking_buffer": "",
    }


def _consume_chat_stream_text(state: dict, chunk: str = "", *, finalize: bool = False) -> tuple[str, str]:
    state["buffer"] += chunk or ""
    visible_parts = []
    thinking_parts = []

    while True:
        if state["mode"] == "think":
            close_index = state["buffer"].lower().find(THINK_CLOSE_TAG)
            if close_index == -1:
                if finalize:
                    flush = state["buffer"]
                    state["buffer"] = ""
                else:
                    keep = len(THINK_CLOSE_TAG) - 1
                    if len(state["buffer"]) <= keep:
                        break
                    flush = state["buffer"][:-keep]
                    state["buffer"] = state["buffer"][-keep:]
                if flush:
                    thinking_parts.append(flush)
                break
            prefix = state["buffer"][:close_index]
            if prefix:
                thinking_parts.append(prefix)
            state["buffer"] = state["buffer"][close_index + len(THINK_CLOSE_TAG):]
            state["mode"] = "visible"
            continue

        lower_buffer = state["buffer"].lower()
        open_index = lower_buffer.find(THINK_OPEN_TAG)
        close_index = lower_buffer.find(THINK_CLOSE_TAG)
        if close_index != -1 and (open_index == -1 or close_index < open_index):
            prefix = state["buffer"][:close_index]
            if prefix:
                thinking_parts.append(prefix)
            state["buffer"] = state["buffer"][close_index + len(THINK_CLOSE_TAG):]
            state["mode"] = "visible"
            continue
        if open_index == -1:
            if finalize:
                flush = state["buffer"]
                state["buffer"] = ""
            else:
                keep = len(THINK_OPEN_TAG) - 1
                if len(state["buffer"]) <= keep:
                    break
                flush = state["buffer"][:-keep]
                state["buffer"] = state["buffer"][-keep:]
            if flush:
                visible_parts.append(flush)
            break

        prefix = state["buffer"][:open_index]
        if prefix:
            visible_parts.append(prefix)
        state["buffer"] = state["buffer"][open_index + len(THINK_OPEN_TAG):]
        state["mode"] = "think"

    visible_text = "".join(visible_parts)
    thinking_text = "".join(thinking_parts)
    if visible_text and not state["started_visible"]:
        visible_text = visible_text.lstrip()
    if visible_text:
        state["started_visible"] = True
    if visible_text:
        state["visible_buffer"] += visible_text
    if thinking_text:
        state["thinking_buffer"] += thinking_text
    return visible_text, thinking_text


def _resolve_saved_thinking_text(message_item: dict) -> str:
    thinking_steps = message_item.get("thinking_steps") or []
    if thinking_steps:
        return _format_thinking_text(thinking_steps)
    if message_item.get("model_think_text"):
        return str(message_item.get("model_think_text"))
    raw_answer = message_item.get("raw_answer") or message_item.get("full_answer") or ""
    if raw_answer:
        return _extract_think_content(raw_answer)
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


async def _get_request_payload_and_files(request: Request) -> tuple[dict, list[UploadFile]]:
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("请求体必须是 JSON 对象")
        return payload, []
    form = await request.form()
    payload = {}
    upload_files = []
    for key, value in form.multi_items():
        if isinstance(value, (UploadFile, StarletteUploadFile)):
            if key == "files":
                upload_files.append(value)
            continue
        payload[key] = value
    return payload, upload_files


def _looks_like_tool_query(message: str, web_search: bool) -> bool:
    if web_search:
        return True
    lowered = (message or "").lower()
    keyword_groups = [
        ("数据库", "sql", "表", "字段", "统计", "发票", "员工", "总数", "总额", "查询"),
        ("知识库", "rag", "文档", "附件", "文件", "资料", "根据知识库", "根据文档"),
        ("计算", "calculator", "算一下", "帮我算", "+", "-", "*", "/", "根号"),
        ("搜索", "联网", "上网", "网页", "官网", "新闻", "参考链接"),
    ]
    return any(any(keyword in lowered for keyword in group) for group in keyword_groups)


async def iterate_fast_chat_events(message: str, system_prompt: str):
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=os.getenv("CHAT_MODEL_NAME", "gpt-4o"),
        temperature=env_float("CHAT_MODEL_TEMPERATURE", 0.0),
        streaming=True,
        max_tokens=env_int("CHAT_MODEL_MAX_TOKENS", 4096),
        timeout=env_float("CHAT_MODEL_TIMEOUT", 120),
    )
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=message)]

    full_ai_response = ""
    stream_state = _new_chat_stream_state()
    async for chunk in llm.astream(messages):
        text = getattr(chunk, "content", "") or ""
        if not text:
            continue
        full_ai_response += text
        visible_delta, thinking_delta = _consume_chat_stream_text(stream_state, text)
        if thinking_delta:
            yield {"type": "thinking_delta", "delta": thinking_delta}
        if visible_delta:
            yield {"type": "answer_delta", "delta": visible_delta}

    visible_tail, thinking_tail = _consume_chat_stream_text(stream_state, finalize=True)
    if thinking_tail:
        yield {"type": "thinking_delta", "delta": thinking_tail}
    if visible_tail:
        yield {"type": "answer_delta", "delta": visible_tail}

    checked_answer = _strip_think_blocks(full_ai_response)
    is_safe, safety_msg = check_output_safety(message, checked_answer)
    if not is_safe:
        checked_answer = f"⚠️ [安全拦截] {safety_msg}"
        yield {"type": "answer_replace", "content": checked_answer}

    yield {
        "type": "complete",
        "result": {
            "answer": checked_answer,
            "raw_answer": full_ai_response,
            "model_think_text": _extract_think_content(full_ai_response),
            "sources": [],
            "thinking_steps": [],
        }
    }


async def iterate_chat_events(message: str, conversation_id: str, system_prompt: str, web_search: bool, user_identity: str):
    if not _looks_like_tool_query(message, web_search):
        async for event in iterate_fast_chat_events(message, system_prompt):
            yield event
        return

    inputs = {
        "messages": [HumanMessage(content=message)],
        "enable_web": web_search,
        "select_model": os.getenv("CHAT_MODEL_NAME", "gpt-4o"),
        "user_identity": user_identity,
    }
    config = {"configurable": {"thread_id": conversation_id}}

    full_ai_response = ""
    stream_state = _new_chat_stream_state()
    sources = []
    tool_trace_events = []
    emitted_trace_keys = set()

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
            if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
                continue
            if msg.content:
                full_ai_response += msg.content
                visible_delta, thinking_delta = _consume_chat_stream_text(stream_state, msg.content)
                if thinking_delta:
                    yield {"type": "thinking_delta", "delta": thinking_delta}
                if visible_delta:
                    yield {"type": "answer_delta", "delta": visible_delta}

    visible_tail, thinking_tail = _consume_chat_stream_text(stream_state, finalize=True)
    if thinking_tail:
        yield {"type": "thinking_delta", "delta": thinking_tail}
    if visible_tail:
        yield {"type": "answer_delta", "delta": visible_tail}

    checked_answer = _strip_think_blocks(full_ai_response)
    is_safe, safety_msg = check_output_safety(message, checked_answer)
    if not is_safe:
        checked_answer = f"⚠️ [安全拦截] {safety_msg}"
        yield {"type": "answer_replace", "content": checked_answer}

    yield {
        "type": "complete",
        "result": {
            "answer": checked_answer,
            "raw_answer": full_ai_response,
            "model_think_text": _extract_think_content(full_ai_response),
            "sources": sources,
            "thinking_steps": list(tool_trace_events),
        }
    }


async def run_chat(message: str, conversation_id: str, system_prompt: str, web_search: bool, user_identity: str):
    answer = ""
    raw_answer = ""
    model_think_text = ""
    sources = []
    thinking_steps = []
    async for event in iterate_chat_events(message, conversation_id, system_prompt, web_search, user_identity):
        if event.get("type") == "complete":
            result = event.get("result", {})
            answer = result.get("answer", "")
            raw_answer = result.get("raw_answer", "")
            model_think_text = result.get("model_think_text", "")
            sources = result.get("sources", [])
            thinking_steps = result.get("thinking_steps", [])
    return answer, raw_answer, model_think_text, sources, thinking_steps


async def _thinking_text_stream(text: str, chunk_size: Optional[int] = None) -> AsyncIterator[str]:
    content = text or ""
    chunk_size = chunk_size or env_int("CHAT_THINKING_CHUNK_SIZE", 48)
    for index in range(0, len(content), chunk_size):
        yield content[index:index + chunk_size]


@app.get("/api/chat/new_session", tags=["对话"], summary="创建新会话", description="创建一个新的对话会话并返回 conversation_id。")
async def create_new_session():
    conversation_id = now_ms()
    return success_response("新建对话成功", {"conversation_id": conversation_id})


@app.post(
    "/api/chat",
    tags=["对话"],
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
                            "system_prompt": {"type": "string", "description": "系统提示词"},
                            "web_search": {"type": "boolean", "description": "是否启用联网搜索"},
                            "db_version": {"type": "string", "description": "数据库版本标记"},
                            "user_identity": {"type": "string", "description": "用户身份"},
                        },
                    },
                    "examples": {
                        "json_without_files": {
                            "summary": "无附件对话请求",
                            "value": {
                                "message": "你好",
                                "conversation_id": "1775220000000",
                                "web_search": False,
                                "user_identity": "guest"
                            }
                        }
                    }
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["message", "conversation_id"],
                        "properties": {
                            "message": {"type": "string"},
                            "conversation_id": {"type": "string"},
                            "files": {"type": "array", "items": {"type": "string", "format": "binary"}},
                            "system_prompt": {"type": "string"},
                            "web_search": {"type": "boolean"},
                            "db_version": {"type": "string"},
                            "user_identity": {"type": "string"},
                        },
                    },
                    "encoding": {
                        "files": {
                            "style": "form"
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
    accessToken: Optional[str] = Header(None),
):
    try:
        payload, files = await _get_request_payload_and_files(request)
    except ValueError as exc:
        return error_response("发送对话失败", {"reason": str(exc)}, 400)

    message = str(payload.get("message") or "").strip()
    conversation_id = str(payload.get("conversation_id") or "").strip()
    system_prompt = str(payload.get("system_prompt") or "You are a helpful assistant")
    web_search = str(payload.get("web_search", "false")).lower() in {"1", "true", "yes", "on"}
    db_version = payload.get("db_version")
    db_version = str(db_version).strip() if db_version not in (None, "") else None
    user_identity = str(payload.get("user_identity") or "guest")

    if not message:
        return error_response("发送对话失败", {"reason": "message 不能为空"}, 400)
    if not conversation_id:
        return error_response("发送对话失败", {"reason": "conversation_id 不能为空"}, 400)

    sanitized_message, is_safe, error_msg = check_input_safety(message)
    if not is_safe:
        return error_response("发送对话失败", {"reason": error_msg}, 400)

    user = get_logged_in_user(accessToken)
    history_record, history_path = load_history_record(conversation_id, user)
    message_index = len(history_record.get("messages", []))
    uploaded_files = save_chat_uploads(conversation_id, message_index, files or [])
    file_contexts = build_uploaded_file_contexts(uploaded_files)
    model_message = compose_chat_prompt(sanitized_message, history_record, file_contexts)

    async def event_stream():
        try:
            yield _sse_comment("stream-open")
            latest_answer = ""
            latest_thinking_text = ""
            latest_raw_answer = ""
            latest_model_think_text = ""
            latest_sources = []
            latest_thinking_steps = []
            async for event in iterate_chat_events(
                model_message,
                conversation_id,
                system_prompt,
                web_search,
                user_identity or "guest",
            ):
                event_type = event.get("type")
                if event_type == "progress":
                    yield _sse_comment(event.get("message") or "progress")
                    continue
                if event_type == "thinking_delta":
                    latest_thinking_text += event.get("delta", "")
                    async for wire_event in _yield_text_events("thinking_delta", event.get("delta", "")):
                        yield wire_event
                    continue
                if event_type == "answer_delta":
                    latest_answer += event.get("delta", "")
                    async for wire_event in _yield_text_events("answer_delta", event.get("delta", "")):
                        yield wire_event
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
                        "thinking_text": _format_thinking_text(latest_thinking_steps) or latest_thinking_text or latest_model_think_text,
                        "model_think_text": latest_model_think_text,
                        "thinking_steps": latest_thinking_steps,
                        "created_at": now_ms(),
                        "updated_at": now_ms(),
                        "createdAt": now_display(),
                        "updatedAt": now_display(),
                    }
                    history_record["user"] = build_user_brief(user)
                    history_record.setdefault("messages", []).append(message_item)
                    save_history_record(history_record, history_path)
                    yield _sse_event({"type": "done", "data": _build_chat_done_payload(message_item)})
                    return
        except Exception as exc:
            yield _sse_event({"type": "error", "message": str(exc)})

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@app.get("/api/chat/{conversation_id}/title", tags=["对话"], summary="获取会话标题", description="读取指定会话的首轮问题，并将其作为会话标题返回。")
async def get_chat_title(conversation_id: str):
    history_record, _ = load_history_record(conversation_id)
    if not history_record.get("messages"):
        return error_response("获取标题失败", {"conversation_id": conversation_id}, 404)
    first_question = history_record["messages"][0].get("question", "")
    return success_response("获取标题成功", {
        "conversation_id": conversation_id,
        "title": first_question,
        "question": first_question,
    })


@app.post("/api/upload", tags=["对话"], summary="上传对话附件", description="为指定会话和消息轮次上传附件，并记录到历史消息中。")
async def upload_chat_files(
    conversation_id: str = Form(...),
    message_index: Optional[int] = Form(None),
    files: List[UploadFile] = File(...),
):
    history_record, history_path = load_history_record(conversation_id)
    target_index = message_index if message_index is not None else len(history_record.get("messages", []))
    if target_index < 0:
        return error_response("上传文件失败", {"reason": "message_index 不能为负数"}, 400)
    uploaded_files = save_chat_uploads(conversation_id, target_index, files or [])

    if 0 <= target_index < len(history_record.get("messages", [])):
        history_record["messages"][target_index].setdefault("uploaded_files", []).extend(uploaded_files)
        history_record["messages"][target_index]["files"] = [item["filename"] for item in history_record["messages"][target_index]["uploaded_files"]]
        save_history_record(history_record, history_path)

    return success_response("上传文件成功", {
        "conversation_id": conversation_id,
        "message_index": target_index,
        "files": uploaded_files,
    })


@app.get("/api/history/list", tags=["历史记录"], summary="查询历史记录列表", description="按关键词、时间范围和分页参数筛选历史对话列表。")
async def list_histories(
    search: str = Query("", description="历史记录关键词，可匹配标题、问题和回答。"),
    start_time: Optional[str] = Query(None, description="开始时间，毫秒时间戳。"),
    end_time: Optional[str] = Query(None, description="结束时间，毫秒时间戳。"),
    page: int = Query(1, description="页码，从 1 开始。"),
    size: int = Query(10, description="每页数量，默认 10。"),
):
    results = []
    try:
        start_ms = parse_optional_millis(start_time, "start_time")
        end_ms = parse_optional_millis(end_time, "end_time")
        page, size = normalize_page_size(page, size)
    except ValueError as exc:
        return error_response("获取历史记录失败", {"reason": str(exc)}, 400)
    for record in list_history_records():
        updated_at = int(record.get("updated_at") or 0)
        if start_ms is not None and updated_at < start_ms:
            continue
        if end_ms is not None and updated_at > end_ms:
            continue
        title = record.get("title", "")
        text_blob = "\n".join(
            f"{item.get('question', '')}\n{item.get('answer', '')}"
            for item in record.get("messages", [])
        )
        if search and search.lower() not in (title + text_blob).lower():
            continue
        results.append(build_history_list_item(record))
    results.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return success_response("获取历史记录成功", paginate_payload(results, page, size))


@app.get("/api/history/{conversation_id}", tags=["历史记录"], summary="获取历史记录详情", description="返回指定 conversation_id 的完整历史对话内容。")
async def get_history_detail(conversation_id: str):
    history_record, _ = load_history_record(conversation_id)
    if not history_record.get("messages"):
        return error_response("获取历史详情失败", {"conversation_id": conversation_id}, 404)
    return success_response("获取历史详情成功", history_record)


@app.delete("/api/chat/{conversation_id}", tags=["历史记录"], summary="删除单条历史记录", description="删除指定会话的历史记录文件，并清理空目录。")
async def delete_history(conversation_id: str):
    path = resolve_history_path(conversation_id)
    if not path:
        return error_response("删除历史对话失败", {"conversation_id": conversation_id}, 404)
    path.unlink()
    cleanup_empty_parents(path, HISTORY_ROOT)
    return success_response("删除历史对话成功", {"conversation_id": conversation_id})


@app.post("/api/history/batch_delete", tags=["历史记录"], summary="批量删除历史记录", description="根据传入的会话 ID 列表批量删除历史对话。")
async def batch_delete_history(data: dict = Body(...)):
    try:
        ids = ensure_id_list(data, "ids", "conversation_ids")
    except ValueError as exc:
        return error_response("批量删除历史对话失败", {"reason": str(exc)}, 400)
    deleted = []
    for conversation_id in ids:
        path = resolve_history_path(conversation_id)
        if path:
            path.unlink()
            cleanup_empty_parents(path, HISTORY_ROOT)
            deleted.append(conversation_id)
    return success_response("批量删除历史对话成功", {"deleted_ids": deleted})


@app.get(
    "/api/chat/{conversation_id}/thinking",
    tags=["对话"],
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
    tags=["反馈"],
    summary="提交对话反馈",
    description="对指定消息提交点赞或点踩反馈，并可附带原因、文字说明和图片。",
    openapi_extra={
        "requestBody": {
            "description": "支持 application/json（无图片）和 multipart/form-data（带图片）。",
            "required": True,
        }
    },
)
async def save_feedback(
    request: Request,
    accessToken: Optional[str] = Header(None),
):
    try:
        payload, upload_files = await _get_request_payload_and_files(request)
    except ValueError as exc:
        return error_response("提交反馈失败", {"reason": str(exc)}, 400)

    conversation_id = str(payload.get("conversation_id") or "").strip()
    type = str(payload.get("type") or "").strip()
    comment = str(payload.get("comment") or "")
    reasons = payload.get("reasons")
    if not conversation_id:
        return error_response("提交反馈失败", {"reason": "conversation_id 不能为空"}, 400)
    try:
        message_index = int(payload.get("message_index"))
    except Exception:
        return error_response("提交反馈失败", {"reason": "message_index 必须是整数"}, 400)

    try:
        type = validate_feedback_type(type)
    except ValueError as exc:
        return error_response("提交反馈失败", {"reason": str(exc)}, 400)

    if message_index < 0:
        return error_response("提交反馈失败", {"reason": "message_index 不能为负数"}, 400)

    user = get_logged_in_user(accessToken)
    history_record, history_path = load_history_record(conversation_id)
    messages = history_record.get("messages", [])
    if not (0 <= message_index < len(messages)):
        return error_response("提交反馈失败", {"conversation_id": conversation_id, "message_index": message_index}, 404)

    target_message = messages[message_index]
    old_feedback = target_message.get("feedback")
    if old_feedback == type:
        feedback_state = None
        state = None
    else:
        feedback_state = type
        state = type

    reason_list = parse_reasons(reasons)
    upload_list = upload_files or []
    if state == "dislike" and not any([reason_list, comment, upload_list]):
        return error_response("提交反馈失败", {"reason": "点踩反馈必须填写原因、描述或上传截图"}, 400)

    target_message["feedback"] = feedback_state
    target_message["updated_at"] = now_ms()
    target_message["updatedAt"] = now_display()
    save_history_record(history_record, history_path)

    feedback_id = f"fb_{conversation_id}_{message_index}"
    target_dir = get_feedback_dir(feedback_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    info_path = target_dir / "feedback.json"
    existing = read_json(info_path, {}) if info_path.exists() else {}
    
    # 获取已有的图片列表（兼容 object 格式）
    pictures_list = existing.get("pictures_list", [])
    picture_names = [p["filename"] for p in pictures_list] if isinstance(pictures_list, list) and pictures_list and isinstance(pictures_list[0], dict) else existing.get("pictures", [])

    for upload in upload_list:
        original_name = Path(upload.filename or "feedback_image").name
        stem = Path(original_name).stem
        suffix = Path(original_name).suffix
        final_name = original_name
        counter = 1
        while final_name in picture_names:
            final_name = f"{stem}_{counter}{suffix}"
            counter += 1

        # MinIO 路径
        object_name = f"feedback/{today_str()}/{feedback_id}/{final_name}"
        
        if storage_service.upload_file_obj(upload.file, object_name, getattr(upload, 'content_type', 'image/png')):
            picture_info = {
                "filename": final_name,
                "object_name": object_name,
                "url": storage_service.get_presigned_url(object_name)
            }
            if isinstance(pictures_list, list):
                pictures_list.append(picture_info)
            picture_names.append(final_name)

    current_time = now_ms()
    question = target_message.get("question", "")
    answer = target_message.get("answer", "")
    feedback_info = {
        "id": feedback_id,
        "conversation_id": conversation_id,
        "message_index": message_index,
        "type": type,
        "state": state,
        "time": existing.get("time") or current_time,
        "update_time": current_time,
        "createdAt": existing.get("createdAt") or now_display(),
        "updatedAt": now_display(),
        "reasons": reason_list,
        "comment": comment or "",
        "pictures": picture_names,
        "pictures_list": pictures_list,
        "user": build_user_payload(user),
        "name": user.get("name", ""),
        "enterprise": user.get("company", ""),
        "phone": user.get("phone", ""),
        "record_id": user.get("record_id", ""),
        "ip_address": user.get("ip_address", ""),
        "feedback_scene": "针对回答效果",
        "question": question,
        "answer": answer,
        "process_status": existing.get("process_status", "未处理")
    }
    write_json(info_path, feedback_info)
    return success_response("提交反馈成功", build_feedback_summary(feedback_info))


@app.post("/api/feedback/upload_pictures", tags=["反馈"], summary="上传反馈图片", description="为指定反馈补充上传截图图片。")
async def upload_feedback_pictures(
    conversation_id: str = Form(...),
    message_index: int = Form(...),
    pictures: List[UploadFile] = File(...),
):
    if message_index < 0:
        return error_response("上传图片失败", {"reason": "message_index 不能为负数"}, 400)

    feedback_id = f"fb_{conversation_id}_{message_index}"
    target_dir = get_feedback_dir(feedback_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    info_path = target_dir / "feedback.json"
    info = read_json(info_path, {}) if info_path.exists() else {
        "id": feedback_id,
        "conversation_id": conversation_id,
        "message_index": message_index,
        "pictures": [],
        "pictures_list": []
    }
    
    pictures_list = info.get("pictures_list", [])
    existing_names = {item.get("filename") for item in pictures_list if isinstance(item, dict) and item.get("filename")}
    saved = []
    for upload in pictures or []:
        original_name = Path(upload.filename or "feedback_image").name
        stem = Path(original_name).stem
        suffix = Path(original_name).suffix
        final_name = original_name
        counter = 1
        while final_name in existing_names:
            final_name = f"{stem}_{counter}{suffix}"
            counter += 1
        existing_names.add(final_name)
        object_name = f"feedback/{today_str()}/{feedback_id}/{final_name}"

        if storage_service.upload_file_obj(upload.file, object_name, getattr(upload, 'content_type', 'image/png')):
            pic_item = {
                "file_id": f"pic_{now_ms()}_{len(saved)}",
                "filename": final_name,
                "object_name": object_name,
                "url": storage_service.get_presigned_url(object_name),
            }
            saved.append(pic_item)
            pictures_list.append(pic_item)

    info["pictures"] = list(dict.fromkeys((info.get("pictures") or []) + [item["filename"] for item in saved]))
    info["pictures_list"] = pictures_list
    info.setdefault("time", now_ms())
    info["update_time"] = now_ms()
    info.setdefault("createdAt", now_display())
    info["updatedAt"] = now_display()
    write_json(info_path, info)
    return success_response("上传图片成功", {
        "conversation_id": conversation_id,
        "message_index": message_index,
        "pictures": saved,
    })


@app.get("/api/feedback/list", tags=["反馈"], summary="查询反馈列表", description="按姓名、企业、反馈类型、时间范围和分页参数筛选反馈记录。")
async def list_feedbacks(
    name: str = Query("", description="按反馈用户姓名筛选。"),
    enterprise: str = Query("", description="按企业名称筛选。"),
    type: str = Query("", description="兼容旧版 like/dislike 状态筛选。"),
    feedback_type: str = Query("全部", description="前端筛选类型，支持 全部、针对问题、针对回答效果、举报、点赞、点踩。"),
    start_time: Optional[str] = Query(None, description="开始时间，毫秒时间戳。"),
    end_time: Optional[str] = Query(None, description="结束时间，毫秒时间戳。"),
    page: int = Query(1, description="页码，从 1 开始。"),
    size: int = Query(10, description="每页数量，默认 10。"),
):
    results = []
    try:
        start_ms = parse_optional_millis(start_time, "start_time")
        end_ms = parse_optional_millis(end_time, "end_time")
        page, size = normalize_page_size(page, size)
    except ValueError as exc:
        return error_response("获取反馈列表失败", {"reason": str(exc)}, 400)
    for path in FEEDBACK_ROOT.glob("*/fb_*/feedback.json"):
        info = read_json(path, {})
        user = build_feedback_user(info)
        if name and name.lower() not in user.get("name", "").lower():
            continue
        if enterprise and enterprise.lower() not in user.get("enterprise", "").lower():
            continue
        if type and info.get("type") != type:
            continue
        if not match_feedback_type(info, feedback_type):
            continue
        update_time = int(info.get("update_time") or 0)
        if start_ms is not None and update_time < start_ms:
            continue
        if end_ms is not None and update_time > end_ms:
            continue
        results.append(build_feedback_summary(info))
    results.sort(key=lambda item: item.get("update_time", ""), reverse=True)
    return success_response("获取反馈列表成功", paginate_payload(results, page, size))


@app.get("/api/feedback/{feedback_id}", tags=["反馈"], summary="通过反馈 ID 获取详情", description="根据反馈 ID 返回对应的反馈详情。")
async def get_feedback_detail_by_id(feedback_id: str):
    target_dir = find_feedback_dir(feedback_id)
    if not target_dir:
        return error_response("获取反馈详情失败", {"id": feedback_id}, 404)
    return success_response("获取反馈详情成功", build_feedback_summary(read_json(target_dir / "feedback.json", {})))


@app.get("/api/feedback/detail/{date}/{id}", tags=["反馈"], summary="按日期路径获取反馈详情", description="根据日期目录和反馈 ID 读取反馈详情。")
async def get_feedback_detail(date: str, id: str):
    path = FEEDBACK_ROOT / date / id / "feedback.json"
    if not path.exists():
        return error_response("获取反馈详情失败", {"id": id}, 404)
    return success_response("获取反馈详情成功", build_feedback_summary(read_json(path, {})))


@app.post("/api/feedback/process", tags=["反馈"], summary="处理反馈", description="将反馈标记为已处理，并可选择收录到优秀问答或负向问答库。")
async def process_feedback(data: dict = Body(...)):
    date_path = data.get("date_path")
    feedback_id = str(data.get("id") or "").strip()
    if not feedback_id:
        return error_response("处理反馈失败", {"reason": "id 不能为空"}, 400)
    processor = data.get("processor", "系统管理员")
    is_collect = bool(data.get("is_collect", False))

    target_dir = FEEDBACK_ROOT / date_path / feedback_id if date_path else find_feedback_dir(feedback_id)
    if not target_dir or not (target_dir / "feedback.json").exists():
        return error_response("处理反馈失败", {"id": feedback_id}, 404)

    info_path = target_dir / "feedback.json"
    info = read_json(info_path, {})
    info["process_status"] = "已处理"
    info["processor"] = processor
    info["processed_at"] = now_ms()
    info["processedAt"] = now_display()
    if is_collect:
        target_file = (EXCELLENT_DIR if info.get("type") == "like" else NEGATIVE_QA_DIR) / f"{feedback_id}.json"
        write_json(target_file, {
            "question": info.get("question", ""),
            "answer": info.get("answer", ""),
            "feedback_id": feedback_id,
            "original_type": info.get("type"),
            "collected_at": now_ms(),
            "collectedAt": now_display(),
        })
        info["process_result"] = "已收录"
    else:
        info["process_result"] = "已处理(未收录)"
    write_json(info_path, info)
    return success_response("处理反馈成功", build_feedback_summary(info))


@app.post("/api/feedback/batch_delete", tags=["反馈"], summary="批量删除反馈", description="根据反馈 ID 列表批量删除反馈目录。")
async def batch_delete_feedback(data: dict = Body(...)):
    try:
        ids = ensure_id_list(data, "ids")
    except ValueError as exc:
        return error_response("批量删除反馈失败", {"reason": str(exc)}, 400)
    deleted = []
    for feedback_id in ids:
        target_dir = find_feedback_dir(feedback_id)
        if target_dir and target_dir.exists():
            shutil.rmtree(target_dir)
            deleted.append(feedback_id)
    return success_response("批量删除反馈成功", {"deleted_ids": deleted})


@app.delete("/api/feedback/{date}/{id}", tags=["反馈"], summary="删除单条反馈", description="根据日期目录和反馈 ID 删除指定反馈。")
async def delete_feedback(date: str, id: str):
    target_dir = FEEDBACK_ROOT / date / id
    if not target_dir.exists():
        return error_response("删除反馈失败", {"id": id}, 404)
    shutil.rmtree(target_dir)
    cleanup_empty_parents(target_dir, FEEDBACK_ROOT)
    return success_response("删除反馈成功", {"id": id})


@app.get("/api/kb/list", tags=["知识库"], summary="获取知识库列表", description="返回当前所有知识库的基础信息列表，支持分页。")
async def get_kb_list(
    page: int = Query(1, description="页码，从 1 开始。"),
    size: int = Query(10, description="每页数量，默认 10。"),
):
    page, size = normalize_page_size(page, size)
    items = kb_service.load_all()
    return success_response("获取知识库列表成功", paginate_payload(items, page, size))


@app.get("/api/kb/{id}", tags=["知识库"], summary="获取知识库详情", description="根据知识库 ID 返回知识库详情。")
async def get_kb_detail(id: str, url: Optional[str] = Query(None)):
    _ = url
    detail = kb_service.get_kb_detail(id)
    if not detail:
        return error_response("获取知识库详情失败", {"id": id}, 404)
    return success_response("获取知识库详情成功", detail)


@app.post(
    "/api/kb/create",
    tags=["知识库"],
    summary="创建知识库",
    description="创建一个新的知识库，仅需名称和模型类型，不再区分企业、部门、个人分类。",
    openapi_extra={
        "requestBody": {
            "description": "JSON 请求体，包含知识库名称和模型标识。",
            "required": True,
        }
    },
)
async def create_kb(request: Request):
    try:
        payload = await _get_request_payload(request)
    except ValueError as exc:
        return error_response("创建知识库失败", {"reason": str(exc)}, 400)
    name = str(payload.get("name") or "").strip()
    model = str(payload.get("model") or "openai").strip() or "openai"
    if not name:
        return error_response("创建知识库失败", {"reason": "name 不能为空"}, 400)
    created = kb_service.create_kb(name=name, model=model)
    return success_response("创建知识库成功", created)


@app.post(
    "/api/kb/update",
    tags=["知识库"],
    summary="更新知识库",
    description="更新知识库名称、备注、启用状态、授权用户，并支持在一次请求中预览或确认文件上传和删除。",
    openapi_extra={
        "requestBody": {
            "description": "支持 application/json（无文件）和 multipart/form-data（带文件）的知识库更新请求。",
            "required": True,
        }
    },
)
async def update_kb(
    request: Request,
):
    try:
        payload, files = await _get_request_payload_and_files(request)
    except ValueError as exc:
        return error_response("更新知识库失败", {"reason": str(exc)}, 400)

    id = str(payload.get("id") or "").strip()
    name = payload.get("name")
    remark = payload.get("remark")
    enabled = payload.get("enabled")
    users = payload.get("users")
    delete_files = payload.get("delete_files")
    confirm = str(payload.get("confirm", "true")).lower() in {"1", "true", "yes", "on"}
    if not id:
        return error_response("更新知识库失败", {"reason": "id 不能为空"}, 400)

    update_data = {}
    if name is not None:
        update_data["name"] = name
    if remark is not None:
        update_data["remark"] = remark
    if enabled is not None:
        update_data["enabled"] = str(enabled).lower() == "true"
    if users:
        try:
            update_data["users"] = json.loads(users)
        except Exception:
            return error_response("更新知识库失败", {"reason": "users 字段不是合法 JSON"}, 400)
    delete_filenames = []
    if delete_files:
        try:
            loaded = json.loads(delete_files)
        except Exception:
            return error_response("更新知识库失败", {"reason": "delete_files 字段不是合法 JSON"}, 400)
        if not isinstance(loaded, list):
            return error_response("更新知识库失败", {"reason": "delete_files 必须是数组"}, 400)
        delete_filenames = [str(item) for item in loaded if str(item).strip()]
    try:
        updated = kb_service.update_kb(id, update_data, new_files=files or [], delete_filenames=delete_filenames, confirm=confirm)
    except Exception as exc:
        return error_response("更新知识库失败", {"reason": str(exc)}, 500)
    if not updated:
        return error_response("更新知识库失败", {"id": id}, 404)
    msg = "预览知识库更新成功" if updated.get("preview") else "更新知识库成功"
    return success_response(msg, updated)


@app.delete("/api/kb/{id}", tags=["知识库"], summary="删除知识库", description="删除指定知识库及其元数据。")
async def delete_kb(id: str):
    try:
        deleted = kb_service.delete_kb(id)
    except Exception as exc:
        return error_response("删除知识库失败", {"reason": str(exc)}, 500)
    if not deleted:
        return error_response("删除知识库失败", {"id": id}, 404)
    return success_response("删除知识库成功", deleted)


@app.get("/api/kb/{id}/files", tags=["知识库"], summary="获取知识库文件列表", description="返回指定知识库关联的文件列表和访问地址。")
async def list_kb_files(id: str):
    detail = kb_service.get_kb_detail(id)
    if not detail:
        return error_response("获取知识库文件失败", {"id": id}, 404)
    return success_response("获取知识库文件成功", {
        "id": id,
        "url": detail.get("url", ""),
        "files": detail.get("files", []),
    })


@app.post("/api/kb/{id}/upload", tags=["知识库"], summary="上传知识库文件", description="向指定知识库上传一个或多个文档文件。")
async def upload_kb_file(
    id: str,
    files: List[UploadFile] = File(...),
):
    try:
        result = kb_service.save_files(id, files)
    except Exception as exc:
        return error_response("上传知识库文档失败", {"reason": str(exc)}, 500)
    if result is None:
        return error_response("上传知识库文档失败", {"id": id}, 404)
    return success_response("上传知识库文档成功", {"id": id, "files": result.get("files", []) if isinstance(result, dict) else result})


@app.post("/api/kb/{id}/delete_files", tags=["知识库"], summary="批量删除知识库文件", description="从指定知识库中批量删除多个文件。")
async def delete_kb_files(id: str, data: dict = Body(...)):
    try:
        filenames = ensure_id_list(data, "filenames", "files")
    except ValueError as exc:
        return error_response("删除知识库文档失败", {"reason": str(exc)}, 400)
    try:
        deleted = kb_service.delete_files(id, filenames)
    except Exception as exc:
        return error_response("删除知识库文档失败", {"reason": str(exc)}, 500)
    if deleted is None:
        return error_response("删除知识库文档失败", {"id": id}, 404)
    return success_response("删除知识库文档成功", {"id": id, "deleted_files": deleted})


@app.post(
    "/api/kb/{id}/delete_file",
    tags=["知识库"],
    summary="删除单个知识库文件",
    description="从指定知识库中删除单个文件。",
    openapi_extra={
        "requestBody": {
            "description": "JSON 请求体，包含 filename。",
            "required": True,
        }
    },
)
async def delete_kb_file(id: str, request: Request):
    try:
        payload = await _get_request_payload(request)
    except ValueError as exc:
        return error_response("删除知识库文档失败", {"reason": str(exc)}, 400)
    filename = str(payload.get("filename") or "").strip()
    if not filename:
        return error_response("删除知识库文档失败", {"reason": "filename 不能为空"}, 400)
    detail = kb_service.get_kb_detail(id)
    if not detail:
        return error_response("删除知识库文档失败", {"id": id}, 404)
    try:
        deleted = kb_service.delete_files(id, [filename]) or []
    except Exception as exc:
        return error_response("删除知识库文档失败", {"reason": str(exc)}, 500)
    if not deleted:
        return error_response("删除知识库文档失败", {"id": id, "filename": filename}, 404)
    return success_response("删除知识库文档成功", {"id": id, "deleted_files": deleted})


@app.get("/api/db/select_options", tags=["数据库"], summary="获取数据库显式可选字段", description="返回数据库中的表、表注释、字段注释，并可基于问题返回推荐表。")
async def get_db_select_options(
    question: Optional[str] = Query(None, description="可选，自然语言问题，用于返回推荐表。"),
):
    try:
        db = DatabaseSelector()
        detailed = db._extract_all_table_detailed_comments() or {}
        selected_tables = db.select_table(question.strip()) if question and question.strip() else []
        if question and question.strip() and not selected_tables:
            selected_tables = fallback_select_tables(question.strip(), detailed)
        options = []
        for table_name, info in detailed.items():
            options.append({
                "table_name": table_name,
                "table_comment": info.get("table_comment", ""),
                "column_comments": info.get("column_comments", []),
                "selected": table_name in selected_tables,
            })
        return success_response("获取数据库显式可选字段成功", {
            "question": question or "",
            "selected_tables": selected_tables,
            "options": options,
            "total": len(options),
        })
    except Exception as exc:
        return error_response("获取数据库显式可选字段失败", {"reason": str(exc)}, 500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
