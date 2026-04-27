"""用户认证与角色服务。

角色体系（4 层）：
  guest            无 token，游客。按 IP 生成固定假名"游客N"。
  user             operaterStatus=1 且 roleName≠"超级管理员"，企业普通员工。
  enterprise_admin operaterStatus=1 且 roleName="超级管理员"，企业管理员。
  管理端通过独立的 /api/admin/ 路由访问，不经过 token 认证。

数据来源：
  Redis 183.69.138.62:6800 db=1
    key: system:LOGIN_ENTERPRISE_USER_TOKEN:LOGIN_ENTERPRISE_USER_TOKEN_{token}
  MySQL 183.69.138.62:33666 / r_d_test
    t_tenant  → 企业名
    t_staff   → 部门人员列表
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import os
import time
from typing import Any, Optional

import pymysql
import redis

# ──────────────────────────────────────────────────────────────
# 角色常量
# ──────────────────────────────────────────────────────────────
ROLE_GUEST = "guest"
ROLE_USER = "user"
ROLE_ENTERPRISE_ADMIN = "enterprise_admin"

# 角色权重（越大权限越高，方便 require_role 比较）
ROLE_LEVEL = {
    ROLE_GUEST: 0,
    ROLE_USER: 1,
    ROLE_ENTERPRISE_ADMIN: 2,
}

# ──────────────────────────────────────────────────────────────
# Redis 配置
# ──────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("PARTNER_REDIS_HOST", "183.69.138.62")
REDIS_PORT = int(os.getenv("PARTNER_REDIS_PORT", "6800"))
REDIS_PASSWORD = os.getenv("PARTNER_REDIS_PASSWORD", "ty188$#456.8")
REDIS_DB = int(os.getenv("PARTNER_REDIS_DB", "1"))
REDIS_TOKEN_PREFIX = "system:LOGIN_ENTERPRISE_USER_TOKEN:LOGIN_ENTERPRISE_USER_TOKEN_"

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
            db=REDIS_DB, decode_responses=True,
            socket_connect_timeout=5, socket_timeout=5,
        )
    return _redis_client


# ──────────────────────────────────────────────────────────────
# MySQL 辅助
# ──────────────────────────────────────────────────────────────
_mysql_conn: Optional[pymysql.Connection] = None


def _get_mysql_conn():
    """复用 MySQL 连接（断线自动重连）。"""
    global _mysql_conn
    if _mysql_conn is not None:
        try:
            _mysql_conn.ping(reconnect=True)
            return _mysql_conn
        except Exception:
            _mysql_conn = None
    _mysql_conn = pymysql.connect(
        host=os.getenv("DB_MYSQL_HOST", "183.69.138.62"),
        port=int(os.getenv("DB_MYSQL_PORT", "33666")),
        user=os.getenv("DB_MYSQL_USER", "hagongda"),
        passwd=os.getenv("DB_MYSQL_PASSWORD", ""),
        db=os.getenv("DB_MYSQL_NAME", "r_d_test"),
        charset="utf8", connect_timeout=10,
    )
    return _mysql_conn


def _query_tenant_name(tenant_id: int) -> Optional[str]:
    conn = _get_mysql_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT ENTERPRISE_NAME FROM t_tenant WHERE ID = %s", (tenant_id,))
        row = cur.fetchone()
        return row[0] if row else None


_dept_cache: dict[int, tuple[list[dict], float]] = {}
DEPT_CACHE_TTL = 300  # 5 分钟缓存


def get_department_users(tenant_id: int) -> list[dict]:
    """查同租户的在职员工，按 t_dept 真实层级构建嵌套树。结果缓存 5 分钟。

    返回结构：
        [
          {
            "id": 10051, "name": "一级", "level": 2,
            "members": [{"name": "张三", "staffId": 123}, ...],
            "children": [ { ... 同上结构 ... } ]
          }
        ]
    """
    cached = _dept_cache.get(tenant_id)
    if cached and time.time() - cached[1] < DEPT_CACHE_TTL:
        return cached[0]

    conn = _get_mysql_conn()
    with conn.cursor() as cur:
        # TENANT_ID=0 是全局默认部门（人事/财务/研发），所有租户共享；
        # TENANT_ID=? 是租户自建部门，可能以全局部门为根继续下扩
        # ID=10000 是甲方约定的固定"离职部门"ID，永远不在成员选择树中展示
        cur.execute(
            "SELECT ID, PARENT_ID, LEVEL, NAME FROM t_dept "
            "WHERE (TENANT_ID = %s OR TENANT_ID = 0) "
            "AND ENABLE_STATUS = 9999 AND OPERATER_STATUS <> -1 "
            "AND ID <> 10000 "
            "ORDER BY LEVEL, INDEX_SORT, ID",
            (tenant_id,),
        )
        dept_rows = cur.fetchall()

        cur.execute(
            "SELECT ID, FULL_NAME, DEPT_ID FROM t_staff "
            "WHERE TENANT_ID = %s AND EXIST_WORK_STATUS = 9999 "
            "ORDER BY ID",
            (tenant_id,),
        )
        staff_rows = cur.fetchall()

    nodes: dict[int, dict] = {}
    for dept_id, parent_id, level, name in dept_rows:
        nodes[dept_id] = {
            "id": dept_id,
            "name": name or "",
            "level": level,
            "members": [],
            "children": [],
        }

    for staff_id, full_name, dept_id in staff_rows:
        name = (full_name or "").strip()
        if not name or dept_id not in nodes:
            continue
        nodes[dept_id]["members"].append({"name": name, "staffId": staff_id})

    roots: list[dict] = []
    for dept_id, parent_id, _level, _name in dept_rows:
        node = nodes[dept_id]
        parent = nodes.get(parent_id)
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)

    # 剪枝：去掉自身 + 所有后代都没有在职成员的节点
    # （如"离职人员"部门，因为我们已过滤 EXIST_WORK_STATUS=9999，里面天然没人）
    def prune(node: dict) -> bool:
        node["children"] = [c for c in node["children"] if prune(c)]
        return bool(node["members"] or node["children"])

    roots = [r for r in roots if prune(r)]

    _dept_cache[tenant_id] = (roots, time.time())
    return roots


# ──────────────────────────────────────────────────────────────
# 游客命名（同 IP 固定名）
# ──────────────────────────────────────────────────────────────
def make_guest_name(ip: str) -> str:
    """对 IP 做稳定 hash → "游客XXXX"，同 IP 永远同名。"""
    h = int(hashlib.md5((ip or "unknown").encode()).hexdigest(), 16) % 10000
    return f"游客{h}"


# ──────────────────────────────────────────────────────────────
# 角色判定
# ──────────────────────────────────────────────────────────────
def _determine_role(data: dict) -> str:
    if data.get("roleName") == "超级管理员":
        return ROLE_ENTERPRISE_ADMIN
    return ROLE_USER


# ──────────────────────────────────────────────────────────────
# Token → 用户信息（带缓存）
# ──────────────────────────────────────────────────────────────
_token_cache: dict[str, tuple[dict, float]] = {}
TOKEN_CACHE_TTL = 300


def get_user_by_token(token: str) -> Optional[dict[str, Any]]:
    """从 Redis 查 token → 用户信息。无效/过期返回 None。"""
    if not token:
        return None

    cached = _token_cache.get(token)
    if cached and time.time() - cached[1] < TOKEN_CACHE_TTL:
        return dict(cached[0])

    try:
        raw = _get_redis().get(f"{REDIS_TOKEN_PREFIX}{token}")
    except Exception as exc:
        print(f"[user_auth] Redis 查询失败: {exc}")
        return None

    if not raw:
        return None
    try:
        data = json.loads(raw)
    except Exception:
        return None

    role = _determine_role(data)
    user: dict[str, Any] = {
        "name": data.get("staffFullName") or data.get("account") or "",
        "phone": data.get("account") or "",
        "company": "",
        "department": "",
        "ip_address": "",
        "user_id": str(data.get("id") or ""),
        "record_id": str(data.get("staffId") or ""),
        "tenant_id": data.get("tenantId"),
        "staff_id": data.get("staffId"),
        "role_name": data.get("roleName") or "",
        "role": role,
    }

    if user["tenant_id"]:
        try:
            company = _query_tenant_name(user["tenant_id"])
            if company:
                user["company"] = company
        except Exception as exc:
            print(f"[user_auth] 查租户名失败: {exc}")

    _token_cache[token] = (dict(user), time.time())
    return user


def clear_token_cache():
    _token_cache.clear()


# ──────────────────────────────────────────────────────────────
# 游客构造
# ──────────────────────────────────────────────────────────────
def make_guest_user(ip: str = "") -> dict[str, Any]:
    name = make_guest_name(ip)
    return {
        "name": name,
        "phone": "",
        "company": "",
        "department": "",
        "ip_address": ip,
        "user_id": "",
        "record_id": "",
        "tenant_id": None,
        "staff_id": None,
        "role_name": "",
        "role": ROLE_GUEST,
    }


# ──────────────────────────────────────────────────────────────
# ContextVar：请求生命周期内的当前用户
# ──────────────────────────────────────────────────────────────
_current_user_var: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "current_user", default=None
)


def set_current_user(user: Optional[dict]) -> None:
    _current_user_var.set(user)


def get_current_user() -> dict[str, Any]:
    user = _current_user_var.get()
    if user:
        return user
    return make_guest_user()


def current_role() -> str:
    return get_current_user().get("role", ROLE_GUEST)


# ──────────────────────────────────────────────────────────────
# 权限检查（在 app.py 的接口入口调用）
# ──────────────────────────────────────────────────────────────
def check_role(min_role: str) -> Optional[tuple[str, int]]:
    """检查当前用户角色是否 >= min_role。
    通过返回 None；不通过返回 (错误消息, HTTP 状态码)。
    """
    user = get_current_user()
    user_level = ROLE_LEVEL.get(user.get("role", ROLE_GUEST), 0)
    required_level = ROLE_LEVEL.get(min_role, 0)
    if user_level >= required_level:
        return None
    role_labels = {
        ROLE_USER: "登录",
        ROLE_ENTERPRISE_ADMIN: "企业管理员",
    }
    label = role_labels.get(min_role, min_role)
    return f"需要{label}权限", 401
