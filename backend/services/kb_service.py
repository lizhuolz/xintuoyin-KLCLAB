import io
import json
import tempfile
from datetime import datetime
from pathlib import Path

from services.kb_file_parser import extract_kb_file_text
from services.milvus_service import build_milvus_service_from_env
from services.storage_service import storage_service

BASE_DIR = Path(__file__).parent.parent
METADATA_FILE = BASE_DIR / "data" / "kb_metadata.json"
USER_JSON_FILE = BASE_DIR.parent / "user.json"
DEFAULT_KB_CATEGORY = "知识库"


class KBService:
    def __init__(self):
        self._ensure_files()
        self.vector_service = build_milvus_service_from_env()

    def _ensure_files(self):
        METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not METADATA_FILE.exists():
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)

    def _ensure_storage_ready(self):
        storage_service.ensure_ready()

    def _get_user_info(self):
        if USER_JSON_FILE.exists():
            try:
                with open(USER_JSON_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "name": "未知用户",
            "company": "未知公司",
            "department": "未知部门",
            "phone": "",
            "record_id": "",
            "ip_address": "",
        }

    def _now_ms(self):
        return str(int(datetime.now().timestamp() * 1000))

    def _now_display(self):
        return datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    def _read_all_raw(self):
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_all_raw(self, data):
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _normalize_users(self, users):
        normalized = []
        for item in users or []:
            if isinstance(item, dict):
                normalized.append({
                    "name": item.get("name") or item.get("fullName") or "",
                    "phone": item.get("phone") or item.get("phones") or "",
                    "categoryName": item.get("categoryName") or item.get("company") or "",
                    "record_id": item.get("record_id") or item.get("recordId") or item.get("RecordID") or item.get("user_id") or "",
                    "ip_address": item.get("ip_address") or item.get("ip") or "",
                })
            else:
                normalized.append({
                    "name": str(item),
                    "phone": "",
                    "categoryName": "",
                    "record_id": "",
                    "ip_address": "",
                })
        return normalized

    def _sanitize_segment(self, value: str, default: str) -> str:
        safe = "".join(c for c in str(value or "") if c.isalnum() or c in (" ", "_", "-")).strip()
        return safe or default

    def _kb_prefix(self, kb):
        return f"documents/{kb.get('physical_path', '').strip('/')}"

    def _list_storage_objects(self, kb):
        prefix = self._kb_prefix(kb).rstrip("/") + "/"
        return storage_service.list_files(prefix)

    def _existing_paths(self, all_kb):
        return {item.get("physical_path", "") for item in all_kb}

    def _build_physical_path(self, *, name: str, user: dict, all_kb: list[dict]):
        owner = self._sanitize_segment(user.get("name", ""), "guest")
        kb_name = self._sanitize_segment(name, self._now_ms())
        base = f"{DEFAULT_KB_CATEGORY}/{owner}/{kb_name}"
        candidate = base
        suffix = 1
        existing = self._existing_paths(all_kb)
        while candidate in existing:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _format_kb(self, kb, files=None):
        file_items = files if files is not None else self._list_storage_objects(kb)
        file_count = len(file_items)
        return {
            "id": kb.get("id"),
            "name": kb.get("name", ""),
            "category": kb.get("category", DEFAULT_KB_CATEGORY),
            "model": kb.get("model", "openai"),
            "remark": kb.get("remark", ""),
            "enabled": bool(kb.get("enabled", True)),
            "users": self._normalize_users(kb.get("users", [])),
            "fileCount": file_count,
            "url": kb.get("physical_path", ""),
            "physical_path": kb.get("physical_path", ""),
            "owner_info": kb.get("owner_info", ""),
            "created_at": kb.get("created_at") or kb.get("updated_at") or "",
            "updated_at": kb.get("updated_at") or "",
            "createdAt": kb.get("createdAt") or kb.get("updatedAt") or "",
            "updatedAt": kb.get("updatedAt") or "",
        }

    def _extract_object_text(self, object_name: str, filename: str):
        suffix = Path(filename).suffix
        with tempfile.TemporaryDirectory(prefix="kb_sync_") as tmpdir:
            tmp_path = Path(tmpdir) / f"payload{suffix}"
            if not storage_service.download_file(object_name, str(tmp_path)):
                raise RuntimeError(f"从 MinIO 下载文件失败: {object_name}")
            return extract_kb_file_text(tmp_path)

    def _reindex_kb(self, kb):
        self.vector_service.delete_by_kb(kb.get("id", ""))
        all_records = []
        for obj in sorted(self._list_storage_objects(kb), key=lambda item: item["object_name"]):
            object_name = obj["object_name"]
            file_name = object_name.rsplit("/", 1)[-1]
            if not file_name:
                continue
            text = self._extract_object_text(object_name, file_name)
            rel_path = f"{kb.get('physical_path', '').rstrip('/')}/{file_name}"
            all_records.extend(
                self.vector_service.build_chunk_records(
                    kb=kb,
                    file_name=file_name,
                    rel_path=rel_path,
                    text=text,
                )
            )
        self.vector_service.upsert_records(all_records)

    def _current_file_items(self, kb):
        results = []
        for obj in sorted(self._list_storage_objects(kb), key=lambda item: item["last_modified"], reverse=True):
            object_name = obj["object_name"]
            filename = object_name.rsplit("/", 1)[-1]
            if not filename:
                continue
            uploaded_at = str(int(obj["last_modified"].timestamp() * 1000))
            results.append({
                "file_id": f"{kb.get('id')}:{filename}",
                "name": filename,
                "url": storage_service.get_presigned_url(object_name),
                "size": obj["size"],
                "uploaded_at": uploaded_at,
                "uploadedAt": obj["last_modified"].strftime("%Y/%m/%d %H:%M:%S"),
                "object_name": object_name,
            })
        return results

    def _build_unique_object_name(self, kb, original_name: str, reserved_names=None):
        safe_name = Path(original_name or "unnamed_file").name
        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix
        existing_names = set(reserved_names or [])
        if not existing_names:
            existing_names = {
                item["object_name"].rsplit("/", 1)[-1]
                for item in self._list_storage_objects(kb)
            }
        candidate = safe_name
        index = 1
        while candidate in existing_names:
            candidate = f"{stem}_{index}{suffix}"
            index += 1
        return f"{self._kb_prefix(kb)}/{candidate}", candidate

    def _build_upload_plan(self, kb, file_objs, delete_set=None):
        reserved_names = {item["name"] for item in self._current_file_items(kb)} - set(delete_set or set())
        upload_plan = []
        for file_obj in file_objs or []:
            object_name, final_name = self._build_unique_object_name(kb, file_obj.filename or "unnamed_file", reserved_names)
            reserved_names.add(final_name)
            upload_plan.append({
                "file_obj": file_obj,
                "object_name": object_name,
                "final_name": final_name,
            })
        return upload_plan

    def _apply_metadata_update(self, kb, update_data):
        updated_kb = dict(kb)
        for key in ["name", "remark", "users", "enabled"]:
            if key in update_data:
                updated_kb[key] = update_data[key]
        updated_kb.setdefault("category", DEFAULT_KB_CATEGORY)
        updated_kb["updated_at"] = self._now_ms()
        updated_kb["updatedAt"] = self._now_display()
        return updated_kb

    def _build_update_preview(self, kb, update_data, upload_plan, delete_files):
        current_files = self.list_files(kb.get("id"))
        delete_set = set(delete_files or [])
        preview_files = [item for item in current_files if item["name"] not in delete_set]
        preview_files.extend({
            "file_id": f"pending:{plan['final_name']}",
            "name": plan["final_name"],
            "url": "",
            "size": 0,
            "uploaded_at": "",
            "uploadedAt": "待提交",
        } for plan in upload_plan)
        preview_kb = self._apply_metadata_update(kb, update_data)
        formatted = self._format_kb(preview_kb, files=[{"object_name": item["name"], "size": item.get("size", 0), "last_modified": datetime.now()} for item in preview_files])
        formatted["files"] = preview_files
        formatted["pending"] = {
            "delete_files": list(delete_files or []),
            "upload_files": [plan["final_name"] for plan in upload_plan],
            "metadata": {key: value for key, value in update_data.items()},
            "confirm_required": True,
        }
        formatted["preview"] = True
        return formatted

    def load_all(self):
        self._ensure_storage_ready()
        return [self._format_kb(item) for item in self._read_all_raw()]

    def save_all(self, data):
        self._write_all_raw(data)

    def create_kb(self, name, model="openai"):
        self._ensure_storage_ready()
        user = self._get_user_info()
        all_kb = self._read_all_raw()
        kb_id = f"kb_{self._now_ms()}"
        now_ms = self._now_ms()
        now_display = self._now_display()
        new_kb = {
            "id": kb_id,
            "name": name,
            "model": model,
            "category": DEFAULT_KB_CATEGORY,
            "owner_info": f"{user.get('company', '')}/{user.get('department', '')}",
            "physical_path": self._build_physical_path(name=name, user=user, all_kb=all_kb),
            "remark": "",
            "users": [{
                "name": user.get("name", ""),
                "phone": user.get("phone", ""),
                "categoryName": user.get("company", ""),
                "record_id": user.get("record_id") or user.get("RecordID") or user.get("user_id") or "",
                "ip_address": user.get("ip_address", ""),
            }],
            "enabled": True,
            "created_at": now_ms,
            "updated_at": now_ms,
            "createdAt": now_display,
            "updatedAt": now_display,
        }
        all_kb.append(new_kb)
        self._write_all_raw(all_kb)
        return self._format_kb(new_kb)

    def get_kb(self, kb_id):
        for kb in self._read_all_raw():
            if kb.get("id") == kb_id:
                kb.setdefault("category", DEFAULT_KB_CATEGORY)
                return kb
        return None

    def get_kb_detail(self, kb_id):
        self._ensure_storage_ready()
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        formatted = self._format_kb(kb)
        formatted["files"] = self.list_files(kb_id)
        return formatted

    def update_kb(self, kb_id, update_data, new_files=None, delete_filenames=None, confirm=True):
        self._ensure_storage_ready()
        all_kb = self._read_all_raw()
        match_index = next((index for index, item in enumerate(all_kb) if item.get("id") == kb_id), None)
        if match_index is None:
            return None

        kb = dict(all_kb[match_index])
        delete_files = [Path(name).name for name in (delete_filenames or []) if str(name).strip()]
        upload_plan = self._build_upload_plan(kb, new_files or [], set(delete_files))
        if not confirm:
            return self._build_update_preview(kb, update_data, upload_plan, delete_files)

        original_all_kb = list(all_kb)
        original_kb = dict(kb)
        deleted_backups = []
        uploaded_objects = []
        try:
            prefix = self._kb_prefix(kb)
            current_files = {item["name"]: item for item in self._current_file_items(kb)}
            for filename in delete_files:
                current = current_files.get(filename)
                if not current:
                    continue
                object_name = current["object_name"]
                backup_bytes = storage_service.read_file_bytes(object_name)
                deleted_backups.append({
                    "filename": filename,
                    "object_name": object_name,
                    "content": backup_bytes,
                })
                if not storage_service.delete_file(object_name):
                    raise RuntimeError(f"删除知识库文件失败: {filename}")

            for plan in upload_plan:
                file_obj = plan["file_obj"]
                object_name = plan["object_name"]
                if not storage_service.upload_file_obj(
                    file_obj.file,
                    object_name,
                    getattr(file_obj, "content_type", "application/octet-stream"),
                ):
                    raise RuntimeError(f"上传知识库文件到 MinIO 失败: {object_name}")
                uploaded_objects.append(object_name)

            updated_kb = self._apply_metadata_update(kb, update_data)
            all_kb[match_index] = updated_kb
            self._write_all_raw(all_kb)
            self._reindex_kb(updated_kb)
            result = self._format_kb(updated_kb)
            result["files"] = self.list_files(kb_id)
            result["preview"] = False
            result["pending"] = {
                "delete_files": delete_files,
                "upload_files": [plan["final_name"] for plan in upload_plan],
                "metadata": {key: value for key, value in update_data.items()},
                "confirm_required": False,
            }
            return result
        except Exception:
            for object_name in uploaded_objects:
                storage_service.delete_file(object_name)
            for backup in deleted_backups:
                storage_service.upload_file_obj(
                    io.BytesIO(backup["content"]),
                    backup["object_name"],
                    "application/octet-stream",
                )
            self._write_all_raw(original_all_kb)
            try:
                self._reindex_kb(original_kb)
            except Exception:
                pass
            raise

    def delete_kb(self, kb_id):
        self._ensure_storage_ready()
        all_kb = self._read_all_raw()
        target = next((item for item in all_kb if item.get("id") == kb_id), None)
        if not target:
            return None
        prefix = self._kb_prefix(target).rstrip("/") + "/"
        if not storage_service.delete_files_by_prefix(prefix):
            raise RuntimeError(f"删除 MinIO 知识库目录失败: {prefix}")
        self.vector_service.delete_by_kb(kb_id)
        remain = [item for item in all_kb if item.get("id") != kb_id]
        self._write_all_raw(remain)
        return self._format_kb(target)

    def list_files(self, kb_id):
        self._ensure_storage_ready()
        kb = self.get_kb(kb_id)
        if not kb:
            return []
        items = self._current_file_items(kb)
        for item in items:
            item.pop("object_name", None)
        return items

    def save_files(self, kb_id, file_objs):
        return self.update_kb(kb_id, {}, new_files=file_objs, delete_filenames=[], confirm=True)

    def save_file(self, kb_id, file_obj):
        result = self.save_files(kb_id, [file_obj])
        return bool(result is not None)

    def delete_files(self, kb_id, filenames):
        result = self.update_kb(kb_id, {}, new_files=[], delete_filenames=filenames, confirm=True)
        if result is None:
            return None
        return [Path(name).name for name in filenames or []]

    def delete_file(self, kb_id, filename):
        result = self.delete_files(kb_id, [filename])
        return bool(result)
