import os
import re
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


MAX_KB_FILE_TEXT_CHARS = int(os.getenv("KB_FILE_TEXT_MAX_CHARS", "40000"))


def compact_text(text: str, limit: int = MAX_KB_FILE_TEXT_CHARS) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(compact) <= limit:
        return compact
    return compact[:limit] + " ...(已截断)"


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


def extract_pdf_text(path: Path) -> str:
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
            return compact_text(result.stdout)
        except Exception:
            return ""
    return compact_text("\n".join(parts))


def extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            data = zf.read('word/document.xml')
    except Exception:
        return ''
    return compact_text("\n".join(_extract_text_nodes_from_xml(data)))


def extract_pptx_text(path: Path) -> str:
    texts = []
    try:
        with zipfile.ZipFile(path) as zf:
            for name in sorted(zf.namelist()):
                if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
                    texts.extend(_extract_text_nodes_from_xml(zf.read(name)))
    except Exception:
        return ''
    return compact_text("\n".join(texts))


def extract_xlsx_text(path: Path) -> str:
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
    return compact_text("\n".join(parts))


def extract_kb_file_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    try:
        if suffix in {'.txt', '.md', '.csv', '.json', '.py', '.log'}:
            return compact_text(file_path.read_text(encoding='utf-8', errors='ignore'))
        if suffix == '.pdf':
            return extract_pdf_text(file_path)
        if suffix == '.docx':
            return extract_docx_text(file_path)
        if suffix == '.pptx':
            return extract_pptx_text(file_path)
        if suffix == '.xlsx':
            return extract_xlsx_text(file_path)
        if suffix in {'.doc', '.xls', '.ppt'}:
            return '该文件为旧版 Office 二进制格式，当前服务暂不支持直接抽取正文，请转换为 docx/xlsx/pptx 后重试。'
        return '该文件类型暂不支持正文抽取，但文件已上传保存。'
    except Exception as exc:
        return f'文件解析失败：{exc}'
