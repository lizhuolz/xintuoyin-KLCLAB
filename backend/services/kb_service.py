import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

BASE_DIR = Path(__file__).parent.parent
DOCS_DIR = BASE_DIR.parent / "documents"
METADATA_FILE = BASE_DIR / "data" / "kb_metadata.json"


class KBService:
    def __init__(self):
        self._ensure_files()

    def _ensure_files(self):
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        if not METADATA_FILE.exists():
            METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _read_metadata(self) -> List[Dict[str, Any]]:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("知识库元数据格式错误")
        return data

    def _find_kb(
        self,
        kb_id: str,
        all_kb: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        records = all_kb if all_kb is not None else self.load_all()
        return next((kb for kb in records if kb.get("id") == kb_id), None)

    @staticmethod
    def _safe_filename(filename: str) -> str:
        cleaned = Path((filename or "").strip()).name
        if not cleaned or cleaned in {".", ".."}:
            raise ValueError("文件名不能为空")
        return cleaned

    def get_kb(self, kb_id: str) -> Optional[Dict[str, Any]]:
        return self._find_kb(kb_id, self.load_all())

    def load_all(self):
        all_kb = self._read_metadata()
        for kb in all_kb:
            path = DOCS_DIR / kb["physical_path"]
            kb["fileCount"] = len([f for f in path.iterdir() if f.is_file()]) if path.exists() else 0
        return all_kb

    def save_all(self, data):
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_kb(self, name, model="openai", category="个人知识库/访客"):
        clean_name = (name or "").strip()
        clean_category = (category or "").strip()
        if not clean_name:
            raise ValueError("知识库名称不能为空")
        if not clean_category:
            raise ValueError("知识库分类不能为空")

        all_kb = self.load_all()
        kb_id = str(uuid.uuid4())[:8]
        safe_folder_name = "".join(c for c in clean_name if c.isalnum() or c in (" ", "_", "-")) .strip()
        if not safe_folder_name:
            safe_folder_name = kb_id

        physical_path = f"{clean_category}/{safe_folder_name}"
        full_path = DOCS_DIR / physical_path
        if full_path.exists():
            suffix = datetime.now().strftime("%H%M%S")
            physical_path = f"{clean_category}/{safe_folder_name}_{suffix}"
            full_path = DOCS_DIR / physical_path

        full_path.mkdir(parents=True, exist_ok=True)
        new_kb = {
            "id": kb_id,
            "name": clean_name,
            "model": model,
            "category": clean_category,
            "physical_path": physical_path,
            "remark": "",
            "users": [],
            "enabled": True,
            "updatedAt": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        }
        all_kb.append(new_kb)
        self.save_all(all_kb)
        return new_kb

    def update_kb(self, kb_id, update_data):
        all_kb = self.load_all()
        kb = self._find_kb(kb_id, all_kb)
        if kb:
            for key in ["name", "remark", "users", "enabled"]:
                if key in update_data:
                    kb[key] = update_data[key]
            kb["updatedAt"] = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            self.save_all(all_kb)
            return kb
        return None

    def delete_kb(self, kb_id):
        all_kb = self.load_all()
        to_delete = self._find_kb(kb_id, all_kb)
        if to_delete:
            full_path = DOCS_DIR / to_delete["physical_path"]
            if full_path.exists():
                shutil.rmtree(full_path)
            all_kb = [k for k in all_kb if k["id"] != kb_id]
            self.save_all(all_kb)
            return True
        return False

    def list_files(self, kb_id):
        all_kb = self.load_all()
        kb = self._find_kb(kb_id, all_kb)
        if not kb:
            return []

        full_path = DOCS_DIR / kb["physical_path"]
        if not full_path.exists():
            return []

        files = []
        for file_path in full_path.iterdir():
            if file_path.is_file():
                stats = file_path.stat()
                files.append({"name": file_path.name, "size": f"{stats.st_size / 1024:.1f} KB"})
        return files

    def save_files(self, kb_id: str, file_objs: Iterable[Any]) -> List[str]:
        all_kb = self.load_all()
        kb = self._find_kb(kb_id, all_kb)
        if not kb:
            return []

        target_dir = DOCS_DIR / kb["physical_path"]
        target_dir.mkdir(parents=True, exist_ok=True)

        saved_names: List[str] = []
        for file_obj in file_objs:
            safe_name = self._safe_filename(getattr(file_obj, "filename", ""))
            content = file_obj.file.read()
            with open(target_dir / safe_name, "wb") as f:
                f.write(content)
            saved_names.append(safe_name)
        return saved_names

    def save_file(self, kb_id, file_obj):
        saved = self.save_files(kb_id, [file_obj])
        return saved[0] if saved else False

    def delete_file(self, kb_id, filename):
        all_kb = self.load_all()
        kb = self._find_kb(kb_id, all_kb)
        if not kb:
            return False

        safe_name = self._safe_filename(filename)
        file_path = DOCS_DIR / kb["physical_path"] / safe_name
        if file_path.exists():
            os.remove(file_path)
            return True
        return False
