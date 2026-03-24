from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence

from fastapi import UploadFile, status

from core.http import AppError

DEFAULT_ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv", ".doc", ".docx", ".xls", ".xlsx"}


def get_extension(filename: str) -> str:
    return Path((filename or "").strip()).suffix.lower()


def validate_upload_files(
    files: Optional[Sequence[UploadFile]],
    *,
    field_error_code: str = "EMPTY_FILES",
    allowed_extensions: Optional[set[str]] = None,
) -> List[UploadFile]:
    uploads = [file for file in (files or []) if file is not None]
    if not uploads:
        raise AppError(status.HTTP_400_BAD_REQUEST, field_error_code, "至少上传一个文件")

    allowlist = allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS
    invalid_names = []
    invalid_types = []

    for upload in uploads:
        filename = (upload.filename or "").strip()
        if not filename:
            invalid_names.append(filename)
            continue
        if get_extension(filename) not in allowlist:
            invalid_types.append(filename)

    if invalid_names:
        raise AppError(status.HTTP_400_BAD_REQUEST, "EMPTY_FILE_NAME", "上传文件名不能为空")
    if invalid_types:
        raise AppError(
            status.HTTP_400_BAD_REQUEST,
            "UNSUPPORTED_FILE_TYPE",
            "存在不支持的文件类型",
            detail={
                "allowed_extensions": sorted(allowlist),
                "invalid_filenames": invalid_types,
            },
        )

    return uploads


def compact_file_text(text: str, max_chars: int, tail_chars: int) -> str:
    if len(text) <= max_chars:
        return text

    safe_tail = min(tail_chars, max_chars // 2)
    safe_head = max(1000, max_chars - safe_tail - 200)
    omitted_chars = max(0, len(text) - safe_head - safe_tail)
    notice = (
        f"\n\n[文件内容过长，已截取前 {safe_head} 字符和后 {safe_tail} 字符，"
        f"中间省略 {omitted_chars} 字符]\n\n"
    )
    return text[:safe_head] + notice + text[-safe_tail:]


def _parse_doc_bytes(content: bytes) -> str:
    try:
        import textract

        with tempfile.NamedTemporaryFile(suffix=".doc", delete=True) as tmp:
            tmp.write(content)
            tmp.flush()
            return textract.process(tmp.name).decode("utf-8", errors="ignore")
    except Exception:
        return content.decode("utf-8", errors="ignore")


async def extract_file_text(
    files: Optional[Sequence[UploadFile]],
    *,
    max_chars: int,
    tail_chars: int,
) -> str:
    file_context = ""

    for upload in files or []:
        try:
            filename = (upload.filename or "").lower()
            content = await upload.read()
            text = ""

            if filename.endswith(".pdf"):
                from pypdf import PdfReader

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

                text = docx2txt.process(io.BytesIO(content))
            elif filename.endswith(".doc"):
                text = _parse_doc_bytes(content)
            elif filename.endswith(".xlsx") or filename.endswith(".xls"):
                import pandas as pd

                excel_file = pd.ExcelFile(io.BytesIO(content))
                sheet_texts = [f"工作表: {name}" for name in excel_file.sheet_names]
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    sheet_texts.append(df.to_string(index=False))
                text = "\n\n".join(sheet_texts)
            elif filename.endswith(".csv"):
                import pandas as pd

                df = pd.read_csv(io.BytesIO(content), dtype=str, encoding_errors="ignore")
                text = "工作表: CSV\n" + df.to_csv(index=False)
            else:
                text = content.decode("utf-8", errors="ignore")

            if text:
                compacted = compact_file_text(text, max_chars=max_chars, tail_chars=tail_chars)
                file_context += f"\n文件 {upload.filename} 内容:\n{compacted}"
        except Exception as exc:
            print(f"[File parsing error] ({getattr(upload, 'filename', 'unknown')}): {exc}")

    return file_context
