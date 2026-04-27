import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from flask import Blueprint, jsonify, request

from ..config import settings
from ..services.graph_service import GraphService
from ..services.user_service import UserService

api_bp = Blueprint('api', __name__, url_prefix='/api')

REPO_ROOT = Path(__file__).resolve().parents[4]
EXTERNAL_WORKSPACE_DIR = REPO_ROOT / 'runtime' / 'external_workspace'
EXTERNAL_CURRENT_DB_FILE = EXTERNAL_WORKSPACE_DIR / 'current_db.txt'
INTERNAL_BINDING_DIR = REPO_ROOT / 'runtime' / 'internal_binding_workspace'
INTERNAL_BINDING_GRAPH_FILE = INTERNAL_BINDING_DIR / 'internal_binding_graph.json'


def _deduplicate_graph(graph: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    node_map: Dict[str, Dict[str, Any]] = {}
    for node in graph.get('nodes', []) or []:
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


def _relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


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


def _list_external_graph_files() -> List[Path]:
    if not EXTERNAL_WORKSPACE_DIR.exists():
        return []

    graph_files: List[Path] = []
    for graph_file in sorted(EXTERNAL_WORKSPACE_DIR.glob('*.json')):
        if graph_file.name == 'workspace_meta.json':
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
    binding_graph = _read_graph_file(INTERNAL_BINDING_GRAPH_FILE)

    merged_nodes = internal_graph.get('nodes', []) + binding_graph.get('nodes', [])
    merged_links = internal_graph.get('links', []) + binding_graph.get('links', [])

    node_map = {}
    for node in merged_nodes:
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

    link_map = {}
    for link in merged_links:
        source = link.get('source')
        target = link.get('target')
        relation = link.get('relation')
        if not source or not target or relation is None:
            continue
        key = f'{source}|||{target}|||{relation}'
        normalized = dict(link)
        if key not in link_map:
            link_map[key] = normalized

    return jsonify({
        'code': 0,
        'msg': '成功',
        'data': {
            'graphId': 'combined_graph',
            'graphName': 'combined',
            'nodes': list(node_map.values()),
            'links': list(link_map.values()),
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
        binding_graph = _read_graph_file(INTERNAL_BINDING_GRAPH_FILE)
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

    for external_graph_file in _list_external_graph_files():
        graph = _read_graph_file(external_graph_file)
        graphs.append(
            _build_export_graph(
                graph_id=external_graph_file.stem,
                graph_name=external_graph_file.name,
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
