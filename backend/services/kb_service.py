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
        return {"name": "未知用户", "company": "未知公司", "department": "未知部门", "phone": ""}

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
                })
            else:
                normalized.append({"name": str(item), "phone": "", "categoryName": ""})
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

    def _build_physical_path(self, *, category: str, name: str, user: dict, all_kb: list[dict]):
        scope = "基础知识库" if "基础" in category else "用户知识库"
        owner = self._sanitize_segment(user.get("name", ""), "guest")
        kb_name = self._sanitize_segment(name, self._now_ms())
        base = f"{scope}/{kb_name}" if scope == "基础知识库" else f"{scope}/{owner}/{kb_name}"
        candidate = base
        suffix = 1
        existing = self._existing_paths(all_kb)
        while candidate in existing:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _format_kb(self, kb):
        file_count = len(self._list_storage_objects(kb))
        return {
            "id": kb.get("id"),
            "name": kb.get("name", ""),
            "category": kb.get("category", ""),
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

    def _sync_file_to_vector_store(self, kb, file_name: str, object_name: str):
        text = self._extract_object_text(object_name, file_name)
        rel_path = f"{kb.get('physical_path', '').rstrip('/')}/{file_name}"
        self.vector_service.delete_by_files(kb.get("id", ""), [file_name])
        records = self.vector_service.build_chunk_records(
            kb=kb,
            file_name=file_name,
            rel_path=rel_path,
            text=text,
        )
        self.vector_service.upsert_records(records)

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

    def _build_unique_object_name(self, kb, original_name: str):
        safe_name = Path(original_name or "unnamed_file").name
        stem = Path(safe_name).stem
        suffix = Path(safe_name).suffix
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

    def load_all(self):
        self._ensure_storage_ready()
        return [self._format_kb(item) for item in self._read_all_raw()]

    def save_all(self, data):
        self._write_all_raw(data)

    def create_kb(self, name, model="openai", category="个人知识库"):
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
            "category": category,
            "owner_info": f"{user.get('company', '')}/{user.get('department', '')}",
            "physical_path": self._build_physical_path(category=category, name=name, user=user, all_kb=all_kb),
            "remark": "",
            "users": [{
                "name": user.get("name", ""),
                "phone": user.get("phone", ""),
                "categoryName": user.get("company", ""),
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

    def update_kb(self, kb_id, update_data):
        self._ensure_storage_ready()
        all_kb = self._read_all_raw()
        for index, kb in enumerate(all_kb):
            if kb.get("id") != kb_id:
                continue
            updated_kb = dict(kb)
            for key in ["name", "remark", "users", "enabled"]:
                if key in update_data:
                    updated_kb[key] = update_data[key]
            updated_kb["updated_at"] = self._now_ms()
            updated_kb["updatedAt"] = self._now_display()
            if any(key in update_data for key in ["name", "users", "enabled"]):
                self._reindex_kb(updated_kb)
            all_kb[index] = updated_kb
            self._write_all_raw(all_kb)
            return self._format_kb(updated_kb)
        return None

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
        results = []
        for obj in sorted(self._list_storage_objects(kb), key=lambda item: item["last_modified"], reverse=True):
            object_name = obj["object_name"]
            filename = object_name.rsplit("/", 1)[-1]
            if not filename:
                continue
            uploaded_at = str(int(obj["last_modified"].timestamp() * 1000))
            results.append({
                "file_id": f"{kb_id}:{filename}",
                "name": filename,
                "url": storage_service.get_presigned_url(object_name),
                "size": obj["size"],
                "uploaded_at": uploaded_at,
                "uploadedAt": obj["last_modified"].strftime("%Y/%m/%d %H:%M:%S"),
            })
        return results

    def save_files(self, kb_id, file_objs):
        self._ensure_storage_ready()
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        uploaded_objects = []
        try:
            for file_obj in file_objs or []:
                object_name, final_name = self._build_unique_object_name(kb, file_obj.filename or "unnamed_file")
                if not storage_service.upload_file_obj(
                    file_obj.file,
                    object_name,
                    getattr(file_obj, "content_type", "application/octet-stream"),
                ):
                    raise RuntimeError(f"上传知识库文件到 MinIO 失败: {object_name}")
                self._sync_file_to_vector_store(kb, final_name, object_name)
                uploaded_objects.append(object_name)
            if uploaded_objects:
                self.update_kb(kb_id, {})
            return self.list_files(kb_id)
        except Exception:
            for object_name in uploaded_objects:
                storage_service.delete_file(object_name)
            raise

    def save_file(self, kb_id, file_obj):
        result = self.save_files(kb_id, [file_obj])
        return bool(result is not None)

    def delete_files(self, kb_id, filenames):
        self._ensure_storage_ready()
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        deleted = []
        prefix = self._kb_prefix(kb)
        for filename in filenames or []:
            safe_name = Path(filename).name
            object_name = f"{prefix}/{safe_name}"
            if storage_service.delete_file(object_name):
                deleted.append(safe_name)
        if deleted:
            self.vector_service.delete_by_files(kb_id, deleted)
            self.update_kb(kb_id, {})
        return deleted

    def delete_file(self, kb_id, filename):
        result = self.delete_files(kb_id, [filename])
        return bool(result)
