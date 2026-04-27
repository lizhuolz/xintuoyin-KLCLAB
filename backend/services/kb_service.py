import io
import json
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from config import KB_METADATA_FILE as METADATA_FILE, get_user_profile, now_ms, now_display
from services.kb_file_parser import extract_kb_file_text
from services.milvus_service import build_milvus_service_from_env
from services.storage_service import storage_service

logger = logging.getLogger(__name__)
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

    def _read_all_raw(self):
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write_all_raw(self, data):
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _normalize_users(self, users, creator_staff_id=None):
        normalized = []
        for item in users or []:
            if isinstance(item, dict):
                staff_id = item.get("staffId") or item.get("staff_id") or None
                normalized.append({
                    "staffId": staff_id,
                    "name": item.get("name") or item.get("fullName") or "",
                    "phone": item.get("phone") or item.get("phones") or "",
                    "categoryName": item.get("categoryName") or item.get("company") or "",
                    "record_id": item.get("record_id") or item.get("recordId") or item.get("RecordID") or "",
                    "ip_address": item.get("ip_address") or item.get("ip") or "",
                    "is_creator": creator_staff_id is not None and str(staff_id) == str(creator_staff_id),
                })
            else:
                normalized.append({
                    "staffId": None,
                    "name": str(item),
                    "phone": "",
                    "categoryName": "",
                    "record_id": "",
                    "ip_address": "",
                    "is_creator": False,
                })
        return normalized

    def _sanitize_segment(self, value: str, default: str) -> str:
        safe = "".join(c for c in str(value or "") if c.isalnum() or c in (" ", "_", "-")).strip()
        return safe or default

    def _kb_prefix(self, kb):
        return f"kb/{kb.get('physical_path', '').strip('/')}"

    def _list_storage_objects(self, kb):
        prefix = self._kb_prefix(kb).rstrip("/") + "/"
        return storage_service.list_files(prefix)

    def _existing_paths(self, all_kb):
        return {item.get("physical_path", "") for item in all_kb}

    def _build_physical_path(self, *, name: str, all_kb: list[dict]):
        date = datetime.now().strftime("%Y-%m-%d")
        kb_name = self._sanitize_segment(name, now_ms())
        base = f"{date}/{kb_name}"
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
        # 老数据没有 creator_staff_id 字段时，回退到 users[0]（历史约定第 0 个是创建者）
        creator_staff_id = kb.get("creator_staff_id")
        if not creator_staff_id:
            users_raw = kb.get("users") or []
            if users_raw and isinstance(users_raw[0], dict):
                creator_staff_id = users_raw[0].get("staffId") or users_raw[0].get("staff_id")
        return {
            "id": kb.get("id"),
            "name": kb.get("name", ""),
            "category": kb.get("category", DEFAULT_KB_CATEGORY),
            "model": kb.get("model", "openai"),
            "remark": kb.get("remark", ""),
            "enabled": bool(kb.get("enabled", True)),
            "users": self._normalize_users(kb.get("users", []), creator_staff_id),
            "creator_staff_id": creator_staff_id,
            "tenant_id": kb.get("tenant_id"),
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

    def _build_upload_plan(self, kb, file_infos, delete_set=None):
        reserved_names = {item["name"] for item in self._current_file_items(kb)} - set(delete_set or set())
        upload_plan = []
        for fi in file_infos or []:
            object_name, final_name = self._build_unique_object_name(kb, fi["filename"] or "unnamed_file", reserved_names)
            reserved_names.add(final_name)
            upload_plan.append({
                "staging_object": fi["staging_object"],
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
        # 强制保留创建者：如果新 users 不含 creator，把原 users 里的 creator 条目补回去
        if "users" in update_data and kb.get("creator_staff_id") is not None:
            creator_id = str(kb["creator_staff_id"])
            new_users = list(updated_kb.get("users") or [])
            has_creator = any(
                isinstance(u, dict) and str(u.get("staffId") or u.get("staff_id") or "") == creator_id
                for u in new_users
            )
            if not has_creator:
                creator_entry = next(
                    (u for u in (kb.get("users") or [])
                     if isinstance(u, dict)
                     and str(u.get("staffId") or u.get("staff_id") or "") == creator_id),
                    None,
                )
                if creator_entry is not None:
                    new_users.insert(0, creator_entry)
                    updated_kb["users"] = new_users
        updated_kb["updated_at"] = now_ms()
        updated_kb["updatedAt"] = now_display()
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

    def load_all(self, category=None, tenant_id=None):
        """加载知识库列表。
        tenant_id=None 时不过滤（管理端使用）；
        tenant_id 有值时：基础知识库全部返回；普通知识库仅返回 tenant_id 匹配的。
        """
        self._ensure_storage_ready()
        items = self._read_all_raw()
        if category:
            items = [item for item in items if item.get("category") == category]
        if tenant_id is not None:
            str_tid = str(tenant_id)
            items = [
                item for item in items
                if item.get("category") == "基础知识库"
                or str(item.get("tenant_id") or "") == str_tid
            ]
        items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return [self._format_kb(item) for item in items]

    def save_all(self, data):
        self._write_all_raw(data)

    def create_kb(self, name, model="openai", user=None, category=None):
        self._ensure_storage_ready()
        user = user or get_user_profile()
        is_base = category == "基础知识库"
        all_kb = self._read_all_raw()
        ts_ms = now_ms()
        ts_display = now_display()
        kb_id = f"kb_{ts_ms}"
        creator_staff_id = user.get("staff_id") or user.get("staffId") or None
        tenant_id = user.get("tenant_id") if not is_base else None
        new_kb = {
            "id": kb_id,
            "name": name,
            "model": model,
            "category": "基础知识库" if is_base else DEFAULT_KB_CATEGORY,
            "owner_info": f"{user.get('company', '')}/{user.get('department', '')}",
            "physical_path": self._build_physical_path(name=name, all_kb=all_kb),
            "remark": "",
            "creator_staff_id": creator_staff_id,
            "tenant_id": tenant_id,
            "users": [] if is_base else [{
                "staffId": creator_staff_id,
                "name": user.get("name", ""),
                "phone": user.get("phone", ""),
                "categoryName": user.get("company", ""),
                "record_id": user.get("record_id") or user.get("RecordID") or "",
                "ip_address": user.get("ip_address", ""),
            }],
            "enabled": True,
            "created_at": ts_ms,
            "updated_at": ts_ms,
            "createdAt": ts_display,
            "updatedAt": ts_display,
        }
        all_kb.append(new_kb)
        self._write_all_raw(all_kb)
        return self._format_kb(new_kb)

    def toggle_enabled(self, kb_id: str, enabled: bool):
        all_kb = self._read_all_raw()
        for kb in all_kb:
            if kb.get("id") == kb_id:
                kb["enabled"] = enabled
                kb["updated_at"] = now_ms()
                kb["updatedAt"] = now_display()
                self._write_all_raw(all_kb)
                self.vector_service.update_enabled(kb_id, enabled)
                return self._format_kb(kb)
        return None

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

    def update_kb(self, kb_id, update_data, new_file_infos=None, delete_filenames=None, confirm=True):
        self._ensure_storage_ready()
        all_kb = self._read_all_raw()
        match_index = next((index for index, item in enumerate(all_kb) if item.get("id") == kb_id), None)
        if match_index is None:
            return None

        kb = dict(all_kb[match_index])
        delete_files = [Path(name).name for name in (delete_filenames or []) if str(name).strip()]
        upload_plan = self._build_upload_plan(kb, new_file_infos or [], set(delete_files))
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
                staging_obj = plan["staging_object"]
                object_name = plan["object_name"]
                if not storage_service.move_object(staging_obj, object_name):
                    raise RuntimeError(f"移动知识库文件失败: {object_name}")
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

    def save_files(self, kb_id, file_infos):
        return self.update_kb(kb_id, {}, new_file_infos=file_infos, delete_filenames=[], confirm=True)

    def save_file(self, kb_id, file_obj):
        result = self.save_files(kb_id, [file_obj])
        return bool(result is not None)

    def delete_files(self, kb_id, filenames):
        kb = self.get_kb(kb_id)
        if kb is None:
            return None
        normalized = [Path(name).name for name in filenames or []]
        existing_names = {item["name"] for item in self.list_files(kb_id)}
        delete_targets = [name for name in normalized if name in existing_names]
        result = self.update_kb(kb_id, {}, new_file_infos=[], delete_filenames=delete_targets, confirm=True)
        if result is None:
            return None
        return delete_targets

    def delete_file(self, kb_id, filename):
        result = self.delete_files(kb_id, [filename])
        return bool(result)
