import base64
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import quote

from flask import Blueprint, jsonify, request

from ..config import settings
from ..services.graph_service import GraphService
from ..services.user_service import UserService

api_bp = Blueprint('api', __name__, url_prefix='/api')

REPO_ROOT = Path(__file__).resolve().parents[4]
EXTERNAL_WORKSPACE_DIR = REPO_ROOT / 'runtime' / 'external_workspace'
EXTERNAL_CURRENT_DB_FILE = EXTERNAL_WORKSPACE_DIR / 'current_db.txt'
EXTERNAL_GRAPH_INDEX_FILE = EXTERNAL_WORKSPACE_DIR / 'graph_index.json'
INTERNAL_BINDING_DIR = REPO_ROOT / 'runtime' / 'internal_binding_workspace'
INTERNAL_BINDING_GRAPH_FILE = INTERNAL_BINDING_DIR / 'internal_binding_graph.json'
GRAPH_LOCAL_FILE_ID_PREFIX = 'graph_local'
_COMBINED_GRAPH_CACHE: Dict[str, Any] = {'key': None, 'data': None}
_COMBINED_GRAPH_CACHE_LOCK = threading.Lock()


def _coerce_text(value: Any) -> str:
    if value in (None, '', 'null'):
        return ''
    if isinstance(value, list):
        for item in value:
            text = _coerce_text(item)
            if text:
                return text
        return ''
    return str(value).strip()


def _make_graph_local_file_id(scope: str, filename: str) -> str:
    safe_name = Path(str(filename or '')).name
    token = base64.urlsafe_b64encode(safe_name.encode('utf-8')).decode('ascii').rstrip('=')
    return f'{GRAPH_LOCAL_FILE_ID_PREFIX}:{scope}:{token}'


def _resolve_item_file_name(item: Dict[str, Any]) -> str:
    for key in ('file_name', 'file_path'):
        value = _coerce_text(item.get(key))
        if value:
            return Path(value).name

    attrs = item.get('attrs') if isinstance(item.get('attrs'), dict) else {}
    for key in ('文件名', '文件名称'):
        value = _coerce_text(attrs.get(key))
        if value:
            return Path(value).name
    return ''


def _attach_graph_local_file_ids(graph: Dict[str, Any], *, scope: str) -> Dict[str, List[Dict[str, Any]]]:
    if not isinstance(graph, dict):
        return {'nodes': [], 'links': []}

    url_prefix = '/internal-binding/file/' if scope == 'internal_binding' else '/external/file/'
    normalized_graph: Dict[str, List[Dict[str, Any]]] = {'nodes': [], 'links': []}
    for collection_name in ('nodes', 'links'):
        for item in graph.get(collection_name, []) or []:
            if not isinstance(item, dict):
                continue
            normalized = dict(item)
            file_name = _resolve_item_file_name(normalized)
            if file_name:
                normalized.setdefault('file_name', file_name)
                normalized.setdefault('file_url', f'{url_prefix}{quote(file_name)}')
                if not _coerce_text(normalized.get('staging_file_id')):
                    normalized['staging_file_id'] = _make_graph_local_file_id(scope, file_name)
            normalized_graph[collection_name].append(normalized)
    return normalized_graph


def _resolve_node_name(node: Dict[str, Any]) -> str:
    explicit_name = _coerce_text(node.get('name'))
    if explicit_name:
        return explicit_name

    attrs = node.get('attrs') if isinstance(node.get('attrs'), dict) else {}
    for key in (
        '中文名',
        '名称',
        '姓名',
        '项目名称',
        '企业名称',
        '资产名称',
        '文件名',
    ):
        name = _coerce_text(attrs.get(key))
        if name:
            return name

    return _coerce_text(node.get('id'))


def _ensure_node_name(node: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(node)
    normalized['name'] = _resolve_node_name(normalized)
    return normalized


def _without_table_html(node: Dict[str, Any]) -> Dict[str, Any]:
    if 'table_html' not in node:
        return node
    normalized = dict(node)
    normalized.pop('table_html', None)
    return normalized


def _ensure_graph_node_names(
    graph: Dict[str, Any],
    *,
    strip_table_html: bool = False,
) -> Dict[str, List[Dict[str, Any]]]:
    nodes = []
    for node in graph.get('nodes', []) or []:
        if not isinstance(node, dict):
            continue
        normalized = _ensure_node_name(node)
        if strip_table_html:
            normalized = _without_table_html(normalized)
        nodes.append(normalized)
    return {
        'nodes': nodes,
        'links': graph.get('links', []) or [],
    }


def _should_replace_name(current: Any, incoming: Any, node_id: Any) -> bool:
    current_text = _coerce_text(current)
    incoming_text = _coerce_text(incoming)
    node_id_text = _coerce_text(node_id)
    if not incoming_text:
        return False
    if not current_text:
        return True
    return current_text == node_id_text and incoming_text != node_id_text


def _deduplicate_graph(graph: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    node_map: Dict[str, Dict[str, Any]] = {}
    for node in graph.get('nodes', []) or []:
        node_id = node.get('id')
        if not node_id:
            continue
        normalized = _ensure_node_name(node)
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
                if key == 'name' and not _should_replace_name(node_map[node_id].get('name'), value, node_id):
                    continue
                if value is not None:
                    node_map[node_id][key] = value

    link_map: Dict[str, Dict[str, Any]] = {}
    for link in graph.get('links', []) or []:
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


def _normalize_graph(data: Any) -> Dict[str, List[Dict[str, Any]]]:
    if isinstance(data, dict) and 'nodes' in data and 'links' in data:
        return _deduplicate_graph(
            {
                'nodes': data.get('nodes', []) or [],
                'links': data.get('links', []) or [],
            }
        )

    if isinstance(data, list):
        edges: List[Dict[str, Any]] = []
        nodes_attr: List[Dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            edges.extend(item.get('edges', []) or [])
            nodes_attr.extend(item.get('nodes_attr', []) or [])

        nodes: List[Dict[str, Any]] = []
        links: List[Dict[str, Any]] = []
        for node_item in nodes_attr:
            if not isinstance(node_item, dict):
                continue
            node = {
                'id': node_item.get('object'),
                'name': node_item.get('name') or node_item.get('object'),
                'group': node_item.get('group', 1),
                'attrs': node_item.get('attribute', {}),
            }
            for key, value in node_item.items():
                if key not in {'object', 'attribute'}:
                    node[key] = value
            nodes.append(node)

        for edge in edges:
            if not isinstance(edge, dict):
                continue
            link = {
                'source': edge.get('source'),
                'target': edge.get('target'),
                'relation': edge.get('relation'),
            }
            for key, value in edge.items():
                if key not in {'source', 'target', 'relation'}:
                    link[key] = value
            links.append(link)

        return _deduplicate_graph({'nodes': nodes, 'links': links})

    return {'nodes': [], 'links': []}


def _read_graph_file(graph_file: Path) -> Dict[str, List[Dict[str, Any]]]:
    if not graph_file.exists():
        return {'nodes': [], 'links': []}
    try:
        return _normalize_graph(json.loads(graph_file.read_text(encoding='utf-8')))
    except Exception:
        return {'nodes': [], 'links': []}


def _graph_file_signature(graph_file: Path) -> Tuple[str, int, int]:
    try:
        stat = graph_file.stat()
    except FileNotFoundError:
        return (str(graph_file), -1, -1)
    except OSError:
        return (str(graph_file), -2, -2)
    return (str(graph_file), stat.st_mtime_ns, stat.st_size)


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _read_external_graph_index() -> Dict[str, Dict[str, Any]]:
    if not EXTERNAL_GRAPH_INDEX_FILE.exists():
        return {}
    try:
        data = json.loads(EXTERNAL_GRAPH_INDEX_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items() if isinstance(value, dict)}


def _get_external_graph_display_name(graph_file: Path, index: Dict[str, Dict[str, Any]] = None) -> str:
    if index is None:
        index = _read_external_graph_index()
    entry = index.get(graph_file.stem, {})
    display_name = str(entry.get('graphName') or '').strip()
    return display_name or graph_file.name


def _build_export_graph(
    *,
    graph_id: str,
    graph_name: str,
    scope: str,
    source: str,
    storage_type: str,
    graph: Dict[str, Any],
    persisted: bool,
    is_active: bool,
    file_path: Path | None = None,
) -> Dict[str, Any]:
    normalized_graph = _normalize_graph(graph)
    return {
        'graphId': graph_id,
        'graphName': graph_name,
        'scope': scope,
        'source': source,
        'storageType': storage_type,
        'persisted': persisted,
        'isActive': is_active,
        'node_count': len(normalized_graph.get('nodes', [])),
        'link_count': len(normalized_graph.get('links', [])),
        'file_path': _relative_path(file_path) if file_path else None,
        'nodes': normalized_graph.get('nodes', []),
        'links': normalized_graph.get('links', []),
    }


def _merge_graphs(*graphs: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    merged_nodes: List[Dict[str, Any]] = []
    merged_links: List[Dict[str, Any]] = []
    for graph in graphs:
        if not isinstance(graph, dict):
            continue
        normalized = _normalize_graph(graph)
        merged_nodes.extend(normalized.get('nodes', []) or [])
        merged_links.extend(normalized.get('links', []) or [])
    return _deduplicate_graph({'nodes': merged_nodes, 'links': merged_links})


def _build_combined_graph(internal_graph: Dict[str, Any], binding_graph: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    merged_nodes = internal_graph.get('nodes', []) + binding_graph.get('nodes', [])
    merged_links = internal_graph.get('links', []) + binding_graph.get('links', [])

    node_map = {}
    for node in merged_nodes:
        node_id = node.get('id')
        if not node_id:
            continue
        normalized = _without_table_html(_ensure_node_name(node))
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
                if key == 'name' and not _should_replace_name(node_map[node_id].get('name'), value, node_id):
                    continue
                if value is not None:
                    node_map[node_id][key] = value

    link_map = {}
    for link in merged_links:
        source = link.get('source')
        target = link.get('target')
        relation = link.get('relation')
        if not source or not target or relation is None:
            continue
        link_key = f'{source}|||{target}|||{relation}'
        normalized = dict(link)
        if link_key not in link_map:
            link_map[link_key] = normalized
        else:
            for field, value in normalized.items():
                if value is not None:
                    link_map[link_key][field] = value

    return {'nodes': list(node_map.values()), 'links': list(link_map.values())}


def prime_combined_graph_cache(
    internal_graph: Dict[str, Any],
    binding_graph: Dict[str, Any],
    merged_graph: Dict[str, Any] = None,
) -> None:
    cache_key = (
        id(internal_graph),
        len(internal_graph.get('nodes', []) or []),
        len(internal_graph.get('links', []) or []),
        _graph_file_signature(INTERNAL_BINDING_GRAPH_FILE),
    )
    graph = (
        _ensure_graph_node_names(merged_graph, strip_table_html=True)
        if isinstance(merged_graph, dict)
        else _build_combined_graph(
            internal_graph,
            _attach_graph_local_file_ids(binding_graph, scope='internal_binding'),
        )
    )
    with _COMBINED_GRAPH_CACHE_LOCK:
        _COMBINED_GRAPH_CACHE['key'] = cache_key
        _COMBINED_GRAPH_CACHE['data'] = graph


def _list_external_graph_files() -> List[Path]:
    if not EXTERNAL_WORKSPACE_DIR.exists():
        return []

    graph_files: List[Path] = []
    for graph_file in sorted(EXTERNAL_WORKSPACE_DIR.glob('*.json')):
        if graph_file.name == 'workspace_meta.json':
            continue
        if graph_file.name == EXTERNAL_GRAPH_INDEX_FILE.name:
            continue
        if graph_file.name.startswith('temp_extracted_'):
            continue
        graph_files.append(graph_file)
    return graph_files


@api_bp.get('/health')
def health():
    return jsonify(
        {
            'code': 0,
            'msg': '成功',
            'status': 'ok',
            'app': settings.app_name,
            'provider': 'sql',
        }
    )


@api_bp.get('/providers')
def providers():
    return jsonify(
        {
            'code': 0,
            'msg': '成功',
            'default_provider': 'sql',
            'available_providers': ['sql'],
        }
    )


@api_bp.get('/current-user')
def current_user():
    user = UserService.get_current_user()
    user_dict = user.to_dict()
    return jsonify({'code': 0, 'msg': '成功', 'data': user_dict, **user_dict})


@api_bp.get('/graph')
def graph():
    data = GraphService.get_graph()
    return jsonify({'code': 0, 'msg': '成功', 'data': data})


@api_bp.get('/get_graph')
def get_graph_internal():
    # 与 xintuoyin 前端交互结构对齐：直接返回 nodes + links
    data = GraphService.get_graph()
    return jsonify(
        {
            'nodes': data.get('nodes', []),
            'links': data.get('links', []),
        }
    )


@api_bp.get('/internal/get_graph')
def get_graph_internal_alias():
    data = GraphService.get_graph()
    return jsonify({'code': 0, 'msg': '成功', 'data': data})


@api_bp.get('/internal/workspace/status')
def internal_workspace_status():
    data = GraphService.get_graph_status()
    return jsonify({'code': 0, 'msg': '成功', 'data': data})


@api_bp.get('/node/<node_id>')
def node_detail(node_id: str):
    data = GraphService.get_node_detail(node_id)
    return jsonify({'code': 0, 'msg': '成功', 'data': data})


@api_bp.get('/search')
def search_nodes():
    keyword = request.args.get('keyword', '')
    result = GraphService.search_nodes(keyword)
    return jsonify({'code': 0, 'msg': '成功', 'keyword': keyword, 'data': result})


@api_bp.get('/combined_graph')
def get_combined_graph():
    internal_graph = GraphService.get_graph()
    binding_signature = _graph_file_signature(INTERNAL_BINDING_GRAPH_FILE)
    cache_key = (
        id(internal_graph),
        len(internal_graph.get('nodes', []) or []),
        len(internal_graph.get('links', []) or []),
        binding_signature,
    )

    with _COMBINED_GRAPH_CACHE_LOCK:
        cached_graph = _COMBINED_GRAPH_CACHE.get('data')
        if cached_graph is not None and _COMBINED_GRAPH_CACHE.get('key') == cache_key:
            return jsonify({
                'code': 0,
                'msg': '成功',
                'data': {
                    'graphId': 'combined_graph',
                    'graphName': 'combined',
                    'nodes': cached_graph.get('nodes', []),
                    'links': cached_graph.get('links', []),
                }
            })

    binding_graph = _attach_graph_local_file_ids(
        _read_graph_file(INTERNAL_BINDING_GRAPH_FILE),
        scope='internal_binding',
    )
    merged_graph = _build_combined_graph(internal_graph, binding_graph)

    with _COMBINED_GRAPH_CACHE_LOCK:
        _COMBINED_GRAPH_CACHE['key'] = cache_key
        _COMBINED_GRAPH_CACHE['data'] = merged_graph

    return jsonify({
        'code': 0,
        'msg': '成功',
        'data': {
            'graphId': 'combined_graph',
            'graphName': 'combined',
            'nodes': merged_graph.get('nodes', []),
            'links': merged_graph.get('links', []),
        }
    })


@api_bp.get('/get_all_graph')
def get_all_graph():
    current_external_db = ''
    if EXTERNAL_CURRENT_DB_FILE.exists():
        try:
            current_external_db = EXTERNAL_CURRENT_DB_FILE.read_text(encoding='utf-8').strip()
        except Exception:
            current_external_db = ''

    graphs: List[Dict[str, Any]] = []

    internal_graph = GraphService.get_graph()
    merged_internal_graph = internal_graph
    internal_source = 'sql_provider'
    internal_storage_type = 'sql'
    internal_persisted = False

    if INTERNAL_BINDING_GRAPH_FILE.exists():
        binding_graph = _attach_graph_local_file_ids(
            _read_graph_file(INTERNAL_BINDING_GRAPH_FILE),
            scope='internal_binding',
        )
        merged_internal_graph = _merge_graphs(internal_graph, binding_graph)
        internal_source = 'sql_provider+internal_binding_workspace'
        internal_storage_type = 'hybrid'
        internal_persisted = True

    graphs.append(
        _build_export_graph(
            graph_id=GraphService.INTERNAL_GRAPH_ID,
            graph_name=GraphService.INTERNAL_GRAPH_NAME,
            scope='internal',
            source=internal_source,
            storage_type=internal_storage_type,
            graph=merged_internal_graph,
            persisted=internal_persisted,
            is_active=True,
        )
    )

    external_graph_index = _read_external_graph_index()
    for external_graph_file in _list_external_graph_files():
        graph = _read_graph_file(external_graph_file)
        graphs.append(
            _build_export_graph(
                graph_id=external_graph_file.stem,
                graph_name=_get_external_graph_display_name(external_graph_file, external_graph_index),
                scope='external',
                source='external_workspace',
                storage_type='json_file',
                graph=graph,
                persisted=True,
                is_active=external_graph_file.name == current_external_db,
                file_path=external_graph_file,
            )
        )

    internal_count = sum(1 for graph in graphs if graph.get('scope') == 'internal')
    external_count = sum(1 for graph in graphs if graph.get('scope') == 'external')

    return jsonify(
        {
            'code': 0,
            'msg': '成功',
            'data': {
                'exported_at': datetime.now().isoformat(timespec='seconds'),
                'graph_count': len(graphs),
                'internal_graph_count': internal_count,
                'external_graph_count': external_count,
                'graphs': graphs,
            },
        }
    )
