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

class KBService:
    def __init__(self):
        self._ensure_files()

    def _ensure_files(self):
        if not METADATA_FILE.exists():
            METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(METADATA_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)

    def load_all(self):
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            all_kb = json.load(f)
        
        # 实时统计文件数量
        for kb in all_kb:
            path = DOCS_DIR / kb["physical_path"]
            if path.exists():
                # 只计算文件，排除文件夹
                kb["fileCount"] = len([f for f in path.iterdir() if f.is_file()])
            else:
                kb["fileCount"] = 0
        return all_kb

    def save_all(self, data):
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create_kb(self, name, model="openai", category="个人知识库/访客"):
        """
        category 决定了它在 documents/ 下的物理路径
        例如: 企业知识库, 部门知识库/技术部, 个人知识库/员工A1
        文件夹名直接使用知识库名称，更直观
        """
        all_kb = self.load_all()
        kb_id = str(uuid.uuid4())[:8]
        
        # 处理物理文件夹名：isalnum() 在 Python3 中包含中文
        safe_folder_name = "".join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip()
        if not safe_folder_name:
            safe_folder_name = kb_id
        
        # 物理路径
        physical_path = f"{category}/{safe_folder_name}"
        full_path = DOCS_DIR / physical_path
        
        # 如果重名，加上时间戳防冲突
        if full_path.exists():
            suffix = datetime.now().strftime("%H%M%S")
            physical_path = f"{category}/{safe_folder_name}_{suffix}"
            full_path = DOCS_DIR / physical_path

        full_path.mkdir(parents=True, exist_ok=True)

        new_kb = {
            "id": kb_id,
            "name": name,
            "model": model,
            "category": category,
            "physical_path": physical_path,
            "remark": "",
            "users": [],
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
                # 只允许更新部分字段
                for key in ["name", "remark", "users", "enabled"]:
                    if key in update_data:
                        kb[key] = update_data[key]
                kb["updatedAt"] = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
                self.save_all(all_kb)
                return kb
        return None

    def delete_kb(self, kb_id):
        all_kb = self.load_all()
        to_delete = None
        for kb in all_kb:
            if kb["id"] == kb_id:
                to_delete = kb
                break
        
        if to_delete:
            # 1. 物理删除文件
            full_path = DOCS_DIR / to_delete["physical_path"]
            if full_path.exists():
                shutil.rmtree(full_path)
            
            # 2. 删除元数据
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
        
        files = []
        for f in full_path.iterdir():
            if f.is_file():
                stats = f.stat()
                files.append({
                    "name": f.name,
                    "size": f"{stats.st_size / 1024:.1f} KB"
                })
        return files

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
