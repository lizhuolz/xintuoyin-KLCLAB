from __future__ import annotations

from typing import Any, Dict, List


class NodeDetailResolver:
    def build(self, node: Dict[str, Any]) -> Dict[str, Any]:
        if not node:
            return {'exists': False, 'message': '未找到节点'}

        resolver = DETAIL_RESOLVERS.get(node.get('type'), DefaultDetailResolver())
        return resolver.build(node)


class BaseDetailResolver:
    template = 'default'

    def build(self, node: Dict[str, Any]) -> Dict[str, Any]:
        detail = node.get('detail', {}) or {}
        sections: List[Dict[str, Any]] = []
        self._append_kv_section(sections, '相关信息', detail.get('basic', {}))
        # self._append_kv_section(sections, '动态信息', detail.get('dynamic', {}))
        # self._append_kv_section(sections, '指标信息', detail.get('metrics', {}))
        # self._append_text_section(sections, '说明', detail.get('description', '') or '暂无说明')
        return self._base_payload(node=node, sections=sections)

    def _base_payload(self, node: Dict[str, Any], sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        detail = node.get('detail', {}) or {}
        attrs: Dict[str, Any] = {}
        for section in ('basic', 'dynamic', 'metrics'):
            mapping = detail.get(section)
            if isinstance(mapping, dict):
                attrs.update(mapping)
        if detail.get('description'):
            attrs['说明'] = detail.get('description')

        return {
            'id': node['id'],
            'name': node['name'],
            'type': node['type'],
            'category': node.get('category'),
            'level': node.get('level'),
            'summary': node.get('summary', ''),
            'tags': node.get('tags', []),
            'fixed': node.get('fixed', False),
            'leaf': node.get('leaf', False),
            'identity_key': node.get('identity_key'),
            'parent_id': node.get('parent_id'),
            'side': node.get('side'),
            'attrs': attrs,
            'exists': True,
            'view': {
                'template': self.template,
                'sections': sections,
            },
        }

    def _append_kv_section(self, sections: List[Dict[str, Any]], title: str, mapping: Dict[str, Any]) -> None:
        items = [
            {
                'label': str(key),
                'value': self._stringify(value),
            }
            for key, value in (mapping or {}).items()
            if value not in (None, '')
        ]
        if items:
            sections.append({'type': 'kv', 'title': title, 'items': items})

    def _append_text_section(self, sections: List[Dict[str, Any]], title: str, content: str) -> None:
        if content:
            sections.append({'type': 'text', 'title': title, 'content': content})

    def _stringify(self, value: Any) -> str:
        if isinstance(value, (list, tuple, set)):
            return '、'.join(str(item) for item in value)
        if isinstance(value, dict):
            return '；'.join(f'{key}: {item}' for key, item in value.items())
        return str(value)


class EnterpriseDetailResolver(BaseDetailResolver):
    template = 'ENTERPRISE'
    def build(self, node: Dict[str, Any]) -> Dict[str, Any]:
        detail = node.get('detail', {}) or {}
        sections: List[Dict[str, Any]] = []
        self._append_kv_section(sections, '企业概览', detail.get('basic', {}))
        return self._base_payload(node=node, sections=sections)

class DefaultDetailResolver(BaseDetailResolver):
    template = 'default'


DETAIL_RESOLVERS = {
    'ENTERPRISE': EnterpriseDetailResolver(),
}
