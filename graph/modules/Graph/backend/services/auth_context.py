from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from flask import has_request_context, request

PROJECT_ROOT = Path(__file__).resolve().parents[5]
CHAT_BACKEND_DIR = PROJECT_ROOT / 'backend'


def _ensure_chat_backend_path() -> None:
    backend_path = str(CHAT_BACKEND_DIR)
    if CHAT_BACKEND_DIR.exists() and backend_path not in sys.path:
        sys.path.insert(0, backend_path)


def _get_request_token() -> str:
    if not has_request_context():
        return ''
    return (
        request.headers.get('accessToken')
        or request.headers.get('accesstoken')
        or request.args.get('accessToken')
        or request.args.get('accesstoken')
        or ''
    ).strip()


def get_chat_current_user() -> Optional[Dict[str, Any]]:
    """Reuse the knowledge-QA auth service without changing that module."""
    try:
        _ensure_chat_backend_path()
        from services.user_auth import ROLE_GUEST, get_current_user, get_user_by_token

        context_user = get_current_user()
        if context_user and context_user.get('role') != ROLE_GUEST:
            return dict(context_user)

        token = _get_request_token()
        if not token:
            return None
        user = get_user_by_token(token)
    except Exception:
        return None

    if not user:
        return None

    return dict(user)
