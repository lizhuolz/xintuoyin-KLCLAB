import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

from flask import Flask, jsonify, request, send_from_directory, Response
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
CHAT_BACKEND_DIR = PROJECT_ROOT / 'backend'
GRAPH_PROJECT_DIR = BASE_DIR / 'modules' / 'Graph' 
GRAPH_BACKEND_DIR = GRAPH_PROJECT_DIR / 'backend'
GRAPH_FRONTEND_DIR = GRAPH_PROJECT_DIR / 'frontend'
XINTUOYIN_DIR = BASE_DIR / 'modules' / 'xintuoyin'
WORKSPACE_DIR = BASE_DIR / 'runtime' / 'external_workspace'
INTERNAL_BINDING_DIR = BASE_DIR / 'runtime' / 'internal_binding_workspace'
UPLOAD_FOLDER = WORKSPACE_DIR / 'uploads'
OUTPUT_FILE = WORKSPACE_DIR / 'output_graph.json'
META_FILE = WORKSPACE_DIR / 'workspace_meta.json'
CURRENT_DB_FILE = WORKSPACE_DIR / 'current_db.txt'
EXTERNAL_GRAPH_INDEX_FILE = WORKSPACE_DIR / 'graph_index.json'
INTERNAL_BINDING_UPLOAD_FOLDER = INTERNAL_BINDING_DIR / 'uploads'
INTERNAL_BINDING_GRAPH_FILE = INTERNAL_BINDING_DIR / 'internal_binding_graph.json'
INTERNAL_BINDING_META_FILE = INTERNAL_BINDING_DIR / 'workspace_meta.json'
EXTRACTOR_FILE = XINTUOYIN_DIR / 'getgraph' / 'main.py'
PROMPT_DIR = XINTUOYIN_DIR / 'getgraph' / 'prompt'
XINTUOYIN_TEMPLATE = XINTUOYIN_DIR / 'templates' / 'index.html'

DEFAULT_API_BASE = os.getenv('EXTERNAL_GRAPH_API_BASE', 'http://127.0.0.1:62272/v1')
DEFAULT_MODEL_PATH = os.getenv('EXTERNAL_GRAPH_MODEL_PATH', 'Qwen3.5-27B')
EXTRACTOR_TIMEOUT_SECONDS = int(os.getenv('EXTERNAL_GRAPH_EXTRACT_TIMEOUT_SECONDS', '180'))

UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
INTERNAL_BINDING_UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
INTERNAL_BINDING_DIR.mkdir(parents=True, exist_ok=True)

GRAPH_LOCAL_FILE_ID_PREFIX = 'graph_local'


def _make_graph_local_file_id(scope: str, filename: str) -> str:
    safe_name = Path(str(filename or '')).name
    token = base64.urlsafe_b64encode(safe_name.encode('utf-8')).decode('ascii').rstrip('=')
    return f'{GRAPH_LOCAL_FILE_ID_PREFIX}:{scope}:{token}'


def _infer_graph_local_scope(save_path: Path) -> str:
    try:
        save_path.resolve().relative_to(INTERNAL_BINDING_UPLOAD_FOLDER.resolve())
        return 'internal_binding'
    except ValueError:
        pass
    try:
        save_path.resolve().relative_to(UPLOAD_FOLDER.resolve())
        return 'external'
    except ValueError:
        return ''

if not CURRENT_DB_FILE.exists():
    CURRENT_DB_FILE.write_text('output_graph.json', encoding='utf-8')

def get_current_db_name() -> str:
    if CURRENT_DB_FILE.exists():
        name = CURRENT_DB_FILE.read_text(encoding='utf-8').strip()
        if name:
            return name
    return 'output_graph.json'

def get_current_output_file() -> Path:
    return WORKSPACE_DIR / get_current_db_name()


def _display_name_from_filename(filename: str) -> str:
    return Path(str(filename or '').strip()).stem


def read_external_graph_index() -> Dict[str, Dict]:
    if not EXTERNAL_GRAPH_INDEX_FILE.exists():
        return {}
    try:
        data = json.loads(EXTERNAL_GRAPH_INDEX_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items() if isinstance(value, dict)}


def write_external_graph_index(index: Dict[str, Dict]) -> None:
    EXTERNAL_GRAPH_INDEX_FILE.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def get_external_graph_display_name(graph_name: str) -> str:
    normalized_name = str(graph_name or '').strip()
    if not normalized_name:
        return ''
    graph_id = Path(normalized_name).stem
    index = read_external_graph_index()
    entry = index.get(graph_id, {})
    display_name = str(entry.get('graphName') or '').strip()
    return display_name or normalized_name


def ensure_external_graph_display_name(graph_name: str, uploaded_files: List[str]) -> str:
    normalized_name = str(graph_name or '').strip()
    if not normalized_name:
        return ''
    graph_id = Path(normalized_name).stem
    index = read_external_graph_index()
    existing_entry = index.get(graph_id, {})
    existing_name = str(existing_entry.get('graphName') or '').strip()
    if existing_name:
        return existing_name

    first_file = ''
    for name in uploaded_files:
        normalized = str(name or '').strip()
        if normalized:
            first_file = normalized
            break

    display_name = _display_name_from_filename(first_file) or graph_id
    index[graph_id] = {
        **existing_entry,
        'graphId': graph_id,
        'graphFile': normalized_name,
        'graphName': display_name,
        'firstFileName': first_file or None,
    }
    write_external_graph_index(index)
    return display_name


def _normalize_graph_id(graph_id: str) -> str:
    graph_id_stem = str(graph_id or '').strip()
    if graph_id_stem.endswith('.json'):
        graph_id_stem = graph_id_stem[:-5]
    return graph_id_stem


def resolve_graph_file(graph_id: str = '', must_exist: bool = False) -> Path:
    graph_id_stem = _normalize_graph_id(graph_id)
    if not graph_id_stem:
        target_file = get_current_output_file()
    elif graph_id_stem == INTERNAL_BINDING_GRAPH_FILE.stem:
        target_file = INTERNAL_BINDING_GRAPH_FILE
    else:
        if (
            graph_id_stem in {'.', '..'}
            or '/' in graph_id_stem
            or '\\' in graph_id_stem
            or graph_id_stem == 'workspace_meta'
        ):
            raise ValueError('无效的 graphId')
        target_file = WORKSPACE_DIR / f'{graph_id_stem}.json'

    if must_exist and not target_file.exists():
        raise FileNotFoundError(f'图谱 {_normalize_graph_id(graph_id) or target_file.stem} 不存在')
    return target_file


def read_graph_by_id(graph_id: str = '', must_exist: bool = False) -> Dict:
    return read_graph_file(resolve_graph_file(graph_id, must_exist=must_exist))


def save_graph_by_id(graph: Dict, graph_id: str = '', must_exist: bool = False) -> Dict:
    return save_graph_file(resolve_graph_file(graph_id, must_exist=must_exist), graph)


def get_request_graph_id(payload: Dict | None = None) -> str:
    if isinstance(payload, dict):
        graph_id = payload.get('graphId')
        if graph_id not in [None, '']:
            return str(graph_id).strip()
    for source in (request.args, request.form):
        graph_id = source.get('graphId')
        if graph_id not in [None, '']:
            return str(graph_id).strip()
    return ''

if not get_current_output_file().exists():
    get_current_output_file().write_text(json.dumps({'nodes': [], 'links': []}, ensure_ascii=False, indent=2), encoding='utf-8')
if not META_FILE.exists():
    META_FILE.write_text(json.dumps({'exists': False, 'files': [], 'last_upload_at': None}, ensure_ascii=False, indent=2), encoding='utf-8')
if not INTERNAL_BINDING_GRAPH_FILE.exists():
    INTERNAL_BINDING_GRAPH_FILE.write_text(json.dumps({'nodes': [], 'links': []}, ensure_ascii=False, indent=2), encoding='utf-8')
if not INTERNAL_BINDING_META_FILE.exists():
    INTERNAL_BINDING_META_FILE.write_text(json.dumps({'exists': False, 'files': [], 'last_upload_at': None}, ensure_ascii=False, indent=2), encoding='utf-8')

from modules.Graph.backend.api.routes import api_bp  # noqa: E402
from modules.Graph.backend.config import settings  # noqa: E402


app = Flask(__name__)
CORS(app)
app.register_blueprint(api_bp)


def deduplicate_graph(graph: Dict) -> Dict:
    node_map = {}
    for node in graph.get('nodes', []):
        node_id = node.get('id')
        if not node_id:
            continue
        normalized = dict(node)
        if 'attrs' not in normalized or not isinstance(normalized.get('attrs'), dict):
            normalized['attrs'] = {}
        if node_id not in node_map:
            node_map[node_id] = normalized
        else:
            if isinstance(normalized.get('attrs'), dict):
                node_map[node_id]['attrs'].update(normalized['attrs'])
            for key, value in normalized.items():
                if key == 'attrs':
                    continue
                if value is not None:
                    node_map[node_id][key] = value

    link_map = {}
    for link in graph.get('links', []):
        source = link.get('source')
        target = link.get('target')
        relation = link.get('relation')
        if not source or not target or relation is None:
            continue
        dedup_key = f'{source}|||{target}|||{relation}'
        normalized = dict(link)
        if dedup_key not in link_map:
            link_map[dedup_key] = normalized
        else:
            for key, value in normalized.items():
                if value is not None:
                    link_map[dedup_key][key] = value
    return {'nodes': list(node_map.values()), 'links': list(link_map.values())}


def normalize_graph(data):
    if isinstance(data, dict) and 'nodes' in data and 'links' in data:
        nodes = data.get('nodes', [])
        links = data.get('links', [])
    elif isinstance(data, list):
        edges = []
        nodes_attr = []
        for item in data:
            edges.extend(item.get('edges', []))
            nodes_attr.extend(item.get('nodes_attr', []))
        nodes = []
        links = []
        for node_item in nodes_attr:
            node = {
                'id': node_item.get('object'),
                'group': node_item.get('group', 1),
                'attrs': node_item.get('attribute', {}),
            }
            for key, value in node_item.items():
                if key not in {'object', 'attribute'}:
                    node[key] = value
            nodes.append(node)
        for edge in edges:
            link = {
                'source': edge.get('source'),
                'target': edge.get('target'),
                'relation': edge.get('relation'),
            }
            for key, value in edge.items():
                if key not in {'source', 'target', 'relation'}:
                    link[key] = value
            links.append(link)
    else:
        nodes = []
        links = []
    return deduplicate_graph({'nodes': nodes, 'links': links})


def read_graph_file(graph_file: Path) -> Dict:
    if not graph_file.exists():
        return {'nodes': [], 'links': []}
    try:
        return normalize_graph(json.loads(graph_file.read_text(encoding='utf-8')))
    except Exception as exc:
        print(f'[external-graph] failed to read graph: {exc}')
        return {'nodes': [], 'links': []}


def save_graph_file(graph_file: Path, graph: Dict) -> Dict:
    normalized = deduplicate_graph(graph)
    graph_file.parent.mkdir(parents=True, exist_ok=True)
    graph_file.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding='utf-8')
    return normalized


def read_graph() -> Dict:
    return read_graph_file(get_current_output_file())


def save_graph(graph: Dict) -> Dict:
    return save_graph_file(get_current_output_file(), graph)


def read_internal_binding_graph() -> Dict:
    return read_graph_file(INTERNAL_BINDING_GRAPH_FILE)


def save_internal_binding_graph(graph: Dict) -> Dict:
    return save_graph_file(INTERNAL_BINDING_GRAPH_FILE, graph)


def merge_graph(base_graph: Dict, incoming_graph: Dict) -> Dict:
    merged = {
        'nodes': list(base_graph.get('nodes', [])) + list(incoming_graph.get('nodes', [])),
        'links': list(base_graph.get('links', [])) + list(incoming_graph.get('links', [])),
    }
    return deduplicate_graph(merged)


def graph_without_table_html(graph: Dict) -> Dict:
    nodes = []
    changed = False
    for node in graph.get('nodes', []):
        if isinstance(node, dict) and 'table_html' in node:
            normalized = dict(node)
            normalized.pop('table_html', None)
            nodes.append(normalized)
            changed = True
        else:
            nodes.append(node)
    if not changed:
        return graph
    return {'nodes': nodes, 'links': graph.get('links', [])}


def attach_file_metadata_to_graph(
    graph: Dict,
    *,
    file_id: str,
    file_name: str,
    file_url: str,
    staging_file_id: str | None,
) -> Dict:
    if not isinstance(graph, dict):
        return graph

    for collection_name in ('nodes', 'links'):
        for item in graph.get(collection_name, []) or []:
            if not isinstance(item, dict):
                continue
            item.setdefault('file_id', file_id)
            item.setdefault('file_name', file_name)
            item.setdefault('file_url', file_url)
            if staging_file_id:
                item['staging_file_id'] = staging_file_id
    return graph


def graph_has_content(graph: Dict) -> bool:
    return bool(graph.get('nodes') or graph.get('links'))


def graph_has_meaningful_content(graph: Dict) -> bool:
    if graph.get('links'):
        return True

    for node in graph.get('nodes', []):
        attrs = node.get('attrs', {})
        if isinstance(attrs, dict):
            for key, value in attrs.items():
                if key in {'文件名', '文件类别'}:
                    continue
                if value not in (None, '', 'null'):
                    return True
        if node.get('type') or node.get('table_html'):
            return True
    return False


def read_workspace_meta() -> Dict:
    if not META_FILE.exists():
        return {'exists': False, 'files': [], 'last_upload_at': None}
    try:
        meta = json.loads(META_FILE.read_text(encoding='utf-8'))
        meta['exists'] = bool(meta.get('files')) or has_external_workspace()
        return meta
    except Exception:
        return {'exists': has_external_workspace(), 'files': [], 'last_upload_at': None}


def write_workspace_meta(files: List[str]) -> Dict:
    payload = {
        'exists': True,
        'files': files,
        'last_upload_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
    }
    META_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


def read_internal_binding_meta() -> Dict:
    if not INTERNAL_BINDING_META_FILE.exists():
        return {'exists': False, 'files': [], 'last_upload_at': None}
    try:
        meta = json.loads(INTERNAL_BINDING_META_FILE.read_text(encoding='utf-8'))
        meta['exists'] = bool(meta.get('files')) or has_internal_binding_workspace()
        return meta
    except Exception:
        return {'exists': has_internal_binding_workspace(), 'files': [], 'last_upload_at': None}


def write_internal_binding_meta(files: List[str]) -> Dict:
    existing_files = read_internal_binding_meta().get('files', [])
    merged_files: List[str] = []
    for name in list(existing_files) + list(files):
        normalized = str(name or '').strip()
        if normalized and normalized not in merged_files:
            merged_files.append(normalized)

    payload = {
        'exists': bool(merged_files) or has_internal_binding_workspace(),
        'files': merged_files,
        'last_upload_at': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
    }
    INTERNAL_BINDING_META_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    return payload


def has_external_workspace() -> bool:
    graph = read_graph()
    return graph_has_content(graph)


def has_internal_binding_workspace() -> bool:
    graph = read_internal_binding_graph()
    return graph_has_content(graph)


def clear_external_workspace(remove_files: bool = True) -> Dict:
    save_graph({'nodes': [], 'links': []})
    removed_files = []
    if remove_files and UPLOAD_FOLDER.exists():
        for entry in UPLOAD_FOLDER.iterdir():
            removed_files.append(entry.name)
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
    if META_FILE.exists():
        META_FILE.unlink(missing_ok=True)
    return {'status': 'success', 'removed_files': removed_files}


def get_workspace_status() -> Dict:
    graph = read_graph()
    meta = read_workspace_meta()
    return {
        'exists': meta.get('exists', False) or bool(graph.get('nodes') or graph.get('links')),
        'files': meta.get('files', []),
        'last_upload_at': meta.get('last_upload_at'),
        'node_count': len(graph.get('nodes', [])),
        'link_count': len(graph.get('links', [])),
    }


def get_internal_binding_status() -> Dict:
    graph = read_internal_binding_graph()
    meta = read_internal_binding_meta()
    return {
        'exists': meta.get('exists', False) or bool(graph.get('nodes') or graph.get('links')),
        'files': meta.get('files', []),
        'last_upload_at': meta.get('last_upload_at'),
        'node_count': len(graph.get('nodes', [])),
        'link_count': len(graph.get('links', [])),
        'graphId': INTERNAL_BINDING_GRAPH_FILE.stem,
        'graphName': INTERNAL_BINDING_GRAPH_FILE.name,
    }


def _coerce_process_output(value) -> str:
    if value is None:
        return ''
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value)


def run_extractor(file_path: Path, output_path: Path) -> Dict:
    cmd = [
        sys.executable,
        str(EXTRACTOR_FILE),
        '--input_file_path', str(file_path),
        '--output_file_path', str(output_path),
        '--api_base', DEFAULT_API_BASE,
        '--model_path', DEFAULT_MODEL_PATH,
        '--prompt_txt_path', str(PROMPT_DIR),
    ]
    child_env = os.environ.copy()
    existing_no_proxy = child_env.get('NO_PROXY') or child_env.get('no_proxy') or ''
    no_proxy_items = [item.strip() for item in existing_no_proxy.split(',') if item.strip()]
    for item in ('127.0.0.1', 'localhost', '10.249.40.204'):
        if item not in no_proxy_items:
            no_proxy_items.append(item)
    child_env['NO_PROXY'] = ','.join(no_proxy_items)
    child_env['no_proxy'] = child_env['NO_PROXY']
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=EXTRACTOR_TIMEOUT_SECONDS,
            env=child_env,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            'file': file_path.name,
            'status': 'failed',
            'returncode': None,
            'stdout': _coerce_process_output(exc.stdout),
            'stderr': _coerce_process_output(exc.stderr),
            'command': cmd,
            'error': f'提取超时（>{EXTRACTOR_TIMEOUT_SECONDS}s），已终止处理',
        }

    result = {
        'file': file_path.name,
        'status': 'ok' if completed.returncode == 0 else 'failed',
        'returncode': completed.returncode,
        'stdout': completed.stdout,
        'stderr': completed.stderr,
        'command': cmd,
    }
    if completed.returncode != 0:
        stderr_text = result.get('stderr', '')
        if 'CUDA out of memory' in stderr_text or 'OutOfMemoryError' in stderr_text:
            result['error'] = '文档转换失败：OCR 阶段显存不足'
        return result

    if not output_path.exists():
        result['status'] = 'failed'
        result['error'] = '提取完成但未生成输出文件'
        return result

    try:
        extracted_graph = normalize_graph(json.loads(output_path.read_text(encoding='utf-8')))
    except Exception as exc:
        result['status'] = 'failed'
        result['error'] = f'提取结果解析失败: {exc}'
        return result

    if not graph_has_meaningful_content(extracted_graph):
        result['status'] = 'failed'
        result['error'] = '提取结果为空，未生成任何图谱节点或关系'
        result['empty_graph'] = True
        return result

    result['graph'] = extracted_graph
    result['graph_stats'] = {
        'node_count': len(extracted_graph.get('nodes', [])),
        'link_count': len(extracted_graph.get('links', [])),
    }
    return result


@app.get('/')
def index():
    return send_from_directory(GRAPH_FRONTEND_DIR, 'index.html')


@app.get('/assets/<path:path>')
def frontend_assets(path: str):
    return send_from_directory(GRAPH_FRONTEND_DIR / 'assets', path)


@app.get('/external-view')
def external_view():
    return Response(XINTUOYIN_TEMPLATE.read_text(encoding='utf-8'), mimetype='text/html')


@app.get('/external/workspace/status')
def external_workspace_status():
    status = get_workspace_status()
    # Add current db info to status
    status['current_db'] = get_current_db_name()
    status['available_dbs'] = [
        f.name
        for f in WORKSPACE_DIR.glob('*.json')
        if f.name not in {'workspace_meta.json', EXTERNAL_GRAPH_INDEX_FILE.name}
    ]
    if status['current_db'] not in status['available_dbs']:
        status['available_dbs'].append(status['current_db'])
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": status
    })

@app.post('/external/workspace/switch_db')
def external_workspace_switch_db():
    payload = request.get_json(silent=True) or {}
    db_name = payload.get('db_name')
    if not db_name or not db_name.endswith('.json') or db_name == 'workspace_meta.json':
        return jsonify({
            "code": 400,
            "msg": "无效的图谱数据库文件名"
        }), 400
    
    CURRENT_DB_FILE.write_text(db_name, encoding='utf-8')
    if not get_current_output_file().exists():
        get_current_output_file().write_text(json.dumps({'nodes': [], 'links': []}, ensure_ascii=False, indent=2), encoding='utf-8')
        
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": {
            'status': 'success',
            'current_db': db_name,
            'message': f'已切换至图谱: {db_name}'
        }
    })

@app.post('/external/workspace/create_db')
def external_workspace_create_db():
    payload = request.get_json(silent=True) or {}
    db_name = payload.get('db_name')
    if not db_name:
        return jsonify({
            "code": 400,
            "msg": "数据库名称不能为空"
        }), 400
    
    if not db_name.endswith('.json'):
        db_name += '.json'
        
    if db_name == 'workspace_meta.json':
        return jsonify({
            "code": 400,
            "msg": "无效的图谱数据库文件名"
        }), 400
        
    new_db_file = WORKSPACE_DIR / db_name
    if new_db_file.exists():
        return jsonify({
            "code": 409,
            "msg": f"图谱 {db_name} 已存在"
        }), 409
        
    new_db_file.write_text(json.dumps({'nodes': [], 'links': []}, ensure_ascii=False, indent=2), encoding='utf-8')
    CURRENT_DB_FILE.write_text(db_name, encoding='utf-8')
    
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": {
            'status': 'success',
            'current_db': db_name,
            'message': f'已创建并切换至新图谱: {db_name}'
        }
    })

@app.post('/external/workspace/clear')
def external_workspace_clear():
    result = clear_external_workspace(remove_files=True)
    result.update(get_workspace_status())
    result['message'] = '系统外知识图谱子界面已删除'
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": result
    })


# 图谱上传后顺带把原文件副本上传到 chat 的 MinIO staging 区，
# 让前端可以直接把 staging_file_id 喂给 /api/chat 的 file_ids，
# 避免对话场景下用户重新上传一次同一份文件。


def _stage_file_for_chat(save_path: Path):
    """把图谱已保存的文件副本上传到 chat staging。
    返回 chat staging file_id；上传失败时返回可由 chat 解析的本地图谱文件 id。
    聊天接口已支持图片，所以这里不再跳过图片文件，避免 staging_file_id 为空。
    """
    local_scope = _infer_graph_local_scope(save_path)
    local_file_id = _make_graph_local_file_id(local_scope, save_path.name) if local_scope else None
    try:
        import mimetypes, time, uuid
        backend_path = str(CHAT_BACKEND_DIR)
        if CHAT_BACKEND_DIR.exists() and backend_path not in sys.path:
            sys.path.insert(0, backend_path)
        from services.storage_service import storage_service
        file_id = f"f_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        object_name = f"staging/{file_id}/{save_path.name}"
        content_type = mimetypes.guess_type(save_path.name)[0] or 'application/octet-stream'
        with open(save_path, 'rb') as f:
            if not storage_service.upload_file_obj(f, object_name, content_type):
                return local_file_id
        return file_id
    except Exception as exc:
        print(f"[graph] stage_file_for_chat failed: {exc}", file=sys.stderr)
        return local_file_id


@app.post('/upload')
def upload_file():
    if 'file' not in request.files:
        return jsonify({
            "code": 400,
            "msg": "未接收到文件"
        }), 400

    is_default = request.form.get('isDefault', 'true').lower() == 'true'
    graph_id = request.form.get('graphId', '').strip()
    now_ms = lambda: int(__import__('time').time() * 1000)

    if is_default:
        from modules.Graph.backend.services.graph_service import GraphService
        files = request.files.getlist('file')
        saved_files = []
        successful_files = []
        preprocess_results = []
        extracted_graphs = []

        for file in files:
            if not file or not file.filename:
                continue
            safe_name = Path(file.filename).name
            save_path = INTERNAL_BINDING_UPLOAD_FOLDER / safe_name
            file.save(save_path)

            file_id = f"file_{now_ms()}_{safe_name}"
            file_url = f"/internal-binding/file/{safe_name}"
            staging_file_id = _stage_file_for_chat(save_path)

            saved_files.append({
                'id': file_id,
                'name': safe_name,
                'url': file_url,
                'staging_file_id': staging_file_id,
            })

            temp_output = INTERNAL_BINDING_DIR / f"temp_extracted_{now_ms()}_{safe_name}.json"
            extraction = run_extractor(save_path, temp_output)
            extracted_graph = extraction.pop('graph', None)
            extraction.pop('graph_stats', None)
            preprocess_results.append(extraction)
            if extracted_graph:
                attach_file_metadata_to_graph(
                    extracted_graph,
                    file_id=file_id,
                    file_name=safe_name,
                    file_url=file_url,
                    staging_file_id=staging_file_id,
                )
                successful_files.append(safe_name)
                extracted_graphs.append(extracted_graph)
            if temp_output.exists():
                temp_output.unlink(missing_ok=True)

        if not saved_files:
            return jsonify({
                "code": 400,
                "msg": "未选择有效文件"
            }), 400

        binding_graph = read_internal_binding_graph()
        for extracted in extracted_graphs:
            if extracted and isinstance(extracted, dict):
                binding_graph = merge_graph(binding_graph, extracted)

        if successful_files:
            write_internal_binding_meta(successful_files)
            binding_graph = save_internal_binding_graph(binding_graph)
        else:
            binding_graph = read_internal_binding_graph()

        internal_graph = GraphService.get_graph()
        merged_graph = deduplicate_graph({
            'nodes': list(internal_graph.get('nodes', [])) + list(binding_graph.get('nodes', [])),
            'links': list(internal_graph.get('links', [])) + list(binding_graph.get('links', [])),
        })
        try:
            from modules.Graph.backend.api.routes import prime_combined_graph_cache
            prime_combined_graph_cache(internal_graph, binding_graph, merged_graph)
        except Exception as exc:
            print(f"[graph] prime_combined_graph_cache failed: {exc}", file=sys.stderr)

        success_count = len([item for item in preprocess_results if item['status'] == 'ok'])
        failed = [item for item in preprocess_results if item['status'] != 'ok']
        if success_count == 0:
            status_code = 200
            code = 422
            msg = '未提取到有效图谱内容'
            status = 'failed'
            message = '上传文件未提取到任何图谱节点或关系，请检查文件内容'
        elif failed:
            status_code = 200
            code = 207
            msg = '部分文件处理失败'
            status = 'partial_success'
            message = f'成功处理 {success_count} 个文件并挂载到系统内绑定图谱'
        else:
            status_code = 200
            code = 0
            msg = '成功'
            status = 'success'
            message = f'成功处理 {success_count} 个文件并挂载到系统内绑定图谱'

        return jsonify({
            "code": code,
            "msg": msg,
            "data": {
                'status': status,
                'message': message,
                'isDefault': True,
                'files': saved_files,
                'preprocess_results': preprocess_results,
                'merged_to': 'internal_binding_graph',
                'binding_graph': {
                    'graphId': INTERNAL_BINDING_GRAPH_FILE.stem,
                    'graphName': INTERNAL_BINDING_GRAPH_FILE.name,
                    'node_count': len(binding_graph.get('nodes', [])),
                    'link_count': len(binding_graph.get('links', [])),
                },
                'graph': {
                    'node_count': len(merged_graph.get('nodes', [])),
                    'link_count': len(merged_graph.get('links', [])),
                },
            }
        }), status_code

    else:
        previous_db = get_current_db_name()
        created_new_db = False
        if graph_id:
            graph_id_stem = graph_id[:-5] if graph_id.endswith('.json') else graph_id
            target_db = f"{graph_id_stem}.json"
            if (
                not graph_id_stem
                or graph_id_stem in {'.', '..'}
                or '/' in graph_id
                or '\\' in graph_id
                or target_db == 'workspace_meta.json'
            ):
                return jsonify({
                    "code": 400,
                    "msg": "无效的 graphId，请传入已有图谱的 graphId（不包含路径）"
                }), 400

            target_file = WORKSPACE_DIR / target_db
            if not target_file.exists():
                return jsonify({
                    "code": 404,
                    "msg": f"图谱 {graph_id_stem} 不存在，请检查 graphId 或先创建图谱"
                }), 404

            CURRENT_DB_FILE.write_text(target_db, encoding='utf-8')
        else:
            timestamp = now_ms()
            target_db = f"new_graph_{timestamp}.json"
            new_db_file = WORKSPACE_DIR / target_db
            new_db_file.write_text(json.dumps({'nodes': [], 'links': []}, ensure_ascii=False, indent=2), encoding='utf-8')
            CURRENT_DB_FILE.write_text(target_db, encoding='utf-8')
            created_new_db = True

        files = request.files.getlist('file')
        saved_files = []
        successful_files = []
        preprocess_results = []
        current_graph = read_graph()

        for file in files:
            if not file or not file.filename:
                continue
            safe_name = Path(file.filename).name
            save_path = UPLOAD_FOLDER / safe_name
            file.save(save_path)

            file_id = f"file_{now_ms()}_{safe_name}"
            file_url = f"/external/file/{safe_name}"
            staging_file_id = _stage_file_for_chat(save_path)

            saved_files.append({
                'id': file_id,
                'name': safe_name,
                'url': file_url,
                'staging_file_id': staging_file_id,
            })
            temp_output = WORKSPACE_DIR / f"temp_extracted_{now_ms()}_{safe_name}.json"
            extraction = run_extractor(save_path, temp_output)
            extracted_graph = extraction.pop('graph', None)
            extraction.pop('graph_stats', None)
            preprocess_results.append(extraction)
            if extracted_graph:
                attach_file_metadata_to_graph(
                    extracted_graph,
                    file_id=file_id,
                    file_name=safe_name,
                    file_url=file_url,
                    staging_file_id=staging_file_id,
                )
                successful_files.append(safe_name)
                current_graph = merge_graph(current_graph, extracted_graph)
            if temp_output.exists():
                temp_output.unlink(missing_ok=True)

        if not saved_files:
            return jsonify({
                "code": 400,
                "msg": "未选择有效文件"
            }), 400

        if successful_files:
            graph = save_graph(current_graph)
            write_workspace_meta(successful_files)
            ensure_external_graph_display_name(get_current_db_name(), successful_files)
        else:
            if created_new_db:
                target_file = WORKSPACE_DIR / target_db
                target_file.unlink(missing_ok=True)
                CURRENT_DB_FILE.write_text(previous_db, encoding='utf-8')
            graph = read_graph()
        current_db = get_current_db_name()
        response_graph_id = current_db.replace('.json', '')
        success_count = len([item for item in preprocess_results if item['status'] == 'ok'])
        failed = [item for item in preprocess_results if item['status'] != 'ok']
        if success_count == 0:
            status_code = 200
            code = 422
            msg = '未提取到有效图谱内容'
            status = 'failed'
            message = '上传文件未提取到任何图谱节点或关系，已阻止生成空图谱'
        elif failed:
            status_code = 200
            code = 207
            msg = '部分文件处理失败'
            status = 'partial_success'
            message = f'成功保存 {success_count} 个文件到图谱 {current_db}'
        else:
            status_code = 200
            code = 0
            msg = '成功'
            status = 'success'
            message = f'成功保存 {success_count} 个文件到图谱 {current_db}'

        return jsonify({
            "code": code,
            "msg": msg,
            "data": {
                'status': status,
                'message': message,
                'isDefault': False,
                'graphId': response_graph_id,
                'files': saved_files,
                'workspace': get_workspace_status(),
                'preprocess_results': preprocess_results,
                'graph': {
                    'node_count': len(graph.get('nodes', [])),
                    'link_count': len(graph.get('links', [])),
                },
            }
        }), status_code


@app.get('/external/file/<filename>')
def serve_uploaded_file(filename: str):
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.get('/internal-binding/file/<filename>')
def serve_internal_binding_file(filename: str):
    return send_from_directory(INTERNAL_BINDING_UPLOAD_FOLDER, filename)


@app.get('/get_graph')
def get_graph():
    graph_id = get_request_graph_id()
    try:
        graph_file = resolve_graph_file(graph_id, must_exist=bool(graph_id))
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"code": 404, "msg": str(exc)}), 404

    graph_data = read_graph_file(graph_file)
    current_db = graph_file.name
    graph_id = graph_file.stem
    graph_name = (
        current_db
        if graph_file == INTERNAL_BINDING_GRAPH_FILE
        else get_external_graph_display_name(current_db)
    )
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": {
            'graphId': graph_id,
            'graphName': graph_name,
            'nodes': graph_data.get('nodes', []),
            'links': graph_data.get('links', []),
        }
    })


@app.post('/graph/node')
def create_node():
    payload = request.get_json(silent=True) or {}
    graph_id = get_request_graph_id(payload)
    node_id = payload.get('id')
    if not node_id:
        return jsonify({
            "code": 400,
            "msg": "节点 id 不能为空"
        }), 400

    try:
        graph = read_graph_by_id(graph_id, must_exist=bool(graph_id))
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"code": 404, "msg": str(exc)}), 404
    if any(node.get('id') == node_id for node in graph['nodes']):
        return jsonify({
            "code": 409,
            "msg": f"节点 {node_id} 已存在"
        }), 409

    node = dict(payload)
    node.pop('graphId', None)
    if 'attrs' not in node or not isinstance(node.get('attrs'), dict):
        node['attrs'] = {}
    graph['nodes'].append(node)
    graph = save_graph_by_id(graph, graph_id)
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": {'status': 'success', 'graphId': resolve_graph_file(graph_id).stem, 'node': node, 'graph': graph}
    })


@app.put('/graph/node/<path:node_id>')
def update_node(node_id):
    payload = request.get_json(silent=True) or {}
    graph_id = get_request_graph_id(payload)
    try:
        graph = read_graph_by_id(graph_id, must_exist=bool(graph_id))
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"code": 404, "msg": str(exc)}), 404
    target = None
    for node in graph['nodes']:
        if node.get('id') == node_id:
            target = node
            break
    if target is None:
        return jsonify({
            "code": 404,
            "msg": f"节点 {node_id} 不存在"
        }), 404

    new_id = payload.get('id', node_id)
    if new_id != node_id and any(node.get('id') == new_id for node in graph['nodes']):
        return jsonify({
            "code": 409,
            "msg": f"节点 {new_id} 已存在"
        }), 409

    merged_attrs = dict(target.get('attrs', {}))
    incoming_attrs = payload.get('attrs')
    if isinstance(incoming_attrs, dict):
        merged_attrs.update(incoming_attrs)

    for key, value in payload.items():
        if key in {'attrs', 'graphId'}:
            continue
        target[key] = value
    target['id'] = new_id
    target['attrs'] = merged_attrs

    if new_id != node_id:
        for link in graph['links']:
            if link.get('source') == node_id:
                link['source'] = new_id
            if link.get('target') == node_id:
                link['target'] = new_id

    graph = save_graph_by_id(graph, graph_id)
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": {'status': 'success', 'graphId': resolve_graph_file(graph_id).stem, 'node': target, 'graph': graph}
    })


@app.delete('/graph/node/<path:node_id>')
def delete_node(node_id):
    payload = request.get_json(silent=True) or {}
    graph_id = get_request_graph_id(payload)
    try:
        graph = read_graph_by_id(graph_id, must_exist=bool(graph_id))
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"code": 404, "msg": str(exc)}), 404
    before_node_count = len(graph['nodes'])
    graph['nodes'] = [node for node in graph['nodes'] if node.get('id') != node_id]
    if len(graph['nodes']) == before_node_count:
        return jsonify({
            "code": 404,
            "msg": f"节点 {node_id} 不存在"
        }), 404
    graph['links'] = [
        link for link in graph['links']
        if link.get('source') != node_id and link.get('target') != node_id
    ]
    graph = save_graph_by_id(graph, graph_id)
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": {'status': 'success', 'graphId': resolve_graph_file(graph_id).stem, 'deleted_node': node_id, 'graph': graph}
    })


@app.post('/graph/link')
def create_link():
    payload = request.get_json(silent=True) or {}
    graph_id = get_request_graph_id(payload)
    source = payload.get('source')
    target = payload.get('target')
    relation = payload.get('relation')
    if not source or not target or relation is None:
        return jsonify({
            "code": 400,
            "msg": "source、target、relation 不能为空"
        }), 400

    try:
        graph = read_graph_by_id(graph_id, must_exist=bool(graph_id))
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"code": 404, "msg": str(exc)}), 404
    exists = any(
        link.get('source') == source and link.get('target') == target and link.get('relation') == relation
        for link in graph['links']
    )
    if exists:
        return jsonify({
            "code": 409,
            "msg": "该关系已存在"
        }), 409

    existing_node_ids = {node.get('id') for node in graph['nodes']}
    if source not in existing_node_ids:
        graph['nodes'].append({'id': source, 'group': 1, 'attrs': {}})
    if target not in existing_node_ids:
        graph['nodes'].append({'id': target, 'group': 1, 'attrs': {}})

    link = dict(payload)
    link.pop('graphId', None)
    graph['links'].append(link)
    graph = save_graph_by_id(graph, graph_id)
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": {'status': 'success', 'graphId': resolve_graph_file(graph_id).stem, 'link': link, 'graph': graph}
    })


@app.put('/graph/link')
def update_link():
    payload = request.get_json(silent=True) or {}
    graph_id = get_request_graph_id(payload)
    old_source = payload.get('old_source')
    old_target = payload.get('old_target')
    old_relation = payload.get('old_relation')
    if not old_source or not old_target or old_relation is None:
        return jsonify({
            "code": 400,
            "msg": "old_source、old_target、old_relation 不能为空"
        }), 400

    try:
        graph = read_graph_by_id(graph_id, must_exist=bool(graph_id))
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"code": 404, "msg": str(exc)}), 404
    target_link = None
    for link in graph['links']:
        if (
            link.get('source') == old_source and
            link.get('target') == old_target and
            link.get('relation') == old_relation
        ):
            target_link = link
            break
    if target_link is None:
        return jsonify({
            "code": 404,
            "msg": "待修改关系不存在"
        }), 404

    for field in ('source', 'target', 'relation'):
        if field in payload:
            target_link[field] = payload[field]
    for key, value in payload.items():
        if key not in {'graphId', 'old_source', 'old_target', 'old_relation', 'source', 'target', 'relation'}:
            target_link[key] = value

    source = target_link.get('source')
    target = target_link.get('target')
    relation = target_link.get('relation')
    if not source or not target or relation is None:
        return jsonify({
            "code": 400,
            "msg": "更新后 source、target、relation 不能为空"
        }), 400

    existing_node_ids = {node.get('id') for node in graph['nodes']}
    if source not in existing_node_ids:
        graph['nodes'].append({'id': source, 'group': 1, 'attrs': {}})
    if target not in existing_node_ids:
        graph['nodes'].append({'id': target, 'group': 1, 'attrs': {}})

    graph = save_graph_by_id(graph, graph_id)
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": {'status': 'success', 'graphId': resolve_graph_file(graph_id).stem, 'link': target_link, 'graph': graph}
    })


@app.delete('/graph/link')
def delete_link():
    payload = request.get_json(silent=True) or {}
    graph_id = get_request_graph_id(payload)
    source = payload.get('source')
    target = payload.get('target')
    relation = payload.get('relation')
    if not source or not target or relation is None:
        return jsonify({
            "code": 400,
            "msg": "source、target、relation 不能为空"
        }), 400

    try:
        graph = read_graph_by_id(graph_id, must_exist=bool(graph_id))
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"code": 404, "msg": str(exc)}), 404
    original_count = len(graph['links'])
    graph['links'] = [
        link for link in graph['links']
        if not (link.get('source') == source and link.get('target') == target and link.get('relation') == relation)
    ]
    if len(graph['links']) == original_count:
        return jsonify({
            "code": 404,
            "msg": "待删除关系不存在"
        }), 404
    graph = save_graph_by_id(graph, graph_id)
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": {'status': 'success', 'graphId': resolve_graph_file(graph_id).stem, 'deleted_link': {'source': source, 'target': target, 'relation': relation}, 'graph': graph}
    })


@app.post('/graph/merge')
def merge_graph_api():
    payload = request.get_json(silent=True) or {}
    graph_id = get_request_graph_id(payload)
    incoming_data = payload.get('graph')
    merge_file_path = payload.get('file_path')

    if incoming_data is None and not merge_file_path:
        return jsonify({
            "code": 400,
            "msg": "请提供 graph 或 file_path"
        }), 400

    if incoming_data is None and merge_file_path:
        file = Path(merge_file_path)
        if not file.exists():
            return jsonify({
                "code": 400,
                "msg": f"文件不存在: {merge_file_path}"
            }), 400
        try:
            incoming_data = json.loads(file.read_text(encoding='utf-8'))
        except Exception as exc:
            return jsonify({
                "code": 400,
                "msg": f"读取待合并文件失败: {exc}"
            }), 400

    try:
        current = read_graph_by_id(graph_id, must_exist=bool(graph_id))
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"code": 404, "msg": str(exc)}), 404
    incoming = normalize_graph(incoming_data)
    merged = merge_graph(current, incoming)
    merged = save_graph_by_id(merged, graph_id)

    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": {
            'status': 'success',
            'base_node_count': len(current.get('nodes', [])),
            'base_link_count': len(current.get('links', [])),
            'incoming_node_count': len(incoming.get('nodes', [])),
            'incoming_link_count': len(incoming.get('links', [])),
            'merged_node_count': len(merged.get('nodes', [])),
            'merged_link_count': len(merged.get('links', [])),
            'graphId': resolve_graph_file(graph_id).stem,
            'graph': graph_without_table_html(merged),
        }
    })


@app.post('/graph/clear')
def clear_graph_api():
    payload = request.get_json(silent=True) or {}
    graph_id = get_request_graph_id(payload)
    try:
        cleared = save_graph_by_id({'nodes': [], 'links': []}, graph_id, must_exist=bool(graph_id))
    except ValueError as exc:
        return jsonify({"code": 400, "msg": str(exc)}), 400
    except FileNotFoundError as exc:
        return jsonify({"code": 404, "msg": str(exc)}), 404
    return jsonify({
        "code": 0,
        "msg": "成功",
        "data": {'status': 'success', 'graphId': resolve_graph_file(graph_id).stem, 'message': '图谱已清空', 'graph': cleared}
    })


if __name__ == '__main__':
    app.run(host=settings.host, port=settings.port, debug=settings.debug)
