from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Sequence

from ..providers.sql_provider import get_sql_provider


class GraphService:
    INTERNAL_GRAPH_ID = 'internal_sql_graph'
    INTERNAL_GRAPH_NAME = '系统图谱'
    _FIXED_ASSET_CODE_PREFIX = 'gd'
    _INTANGIBLE_ASSET_CODE_PREFIX = 'wx'

    _UNIFIED_KIND_TO_GROUP = {
        'person': 1,
        'fixed_asset': 3,
        'intangible_asset': 3,
        'enterprise': 2,
    }
    _DEFAULT_GROUP = 4

    _PERSON_NODE_TYPES = {
        '4_PROJECT_PERSONNEL_STAFF',
        '4_STAFF',
        '3_WAGE_STAFF',
        '4_ATTENDANCE_STAFF',
    }
    _FIXED_ASSET_NODE_TYPES = {
        '4_PROJECT_FIXED_ASSET',
        '3_FIN_FIXED_ASSET',
    }
    _INTANGIBLE_ASSET_NODE_TYPES = {
        '4_PROJECT_INTANGIBLE_ASSET',
        '3_FIN_INTANGIBLE_ASSET',
    }
    _INTANGIBLE_ASSET_HINTS = (
        '专利',
        '软著',
        '非专利',
        '无形',
        '著作权',
    )
    _SOURCE_TITLE_BY_TYPE = {
        '4_PROJECT_PERSONNEL_STAFF': '项目库-项目-项目人员',
        '4_STAFF': '人事-成员-部门',
        '3_WAGE_STAFF': '人事-工资',
        '4_ATTENDANCE_STAFF': '人事-考勤',
        '4_PROJECT_FIXED_ASSET': '项目库-项目-固定资产',
        '3_FIN_FIXED_ASSET': '财务-固定资产',
        '4_PROJECT_INTANGIBLE_ASSET': '项目库-项目-无形资产',
        '3_FIN_INTANGIBLE_ASSET': '财务-无形资产',
    }
    _PERSON_IDENTITY_KEYS = (
        '工号',
        '员工工号',
        '员工编号',
        '员工ID',
        '人员ID',
        '职工ID',
        '职工编号',
        'ID',
        '身份证',
    )
    _ASSET_IDENTITY_KEYS = (
        '资产编号',
        '资产编码',
        '资产ID',
        'ID',
        '编码',
        '编号',
    )

    @staticmethod
    def get_graph():
        provider = get_sql_provider()
        user = provider.get_current_user()
        payload = provider.get_graph_payload(user)
        flat_graph = GraphService._build_flat_graph(payload)
        return {
            'graphId': GraphService.INTERNAL_GRAPH_ID,
            'graphName': GraphService.INTERNAL_GRAPH_NAME,
            'nodes': flat_graph['nodes'],
            'links': flat_graph['links'],
        }

    @staticmethod
    def get_graph_status():
        graph = GraphService.get_graph()
        nodes = graph.get('nodes', [])
        links = graph.get('links', [])
        return {
            'exists': bool(nodes or links),
            'node_count': len(nodes),
            'link_count': len(links),
            'graphId': graph.get('graphId'),
            'graphName': graph.get('graphName'),
            'available_graphs': [graph.get('graphName')],
        }

    @staticmethod
    def get_node_detail(node_id: str):
        provider = get_sql_provider()
        user = provider.get_current_user()
        return provider.get_node_detail(node_id, user)

    @staticmethod
    def search_nodes(keyword: str):
        provider = get_sql_provider()
        user = provider.get_current_user()

        keyword_norm = (keyword or '').strip().lower()
        if not keyword_norm:
            return []

        payload = provider.get_graph_payload(user)
        flat_graph = GraphService._build_flat_graph(payload)
        matches = []
        for node in flat_graph.get('nodes', []):
            node_id = str(node.get('id', '')).strip()
            node_name = str(node.get('name', '')).strip()
            haystacks = [node_id.lower(), node_name.lower()]
            if not any(keyword_norm in text for text in haystacks):
                continue
            matches.append(
                {
                    'id': node_id,
                    'name': node_name,
                    'level': node.get('level'),
                    'parent_id': node.get('parent_id'),
                    'type': node.get('type'),
                    'identity_key': node.get('identity_key'),
                }
            )
        return matches

    @staticmethod
    def _build_flat_graph(payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        root = payload.get('root') or {}

        nodes_by_id: Dict[str, Dict[str, Any]] = {}
        links: List[Dict[str, Any]] = []
        link_seen: set[str] = set()
        unified_identity_index: Dict[str, str] = {}

        def normalize_text(value: Any) -> str:
            return ' '.join(str(value or '').strip().split())

        def is_empty(value: Any) -> bool:
            if value in (None, '', 'null'):
                return True
            if isinstance(value, (list, tuple, set, dict)) and not value:
                return True
            return False

        def as_tags(value: Any) -> List[str]:
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                return [str(item) for item in value if str(item).strip()]
            return []

        def merge_value(existing: Any, incoming: Any) -> Any:
            if is_empty(incoming):
                return existing
            if is_empty(existing):
                return incoming
            if existing == incoming:
                return existing
            if isinstance(existing, list):
                merged = [item for item in existing]
                if incoming not in merged:
                    merged.append(incoming)
                return merged
            if isinstance(incoming, list):
                merged = [existing]
                for item in incoming:
                    if item not in merged:
                        merged.append(item)
                return merged
            return [existing, incoming]

        def merge_attrs(target: Dict[str, Any], incoming: Dict[str, Any]) -> None:
            for key, value in incoming.items():
                if is_empty(value):
                    continue
                if key not in target:
                    target[key] = value
                else:
                    target[key] = merge_value(target.get(key), value)

        def extract_attrs(detail: Dict[str, Any]) -> Dict[str, Any]:
            attrs: Dict[str, Any] = {}
            # 按要求仅展示 detail.basic 中的信息
            data = detail.get('basic')
            if isinstance(data, dict):
                merge_attrs(attrs, data)
            return attrs

        def normalize_identity_value(value: Any) -> str:
            if is_empty(value):
                return ''
            if isinstance(value, list):
                for item in value:
                    normalized = normalize_identity_value(item)
                    if normalized:
                        return normalized
                return ''
            return normalize_text(value).lower()

        def first_attr_identity(attrs: Dict[str, Any], keys: Sequence[str]) -> str:
            for key in keys:
                if key not in attrs:
                    continue
                normalized = normalize_identity_value(attrs.get(key))
                if normalized:
                    return normalized
            return ''

        def extract_suffix_after_prefix(node_id: str, prefix: str, *, use_last_segment: bool = False) -> str:
            if not node_id.startswith(prefix):
                return ''
            tail = node_id[len(prefix):].strip('_')
            if not tail:
                return ''
            if use_last_segment and '_' in tail:
                tail = tail.rsplit('_', 1)[-1]
            return normalize_identity_value(tail)

        def extract_identity_from_node_id(node_type: str, node_id: str) -> str:
            if node_type == '4_STAFF':
                return extract_suffix_after_prefix(node_id, '4_STAFF_')
            if node_type == '3_WAGE_STAFF':
                return extract_suffix_after_prefix(node_id, '3_WAGE_STAFF_')
            if node_type == '4_ATTENDANCE_STAFF':
                return extract_suffix_after_prefix(node_id, '4_ATTENDANCE_STAFF_', use_last_segment=True)
            if node_type == '4_PROJECT_PERSONNEL_STAFF':
                return extract_suffix_after_prefix(node_id, '4_PROJECT_PERSONNEL_STAFF_', use_last_segment=True)
            if node_type == '3_FIN_FIXED_ASSET':
                return extract_suffix_after_prefix(node_id, '3_FIN_FIXED_ASSET_')
            if node_type == '4_PROJECT_FIXED_ASSET':
                return extract_suffix_after_prefix(node_id, '4_PROJECT_FIXED_ASSET_', use_last_segment=True)
            if node_type == '3_FIN_INTANGIBLE_ASSET':
                return extract_suffix_after_prefix(node_id, '3_FIN_INTANGIBLE_ASSET_')
            if node_type == '4_PROJECT_INTANGIBLE_ASSET':
                return extract_suffix_after_prefix(node_id, '4_PROJECT_INTANGIBLE_ASSET_', use_last_segment=True)
            if node_type == '4_ATTENDANCE_ASSET':
                return extract_suffix_after_prefix(node_id, '4_ATTENDANCE_ASSET_', use_last_segment=True)
            return ''

        def extract_identity_from_identity_key(identity_key: Any) -> str:
            text = normalize_identity_value(identity_key)
            if not text:
                return ''
            if ':' in text:
                token = text.rsplit(':', 1)[-1]
                return normalize_identity_value(token)
            return text

        def extract_unified_identity(
            node: Dict[str, Any],
            node_type: str,
            attrs: Dict[str, Any],
            unified_kind: str | None,
            node_id: str,
        ) -> str:
            if unified_kind == 'person':
                token = first_attr_identity(attrs, GraphService._PERSON_IDENTITY_KEYS)
            elif unified_kind in {'fixed_asset', 'intangible_asset'}:
                token = first_attr_identity(attrs, GraphService._ASSET_IDENTITY_KEYS)
            else:
                return ''

            if token:
                return token
            token = extract_identity_from_node_id(node_type, node_id)
            if token:
                return token
            return extract_identity_from_identity_key(node.get('identity_key'))

        def infer_asset_kind_by_code_prefix(identity_token: str) -> str | None:
            token = normalize_identity_value(identity_token)
            if not token:
                return None
            if token.startswith(GraphService._FIXED_ASSET_CODE_PREFIX):
                return 'fixed_asset'
            if token.startswith(GraphService._INTANGIBLE_ASSET_CODE_PREFIX):
                return 'intangible_asset'
            return None

        def extract_asset_identity_hint(node: Dict[str, Any], node_type: str, attrs: Dict[str, Any], node_id: str) -> str:
            token = first_attr_identity(attrs, GraphService._ASSET_IDENTITY_KEYS)
            if token:
                return token
            token = extract_identity_from_node_id(node_type, node_id)
            if token:
                return token
            return extract_identity_from_identity_key(node.get('identity_key'))

        def preload_asset_identity_hints(root_node: Dict[str, Any]) -> tuple[set[str], set[str]]:
            fixed_tokens: set[str] = set()
            intangible_tokens: set[str] = set()

            def dfs(current: Dict[str, Any]) -> None:
                current_id = str(current.get('id', '')).strip()
                current_type = str(current.get('type', '')).strip()
                current_detail = current.get('detail') if isinstance(current.get('detail'), dict) else {}
                current_attrs = extract_attrs(current_detail)

                if current_type in GraphService._FIXED_ASSET_NODE_TYPES:
                    token = extract_asset_identity_hint(current, current_type, current_attrs, current_id)
                    if token:
                        prefix_kind = infer_asset_kind_by_code_prefix(token)
                        if prefix_kind == 'intangible_asset':
                            intangible_tokens.add(token)
                        else:
                            fixed_tokens.add(token)
                elif current_type in GraphService._INTANGIBLE_ASSET_NODE_TYPES:
                    token = extract_asset_identity_hint(current, current_type, current_attrs, current_id)
                    if token:
                        prefix_kind = infer_asset_kind_by_code_prefix(token)
                        if prefix_kind == 'fixed_asset':
                            fixed_tokens.add(token)
                        else:
                            intangible_tokens.add(token)

                for child in current.get('children') or []:
                    if isinstance(child, dict):
                        dfs(child)

            if isinstance(root_node, dict) and root_node:
                dfs(root_node)

            return fixed_tokens, intangible_tokens

        fixed_asset_hint_tokens, intangible_asset_hint_tokens = preload_asset_identity_hints(root)

        @staticmethod
        def unified_kind_to_group(unified_kind: str | None) -> int:
            if unified_kind and unified_kind in GraphService._UNIFIED_KIND_TO_GROUP:
                return GraphService._UNIFIED_KIND_TO_GROUP[unified_kind]
            return GraphService._DEFAULT_GROUP

        def classify_unified_kind(node: Dict[str, Any], node_type: str, attrs: Dict[str, Any], node_id: str) -> str | None:
            if node_type in GraphService._FIXED_ASSET_NODE_TYPES | GraphService._INTANGIBLE_ASSET_NODE_TYPES | {'4_ATTENDANCE_ASSET'}:
                hint_token = extract_asset_identity_hint(node, node_type, attrs, node_id)
                prefix_kind = infer_asset_kind_by_code_prefix(hint_token)
                if prefix_kind:
                    return prefix_kind

            if node_type in GraphService._PERSON_NODE_TYPES:
                return 'person'
            if node_type in GraphService._FIXED_ASSET_NODE_TYPES:
                return 'fixed_asset'
            if node_type in GraphService._INTANGIBLE_ASSET_NODE_TYPES:
                return 'intangible_asset'
            if node_type == '4_ATTENDANCE_ASSET':
                asset_type_text = normalize_text(attrs.get('资产类型')).lower()
                if any(token in asset_type_text for token in GraphService._INTANGIBLE_ASSET_HINTS):
                    return 'intangible_asset'
                hint_token = extract_asset_identity_hint(node, node_type, attrs, node_id)
                if hint_token:
                    in_fixed = hint_token in fixed_asset_hint_tokens
                    in_intangible = hint_token in intangible_asset_hint_tokens
                    if in_intangible and not in_fixed:
                        return 'intangible_asset'
                    if in_fixed and not in_intangible:
                        return 'fixed_asset'
                    if in_intangible and in_fixed:
                        return 'intangible_asset'
                return 'fixed_asset'
            return None

        def unified_node_type(unified_kind: str | None) -> str | None:
            if unified_kind == 'person':
                return 'UNIFIED_PERSON'
            if unified_kind == 'fixed_asset':
                return 'UNIFIED_FIXED_ASSET'
            if unified_kind == 'intangible_asset':
                return 'UNIFIED_INTANGIBLE_ASSET'
            return None

        def build_canonical_id(node_id: str, unified_kind: str | None, identity_token: str) -> str:
            if not unified_kind:
                return node_id
            if not identity_token:
                return node_id
            key = f'{unified_kind}:{identity_token}'
            existing = unified_identity_index.get(key)
            if existing:
                return existing
            digest = hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]
            canonical_id = f'U_{unified_kind.upper()}_{digest}'
            unified_identity_index[key] = canonical_id
            return canonical_id

        def source_block_title(node_type: str, unified_kind: str | None) -> str:
            if node_type == '4_ATTENDANCE_ASSET':
                if unified_kind == 'intangible_asset':
                    return '人事-考勤组-资产（无形资产类型）'
                return '人事-考勤组-资产（固定资产类型）'
            return GraphService._SOURCE_TITLE_BY_TYPE.get(node_type, '相关信息')

        def walk(node: Dict[str, Any], parent_canonical_id: str | None = None) -> None:
            node_id = str(node.get('id', '')).strip()
            if not node_id:
                return

            node_name = normalize_text(node.get('name')) or node_id
            node_type = str(node.get('type', '')).strip()
            detail = node.get('detail') if isinstance(node.get('detail'), dict) else {}
            attrs = extract_attrs(detail)
            base_unified_kind = classify_unified_kind(node, node_type, attrs, node_id)
            identity_token = extract_unified_identity(node, node_type, attrs, base_unified_kind, node_id)
            unified_kind = base_unified_kind if identity_token else None
            canonical_id = build_canonical_id(node_id, unified_kind, identity_token)

            payload = nodes_by_id.get(canonical_id)
            if payload is None:
                group_value = unified_kind_to_group(unified_kind)
                payload = {
                    'id': canonical_id,
                    'name': node_name,
                    'group': group_value,
                    'attrs': {},
                    'attrs_blocks': [],
                    'type': unified_node_type(unified_kind) or node_type,
                    'category': node.get('category'),
                    'level': node.get('level'),
                    'side': node.get('side'),
                    'parent_id': parent_canonical_id,
                    'fixed': bool(node.get('fixed')),
                    'leaf': bool(node.get('leaf')),
                    'expandable': bool(node.get('expandable', True)),
                    'summary': node.get('summary', ''),
                    'tags': as_tags(node.get('tags')),
                    'identity_key': (
                        f'UNIFIED:{unified_kind}:{identity_token}'
                        if unified_kind
                        else node.get('identity_key')
                    ),
                    'merged_entity': bool(unified_kind),
                    'merged_entity_kind': unified_kind,
                    '_block_map': {},
                    '_source_node_ids': [],
                }
                nodes_by_id[canonical_id] = payload
            else:
                current_level = payload.get('level')
                incoming_level = node.get('level')
                if isinstance(current_level, int) and isinstance(incoming_level, int):
                    payload['level'] = min(current_level, incoming_level)
                elif current_level is None and isinstance(incoming_level, int):
                    payload['level'] = incoming_level
                payload['leaf'] = bool(payload.get('leaf', False)) and bool(node.get('leaf'))
                payload['expandable'] = bool(payload.get('expandable', False)) or bool(node.get('expandable', True))
                if not payload.get('summary') and node.get('summary'):
                    payload['summary'] = node.get('summary')
                if not payload.get('parent_id') and parent_canonical_id:
                    payload['parent_id'] = parent_canonical_id
                for tag in as_tags(node.get('tags')):
                    if tag not in payload['tags']:
                        payload['tags'].append(tag)

            merge_attrs(payload['attrs'], attrs)
            block_title = source_block_title(node_type, unified_kind)
            block = payload['_block_map'].get(block_title)
            if block is None:
                block = {
                    'title': block_title,
                    'attrs': {},
                }
                payload['_block_map'][block_title] = block
                payload['attrs_blocks'].append(block)
            merge_attrs(block['attrs'], attrs)

            if node_id not in payload['_source_node_ids']:
                payload['_source_node_ids'].append(node_id)

            if parent_canonical_id and parent_canonical_id != canonical_id:
                link_key = f'{parent_canonical_id}|||{canonical_id}|||包含'
                if link_key not in link_seen:
                    link_seen.add(link_key)
                    links.append(
                        {
                            'source': parent_canonical_id,
                            'target': canonical_id,
                            'relation': '包含',
                            'type': 'resolved',
                            'line_style': 'solid',
                        }
                    )

            for child in node.get('children') or []:
                if isinstance(child, dict):
                    walk(child, canonical_id)

        if isinstance(root, dict) and root:
            walk(root, None)

        nodes: List[Dict[str, Any]] = []
        for node in nodes_by_id.values():
            node.pop('_block_map', None)
            source_ids = node.pop('_source_node_ids', [])
            if source_ids:
                node['source_node_ids'] = source_ids
            node['attrs_blocks'] = [
                block for block in node.get('attrs_blocks', [])
                if isinstance(block, dict) and isinstance(block.get('attrs'), dict) and block.get('attrs')
            ]
            nodes.append(node)

        return {'nodes': nodes, 'links': links}
