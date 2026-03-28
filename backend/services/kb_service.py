import json
import os
import shutil
from pathlib import Path
from datetime import datetime

from services.kb_file_parser import extract_kb_file_text
from services.milvus_service import MilvusNotReadyError, build_milvus_service_from_env

BASE_DIR = Path(__file__).parent.parent
DOCS_DIR = BASE_DIR.parent / 'documents'
METADATA_FILE = BASE_DIR / 'data' / 'kb_metadata.json'
USER_JSON_FILE = BASE_DIR.parent / 'user.json'


class KBService:
    def __init__(self):
        self._ensure_files()
        self.vector_service = build_milvus_service_from_env()

    def _ensure_files(self):
        METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not METADATA_FILE.exists():
            with open(METADATA_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        DOCS_DIR.mkdir(parents=True, exist_ok=True)

    def _get_user_info(self):
        if USER_JSON_FILE.exists():
            try:
                with open(USER_JSON_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {'name': '未知用户', 'company': '未知公司', 'department': '未知部门', 'phone': ''}

    def _now_ms(self):
        return str(int(datetime.now().timestamp() * 1000))

    def _now_display(self):
        return datetime.now().strftime('%Y/%m/%d %H:%M:%S')

    def _read_all_raw(self):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _write_all_raw(self, data):
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _normalize_users(self, users):
        normalized = []
        for item in users or []:
            if isinstance(item, dict):
                normalized.append({
                    'name': item.get('name') or item.get('fullName') or '',
                    'phone': item.get('phone') or item.get('phones') or '',
                    'categoryName': item.get('categoryName') or item.get('company') or ''
                })
            else:
                normalized.append({'name': str(item), 'phone': '', 'categoryName': ''})
        return normalized

    def _format_kb(self, kb):
        full_path = DOCS_DIR / kb.get('physical_path', '')
        file_count = 0
        if full_path.exists():
            file_count = len([f for f in full_path.iterdir() if f.is_file()])
        return {
            'id': kb.get('id'),
            'name': kb.get('name', ''),
            'category': kb.get('category', ''),
            'model': kb.get('model', 'openai'),
            'remark': kb.get('remark', ''),
            'enabled': bool(kb.get('enabled', True)),
            'users': self._normalize_users(kb.get('users', [])),
            'fileCount': file_count,
            'url': kb.get('physical_path', ''),
            'physical_path': kb.get('physical_path', ''),
            'owner_info': kb.get('owner_info', ''),
            'created_at': kb.get('created_at') or kb.get('updated_at') or '',
            'updated_at': kb.get('updated_at') or '',
            'createdAt': kb.get('createdAt') or kb.get('updatedAt') or '',
            'updatedAt': kb.get('updatedAt') or ''
        }

    def _kb_dir(self, kb):
        return DOCS_DIR / kb.get('physical_path', '')

    def _sync_file_to_vector_store(self, kb, file_path: Path):
        text = extract_kb_file_text(file_path)
        rel_path = f"{kb.get('physical_path', '').rstrip('/')}/{file_path.name}"
        self.vector_service.delete_by_files(kb.get('id', ''), [file_path.name])
        records = self.vector_service.build_chunk_records(kb=kb, file_name=file_path.name, rel_path=rel_path, text=text)
        self.vector_service.upsert_records(records)

    def _reindex_kb(self, kb):
        target_dir = self._kb_dir(kb)
        self.vector_service.delete_by_kb(kb.get('id', ''))
        if not target_dir.exists():
            return
        all_records = []
        for file_path in sorted(target_dir.iterdir()):
            if not file_path.is_file():
                continue
            text = extract_kb_file_text(file_path)
            rel_path = f"{kb.get('physical_path', '').rstrip('/')}/{file_path.name}"
            all_records.extend(self.vector_service.build_chunk_records(kb=kb, file_name=file_path.name, rel_path=rel_path, text=text))
        self.vector_service.upsert_records(all_records)

    def load_all(self):
        return [self._format_kb(item) for item in self._read_all_raw()]

    def save_all(self, data):
        self._write_all_raw(data)

    def create_kb(self, name, model='openai', category='个人知识库'):
        user = self._get_user_info()
        all_kb = self._read_all_raw()
        kb_id = f"kb_{self._now_ms()}"
        if '企业' in category:
            owner_folder = user.get('company', '通用公司')
        elif '部门' in category:
            owner_folder = user.get('department', '通用部门')
        else:
            owner_folder = user.get('name', '访客')
        safe_name = ''.join([c for c in name if c.isalnum() or c in (' ', '_', '-')]).strip() or kb_id
        physical_path = f"{category}/{owner_folder}/{safe_name}"
        full_path = DOCS_DIR / physical_path
        if full_path.exists():
            physical_path = f"{category}/{owner_folder}/{safe_name}_{datetime.now().strftime('%H%M%S')}"
            full_path = DOCS_DIR / physical_path
        full_path.mkdir(parents=True, exist_ok=True)
        now_ms = self._now_ms()
        now_display = self._now_display()
        new_kb = {
            'id': kb_id,
            'name': name,
            'model': model,
            'category': category,
            'owner_info': f"{user.get('company', '')}/{user.get('department', '')}",
            'physical_path': physical_path,
            'remark': '',
            'users': [{'name': user.get('name', ''), 'phone': user.get('phone', ''), 'categoryName': user.get('company', '')}],
            'enabled': True,
            'created_at': now_ms,
            'updated_at': now_ms,
            'createdAt': now_display,
            'updatedAt': now_display
        }
        all_kb.append(new_kb)
        self._write_all_raw(all_kb)
        return self._format_kb(new_kb)

    def get_kb(self, kb_id):
        for kb in self._read_all_raw():
            if kb.get('id') == kb_id:
                return kb
        return None

    def get_kb_detail(self, kb_id):
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        formatted = self._format_kb(kb)
        formatted['files'] = self.list_files(kb_id)
        return formatted

    def update_kb(self, kb_id, update_data):
        all_kb = self._read_all_raw()
        for kb in all_kb:
            if kb.get('id') == kb_id:
                for key in ['name', 'remark', 'users', 'enabled']:
                    if key in update_data:
                        kb[key] = update_data[key]
                kb['updated_at'] = self._now_ms()
                kb['updatedAt'] = self._now_display()
                self._write_all_raw(all_kb)
                if any(key in update_data for key in ['name', 'users', 'enabled']):
                    self._reindex_kb(kb)
                return self._format_kb(kb)
        return None

    def delete_kb(self, kb_id):
        all_kb = self._read_all_raw()
        target = next((item for item in all_kb if item.get('id') == kb_id), None)
        if not target:
            return None
        full_path = self._kb_dir(target)
        if full_path.exists():
            shutil.rmtree(full_path)
        self.vector_service.delete_by_kb(kb_id)
        remain = [item for item in all_kb if item.get('id') != kb_id]
        self._write_all_raw(remain)
        return self._format_kb(target)

    def list_files(self, kb_id):
        kb = self.get_kb(kb_id)
        if not kb:
            return []
        full_path = self._kb_dir(kb)
        if not full_path.exists():
            return []
        results = []
        for file_path in sorted(full_path.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not file_path.is_file():
                continue
            uploaded_at = str(int(file_path.stat().st_mtime * 1000))
            results.append({
                'file_id': f"{kb_id}:{file_path.name}",
                'name': file_path.name,
                'url': f"{kb.get('physical_path', '').rstrip('/')}/{file_path.name}",
                'size': file_path.stat().st_size,
                'uploaded_at': uploaded_at,
                'uploadedAt': datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y/%m/%d %H:%M:%S')
            })
        return results

    def save_files(self, kb_id, file_objs):
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        target_dir = self._kb_dir(kb)
        target_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for file_obj in file_objs or []:
            original_name = Path(file_obj.filename or 'unnamed_file').name
            final_name = original_name
            stem = Path(original_name).stem
            suffix = Path(original_name).suffix
            index = 1
            while (target_dir / final_name).exists():
                final_name = f"{stem}_{index}{suffix}"
                index += 1
            with open(target_dir / final_name, 'wb') as f:
                f.write(file_obj.file.read())
            saved.append(final_name)
        if saved:
            self.update_kb(kb_id, {})
            for filename in saved:
                self._sync_file_to_vector_store(kb, target_dir / filename)
        return self.list_files(kb_id)

    def save_file(self, kb_id, file_obj):
        result = self.save_files(kb_id, [file_obj])
        return bool(result is not None)

    def delete_files(self, kb_id, filenames):
        kb = self.get_kb(kb_id)
        if not kb:
            return None
        target_dir = self._kb_dir(kb)
        deleted = []
        for filename in filenames or []:
            safe_name = Path(filename).name
            file_path = target_dir / safe_name
            if file_path.exists() and file_path.is_file():
                os.remove(file_path)
                deleted.append(safe_name)
        if deleted:
            self.vector_service.delete_by_files(kb_id, deleted)
            self.update_kb(kb_id, {})
        return deleted

    def delete_file(self, kb_id, filename):
        result = self.delete_files(kb_id, [filename])
        return bool(result)
