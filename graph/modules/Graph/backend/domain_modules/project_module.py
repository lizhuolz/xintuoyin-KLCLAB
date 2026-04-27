
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from ..models.graph_models import GraphNode


class ProjectGraphBuilderMixin:

    @staticmethod
    def _to_float(value: Any) -> float:
        if value in (None, '', 'null'):
            return 0.0
        try:
            return float(value)
        except Exception:
            return 0.0


    def build_project_nodes(self, tenant_id: str, projects: List[Dict[str, Any]]) -> List[GraphNode]:
        nodes: List[GraphNode] = []
        for project in projects:
            project_id = str(project.get('id', 'unknown'))
            project_name = project.get('name') or f'项目_{project_id}'

            overview_node = self._node(
                node_id=f'3_PROJECT_OVERVIEW_{project_id}',
                name='项目概览',
                node_type='3_PROJECT_OVERVIEW',
                category='fixed_domain',
                level=3,
                side='left',
                parent_id=f'2_PROJECT_{project_id}',
                identity_key=f'PROJECT_OVERVIEW:{project_id}',
                fixed=True,
                summary=f"预算：{project.get('budget_amount', 0)}；已执行：{project.get('executed_budget_amount', 0)}",
                detail=self._detail(
                    basic={
                        '项目名称': project_name,
                        '项目编号': project.get('code', ''),
                        '项目预算金额': project.get('budget_amount', 0),
                        '预算已执行情况': project.get('executed_budget_amount', 0),
                        '项目成本类型top1': project.get('top_cost_type', ''),
                        '项目最新里程碑': project.get('latest_milestone', '') if project.get('latest_milestone', '') else '-',
                    },
                    description='项目概览节点。',
                ),
                children=[],
                expandable=False,
                leaf=True,
            )

            personnel_payload = project.get('personnel', {}) or {}
            personnel_children = self.build_project_personnel_staff_nodes(
                project_id,
                personnel_payload.get('staff', []) or [],
            )

            fixed_asset_payload = project.get('fixed_assets', {}) or {}
            fixed_asset_children = self.build_project_asset_nodes(
                project_id,
                fixed_asset_payload.get('assets', []) or [],
                node_type='fixed',
            )

            intangible_asset_payload = project.get('intangible_assets', {}) or {}
            intangible_asset_children = self.build_project_asset_nodes(
                project_id,
                intangible_asset_payload.get('assets', []) or [],
                node_type='intangible',
            )

            material_children = self.build_project_material_nodes(project_id, project_name, project.get('materials', {}) or {})
            file_children = self.build_project_file_category_nodes(project_id, project.get('files', {}) or {})

            project_children: List[GraphNode] = [overview_node]

            participant_count = int(personnel_payload.get('participant_count') or len(personnel_children) or 0)
            if participant_count > 0 or personnel_children:
                project_children.append(
                    self._node(
                        node_id=f'3_PROJECT_PERSONNEL_{project_id}',
                        name='项目人员',
                        node_type='3_PROJECT_PERSONNEL',
                        category='fixed_domain',
                        level=3,
                        side='left',
                        parent_id=f'2_PROJECT_{project_id}',
                        identity_key=f'PROJECT_PERSONNEL:{project_id}',
                        fixed=True,
                        summary=f"参与人数：{participant_count}",
                        detail=self._detail(
                            basic={
                                '项目名称': project_name,
                                '该年参与人数': participant_count,
                                '该年研发工时top1': personnel_payload.get('top1_staff', ''),
                            },
                            description='项目人员节点。',
                        ),
                        children=personnel_children,
                        expandable=bool(personnel_children),
                        leaf=not bool(personnel_children),
                    )
                )

            fixed_asset_count = int(fixed_asset_payload.get('asset_count') or len(fixed_asset_children) or 0)
            fixed_asset_year_depreciation = fixed_asset_payload.get('year_depreciation', 0)
            fixed_asset_top1 = fixed_asset_payload.get('top1_asset', '')
            if fixed_asset_count > 0 or fixed_asset_year_depreciation or fixed_asset_top1 or fixed_asset_children:
                project_children.append(
                    self._node(
                        node_id=f'3_PROJECT_FIXED_ASSET_{project_id}',
                        name='固定资产',
                        node_type='3_PROJECT_FIXED_ASSET',
                        category='fixed_domain',
                        level=3,
                        side='left',
                        parent_id=f'2_PROJECT_{project_id}',
                        identity_key=f'PROJECT_FIXED_ASSET:{project_id}',
                        fixed=True,
                        summary=f"资产数量：{fixed_asset_count}",
                        detail=self._detail(
                            basic={
                                '项目名称': project_name,
                                '固定资产数量': fixed_asset_count,
                                '该年固定资产预计折旧金额': fixed_asset_year_depreciation,
                                '该年研发固定资产研发工时top1': fixed_asset_top1,
                            },
                        ),
                        children=fixed_asset_children,
                        expandable=bool(fixed_asset_children),
                        leaf=not bool(fixed_asset_children),
                    )
                )

            intangible_asset_count = int(intangible_asset_payload.get('asset_count') or len(intangible_asset_children) or 0)
            intangible_asset_year_amortization = intangible_asset_payload.get('year_amortization', 0)
            intangible_asset_top1 = intangible_asset_payload.get('top1_asset', '')
            if intangible_asset_count > 0 or intangible_asset_year_amortization or intangible_asset_top1 or intangible_asset_children:
                project_children.append(
                    self._node(
                        node_id=f'3_PROJECT_INTANGIBLE_ASSET_{project_id}',
                        name='无形资产',
                        node_type='3_PROJECT_INTANGIBLE_ASSET',
                        category='fixed_domain',
                        level=3,
                        side='left',
                        parent_id=f'2_PROJECT_{project_id}',
                        identity_key=f'PROJECT_INTANGIBLE_ASSET:{project_id}',
                        fixed=True,
                        summary=f"资产数量：{intangible_asset_count}",
                        detail=self._detail(
                            basic={
                                '项目名称': project_name,
                                '该年参与资产数量': intangible_asset_count,
                                '该年无形资产预计摊销金额': intangible_asset_year_amortization,
                                '该年研发无形资产研发工时top1': intangible_asset_top1,
                            },
                        ),
                        children=intangible_asset_children,
                        expandable=bool(intangible_asset_children),
                        leaf=not bool(intangible_asset_children),
                    )
                )

            materials_payload = project.get('materials', {}) or {}
            material_total_amount = self._to_float(materials_payload.get('total_amount'))
            if material_total_amount > 0 or material_children:
                project_children.append(
                    self._node(
                        node_id=f'3_PROJECT_MATERIAL_{project_id}',
                        name='项目物料',
                        node_type='3_PROJECT_MATERIAL',
                        category='fixed_domain',
                        level=3,
                        side='left',
                        parent_id=f'2_PROJECT_{project_id}',
                        identity_key=f'PROJECT_MATERIAL:{project_id}',
                        fixed=True,
                        summary=f"消耗总额：{material_total_amount}",
                        detail=self._detail(
                            basic={
                                '项目名称': project_name,
                                '该年物料消耗金额': material_total_amount,
                            },
                        ),
                        children=material_children,
                        expandable=bool(material_children),
                        leaf=not bool(material_children),
                    )
                )

            fee_amount = self._to_float(project.get('fee_amount'))
            if fee_amount > 0:
                project_children.append(
                    self._node(
                        node_id=f'3_PROJECT_FEE_{project_id}',
                        name='项目费用',
                        node_type='3_PROJECT_FEE',
                        category='fixed_domain',
                        level=3,
                        side='left',
                        parent_id=f'2_PROJECT_{project_id}',
                        identity_key=f'PROJECT_FEE:{project_id}',
                        fixed=True,
                        summary=f"费用：{fee_amount}",
                        detail=self._detail(
                            basic={
                                '项目名称': project_name,
                                '该项目费用金额': fee_amount,
                            }
                        ),
                        children=[],
                        expandable=False,
                        leaf=True,
                    )
                )

            file_count = int((project.get('files', {}) or {}).get('file_count') or 0)
            if file_count > 0 or file_children:
                project_children.append(
                    self._node(
                        node_id=f'3_PROJECT_FILES_{project_id}',
                        name='项目文件',
                        node_type='3_PROJECT_FILES',
                        category='fixed_domain',
                        level=3,
                        side='left',
                        parent_id=f'2_PROJECT_{project_id}',
                        identity_key=f'PROJECT_FILES:{project_id}',
                        fixed=True,
                        summary=f"文件数：{file_count}",
                        detail=self._detail(
                            basic={
                                '项目名称': project_name,
                                '项目文件数量': file_count,
                            }
                        ),
                        children=file_children,
                        expandable=bool(file_children),
                        leaf=not bool(file_children),
                    )
                )

            nodes.append(
                self._node(
                    node_id=f'2_PROJECT_{project_id}',
                    name=project_name,
                    node_type='2_PROJECT',
                    category='dynamic',
                    level=2,
                    side='left',
                    parent_id='1_PROJECT_LIBRARY',
                    identity_key=f'PROJECT:{project_id}',
                    fixed=False,
                    summary=project.get('status', '项目节点'),
                    detail=self._detail(
                        basic={
                            '项目名称': project_name,
                            '项目编号': project.get('code', ''),
                            '项目负责人': project.get('leader', ''),
                            '项目周期': project.get('period', ''),
                            '项目状态': project.get('status', ''),
                        },
                        description='项目名称节点。',
                    ),
                    children=project_children,
                    expandable=bool(project_children),
                    leaf=not bool(project_children),
                )
            )
        return nodes

    def build_project_personnel_staff_nodes(self, project_id: str, staff_rows: List[Dict[str, Any]]) -> List[GraphNode]:
        nodes: List[GraphNode] = []
        for staff in staff_rows:
            staff_id = str(staff.get('id', 'unknown'))
            nodes.append(
                self._node(
                    node_id=f'4_PROJECT_PERSONNEL_STAFF_{project_id}_{staff_id}',
                    name=staff.get('name', f'员工_{staff_id}'),
                    node_type='4_PROJECT_PERSONNEL_STAFF',
                    category='dynamic',
                    level=4,
                    side='left',
                    parent_id=f'3_PROJECT_PERSONNEL_{project_id}',
                    identity_key=f'PROJECT_PERSONNEL_STAFF:{project_id}:{staff_id}',
                    fixed=False,
                    summary=f"工时：{staff.get('year_rd_hours', 0)}h",
                    detail=self._detail(
                        basic={
                            '员工名称': staff.get('name', ''),
                            '工号': staff.get('work_num', ''),
                            '部门': staff.get('dept_name', ''),
                            '聘用方式': staff.get('employ_way_text', ''),
                            '入职日期': staff.get('entry_date', ''),
                            '该年研发工时投入': staff.get('year_rd_hours', 0),
                        }
                    ),
                    children=[],
                    expandable=False,
                    leaf=True,
                )
            )
        return nodes

    def build_project_asset_nodes(self, project_id: str, asset_rows: List[Dict[str, Any]], node_type: str) -> List[GraphNode]:
        nodes: List[GraphNode] = []
        prefix = 'FIXED' if node_type == 'fixed' else 'INTANGIBLE'
        parent = f'3_PROJECT_FIXED_ASSET_{project_id}' if node_type == 'fixed' else f'3_PROJECT_INTANGIBLE_ASSET_{project_id}'
        for asset in asset_rows:
            asset_id = str(asset.get('id', 'unknown'))
            nodes.append(
                self._node(
                    node_id=f'4_PROJECT_{prefix}_ASSET_{project_id}_{asset_id}',
                    name=asset.get('name', f'资产_{asset_id}'),
                    node_type=f'4_PROJECT_{prefix}_ASSET',
                    category='dynamic',
                    level=4,
                    side='left',
                    parent_id=parent,
                    identity_key=f'PROJECT_{prefix}_ASSET:{project_id}:{asset_id}',
                    fixed=False,
                    summary=f"累计工时：{asset.get('project_total_rd_hours', 0)}h",
                    detail=self._detail(
                        basic={
                            '资产名称': asset.get('name', ''),
                            '资产编号': asset.get('code', ''),
                            '资产类型': asset.get('asset_type', ''),
                            '资产来源': asset.get('source', ''),
                            '本月研发工时': asset.get('month_rd_hours', 0),
                            '项目累积工时': asset.get('project_total_rd_hours', 0),
                        }
                    ),
                    children=[],
                    expandable=False,
                    leaf=True,
                )
            )
        return nodes

    def build_project_material_nodes(self, project_id: str, project_name: str, materials_payload: Dict[str, Any]) -> List[GraphNode]:
        children: List[GraphNode] = []

        material_kind_count = int(materials_payload.get('material_kind_count') or 0)
        material_amount = self._to_float(materials_payload.get('material_amount'))
        if material_kind_count > 0 or material_amount > 0:
            children.append(
                self._node(
                    node_id=f'4_PROJECT_MATERIAL_MATERIAL_{project_id}',
                    name='项目材料',
                    node_type='4_PROJECT_MATERIAL_MATERIAL',
                    category='fixed_domain',
                    level=4,
                    side='left',
                    parent_id=f'3_PROJECT_MATERIAL_{project_id}',
                    identity_key=f'PROJECT_MATERIAL_MATERIAL:{project_id}',
                    fixed=True,
                    summary=f"种类数：{material_kind_count}",
                    detail=self._detail(
                        basic={
                            '项目名称': project_name,
                            '该年消耗材料种类数量': material_kind_count,
                        }
                    ),
                    children=[],
                    expandable=False,
                    leaf=True,
                )
            )

        fuel_kind_count = int(materials_payload.get('fuel_kind_count') or 0)
        fuel_amount_year = self._to_float(materials_payload.get('fuel_amount'))
        fuel_amount_total = self._to_float(materials_payload.get('fuel_total_amount'))
        if fuel_kind_count > 0 or fuel_amount_year > 0 or fuel_amount_total > 0:
            children.append(
                self._node(
                    node_id=f'4_PROJECT_MATERIAL_FUEL_{project_id}',
                    name='项目燃料',
                    node_type='4_PROJECT_MATERIAL_FUEL',
                    category='fixed_domain',
                    level=4,
                    side='left',
                    parent_id=f'3_PROJECT_MATERIAL_{project_id}',
                    identity_key=f'PROJECT_MATERIAL_FUEL:{project_id}',
                    fixed=True,
                    summary=f"种类数：{fuel_kind_count}",
                    detail=self._detail(
                        basic={
                            '项目名称': project_name,
                            '该年消耗燃料种类数量': fuel_kind_count,
                            '该年消耗燃料总金额': fuel_amount_year,
                            '该项目消耗燃料总金额': fuel_amount_total,
                        }
                    ),
                    children=[],
                    expandable=False,
                    leaf=True,
                )
            )

        power_record_count = int(materials_payload.get('power_record_count') or 0)
        power_amount = self._to_float(materials_payload.get('power_amount'))
        if power_record_count > 0 or power_amount > 0:
            children.append(
                self._node(
                    node_id=f'4_PROJECT_MATERIAL_POWER_{project_id}',
                    name='项目动力',
                    node_type='4_PROJECT_MATERIAL_POWER',
                    category='fixed_domain',
                    level=4,
                    side='left',
                    parent_id=f'3_PROJECT_MATERIAL_{project_id}',
                    identity_key=f'PROJECT_MATERIAL_POWER:{project_id}',
                    fixed=True,
                    summary=f"记录数：{power_record_count}",
                    detail=self._detail(
                        basic={
                            '项目名称': project_name,
                            '代核算记录条数': power_record_count,
                            '已核算记录总金额': power_amount,
                        }
                    ),
                    children=[],
                    expandable=False,
                    leaf=True,
                )
            )

        return children

    def build_project_file_category_nodes(self, project_id: str, files_payload: Dict[str, Any]) -> List[GraphNode]:
        mapping = [
            ('项目成果', 'achievement_files', '项目成果文件数量', '4_PROJECT_FILE_ACHIEVEMENT'),
            ('项目结题', 'closing_files', '项目结题文件数量', '4_PROJECT_FILE_CLOSING'),
            ('其他文件', 'other_files', '项目其他文件数量', '4_PROJECT_FILE_OTHER'),
        ]
        children: List[GraphNode] = []
        for display_name, payload_key, detail_key, node_type in mapping:
            file_rows = files_payload.get(payload_key, []) or []
            if not file_rows:
                continue

            file_nodes: List[GraphNode] = []
            for file_item in file_rows:
                file_id = str(file_item.get('id', file_item.get('name', 'unknown')))
                file_nodes.append(
                    self._node(
                        node_id=f'5_{node_type}_{project_id}_{file_id}',
                        name=file_item.get('name', f'文件_{file_id}'),
                        node_type=f'5_{node_type}',
                        category='dynamic',
                        level=5,
                        side='left',
                        parent_id=f'4_{node_type}_{project_id}',
                        identity_key=f'{node_type}:{project_id}:{file_id}',
                        fixed=False,
                        summary='文件节点',
                        detail=self._detail(
                            basic={'文件名称': file_item.get('name', '')},
                            dynamic={'所属项目': files_payload.get('project_name', '')},
                        ),
                        children=[],
                        expandable=False,
                        leaf=True,
                    )
                )

            children.append(
                self._node(
                    node_id=f'4_{node_type}_{project_id}',
                    name=display_name,
                    node_type=node_type,
                    category='fixed_domain',
                    level=4,
                    side='left',
                    parent_id=f'3_PROJECT_FILES_{project_id}',
                    identity_key=f'{node_type}:{project_id}',
                    fixed=True,
                    summary=f"文件数：{len(file_rows)}",
                    detail=self._detail(
                        basic={
                            '项目名称': files_payload.get('project_name', ''),
                            detail_key: len(file_rows),
                        }
                    ),
                    children=file_nodes,
                    expandable=bool(file_nodes),
                    leaf=not bool(file_nodes),
                )
            )
        return children


class ProjectRepositoryMixin:

    def fetch_project_library_domain(
        self,
        conn,
        tenant_id: str,
        year: int,
        month: int,
        hr_domain: Dict[str, Any],
    ) -> Dict[str, Any]:
        staff_map = {
            str(row.get('id')): row
            for row in (hr_domain.get('active_staff_rows', []) or [])
            if row.get('id') not in (None, '')
        }
        year_start, next_year_start = self._year_range(year)
        month_start, next_month_start = self._month_range(year, month)

        project_rows = self._load_project_base_rows(conn, tenant_id)
        budget_fallback = self._load_project_budget_totals(conn, tenant_id)
        completion_dates = self._load_project_completion_dates(conn, tenant_id)
        milestone_by_project = self._load_project_latest_milestones(conn, tenant_id)

        personnel_payload, project_name_hints = self._load_project_personnel_payload(
            conn,
            tenant_id,
            year_start,
            next_year_start,
            month_start,
            next_month_start,
            staff_map,
        )
        fixed_assets_payload = self._load_project_fixed_assets_payload(
            conn,
            tenant_id,
            year_start,
            next_year_start,
            month_start,
            next_month_start,
        )
        intangible_assets_payload = self._load_project_intangible_assets_payload(
            conn,
            tenant_id,
            year_start,
            next_year_start,
            month_start,
            next_month_start,
        )
        materials_payload = self._load_project_material_payload(conn, tenant_id, year)
        cost_payload = self._load_project_cost_payload(conn, tenant_id)
        files_payload = self._load_project_files_payload(conn, tenant_id)

        all_project_ids: Set[str] = set(project_rows.keys())
        for payload in (
            personnel_payload,
            fixed_assets_payload,
            intangible_assets_payload,
            materials_payload,
            cost_payload,
            files_payload,
        ):
            all_project_ids.update(payload.keys())
        all_project_ids.update(completion_dates.keys())
        all_project_ids.update(milestone_by_project.keys())

        status_stats = {'progress_month': 0, 'completed_year': 0, 'draft': 0}
        projects: List[Dict[str, Any]] = []

        for project_id in sorted(all_project_ids, key=lambda item: (project_rows.get(item, {}).get('name') or project_name_hints.get(item) or item)):
            info = dict(project_rows.get(project_id, {}))
            if not info:
                info = {
                    'id': project_id,
                    'name': project_name_hints.get(project_id) or f'项目_{project_id}',
                    'code': '',
                    'leader': '',
                    'period': '',
                    'status': '',
                    'status_bucket': 'unknown',
                    'budget_amount': 0.0,
                    'start_date': None,
                    'end_date': None,
                    'research_year': None,
                }

            if self._to_float(info.get('budget_amount')) <= 0:
                info['budget_amount'] = round(self._to_float(budget_fallback.get(project_id)), 2)

            personnel = personnel_payload.get(
                project_id,
                {
                    'participant_count': 0,
                    'top1_staff': '',
                    'staff': [],
                    'has_current_month_hours': False,
                },
            )
            fixed_assets = fixed_assets_payload.get(
                project_id,
                {'asset_count': 0, 'year_depreciation': 0.0, 'top1_asset': '', 'assets': []},
            )
            intangible_assets = intangible_assets_payload.get(
                project_id,
                {'asset_count': 0, 'year_amortization': 0.0, 'top1_asset': '', 'assets': []},
            )
            materials = materials_payload.get(
                project_id,
                {
                    'total_amount': 0.0,
                    'material_amount': 0.0,
                    'material_kind_count': 0,
                    'fuel_kind_count': 0,
                    'fuel_amount': 0.0,
                    'fuel_total_amount': 0.0,
                    'power_record_count': 0,
                    'power_amount': 0.0,
                },
            )
            costs = cost_payload.get(project_id, {'fee_amount': 0.0, 'top_cost_type': '', 'executed_budget_amount': 0.0})
            files = dict(
                files_payload.get(
                    project_id,
                    {
                        'project_name': info.get('name', ''),
                        'file_count': 0,
                        'achievement_files': [],
                        'closing_files': [],
                        'other_files': [],
                    },
                )
            )
            files['project_name'] = info.get('name', '')

            completion_date = completion_dates.get(project_id)
            status_bucket = info.get('status_bucket') or self._project_status_bucket(info.get('status'))

            if self._is_project_in_year(info, year_start, next_year_start, personnel, fixed_assets, intangible_assets, materials, files, completion_date):
                pass
            else:
                continue

            if self._is_project_active_in_month(info, month_start, next_month_start, status_bucket, personnel):
                status_stats['progress_month'] += 1
            if completion_date and completion_date.year == year:
                status_stats['completed_year'] += 1
            elif not completion_date and status_bucket == 'completed':
                end_date = info.get('end_date')
                if end_date and end_date.year == year:
                    status_stats['completed_year'] += 1
            if status_bucket == 'draft':
                status_stats['draft'] += 1

            projects.append(
                {
                    'id': project_id,
                    'name': info.get('name', f'项目_{project_id}'),
                    'code': info.get('code', ''),
                    'leader': info.get('leader', ''),
                    'period': info.get('period', ''),
                    'status': info.get('status', ''),
                    'budget_amount': round(self._to_float(info.get('budget_amount')), 2),
                    'executed_budget_amount': round(self._to_float(costs.get('executed_budget_amount')), 2),
                    'top_cost_type': costs.get('top_cost_type', ''),
                    'latest_milestone': milestone_by_project.get(project_id, ''),
                    'personnel': {
                        'participant_count': int(personnel.get('participant_count') or 0),
                        'top1_staff': personnel.get('top1_staff', ''),
                        'staff': personnel.get('staff', []) or [],
                    },
                    'fixed_assets': fixed_assets,
                    'intangible_assets': intangible_assets,
                    'materials': materials,
                    'fee_amount': round(self._to_float(costs.get('fee_amount')), 2),
                    'files': files,
                }
            )

        return {
            'detail': {
                '该年中总研发项目数量': len(projects),
                '当月正在进行的项目数量': status_stats['progress_month'],
                '当年已完成项目数量': status_stats['completed_year'],
                '草稿项目数量': status_stats['draft'],
            },
            'projects': projects,
        }

    def _load_project_base_rows(self, conn, tenant_id: str) -> Dict[str, Dict[str, Any]]:
        sql = """
            SELECT
                p.`ID`,
                p.`PROJECT_NAME`,
                p.`PROJECT_RESEARCH_NO`,
                p.`PROJECT_MANAGER_NAMES`,
                p.`START_DATE`,
                p.`END_DATE`,
                p.`PROJECT_STATUS`,
                p.`GENERAL_BUDGET`,
                p.`PROJECT_RESEARCH_YEAR`
            FROM `T_PROJECT` p
            WHERE p.`TENANT_ID` = %s
        """

        rows: Dict[str, Dict[str, Any]] = {}
        for row in self._safe_rows(conn, sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            if not project_id:
                continue
            start_date = self._normalize_date(row[4])
            end_date = self._normalize_date(row[5])
            period = ''
            if start_date or end_date:
                period = f"{start_date.strftime('%Y-%m-%d') if start_date else ''} ~ {end_date.strftime('%Y-%m-%d') if end_date else ''}".strip()
            status_text = self._project_status_text(row[6])
            rows[project_id] = {
                'id': project_id,
                'name': self._stringify(row[1]) or f'项目_{project_id}',
                'code': self._stringify(row[2]),
                'leader': self._stringify(row[3]),
                'period': period,
                'status': status_text,
                'status_bucket': self._project_status_bucket(row[6]),
                'budget_amount': round(self._to_float(row[7]), 2),
                'start_date': start_date,
                'end_date': end_date,
                'research_year': self._to_int(row[8]) if row[8] not in (None, '') else None,
            }
        return rows

    def _load_project_budget_totals(self, conn, tenant_id: str) -> Dict[str, float]:
        amount_cols = [
            'PERSONNEL_LABOR_COSTS',
            'DIRECT_INVESTMENT_COST',
            'FIXED_ASSETS_DEPRECIATION_FEE',
            'INTANGIBLE_ASSETS_AMORTIZATION_FEE',
            'NEW_PRODUCT_DESIGN_FEE',
            'OTHER_RELATED_FEE',
            'COMMISSION_R_D_FEE',
        ]
        select_expr = ' + '.join([f"COALESCE(b.`{col}`, 0)" for col in amount_cols])
        sql = (
            f"SELECT b.`PROJECT_ID`, SUM({select_expr}) "
            "FROM `T_PROJECT_BUDGET` b "
            "WHERE b.`TENANT_ID` = %s "
            "GROUP BY b.`PROJECT_ID`"
        )

        totals: Dict[str, float] = {}
        for row in self._safe_rows(conn, sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            if project_id:
                totals[project_id] = round(self._to_float(row[1]), 2)
        return totals

    def _load_project_completion_dates(self, conn, tenant_id: str) -> Dict[str, Any]:
        sql = """
            SELECT a.`PROJECT_ID`, a.`ACCEPTANCE_TIME`, a.`TYPE`
            FROM `T_PROJECT_ACCEPTANCE` a
            WHERE a.`TENANT_ID` = %s
        """

        preferred: Dict[str, Any] = {}
        fallback: Dict[str, Any] = {}
        for row in self._safe_rows(conn, sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            accepted_date = self._normalize_date(row[1])
            accepted_type = self._to_int(row[2])
            if not project_id or accepted_date is None:
                continue

            previous = fallback.get(project_id)
            if previous is None or accepted_date > previous:
                fallback[project_id] = accepted_date

            if accepted_type == 200:
                previous_preferred = preferred.get(project_id)
                if previous_preferred is None or accepted_date > previous_preferred:
                    preferred[project_id] = accepted_date

        result = dict(fallback)
        result.update(preferred)
        return result

    def _load_project_latest_milestones(self, conn, tenant_id: str) -> Dict[str, str]:
        sql = """
            SELECT m.`PROJECT_ID`, m.`NAME`, m.`TIME`
            FROM `T_PROJECT_MILESTONE` m
            WHERE m.`TENANT_ID` = %s
        """

        latest_by_project: Dict[str, Tuple[Any, str]] = {}
        for row in self._safe_rows(conn, sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            name = self._stringify(row[1])
            milestone_date = self._normalize_date(row[2]) if row[2] not in (None, '') else None
            if not project_id or not name:
                continue
            previous = latest_by_project.get(project_id)
            if previous is None:
                latest_by_project[project_id] = (milestone_date, name)
                continue
            previous_date = previous[0]
            if previous_date is None and milestone_date is not None:
                latest_by_project[project_id] = (milestone_date, name)
            elif milestone_date is not None and previous_date is not None and milestone_date > previous_date:
                latest_by_project[project_id] = (milestone_date, name)

        return {project_id: value[1] for project_id, value in latest_by_project.items()}

    def _load_project_personnel_payload(
        self,
        conn,
        tenant_id: str,
        year_start,
        next_year_start,
        month_start,
        next_month_start,
        staff_map: Dict[str, Dict[str, Any]],
    ) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
        project_name_hints: Dict[str, str] = {}
        hours_by_project_staff: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        month_hours_by_project: Dict[str, float] = defaultdict(float)

        rd_sql = """
            SELECT
                t.`PROJECT_ID`,
                t.`STAFF_ID`,
                t.`R_D_HOUR`,
                t.`DATE`,
                t.`YEARS`,
                t.`MONTHS`
            FROM `T_PROJECT_USER_R_D_TIME` t
            WHERE t.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, rd_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            staff_id = self._stringify(row[1])
            hours = self._to_float(row[2])
            work_date = self._normalize_date(row[3]) if row[3] not in (None, '') else None
            work_year = self._to_int(row[4]) if row[4] not in (None, '') else None
            work_month = self._to_int(row[5]) if row[5] not in (None, '') else None

            if not project_id or not staff_id or hours <= 0:
                continue

            in_year = False
            if work_date is not None:
                in_year = year_start <= work_date < next_year_start
            elif work_year is not None:
                in_year = work_year == year_start.year

            if not in_year:
                continue

            hours_by_project_staff[project_id][staff_id] += hours

            in_month = False
            if work_date is not None:
                in_month = month_start <= work_date < next_month_start
            elif work_year is not None and work_month is not None:
                in_month = work_year == month_start.year and work_month == month_start.month
            if in_month:
                month_hours_by_project[project_id] += hours

        if not hours_by_project_staff:
            fallback_sql = """
                SELECT u.`PROJECT_ID`, u.`STAFF_ID`
                FROM `T_PROJECT_USER` u
                WHERE u.`TENANT_ID` = %s
            """
            for row in self._safe_rows(conn, fallback_sql, (tenant_id,)):
                project_id = self._stringify(row[0])
                staff_id = self._stringify(row[1])
                if project_id and staff_id:
                    hours_by_project_staff[project_id][staff_id] += 0.0

        payload: Dict[str, Dict[str, Any]] = {}
        for project_id, staff_hours in hours_by_project_staff.items():
            staff_rows: List[Dict[str, Any]] = []
            for staff_id, hours in sorted(staff_hours.items(), key=lambda item: (-item[1], item[0])):
                staff = staff_map.get(staff_id, {}) or {}
                staff_rows.append(
                    {
                        'id': staff_id,
                        'name': self._first_non_empty(staff.get('name'), f'员工_{staff_id}'),
                        'work_num': staff.get('work_num', ''),
                        'dept_name': staff.get('dept_name', ''),
                        'employ_way_text': self._employ_way_text(staff.get('employ_way')),
                        'entry_date': staff.get('entry_date', ''),
                        'year_rd_hours': round(hours, 2),
                    }
                )

            payload[project_id] = {
                'participant_count': len(staff_rows),
                'top1_staff': staff_rows[0]['name'] if staff_rows else '',
                'staff': staff_rows,
                'has_current_month_hours': month_hours_by_project.get(project_id, 0) > 0,
            }

        return payload, project_name_hints

    def _load_project_fixed_assets_payload(
        self,
        conn,
        tenant_id: str,
        year_start,
        next_year_start,
        month_start,
        next_month_start,
    ) -> Dict[str, Dict[str, Any]]:
        asset_ids_by_project: Dict[str, Set[str]] = defaultdict(set)
        relation_name_map: Dict[str, Dict[str, str]] = {}
        relation_sql = """
            SELECT
                r.`PROJECT_ID`,
                r.`FIXED_ASSETS_ID`,
                r.`FIXED_ASSETS_NAME`,
                r.`FIXED_ASSETS_CODE`
            FROM `T_PROJECT_FIXED_ASSETS` r
            WHERE r.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, relation_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            asset_id = self._stringify(row[1])
            if not project_id or not asset_id:
                continue
            asset_ids_by_project[project_id].add(asset_id)
            relation_name_map.setdefault(asset_id, {'name': self._stringify(row[2]), 'code': self._stringify(row[3])})

        device_type_name_map: Dict[str, str] = {}
        device_type_sql = "SELECT `ID`, `NAME` FROM `T_DEVICE_TYPE_CONFIG`"
        for row in self._safe_rows(conn, device_type_sql):
            device_type_name_map[self._stringify(row[0])] = self._stringify(row[1])

        asset_meta_map: Dict[str, Dict[str, Any]] = {}
        asset_sql = """
            SELECT
                a.`ID`,
                a.`NAME`,
                a.`CODE`,
                a.`SOURCE_TYPE`,
                a.`DEVICE_TYPE_CONFIG_ID`
            FROM `T_FIXED_ASSETS` a
            WHERE a.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, asset_sql, (tenant_id,)):
            asset_id = self._stringify(row[0])
            if not asset_id:
                continue
            asset_meta_map[asset_id] = {
                'name': self._first_non_empty(self._stringify(row[1]), relation_name_map.get(asset_id, {}).get('name')),
                'code': self._first_non_empty(self._stringify(row[2]), relation_name_map.get(asset_id, {}).get('code')),
                'source': self._fixed_asset_source_text(row[3]),
                'asset_type': device_type_name_map.get(self._stringify(row[4]), ''),
            }

        year_hours_by_project_asset: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        month_hours_by_project_asset: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        total_hours_by_project_asset: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        work_time_sql = """
            SELECT
                w.`PROJECT_ID`,
                w.`FIXED_ASSETS_ID`,
                w.`R_D_HOUR`,
                w.`DATE`,
                w.`YEARS`,
                w.`MONTHS`
            FROM `T_PROJECT_FIXED_ASSETS_WORK_TIME` w
            WHERE w.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, work_time_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            asset_id = self._stringify(row[1])
            hours = self._to_float(row[2])
            work_date = self._normalize_date(row[3]) if row[3] not in (None, '') else None
            work_year = self._to_int(row[4]) if row[4] not in (None, '') else None
            work_month = self._to_int(row[5]) if row[5] not in (None, '') else None
            if not project_id or not asset_id or hours <= 0:
                continue

            total_hours_by_project_asset[project_id][asset_id] += hours
            asset_ids_by_project[project_id].add(asset_id)

            in_year = False
            if work_date is not None:
                in_year = year_start <= work_date < next_year_start
            elif work_year is not None:
                in_year = work_year == year_start.year
            if in_year:
                year_hours_by_project_asset[project_id][asset_id] += hours

            in_month = False
            if work_date is not None:
                in_month = month_start <= work_date < next_month_start
            elif work_year is not None and work_month is not None:
                in_month = work_year == month_start.year and work_month == month_start.month
            if in_month:
                month_hours_by_project_asset[project_id][asset_id] += hours

        depreciation_by_asset: Dict[str, float] = defaultdict(float)
        depreciation_sql = """
            SELECT d.`FIXED_ASSETS_ID`, d.`VAL`, d.`DATE`, d.`YEARS`
            FROM `T_FIXED_ASSETS_DEPRECIATION` d
            WHERE d.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, depreciation_sql, (tenant_id,)):
            asset_id = self._stringify(row[0])
            amount = self._to_float(row[1])
            dep_date = self._normalize_date(row[2]) if row[2] not in (None, '') else None
            dep_year = self._to_int(row[3]) if row[3] not in (None, '') else None
            if not asset_id or amount <= 0:
                continue
            in_year = False
            if dep_date is not None:
                in_year = year_start <= dep_date < next_year_start
            elif dep_year is not None:
                in_year = dep_year == year_start.year
            if in_year:
                depreciation_by_asset[asset_id] += amount

        payload: Dict[str, Dict[str, Any]] = {}
        for project_id, asset_ids in asset_ids_by_project.items():
            asset_rows: List[Dict[str, Any]] = []
            for asset_id in sorted(asset_ids):
                meta = asset_meta_map.get(asset_id, {})
                asset_rows.append(
                    {
                        'id': asset_id,
                        'name': self._first_non_empty(meta.get('name'), relation_name_map.get(asset_id, {}).get('name'), f'资产_{asset_id}'),
                        'code': self._first_non_empty(meta.get('code'), relation_name_map.get(asset_id, {}).get('code')),
                        'asset_type': meta.get('asset_type', ''),
                        'source': meta.get('source', ''),
                        'month_rd_hours': round(month_hours_by_project_asset[project_id].get(asset_id, 0.0), 2),
                        'project_total_rd_hours': round(total_hours_by_project_asset[project_id].get(asset_id, 0.0), 2),
                        'year_rd_hours': round(year_hours_by_project_asset[project_id].get(asset_id, 0.0), 2),
                    }
                )

            top_asset = ''
            if asset_rows:
                top_asset = max(asset_rows, key=lambda item: item.get('year_rd_hours', 0.0)).get('name', '')
                # if max(item.get('year_rd_hours', 0.0) for item in asset_rows) <= 0:
                #     top_asset = ''

            payload[project_id] = {
                'asset_count': len(asset_rows),
                'year_depreciation': round(sum(depreciation_by_asset.get(asset_id, 0.0) for asset_id in asset_ids), 2),
                'top1_asset': top_asset,
                'assets': asset_rows,
            }

        return payload

    def _load_project_intangible_assets_payload(
        self,
        conn,
        tenant_id: str,
        year_start,
        next_year_start,
        month_start,
        next_month_start,
    ) -> Dict[str, Dict[str, Any]]:
        asset_ids_by_project: Dict[str, Set[str]] = defaultdict(set)
        relation_meta_map: Dict[str, Dict[str, str]] = {}
        relation_sql = """
            SELECT
                r.`PROJECT_ID`,
                r.`INTANGIBLE_ASSETS_ID`,
                r.`INTANGIBLE_ASSETS_NAME`,
                r.`INTANGIBLE_ASSETS_CODE`,
                r.`INTANGIBLE_ASSETS_TYPE`
            FROM `T_PROJECT_INTANGIBLE_ASSETS` r
            WHERE r.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, relation_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            asset_id = self._stringify(row[1])
            if not project_id or not asset_id:
                continue
            asset_ids_by_project[project_id].add(asset_id)
            relation_meta_map.setdefault(
                asset_id,
                {
                    'name': self._stringify(row[2]),
                    'code': self._stringify(row[3]),
                    'asset_type': self._intangible_asset_type_text(row[4]),
                },
            )

        asset_meta_map: Dict[str, Dict[str, Any]] = {}
        asset_sql = """
            SELECT
                a.`ID`,
                a.`NAME`,
                a.`CODE`,
                a.`SOURCE_TYPE`,
                a.`ASSETS_TYPE`
            FROM `T_INTANGIBLE_ASSETS` a
            WHERE a.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, asset_sql, (tenant_id,)):
            asset_id = self._stringify(row[0])
            if not asset_id:
                continue
            asset_meta_map[asset_id] = {
                'name': self._first_non_empty(self._stringify(row[1]), relation_meta_map.get(asset_id, {}).get('name')),
                'code': self._first_non_empty(self._stringify(row[2]), relation_meta_map.get(asset_id, {}).get('code')),
                'source': self._intangible_asset_source_text(row[3]),
                'asset_type': self._first_non_empty(self._intangible_asset_type_text(row[4]), relation_meta_map.get(asset_id, {}).get('asset_type')),
            }

        year_hours_by_project_asset: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        month_hours_by_project_asset: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        total_hours_by_project_asset: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        work_time_sql = """
            SELECT
                w.`PROJECT_ID`,
                w.`INTANGIBLE_ASSETS_ID`,
                w.`R_D_HOUR`,
                w.`DATE`,
                w.`YEARS`,
                w.`MONTHS`
            FROM `T_PROJECT_INTANGIBLE_ASSETS_WORK_TIME` w
            WHERE w.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, work_time_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            asset_id = self._stringify(row[1])
            hours = self._to_float(row[2])
            work_date = self._normalize_date(row[3]) if row[3] not in (None, '') else None
            work_year = self._to_int(row[4]) if row[4] not in (None, '') else None
            work_month = self._to_int(row[5]) if row[5] not in (None, '') else None
            if not project_id or not asset_id or hours <= 0:
                continue

            total_hours_by_project_asset[project_id][asset_id] += hours
            asset_ids_by_project[project_id].add(asset_id)

            in_year = False
            if work_date is not None:
                in_year = year_start <= work_date < next_year_start
            elif work_year is not None:
                in_year = work_year == year_start.year
            if in_year:
                year_hours_by_project_asset[project_id][asset_id] += hours

            in_month = False
            if work_date is not None:
                in_month = month_start <= work_date < next_month_start
            elif work_year is not None and work_month is not None:
                in_month = work_year == month_start.year and work_month == month_start.month
            if in_month:
                month_hours_by_project_asset[project_id][asset_id] += hours

        amortization_by_asset: Dict[str, float] = defaultdict(float)
        amortization_sql = """
            SELECT a.`INTANGIBLE_ASSETS_ID`, a.`VAL`, a.`DATE`, a.`YEARS`
            FROM `T_INTANGIBLE_ASSETS_AMORTIZATION` a
            WHERE a.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, amortization_sql, (tenant_id,)):
            asset_id = self._stringify(row[0])
            amount = self._to_float(row[1])
            amt_date = self._normalize_date(row[2]) if row[2] not in (None, '') else None
            amt_year = self._to_int(row[3]) if row[3] not in (None, '') else None
            if not asset_id or amount <= 0:
                continue
            in_year = False
            if amt_date is not None:
                in_year = year_start <= amt_date < next_year_start
            elif amt_year is not None:
                in_year = amt_year == year_start.year
            if in_year:
                amortization_by_asset[asset_id] += amount

        payload: Dict[str, Dict[str, Any]] = {}
        for project_id, asset_ids in asset_ids_by_project.items():
            asset_rows: List[Dict[str, Any]] = []
            for asset_id in sorted(asset_ids):
                meta = asset_meta_map.get(asset_id, {})
                relation_meta = relation_meta_map.get(asset_id, {})
                asset_rows.append(
                    {
                        'id': asset_id,
                        'name': self._first_non_empty(meta.get('name'), relation_meta.get('name'), f'资产_{asset_id}'),
                        'code': self._first_non_empty(meta.get('code'), relation_meta.get('code')),
                        'asset_type': self._first_non_empty(meta.get('asset_type'), relation_meta.get('asset_type')),
                        'source': meta.get('source', ''),
                        'month_rd_hours': round(month_hours_by_project_asset[project_id].get(asset_id, 0.0), 2),
                        'project_total_rd_hours': round(total_hours_by_project_asset[project_id].get(asset_id, 0.0), 2),
                        'year_rd_hours': round(year_hours_by_project_asset[project_id].get(asset_id, 0.0), 2),
                    }
                )

            top_asset = ''
            if asset_rows:
                top_asset = max(asset_rows, key=lambda item: item.get('year_rd_hours', 0.0)).get('name', '')
                # if max(item.get('year_rd_hours', 0.0) for item in asset_rows) <= 0:
                #     top_asset = ''

            payload[project_id] = {
                'asset_count': len(asset_rows),
                'year_amortization': round(sum(amortization_by_asset.get(asset_id, 0.0) for asset_id in asset_ids), 2),
                'top1_asset': top_asset,
                'assets': asset_rows,
            }

        return payload

    def _load_project_material_payload(self, conn, tenant_id: str, year: int) -> Dict[str, Dict[str, Any]]:
        material_amount_year: Dict[str, float] = defaultdict(float)
        material_kinds_year: Dict[str, Set[str]] = defaultdict(set)

        material_sql = """
            SELECT m.`PROJECT_ID`, m.`NAME`, m.`AMOUNT`, m.`COLLECT_TIME`, m.`YEARS`
            FROM `T_PROJECT_MATERIAL` m
            WHERE m.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, material_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            material_name = self._stringify(row[1])
            amount = self._to_float(row[2])
            record_date = self._normalize_date(row[3]) if row[3] not in (None, '') else None
            record_year = self._to_int(row[4]) if row[4] not in (None, '') else None
            if not project_id:
                continue
            in_year = (record_date is not None and record_date.year == year) or (record_date is None and record_year == year)
            if in_year:
                material_amount_year[project_id] += amount
                if material_name:
                    material_kinds_year[project_id].add(material_name)

        fuel_amount_year: Dict[str, float] = defaultdict(float)
        fuel_amount_total: Dict[str, float] = defaultdict(float)
        fuel_kinds_year: Dict[str, Set[str]] = defaultdict(set)
        fuel_sql = """
            SELECT f.`PROJECT_ID`, f.`NAME`, f.`AMOUNT`, f.`CONSUME_TIME`, f.`YEARS`
            FROM `T_PROJECT_FUEL` f
            WHERE f.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, fuel_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            fuel_name = self._stringify(row[1])
            amount = self._to_float(row[2])
            record_date = self._normalize_date(row[3]) if row[3] not in (None, '') else None
            record_year = self._to_int(row[4]) if row[4] not in (None, '') else None
            if not project_id:
                continue
            fuel_amount_total[project_id] += amount
            in_year = (record_date is not None and record_date.year == year) or (record_date is None and record_year == year)
            if in_year:
                fuel_amount_year[project_id] += amount
                if fuel_name:
                    fuel_kinds_year[project_id].add(fuel_name)

        power_record_count: Dict[str, int] = defaultdict(int)
        power_amount: Dict[str, float] = defaultdict(float)
        power_sql = """
            SELECT p.`PROJECT_ID`, p.`TOTAL_AMOUNT`, p.`ACCOUNTING_TIME`
            FROM `T_PROJECT_POWER_CALCULATE` p
            WHERE p.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, power_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            amount = self._to_float(row[1])
            accounting_time = row[2]
            if not project_id:
                continue
            if accounting_time in (None, '', 'null'):
                power_record_count[project_id] += 1
            else:
                power_amount[project_id] += amount

        all_project_ids = set(material_amount_year.keys()) | set(material_kinds_year.keys()) | set(fuel_amount_year.keys()) | set(fuel_amount_total.keys()) | set(fuel_kinds_year.keys()) | set(power_record_count.keys()) | set(power_amount.keys())
        payload: Dict[str, Dict[str, Any]] = {}
        for project_id in all_project_ids:
            payload[project_id] = {
                'total_amount': round(material_amount_year.get(project_id, 0.0) + fuel_amount_year.get(project_id, 0.0), 2),
                'material_amount': round(material_amount_year.get(project_id, 0.0), 2),
                'material_kind_count': len(material_kinds_year.get(project_id, set())),
                'fuel_kind_count': len(fuel_kinds_year.get(project_id, set())),
                'fuel_amount': round(fuel_amount_year.get(project_id, 0.0), 2),
                'fuel_total_amount': round(fuel_amount_total.get(project_id, 0.0), 2),
                'power_record_count': int(power_record_count.get(project_id, 0)),
                'power_amount': round(power_amount.get(project_id, 0.0), 2),
            }
        return payload

    def _load_project_cost_payload(self, conn, tenant_id: str) -> Dict[str, Dict[str, Any]]:
        cost_name_by_id: Dict[str, str] = {}
        for row in self._safe_rows(conn, "SELECT `ID`, `NAME` FROM `T_COST_CONFIG`"):
            cost_name_by_id[self._stringify(row[0])] = self._stringify(row[1])

        cost_sum_by_project: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        cost_sql = """
            SELECT
                c.`PROJECT_ID`,
                c.`COST_CONFIG_ID`,
                c.`ACCOUNTING_STANDARDS_AMOUNT`,
                c.`R_D_VOUCHER_AMOUNT`,
                c.`R_D_ADDITIONAL_DEDUCTION_AMOUNT`,
                c.`HIGH_TECH_COLLECTION_AMOUNT`
            FROM `T_COST_MANAGE_COST_PROJECT_SECOND` c
            WHERE c.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, cost_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            cost_config_id = self._stringify(row[1])
            if not project_id:
                continue
            amount = self._project_cost_amount(row[2], row[3], row[4], row[5])
            if amount <= 0:
                continue
            cost_name = cost_name_by_id.get(cost_config_id) or f'费用类型_{cost_config_id}' if cost_config_id else ''
            if cost_name:
                cost_sum_by_project[project_id][cost_name] += amount

        executed_budget_amount: Dict[str, float] = defaultdict(float)
        executed_sql = """
            SELECT e.`PROJECT_ID`, SUM(COALESCE(e.`APPORTION_AMOUNT`, 0))
            FROM `T_VOUCHER_PROJECT_APPORTION` e
            WHERE e.`TENANT_ID` = %s
            GROUP BY e.`PROJECT_ID`
        """
        for row in self._safe_rows(conn, executed_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            if project_id:
                executed_budget_amount[project_id] = round(self._to_float(row[1]), 2)

        payload: Dict[str, Dict[str, Any]] = {}
        all_project_ids = set(cost_sum_by_project.keys()) | set(executed_budget_amount.keys())
        for project_id in all_project_ids:
            fee_map = cost_sum_by_project.get(project_id, {})
            fee_amount = round(sum(fee_map.values()), 2)
            top_cost_type = self._top_name(fee_map)
            payload[project_id] = {
                'fee_amount': fee_amount,
                'top_cost_type': top_cost_type,
                'executed_budget_amount': round(executed_budget_amount.get(project_id, fee_amount), 2),
            }
        return payload

    def _load_project_files_payload(self, conn, tenant_id: str) -> Dict[str, Dict[str, Any]]:
        achievement_files: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        result_sql = """
            SELECT r.`PROJECT_ID`, r.`ID`, r.`NAME`
            FROM `T_PROJECT_RESULTS` r
            WHERE r.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, result_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            file_id = self._stringify(row[1])
            if project_id and file_id:
                achievement_files[project_id].append(
                    {
                        'id': file_id,
                        'name': self._first_non_empty(self._stringify(row[2]), f'成果文件_{file_id}'),
                    }
                )

        closing_files: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        acceptance_sql = """
            SELECT a.`PROJECT_ID`, a.`ID`, a.`TYPE`, a.`ACCEPTANCE_TIME`, a.`ACCEPTANCE_CONTENT`
            FROM `T_PROJECT_ACCEPTANCE` a
            WHERE a.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, acceptance_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            file_id = self._stringify(row[1])
            acceptance_type = self._to_int(row[2])
            acceptance_date = self._normalize_date(row[3]) if row[3] not in (None, '') else None
            title = self._stringify(row[4])
            if not project_id or not file_id:
                continue
            if acceptance_type not in (0, 200):
                continue
            fallback_name = f"项目结题_{acceptance_date.strftime('%Y-%m-%d')}" if acceptance_date else f'项目结题_{file_id}'
            closing_files[project_id].append(
                {
                    'id': file_id,
                    'name': self._first_non_empty(title, fallback_name),
                }
            )

        other_files: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        other_sql = """
            SELECT o.`PROJECT_ID`, o.`ID`, o.`REPORT_TITLE`
            FROM `T_PROJECT_OTHER` o
            WHERE o.`TENANT_ID` = %s
        """
        for row in self._safe_rows(conn, other_sql, (tenant_id,)):
            project_id = self._stringify(row[0])
            file_id = self._stringify(row[1])
            if project_id and file_id:
                other_files[project_id].append(
                    {
                        'id': file_id,
                        'name': self._first_non_empty(self._stringify(row[2]), f'其他文件_{file_id}'),
                    }
                )

        all_project_ids = set(achievement_files.keys()) | set(closing_files.keys()) | set(other_files.keys())
        payload: Dict[str, Dict[str, Any]] = {}
        for project_id in all_project_ids:
            achievements = achievement_files.get(project_id, [])
            closings = closing_files.get(project_id, [])
            others = other_files.get(project_id, [])
            payload[project_id] = {
                'project_name': '',
                'file_count': len(achievements) + len(closings) + len(others),
                'achievement_files': achievements,
                'closing_files': closings,
                'other_files': others,
            }
        return payload

    def _is_project_in_year(
        self,
        project_info: Dict[str, Any],
        year_start,
        next_year_start,
        personnel: Dict[str, Any],
        fixed_assets: Dict[str, Any],
        intangible_assets: Dict[str, Any],
        materials: Dict[str, Any],
        files: Dict[str, Any],
        completion_date,
    ) -> bool:
        # research_year = project_info.get('research_year')
        # if research_year:
        #     return int(research_year) == year_start.year

        if self._date_overlaps_range(project_info.get('start_date'), project_info.get('end_date'), year_start, next_year_start):
            return True

        if completion_date is not None and completion_date.year == year_start.year:
            return True

        if int(personnel.get('participant_count') or 0) > 0:
            return True
        if int(fixed_assets.get('asset_count') or 0) > 0 or self._to_float(fixed_assets.get('year_depreciation')) > 0:
            return True
        if int(intangible_assets.get('asset_count') or 0) > 0 or self._to_float(intangible_assets.get('year_amortization')) > 0:
            return True
        if self._to_float(materials.get('total_amount')) > 0:
            return True
        if int(files.get('file_count') or 0) > 0:
            return True
        if self._to_float(project_info.get('budget_amount')) > 0:
            return True
        return False

    def _is_project_active_in_month(
        self,
        project_info: Dict[str, Any],
        month_start,
        next_month_start,
        status_bucket: str,
        personnel: Dict[str, Any],
    ) -> bool:
        if status_bucket in {'draft', 'completed', 'not_started'}:
            return False

        if self._date_overlaps_range(project_info.get('start_date'), project_info.get('end_date'), month_start, next_month_start):
            return True

        if bool(personnel.get('has_current_month_hours')):
            return True

        return False

    def _project_cost_amount(self, accounting_amount: Any, voucher_amount: Any, additional_amount: Any, high_tech_amount: Any) -> float:
        for value in (accounting_amount, voucher_amount, additional_amount, high_tech_amount):
            amount = self._to_float(value)
            if amount != 0:
                return amount
        return 0.0

    def _employ_way_text(self, value: Any) -> str:
        numeric = self._to_int(value)
        mapping = {
            100: '正式',
            200: '兼职',
            300: '临时聘用',
            1000: '正式',
            2000: '劳务',
            3000: '实习',
        }
        if numeric in mapping:
            return mapping[numeric]
        text = self._stringify(value)
        return text if text != '0' else ''
