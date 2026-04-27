"""数据库注册表：维护可选 MySQL 连接列表 + 当前活跃连接。

抽象目的：让前端能"加一个新数据库"并切换 sql_tool 实际连的目标，
而不必改 utils/DB_vllm_32B.py 的内部逻辑。

切换机制（monkey-patch 而非改 DB 类）：
  1. 改写 utils.DB_vllm_32B 模块的 5 个连接常量
  2. 把 agent.tools.db_operator._db_instance 置 None，触发下次 sql_tool 调用时重建
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import pymysql

from config import DATA_DIR

DB_REGISTRY_FILE = DATA_DIR / "databases.json"
LEGACY_CURRENT_DB_FILE = DATA_DIR / "current_db.json"

CONNECT_TIMEOUT_SECONDS = 5

REQUIRED_FIELDS = ("name", "host", "port", "user", "password")
PUBLIC_FIELDS = ("id", "name", "host", "port", "user")  # 不含 password


def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_id() -> str:
    return f"db_{_now_ms()}_{uuid.uuid4().hex[:6]}"


def _load_raw() -> dict:
    if not DB_REGISTRY_FILE.exists():
        return {"databases": [], "active_id": ""}
    try:
        data = json.loads(DB_REGISTRY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"databases": [], "active_id": ""}
    if not isinstance(data, dict):
        return {"databases": [], "active_id": ""}
    data.setdefault("databases", [])
    data.setdefault("active_id", "")
    return data


def _save_raw(data: dict) -> None:
    DB_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    DB_REGISTRY_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_label(entry: dict) -> str:
    return f"{entry.get('name', '')}@{entry.get('host', '')}:{entry.get('port', '')}"


def _to_public(entry: dict) -> dict:
    public = {key: entry.get(key) for key in PUBLIC_FIELDS}
    public["label"] = _build_label(entry)
    return public


def _validate_payload(payload: dict) -> tuple[str, str, int, str, str]:
    """从请求 payload 校验并返回 (name, host, port, user, password)。校验失败抛 ValueError。"""
    if not isinstance(payload, dict):
        raise ValueError("请求体必须是 JSON 对象")
    name = str(payload.get("name") or "").strip()
    host = str(payload.get("host") or "").strip()
    port_raw = payload.get("port")
    user = str(payload.get("user") or "").strip()
    password = payload.get("password")
    if password is None:
        password = ""
    password = str(password)

    if not name:
        raise ValueError("数据库名 (name) 不能为空")
    if not host:
        raise ValueError("IP 地址 (host) 不能为空")
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        raise ValueError("端口 (port) 必须是整数")
    if not (0 < port < 65536):
        raise ValueError("端口 (port) 必须在 1~65535 范围")
    if not user:
        raise ValueError("用户名 (user) 不能为空")
    return name, host, port, user, password


def _connection_test(host: str, port: int, user: str, password: str, db_name: str) -> None:
    """试连一次，连不上抛 ValueError（消息已用户友好化）。"""
    try:
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            passwd=password,
            db=db_name,
            charset="utf8",
            connect_timeout=CONNECT_TIMEOUT_SECONDS,
        )
    except pymysql.err.OperationalError as exc:
        code = exc.args[0] if exc.args else 0
        msg = exc.args[1] if len(exc.args) > 1 else str(exc)
        if code == 1045:
            raise ValueError(f"用户名或密码错误：{msg}") from exc
        if code == 1049:
            raise ValueError(f"数据库不存在：{msg}") from exc
        if code in (2003, 2002):
            raise ValueError(f"无法连接到 {host}:{port}（{CONNECT_TIMEOUT_SECONDS}s 超时或被拒绝）") from exc
        raise ValueError(f"MySQL 连接失败 [{code}]：{msg}") from exc
    except Exception as exc:
        raise ValueError(f"MySQL 连接失败：{exc}") from exc
    else:
        try:
            conn.close()
        except Exception:
            pass


def _apply_active(entry: dict) -> None:
    """把 entry 的连接参数注入 utils.DB_vllm_32B 模块常量，并重置 sql_tool 单例。
    其它任何地方一律不动。"""
    import utils.DB_vllm_32B as db_mod
    db_mod.HOST = entry["host"]
    db_mod.PORT = int(entry["port"])
    db_mod.USER = entry["user"]
    db_mod.PASSWD = entry["password"]
    db_mod.DB_NAME = entry["name"]

    # 同步刷一下 env，便于其它代码直接 os.getenv 读到一致值
    os.environ["DB_MYSQL_HOST"] = entry["host"]
    os.environ["DB_MYSQL_PORT"] = str(entry["port"])
    os.environ["DB_MYSQL_USER"] = entry["user"]
    os.environ["DB_MYSQL_PASSWORD"] = entry["password"]
    os.environ["DB_MYSQL_NAME"] = entry["name"]

    # 重置 sql_tool 单例，下次调用会用新参数重新构造 DB
    try:
        import agent.tools.db_operator as db_operator
        db_operator._db_instance = None
    except Exception:
        pass


def _ensure_initialized() -> dict:
    """首次启动时 seed setting.sh 里那份真实 MySQL；并迁移老 current_db.json（如有）。"""
    data = _load_raw()
    changed = False

    if not data["databases"]:
        # seed 默认条目
        default_entry = {
            "id": "db_default",
            "name": os.getenv("DB_MYSQL_NAME", "r_d_test"),
            "host": os.getenv("DB_MYSQL_HOST", "183.69.138.62"),
            "port": int(os.getenv("DB_MYSQL_PORT", "33666")),
            "user": os.getenv("DB_MYSQL_USER", "hagongda"),
            "password": os.getenv("DB_MYSQL_PASSWORD", ""),
        }
        data["databases"].append(default_entry)
        data["active_id"] = "db_default"
        changed = True

    # 迁移老 current_db.json：把它对应到 db_default 的 active_id（如果旧值不在新 schema 里就略过）
    if LEGACY_CURRENT_DB_FILE.exists():
        try:
            LEGACY_CURRENT_DB_FILE.unlink()
        except Exception:
            pass

    if not data["active_id"] and data["databases"]:
        data["active_id"] = data["databases"][0]["id"]
        changed = True

    if changed:
        _save_raw(data)

    # 把当前 active 应用到模块常量
    active = next((e for e in data["databases"] if e["id"] == data["active_id"]), None)
    if active:
        _apply_active(active)

    return data


def list_options() -> dict:
    """供 GET /api/db/options 使用。"""
    data = _load_raw()
    return {
        "databases": [_to_public(entry) for entry in data["databases"]],
        "active_id": data["active_id"],
    }


def get_active_id() -> str:
    return _load_raw()["active_id"]


def select(db_id: str) -> dict:
    """供 POST /api/db/select 使用。校验 id 存在 → 切 active → monkey-patch。"""
    db_id = (db_id or "").strip()
    if not db_id:
        raise ValueError("id 不能为空")
    data = _load_raw()
    entry = next((e for e in data["databases"] if e["id"] == db_id), None)
    if not entry:
        raise ValueError(f"未知数据库 ID：{db_id}")
    data["active_id"] = db_id
    _save_raw(data)
    _apply_active(entry)
    return _to_public(entry)


def add(payload: dict) -> dict:
    """供 POST /api/db/add 使用。校验 → 查重 → test connect → 写入。任何一步失败都抛 ValueError。"""
    name, host, port, user, password = _validate_payload(payload)
    data = _load_raw()

    duplicate = next(
        (
            e for e in data["databases"]
            if e["host"] == host and int(e["port"]) == port
            and e["user"] == user and e["name"] == name
        ),
        None,
    )
    if duplicate:
        raise ValueError(f"该数据库已存在 (id={duplicate['id']})")

    _connection_test(host, port, user, password, name)

    entry = {
        "id": _new_id(),
        "name": name,
        "host": host,
        "port": port,
        "user": user,
        "password": password,
    }
    data["databases"].append(entry)
    _save_raw(data)
    return _to_public(entry)


def initialize_on_startup() -> None:
    """app 启动时调用一次。"""
    _ensure_initialized()
