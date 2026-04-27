from __future__ import annotations

from datetime import datetime
from threading import RLock
from time import time
from typing import Any, Dict, List, Optional, Tuple

from ..builders.graph_builder import GraphTreeBuilder
from ..db.connection import get_mysql_connection
from ..detail.resolvers import NodeDetailResolver
from ..models.graph_models import CurrentUser, GraphNode
from ..repositories.graph_repository import GraphRepository


class SQLGraphProvider:
    name = 'sql'

    def __init__(self):
        self.repository = GraphRepository()
        self.builder = GraphTreeBuilder()
        self.detail_resolver = NodeDetailResolver()
        self._cache_lock = RLock()
        self._graph_cache_ttl_seconds = 120
        self._graph_cache_max_entries = 8
        self._graph_cache: Dict[Tuple[str, str, int, int], Dict[str, Any]] = {}

    def get_current_user(self) -> CurrentUser:
        conn = get_mysql_connection()
        if conn is None:
            return self._fallback_user()

        try:
            self._warmup_schema(conn)
            row = self.repository.fetch_current_user(conn)
            if row:
                return CurrentUser(**row)
        finally:
            conn.close()

        return self._fallback_user()

    def _safe_domain_fetch(self, fetcher, **kwargs) -> Dict:
        try:
            result = fetcher(**kwargs)
        except Exception:
            return {}
        return result or {}

    def _current_period(self) -> Tuple[int, int]:
        now = datetime.now()
        return 2025, 12
        # return now.year, now.month

    def _make_graph_cache_key(self, user: CurrentUser, year: int, month: int) -> Tuple[str, str, int, int]:
        return (str(user.user_id), str(user.enterprise_id), year, month)

    def _warmup_schema(self, conn) -> None:
        try:
            self.repository.warmup_schema_cache(conn)
        except Exception:
            pass

    def _build_graph_entry(self, user: CurrentUser, year: int, month: int) -> Dict[str, Any]:
        conn = get_mysql_connection()
        if conn is None:
            root_node = self.builder.build_placeholder_tree(user)
            root_dict = root_node.to_dict()
            node_index, name_index = self._index_graph_nodes(root_dict)
            return {
                'created_at': time(),
                'root_node': root_node,
                'root_dict': root_dict,
                'node_index': node_index,
                'name_index': name_index,
                'detail_cache': {},
            }

        try:
            self._warmup_schema(conn)
            hr_domain = self._safe_domain_fetch(
                self.repository.fetch_hr_domain,
                conn=conn,
                tenant_id=user.user_id,
                year=year,
                month=month,
            )
            project_domain = self._safe_domain_fetch(
                self.repository.fetch_project_library_domain,
                conn=conn,
                tenant_id=user.user_id,
                year=year,
                month=month,
                hr_domain=hr_domain,
            )
            finance_domain = self._safe_domain_fetch(
                self.repository.fetch_finance_domain,
                conn=conn,
                tenant_id=user.user_id,
                year=year,
                current_month=month,
            )
            declaration_domain = self._safe_domain_fetch(
                self.repository.fetch_declaration_domain,
                conn=conn,
                tenant_id=user.user_id,
                year=year,
            )
            risk_domain = self._safe_domain_fetch(
                self.repository.fetch_risk_domain,
                conn=conn,
                tenant_id=user.user_id,
                year=year,
            )

            payload = {
                'hr': hr_domain,
                'project_library': project_domain,
                'finance': finance_domain,
                'declaration': declaration_domain,
                'risks': risk_domain,
            }
            root_node = self.builder.build_graph_tree(user, payload)
            root_dict = root_node.to_dict()
            node_index, name_index = self._index_graph_nodes(root_dict)
            return {
                'created_at': time(),
                'root_node': root_node,
                'root_dict': root_dict,
                'node_index': node_index,
                'name_index': name_index,
                'detail_cache': {},
            }
        finally:
            conn.close()

    def _prune_graph_cache(self, now_ts: float) -> None:
        expired_keys = [
            key
            for key, entry in self._graph_cache.items()
            if now_ts - float(entry.get('created_at', 0)) > self._graph_cache_ttl_seconds
        ]
        for key in expired_keys:
            self._graph_cache.pop(key, None)

        while len(self._graph_cache) > self._graph_cache_max_entries:
            oldest_key = min(
                self._graph_cache.items(),
                key=lambda item: float(item[1].get('created_at', 0)),
            )[0]
            self._graph_cache.pop(oldest_key, None)

    def _get_graph_entry(self, user: CurrentUser) -> Dict[str, Any]:
        current_year, current_month = self._current_period()
        cache_key = self._make_graph_cache_key(user, current_year, current_month)
        now_ts = time()

        with self._cache_lock:
            entry = self._graph_cache.get(cache_key)
            if entry and now_ts - float(entry.get('created_at', 0)) <= self._graph_cache_ttl_seconds:
                return entry
            self._graph_cache.pop(cache_key, None)
            self._prune_graph_cache(now_ts)

        entry = self._build_graph_entry(user, current_year, current_month)

        with self._cache_lock:
            self._graph_cache[cache_key] = entry
            self._prune_graph_cache(time())
            return self._graph_cache[cache_key]

    def _index_graph_nodes(self, root: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        node_index: Dict[str, Dict[str, Any]] = {}
        name_index: Dict[str, List[Dict[str, Any]]] = {}

        def dfs(node: Dict[str, Any]) -> None:
            node_id = str(node.get('id', '')).strip()
            if node_id:
                node_index[node_id] = node

            node_name = str(node.get('name', '')).strip().lower()
            if node_name:
                name_index.setdefault(node_name, []).append(
                    {
                        'id': node.get('id'),
                        'name': node.get('name'),
                        'level': node.get('level'),
                        'parent_id': node.get('parent_id'),
                        'type': node.get('type'),
                        'identity_key': node.get('identity_key'),
                    }
                )

            for child in node.get('children', []) or []:
                dfs(child)

        dfs(root)
        return node_index, name_index

    def get_graph_tree(self, user: CurrentUser) -> GraphNode:
        return self._get_graph_entry(user)['root_node']

    def get_graph_payload(self, user: CurrentUser) -> Dict:
        entry = self._get_graph_entry(user)
        return {
            'root': entry['root_dict'],
        }

    def get_node_detail(self, node_id: str, user: CurrentUser) -> Dict:
        normalized_node_id = str(node_id).strip()
        entry = self._get_graph_entry(user)
        node = entry['node_index'].get(normalized_node_id)
        if not node:
            return {'id': node_id, 'exists': False, 'message': '未找到节点'}

        cached_detail = entry['detail_cache'].get(normalized_node_id)
        if cached_detail is not None:
            return cached_detail

        detail = self.detail_resolver.build(node)
        with self._cache_lock:
            entry['detail_cache'][normalized_node_id] = detail
        return detail

    def search_nodes(self, keyword: str, user: CurrentUser):
        keyword = (keyword or '').strip().lower()
        if not keyword:
            return []
        entry = self._get_graph_entry(user)
        return list(entry['name_index'].get(keyword, []))

    def _find_node(self, node: Dict, node_id: str) -> Optional[Dict]:
        if node.get('id') == node_id:
            return node
        for child in node.get('children', []):
            result = self._find_node(child, node_id)
            if result:
                return result
        return None

    def _fallback_user(self) -> CurrentUser:
        return CurrentUser(
            user_id='u_sql_demo',
            username='sql_demo_user',
            enterprise_id='ent_sql_demo',
            enterprise_name='待接入企业（SQL Provider）',
        )


_provider: Optional[SQLGraphProvider] = None


def get_sql_provider() -> SQLGraphProvider:
    global _provider
    if _provider is None:
        _provider = SQLGraphProvider()
    return _provider
