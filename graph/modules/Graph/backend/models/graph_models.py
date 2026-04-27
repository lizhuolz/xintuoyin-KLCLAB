from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class NodeDetail:
    basic: Dict[str, Any] = field(default_factory=dict)
    dynamic: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    description: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphNode:
    id: str
    name: str
    type: str
    category: str
    level: int
    side: str = 'right'
    parent_id: Optional[str] = None
    fixed: bool = False
    leaf: bool = False
    expandable: bool = True
    summary: str = ''
    tags: List[str] = field(default_factory=list)
    identity_key: Optional[str] = None
    detail: NodeDetail = field(default_factory=NodeDetail)
    children: List['GraphNode'] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['detail'] = self.detail.to_dict()
        data['children'] = [child.to_dict() for child in self.children]
        return data


@dataclass
class CurrentUser:
    user_id: str
    username: str
    enterprise_id: str
    enterprise_name: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
