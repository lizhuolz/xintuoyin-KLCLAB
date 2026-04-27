import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
USER_JSON_FILE = PROJECT_ROOT / "user.json"
KB_METADATA_FILE = DATA_DIR / "kb_metadata.json"

DEFAULT_USER = {
    "name": "guest",
    "company": "",
    "department": "",
    "phone": "",
    "record_id": "",
    "ip_address": "",
}


def get_user_profile() -> dict:
    """获取当前请求的用户信息。优先从 contextvars（Redis token 解析结果）获取。"""
    try:
        from services.user_auth import get_current_user
        user = get_current_user()
        if user and user.get("name") and user["name"] != "guest":
            return user
    except Exception:
        pass
    return dict(DEFAULT_USER)


def now_ms() -> str:
    return str(int(datetime.now().timestamp() * 1000))


def now_display() -> str:
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def make_timestamps() -> dict:
    ms, display = now_ms(), now_display()
    return {"created_at": ms, "updated_at": ms, "createdAt": display, "updatedAt": display}


def touch_timestamps() -> dict:
    return {"updated_at": now_ms(), "updatedAt": now_display()}
