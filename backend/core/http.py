from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str, detail: Optional[Any] = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


def get_request_id(request: Optional[Request]) -> str:
    if request is None:
        return ""
    return getattr(getattr(request, "state", None), "request_id", "")


def make_json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    return str(value)


def build_payload(
    request: Optional[Request],
    *,
    success: bool,
    code: str,
    message: str,
    data: Optional[Any] = None,
    detail: Optional[Any] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "success": success,
        "code": code,
        "message": message,
        "data": make_json_safe(data),
        "request_id": get_request_id(request),
    }
    if detail is not None:
        payload["detail"] = make_json_safe(detail)
    return payload


def success_response(
    request: Optional[Request],
    *,
    data: Optional[Any] = None,
    message: str = "success",
    code: str = "SUCCESS",
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=build_payload(request, success=True, code=code, message=message, data=data),
    )


def error_response(
    request: Optional[Request],
    *,
    status_code: int,
    code: str,
    message: str,
    detail: Optional[Any] = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=build_payload(
            request,
            success=False,
            code=code,
            message=message,
            data=None,
            detail=detail,
        ),
    )


def validate_required_text(value: Optional[str], field_name: str, error_code: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise AppError(status.HTTP_400_BAD_REQUEST, error_code, f"{field_name}不能为空")
    return cleaned


def validate_identifier(
    value: Optional[str],
    field_name: str = "标识",
    error_code: str = "INVALID_IDENTIFIER",
) -> str:
    cleaned = validate_required_text(value, field_name, error_code)
    safe_value = "".join(c for c in cleaned if c.isalnum() or c in ("-", "_"))
    if safe_value != cleaned:
        raise AppError(status.HTTP_400_BAD_REQUEST, error_code, f"{field_name}格式非法")
    return safe_value
