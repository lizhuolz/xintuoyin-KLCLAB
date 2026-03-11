import json
import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime

# 路径定义
BASE_DIR = Path(__file__).parent.parent
DOCS_DIR = BASE_DIR.parent / "documents"
METADATA_FILE = BASE_DIR / "data" / "kb_metadata.json"
USER_JSON_FILE = BASE_DIR.parent / "user.json"

class KBService:
    def __init__(self):
        self._ensure_files()

    def _ensure_files(self):
        if not METADATA_FILE.exists():
            METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _get_user_info(self):
        """读取演示用户信息"""
        if USER_JSON_FILE.exists():
            try:
                with open(USER_JSON_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return {
            "name": "未知用户",
            "company": "未知公司",
            "department": "未知部门"
        }

    def load_all(self):
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            all_kb = json.load(f)
        
        for kb in all_kb:
            path = DOCS_DIR / kb["physical_path"]
            if path.exists():
                kb["fileCount"] = len([f for f in path.iterdir() if f.is_file()])
            else:
                kb["fileCount"] = 0
        return all_kb

    def save_all(self, data):
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_kb(self, name, model="openai", category="个人知识库"):
        """
        category: 根分类 (企业知识库 / 部门知识库 / 个人知识库)
        逻辑：自动根据用户信息插入二级目录
        """
        user = self._get_user_info()
        all_kb = self.load_all()
        kb_id = str(uuid.uuid4())[:8]
        
        # 1. 确定中间层级
        mid_folder = ""
        if "企业" in category:
            mid_folder = user.get("company", "通用公司")
        elif "部门" in category:
            mid_folder = user.get("department", "通用部门")
        else: # 个人级
            mid_folder = user.get("name", "访客")

        # 2. 处理物理文件夹名 (知识库名)
        safe_kb_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
        if not safe_kb_name: safe_kb_name = kb_id
        
        # 3. 构造物理路径：根分类 / 用户相关目录 / 知识库名
        physical_path = f"{category}/{mid_folder}/{safe_kb_name}"
        full_path = DOCS_DIR / physical_path
        
        # 防止物理路径冲突
        if full_path.exists():
            suffix = datetime.now().strftime("%H%M%S")
            physical_path = f"{category}/{mid_folder}/{safe_kb_name}_{suffix}"
            full_path = DOCS_DIR / physical_path

        full_path.mkdir(parents=True, exist_ok=True)

        new_kb = {
            "id": kb_id,
            "name": name,
            "model": model,
            "category": category, # 存储根分类
            "owner_info": f"{user.get('company')}/{user.get('department')}", # 记录创建时的背景
            "physical_path": physical_path,
            "remark": "",
            "users": [user.get("name")],
            "enabled": True,
            "updatedAt": datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        }
        all_kb.append(new_kb)
        self.save_all(all_kb)
        return new_kb

    def update_kb(self, kb_id, update_data):
        all_kb = self.load_all()
        for kb in all_kb:
            if kb["id"] == kb_id:
                for key in ["name", "remark", "users", "enabled"]:
                    if key in update_data:
                        kb[key] = update_data[key]
                kb["updatedAt"] = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
                self.save_all(all_kb)
                return kb
        return None

    def delete_kb(self, kb_id):
        all_kb = self.load_all()
        to_delete = next((k for k in all_kb if k["id"] == kb_id), None)
        if to_delete:
            full_path = DOCS_DIR / to_delete["physical_path"]
            if full_path.exists(): shutil.rmtree(full_path)
            all_kb = [k for k in all_kb if k["id"] != kb_id]
            self.save_all(all_kb)
            return True
        return False

    def list_files(self, kb_id):
        all_kb = self.load_all()
        kb = next((k for k in all_kb if k["id"] == kb_id), None)
        if not kb: return []
        full_path = DOCS_DIR / kb["physical_path"]
        if not full_path.exists(): return []
        return [{"name": f.name, "size": f"{f.stat().st_size/1024:.1f} KB"} for f in full_path.iterdir() if f.is_file()]

    def save_file(self, kb_id, file_obj):
        all_kb = self.load_all()
        kb = next((k for k in all_kb if k["id"] == kb_id), None)
        if not kb: return False
        target_dir = DOCS_DIR / kb["physical_path"]
        target_dir.mkdir(parents=True, exist_ok=True)
        with open(target_dir / file_obj.filename, "wb") as f:
            f.write(file_obj.file.read())
        return True

    def delete_file(self, kb_id, filename):
        all_kb = self.load_all()
        kb = next((k for k in all_kb if k["id"] == kb_id), None)
        if not kb: return False
        file_path = DOCS_DIR / kb["physical_path"] / filename
        if file_path.exists():
            os.remove(file_path)
            return True
        return False
