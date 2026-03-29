import json
import os
import shutil
from pathlib import Path
from datetime import datetime
from services.storage_service import storage_service

# 路径定义
BASE_DIR = Path(__file__).parent.parent
DOCS_DIR = BASE_DIR.parent / "documents"
METADATA_FILE = BASE_DIR / "data" / "kb_metadata.json"
USER_JSON_FILE = BASE_DIR.parent / "user.json"


class KBService:
    def __init__(self):
        self._ensure_files()

    def _ensure_files(self):
        METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not METADATA_FILE.exists():
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        # 本地 DOCS_DIR 依然保留，用于存放元数据或临时缓存，但实际文件将存入 MinIO

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
            "phone": ""
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
                    "categoryName": item.get("categoryName") or item.get("company") or ""
                })
            else:
                normalized.append({"name": str(item), "phone": "", "categoryName": ""})
        return normalized

    def _format_kb(self, kb):
        # 统计 MinIO 中的文件数量
        prefix = f"documents/{kb.get('physical_path', '')}/"
        minio_files = storage_service.list_files(prefix)
        file_count = len(minio_files)
        
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
            "updatedAt": kb.get("updatedAt") or ""
        }

    def load_all(self):
        return [self._format_kb(item) for item in self._read_all_raw()]

    def save_all(self, data):
        self._write_all_raw(data)

    def create_kb(self, name, model="openai", category="个人知识库"):
        user = self._get_user_info()
        all_kb = self._read_all_raw()
        kb_id = f"kb_{self._now_ms()}"

        # 核心逻辑变更：不再区分企业/部门等级，除基础库外全部扁平化
        if "基础" in category:
            category_folder = "基础知识库"
        else:
            category_folder = "用户知识库"

        safe_name = "".join([c for c in name if c.isalnum() or c in (" ", "_", "-")]).strip() or kb_id
        # 物理路径简化为：分类/知识库名
        physical_path = f"{category_folder}/{safe_name}"
        
        # 检查物理前缀冲突 (MinIO 是虚拟目录，我们通过 metadata 检查)
        now_ms = self._now_ms()
        now_display = self._now_display()
        new_kb = {
            "id": kb_id,
            "name": name,
            "model": model,
            "category": category,
            "owner_info": user.get("name", "未知用户"), # 仅记录创建者
            "physical_path": physical_path,
            "remark": "",
            "users": [{
                "name": user.get("name", ""),
                "phone": user.get("phone", ""),
                "categoryName": user.get("company", "")
            }],
            "enabled": True,
            "created_at": now_ms,
            "updated_at": now_ms,
            "createdAt": now_display,
            "updatedAt": now_display
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
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        formatted = self._format_kb(kb)
        formatted["files"] = self.list_files(kb_id)
        return formatted

    def update_kb(self, kb_id, update_data):
        all_kb = self._read_all_raw()
        for kb in all_kb:
            if kb.get("id") == kb_id:
                for key in ["name", "remark", "users", "enabled"]:
                    if key in update_data:
                        kb[key] = update_data[key]
                kb["updated_at"] = self._now_ms()
                kb["updatedAt"] = self._now_display()
                self._write_all_raw(all_kb)
                return self._format_kb(kb)
        return None

    def delete_kb(self, kb_id):
        all_kb = self._read_all_raw()
        target = next((item for item in all_kb if item.get("id") == kb_id), None)
        if not target:
            return None
        
        # 删除 MinIO 中的物理文件
        prefix = f"documents/{target.get('physical_path', '')}/"
        storage_service.delete_files_by_prefix(prefix)
        
        remain = [item for item in all_kb if item.get("id") != kb_id]
        self._write_all_raw(remain)
        return self._format_kb(target)

    def list_files(self, kb_id):
        kb = self.get_kb(kb_id)
        if not kb:
            return []
        
        prefix = f"documents/{kb.get('physical_path', '')}/"
        minio_files = storage_service.list_files(prefix)
        
        results = []
        for obj in sorted(minio_files, key=lambda x: x['last_modified'], reverse=True):
            obj_name = obj['object_name']
            filename = obj_name.split('/')[-1]
            if not filename: continue
            
            uploaded_at = str(int(obj['last_modified'].timestamp() * 1000))
            results.append({
                "file_id": f"{kb_id}:{filename}",
                "name": filename,
                "url": storage_service.get_presigned_url(obj_name),
                "size": obj['size'],
                "uploaded_at": uploaded_at,
                "uploadedAt": obj['last_modified'].strftime("%Y/%m/%d %H:%M:%S")
            })
        return results

    def save_files(self, kb_id, file_objs):
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        
        base_prefix = f"documents/{kb.get('physical_path', '')}"
        saved = []
        for file_obj in file_objs or []:
            original_name = Path(file_obj.filename or "unnamed_file").name
            # 这里简单处理，如果重名直接覆盖或加时间戳（MinIO 覆盖是默认行为）
            object_name = f"{base_prefix}/{original_name}"
            
            # 流式上传到 MinIO
            if storage_service.upload_file_obj(file_obj.file, object_name, getattr(file_obj, 'content_type', 'application/octet-stream')):
                saved.append(original_name)
        
        if saved:
            self.update_kb(kb_id, {})
        return self.list_files(kb_id)

    def save_file(self, kb_id, file_obj):
        result = self.save_files(kb_id, [file_obj])
        return bool(result is not None)

    def delete_files(self, kb_id, filenames):
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        
        base_prefix = f"documents/{kb.get('physical_path', '')}"
        deleted = []
        for filename in filenames or []:
            safe_name = Path(filename).name
            object_name = f"{base_prefix}/{safe_name}"
            if storage_service.delete_file(object_name):
                deleted.append(safe_name)
        
        if deleted:
            self.update_kb(kb_id, {})
        return deleted

    def delete_file(self, kb_id, filename):
        result = self.delete_files(kb_id, [filename])
        return bool(result)
