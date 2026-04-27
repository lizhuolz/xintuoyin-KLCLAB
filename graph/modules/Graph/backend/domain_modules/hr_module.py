from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from ..models.graph_models import GraphNode


class HrGraphBuilderMixin:
        _GENDER_MAP = {0: '女', 1: '男'}
        _EMPLOYMENT_METHOD_MAP = {100: '正式', 200: '兼职', 300: '临时聘用'}
        _ATTENDANCE_GROUP_TYPE_MAP = {100: '固定排班', 200: '周期排班'}
        _INTANGIBLE_ASSET_TYPE_MAP = {100: '专利', 200: '软著', 300: '非专利技术'}

        def _builder_int(self, value: Any) -> Optional[int]:
            if value in (None, '', 'null'):
                return None
            try:
                return int(float(value))
            except Exception:
                return None

        def _builder_text(self, value: Any) -> str:
            if value in (None, '', 'null'):
                return ''
            return str(value).strip()

        def _builder_compact(self, data: Dict[str, Any]) -> Dict[str, Any]:
            compacted: Dict[str, Any] = {}
            for key, value in data.items():
                if value in (None, '', 'null', []):
                    continue
                compacted[key] = value
            return compacted

        def _builder_enum_text(self, value: Any, mapping: Dict[int, str], *, unknown_prefix: str = '编码值') -> str:
            if value in (None, '', 'null'):
                return ''
            value_int = self._builder_int(value)
            if value_int is not None:
                return mapping.get(value_int, f'{unknown_prefix}:{value_int}')
            return self._builder_text(value)

        def _builder_money_text(self, value: Any) -> str:
            if value in (None, '', 'null'):
                return ''
            try:
                amount = round(float(value), 2)
            except Exception:
                text = self._builder_text(value)
                return f'{text}元' if text else ''
            if abs(amount - int(amount)) < 1e-9:
                return f'{int(amount)}元'
            return f'{amount:.2f}元'

        def _builder_hours_text(self, value: Any) -> str:
            if value in (None, '', 'null'):
                return ''
            try:
                hours = round(float(value), 2)
            except Exception:
                text = self._builder_text(value)
                return f'{text}h' if text else ''
            if abs(hours - int(hours)) < 1e-9:
                return f'{int(hours)}h'
            return f'{hours:.2f}h'

        def build_department_nodes(self, tenant_id: str, departments: List[Dict[str, Any]]) -> List[GraphNode]:
            nodes: List[GraphNode] = []
            for department in departments or []:
                dept_id = self._builder_text(department.get('id')) or 'unknown'
                dept_name = self._builder_text(department.get('name')) or f'未命名部门_{dept_id}'
                staff_rows = department.get('staff', []) or []
                staff_nodes = self.build_member_staff_nodes(
                    tenant_id=tenant_id,
                    dept_id=dept_id,
                    staff_rows=staff_rows,
                )

                staff_count = department.get('staff_count', len(staff_nodes)) or 0
                entry_count = department.get('entry_count', 0) or 0
                leave_count = department.get('leave_count', 0) or 0
                if not staff_nodes and not staff_count and not entry_count and not leave_count:
                    continue

                nodes.append(
                    self._node(
                        node_id=f'3_DEPT_{dept_id}',
                        name=dept_name,
                        node_type='3_DEPT',
                        category='dynamic',
                        level=3,
                        side='right',
                        parent_id='2_MEMBER',
                        identity_key=f'DEPT:{dept_id}',
                        fixed=False,
                        summary=f'员工数量：{staff_count}',
                        detail=self._detail(
                            basic=self._builder_compact(
                                {
                                    '部门名称': dept_name,
                                    '部门人数': f'{staff_count}人',
                                    '该年入职人数': f'{entry_count}人',
                                    '该年离职人数': f'{leave_count}人',
                                }
                            ),
                            dynamic=self._builder_compact(
                                {
                                    '部门ID': dept_id,
                                    '租户ID': tenant_id,
                                }
                            ),
                            metrics={'当前挂载员工节点数': str(len(staff_nodes))},
                            description='部门节点下继续展示员工节点。',
                        ),
                        children=staff_nodes,
                    )
                )
            return nodes

        def build_member_staff_nodes(self, tenant_id: str, dept_id: str, staff_rows: List[Dict[str, Any]]) -> List[GraphNode]:
            nodes: List[GraphNode] = []
            for staff in staff_rows or []:
                staff_id = self._builder_text(staff.get('id')) or 'unknown'
                staff_name = self._builder_text(staff.get('name')) or f'员工_{staff_id}'
                work_num = self._builder_text(staff.get('work_num'))
                if not staff_name and not work_num and staff_id == 'unknown':
                    continue

                nodes.append(
                    self._node(
                        node_id=f'4_STAFF_{staff_id}',
                        name=staff_name,
                        node_type='4_STAFF',
                        category='dynamic',
                        level=4,
                        side='right',
                        parent_id=f'3_DEPT_{dept_id}',
                        identity_key=f'STAFF:{staff_id}',
                        fixed=False,
                        summary=f'工号：{work_num}' if work_num else '员工节点',
                        detail=self._detail(
                            basic=self._builder_compact(
                                {
                                    '员工名称': staff_name,
                                    '年龄': staff.get('age', ''),
                                    '性别': self._builder_enum_text(staff.get('gender'), self._GENDER_MAP, unknown_prefix='性别编码'),
                                    '工号': work_num,
                                    '聘用方式': self._builder_enum_text(
                                        staff.get('employ_way'),
                                        self._EMPLOYMENT_METHOD_MAP,
                                        unknown_prefix='聘用方式编码',
                                    ),
                                    '入职日期': self._builder_text(staff.get('entry_date')),
                                    '手机号': self._builder_text(staff.get('phone')),
                                    '学历': self._builder_text(staff.get('education') if staff.get('education') else "-"),
                                    '专业': self._builder_text(staff.get('major') if staff.get('major') else "-"),
                                    '职务': self._builder_text(staff.get('duty') if staff.get('duty') else "-"),
                                    '职称': self._builder_text(staff.get('title') if staff.get('title') else "-"),
                                    '身份证': self._builder_text(staff.get('id_card') if staff.get('id_card') else "-"),
                                    '劳动合同': self._builder_text(staff.get('has_labor_contract')),
                                }
                            ),
                            dynamic=self._builder_compact(
                                {
                                    '部门ID': dept_id,
                                    '部门名称': self._builder_text(staff.get('dept_name')),
                                    '租户ID': tenant_id,
                                }
                            ),
                            description='成员模块下的员工叶子节点。',
                        ),
                        children=[],
                    )
                )
            return nodes

        def build_wage_staff_nodes(self, tenant_id: str, wage_staff_rows: List[Dict[str, Any]]) -> List[GraphNode]:
            nodes: List[GraphNode] = []
            for staff in wage_staff_rows or []:
                staff_id = self._builder_text(staff.get('id')) or self._builder_text(staff.get('staff_ref')) or 'unknown'
                staff_name = self._builder_text(staff.get('name')) or f'员工_{staff_id}'
                work_num = self._builder_text(staff.get('work_num'))
                year_month = self._builder_text(staff.get('year_month'))
                last_month_wage = staff.get('last_month_wage', 0)

                if not staff_name and not work_num and self._builder_int(last_month_wage) in (None, 0):
                    continue

                summary_prefix = f'{year_month} ' if year_month else ''
                nodes.append(
                    self._node(
                        node_id=f'3_WAGE_STAFF_{staff_id}',
                        name=staff_name,
                        node_type='3_WAGE_STAFF',
                        category='dynamic',
                        level=3,
                        side='right',
                        parent_id='2_WAGE',
                        identity_key=f'WAGE_STAFF:{staff_id}',
                        fixed=False,
                        summary=f'{summary_prefix}工资：{self._builder_money_text(last_month_wage) or "0元"}',
                        detail=self._detail(
                            basic=self._builder_compact(
                                {
                                    '员工名称': staff_name,
                                    '工号': work_num,
                                    '上月工资金额': self._builder_money_text(last_month_wage),
                                    '所属部门': self._builder_text(staff.get('dept_name')),
                                    '公积金': self._builder_money_text(staff.get('housing_provident_fund', 0)),
                                    '五险总额': self._builder_money_text(staff.get('five_insurance_amount', 0)),
                                    '补充养老保险': self._builder_money_text(staff.get('supplement_old_age_insurance', 0)),
                                    '补充医疗保险': self._builder_money_text(staff.get('supplement_medical_insurance', 0)),
                                    '奖金': self._builder_money_text(staff.get('bonus', 0)),
                                    '福利费': self._builder_money_text(staff.get('welfare_fee', 0)),
                                    '股权激励': self._builder_money_text(staff.get('shareholding_incentive', 0)),
                                    '补保补缴明细': self._builder_text(staff.get('repair_insurance_detail') if staff.get('repair_insurance_detail') else "-"),
                                }
                            ),
                            dynamic=self._builder_compact(
                                {
                                    '工资月份': year_month,
                                    '租户ID': tenant_id,
                                }
                            ),
                            description='工资模块下直接挂载员工工资信息。',
                        ),
                        children=[],
                    )
                )
            return nodes

        def build_attendance_group_nodes(self, tenant_id: str, groups: List[Dict[str, Any]]) -> List[GraphNode]:
            nodes: List[GraphNode] = []
            for group in groups or []:
                group_id = self._builder_text(group.get('id')) or 'unknown'
                group_name = self._builder_text(group.get('name')) or f'考勤组_{group_id}'

                staff_nodes: List[GraphNode] = []
                for staff in group.get('staff', []) or []:
                    staff_id = self._builder_text(staff.get('id')) or 'unknown'
                    staff_name = self._builder_text(staff.get('name')) or f'员工_{staff_id}'
                    work_num = self._builder_text(staff.get('work_num'))
                    if not staff_name and not work_num:
                        continue
                    staff_nodes.append(
                        self._node(
                            node_id=f'4_ATTENDANCE_STAFF_{group_id}_{staff_id}',
                            name=staff_name,
                            node_type='4_ATTENDANCE_STAFF',
                            category='dynamic',
                            level=4,
                            side='right',
                            parent_id=f'3_ATTENDANCE_GROUP_{group_id}',
                            identity_key=f'ATTENDANCE_STAFF:{group_id}:{staff_id}',
                            fixed=False,
                            summary=f'本月考勤：{self._builder_hours_text(staff.get("month_attendance_hours", 0)) or "0h"}',
                            detail=self._detail(
                                basic=self._builder_compact(
                                    {
                                        '员工名称': staff_name,
                                        '工号': work_num,
                                        '部门': self._builder_text(staff.get('dept_name')),
                                        '本月合计考勤时长': self._builder_hours_text(staff.get('month_attendance_hours', 0)),
                                        '本月合计研发时长': self._builder_hours_text(staff.get('month_rd_hours', 0)),
                                    }
                                ),
                                dynamic=self._builder_compact(
                                    {
                                        '考勤组ID': group_id,
                                        '租户ID': tenant_id,
                                    }
                                ),
                                description='考勤组下的员工节点。',
                            ),
                            children=[],
                        )
                    )

                asset_nodes: List[GraphNode] = []
                for asset in group.get('assets', []) or []:
                    asset_id = self._builder_text(asset.get('id')) or 'unknown'
                    asset_name = self._builder_text(asset.get('name')) or f'资产_{asset_id}'
                    asset_code = self._builder_text(asset.get('code'))
                    if not asset_name and not asset_code:
                        continue
                    asset_nodes.append(
                        self._node(
                            node_id=f'4_ATTENDANCE_ASSET_{group_id}_{asset_id}',
                            name=asset_name,
                            node_type='4_ATTENDANCE_ASSET',
                            category='dynamic',
                            level=4,
                            side='right',
                            parent_id=f'3_ATTENDANCE_GROUP_{group_id}',
                            identity_key=f'ATTENDANCE_ASSET:{group_id}:{asset_id}',
                            fixed=False,
                            summary=f'本月考勤：{self._builder_hours_text(asset.get("month_attendance_hours", 0)) or "0h"}',
                            detail=self._detail(
                                basic=self._builder_compact(
                                    {
                                        '资产名称': asset_name,
                                        '资产编号': asset_code,
                                        '资产类型': self._builder_text(asset.get('asset_type')),
                                        '本月合计考勤时长': self._builder_hours_text(asset.get('month_attendance_hours', 0)),
                                        '本月合计研发时长': self._builder_hours_text(asset.get('month_rd_hours', 0)),
                                    }
                                ),
                                dynamic=self._builder_compact(
                                    {
                                        '考勤组ID': group_id,
                                        '租户ID': tenant_id,
                                    }
                                ),
                                description='考勤组下的资产节点。',
                            ),
                            children=[],
                        )
                    )

                staff_count = group.get('staff_count', len(staff_nodes)) or 0
                asset_count = group.get('asset_count', len(asset_nodes)) or 0
                if not staff_nodes and not asset_nodes and not staff_count and not asset_count:
                    continue

                nodes.append(
                    self._node(
                        node_id=f'3_ATTENDANCE_GROUP_{group_id}',
                        name=group_name,
                        node_type='3_ATTENDANCE_GROUP',
                        category='dynamic',
                        level=3,
                        side='right',
                        parent_id='2_ATTENDANCE',
                        identity_key=f'ATTENDANCE_GROUP:{group_id}',
                        fixed=False,
                        summary=f'人数：{staff_count}，资产：{asset_count}',
                        detail=self._detail(
                            basic=self._builder_compact(
                                {
                                    '考勤组名称': group_name,
                                    '考勤类型': self._builder_enum_text(
                                        group.get('group_type'),
                                        self._ATTENDANCE_GROUP_TYPE_MAP,
                                        unknown_prefix='考勤组类型编码',
                                    ),
                                    '包含人数': staff_count,
                                    '包含资产': asset_count,
                                    '考勤组规则': self._builder_text(group.get('rule')),
                                    '备注': self._builder_text(group.get('note')),
                                }
                            ),
                            dynamic=self._builder_compact(
                                {
                                    '考勤组ID': group_id,
                                    '租户ID': tenant_id,
                                }
                            ),
                            metrics={
                                '员工节点数': str(len(staff_nodes)),
                                '资产节点数': str(len(asset_nodes)),
                            },
                            description='考勤组节点下继续展示员工和资产。',
                        ),
                        children=staff_nodes + asset_nodes,
                    )
                )
            return nodes


class HrRepositoryMixin:
        _INTANGIBLE_ASSET_TYPE_MAP = {100: '专利', 200: '软著', 300: '非专利技术'}
        _ATTENDANCE_GROUP_TYPE_MAP = {100: '固定排班', 200: '周期排班'}
        _REMOVED_STATUSES = {5555, 7777}

        def _decode_staff_education(self, value: Any) -> str:
            text = self._stringify(value)
            if text in ('', '0'):
                return ''
            return text if not text.isdigit() else f'编码值:{text}'

        def _decode_staff_title(self, value: Any) -> str:
            text = self._stringify(value)
            if text in ('', '0'):
                return ''
            return text if not text.isdigit() else f'编码值:{text}'

        def _decode_group_type(self, value: Any) -> str:
            numeric = self._to_int(value)
            if numeric in self._ATTENDANCE_GROUP_TYPE_MAP:
                return self._ATTENDANCE_GROUP_TYPE_MAP[numeric]
            return self._stringify(value)

        def _decode_intangible_asset_type(self, value: Any) -> str:
            numeric = self._to_int(value)
            if numeric in self._INTANGIBLE_ASSET_TYPE_MAP:
                return self._INTANGIBLE_ASSET_TYPE_MAP[numeric]
            return self._stringify(value)

        def _money_text(self, value: Any) -> str:
            amount = round(self._to_float(value), 2)
            if abs(amount - int(amount)) < 1e-9:
                return f'{int(amount)}元'
            return f'{amount:.2f}元'

        def _hours_text(self, value: Any, *, suffix: str = '时') -> str:
            amount = round(self._to_float(value), 2)
            if abs(amount - int(amount)) < 1e-9:
                return f'{int(amount)}{suffix}'
            return f'{amount:.2f}{suffix}'

        def _previous_year_month(self, year: int, month: int) -> Tuple[int, int]:
            if month == 1:
                return year - 1, 12
            return year, month - 1

        def _resolve_record_year_month(self, dt_value: Any, year_value: Any, month_value: Any) -> Tuple[Optional[int], Optional[int]]:
            normalized = self._normalize_date(dt_value)
            if normalized is not None:
                return normalized.year, normalized.month
            year_int = self._to_int(year_value)
            month_int = self._to_int(month_value)
            if year_int and 1 <= month_int <= 12:
                return year_int, month_int
            return None, None

        def _record_before_context(self, record_year: Optional[int], record_month: Optional[int], current_year: int, current_month: int) -> bool:
            if record_year is None or record_month is None:
                return False
            return (record_year, record_month) < (current_year, current_month)

        def _build_note_text(self, prefix: str, notes: List[str]) -> str:
            if not notes:
                return prefix
            return f'{prefix} {"；".join(notes)}'

        def _format_group_rule(self, group_type: Any, rows: List[Tuple[Any, Any]]) -> str:
            cleaned: List[str] = []
            for day_value, hour_value in rows:
                day_int = self._to_int(day_value)
                hour_float = self._to_float(hour_value)
                if day_int <= 0 and hour_float <= 0:
                    continue
                if abs(hour_float - int(hour_float)) < 1e-9:
                    hour_text = str(int(hour_float))
                else:
                    hour_text = f'{hour_float:.2f}'
                cleaned.append(f'第{day_int}天 {hour_text}小时')
            if not cleaned:
                return ''
            group_type_text = self._decode_group_type(group_type)
            return f'{group_type_text}：' + '；'.join(cleaned)

        def _fetch_staff_rows(self, conn, tenant_id: str, year: int) -> List[Dict[str, Any]]:
            fields = [
                "s.`ID` AS `staff_id`",
                "s.`FULL_NAME` AS `name`",
                "s.`WORK_NUM` AS `work_num`",
                "s.`DEPT_ID` AS `dept_id`",
                "s.`DEPT_NAME` AS `dept_name`",
                "s.`AGE` AS `age`",
                "s.`SEX` AS `gender`",
                "s.`EMPLOYMENT_METHOD` AS `employ_way`",
                "s.`ENTRY_TIME` AS `entry_date`",
                "s.`RESIGN_TIME` AS `resign_date`",
                "s.`PHONES` AS `phone`",
                "s.`EDUCATIONAL_BACKGROUND` AS `education`",
                "s.`MAJOR` AS `major`",
                "s.`POSITION` AS `duty`",
                "s.`POSITIONAL_TITLE` AS `title`",
                "s.`ID_CARD` AS `id_card`",
                "s.`LABOR_CONTRACT_ANNEX_ID` AS `labor_contract_annex_id`",
                "s.`LABOR_CONTRACT_ANNEX_URL` AS `labor_contract_annex_url`",
                "s.`CATEGORY` AS `staff_category`",
            ]

            sql = (
                f"SELECT {', '.join(fields)} "
                "FROM `T_STAFF` s "
                "WHERE s.`TENANT_ID` = %s "
                "ORDER BY s.`DEPT_NAME` ASC, s.`FULL_NAME` ASC"
            )
            rows = self._safe_rows(conn, sql, (tenant_id,))

            results: List[Dict[str, Any]] = []
            for row in rows:
                annex_id = row[16]
                annex_url = row[17]
                has_labor_contract = '已上传' if annex_id not in (None, '', '0') or annex_url not in (None, '', 'null') else '未上传'
                age = self._to_int(row[5])
                results.append(
                    {
                        'id': self._stringify(row[0]),
                        'name': self._first_non_empty(self._stringify(row[1]), f'未命名员工_{row[0]}'),
                        'work_num': self._stringify(row[2]),
                        'dept_id': self._stringify(row[3]) or 'UNKNOWN',
                        'dept_name': self._first_non_empty(self._stringify(row[4]), '未分配部门'),
                        'age': age if age else '',
                        'gender': self._to_int(row[6]),
                        'employ_way': self._to_int(row[7]),
                        'entry_date': self._stringify(row[8]),
                        'resign_date': self._stringify(row[9]),
                        'phone': self._stringify(row[10]),
                        'education': self._decode_staff_education(row[11]),
                        'major': self._stringify(row[12]),
                        'duty': self._stringify(row[13]),
                        'title': self._decode_staff_title(row[14]),
                        'id_card': self._stringify(row[15]),
                        'has_labor_contract': has_labor_contract,
                        'staff_category': row[18],
                    }
                )
            return results

        def _fetch_rd_staff_ids(self, conn, tenant_id: str, year: int, staff_rows: List[Dict[str, Any]]) -> set[str]:
            rd_staff_ids: set[str] = set()
            year_start, next_year_start = self._year_range(year)
            sql = (
                "SELECT DISTINCT t.`STAFF_ID` "
                "FROM `T_PROJECT_USER_R_D_TIME` t "
                "WHERE COALESCE(t.`R_D_HOUR`, 0) > 0 "
                "AND t.`TENANT_ID` = %s "
                "AND t.`DATE` >= %s AND t.`DATE` < %s"
            )
            for row in self._safe_rows(conn, sql, (tenant_id, year_start, next_year_start)):
                rd_staff_ids.add(self._stringify(row[0]))

            for staff in staff_rows:
                if self._category_is_rd(staff.get('staff_category')):
                    rd_staff_ids.add(self._stringify(staff.get('id')))
            return rd_staff_ids

        def fetch_hr_domain(self, conn, tenant_id: str, year: int, month: int) -> Dict[str, Any]:
            staff_rows = self._fetch_staff_rows(conn, tenant_id, year)
            active_staff = [row for row in staff_rows if self._is_active_for_year(row.get('resign_date'), year)]
            active_staff_ids = {self._stringify(row.get('id')) for row in active_staff}
            rd_staff_ids = self._fetch_rd_staff_ids(conn, tenant_id, year, staff_rows)
            active_rd_staff_ids = active_staff_ids & rd_staff_ids

            year_start, next_year_start = self._year_range(year)
            total_rd_hours = 0.0
            month_rd_hours_by_staff: Dict[str, float] = defaultdict(float)
            year_rd_hours_by_staff: Dict[str, float] = defaultdict(float)
            rd_sql = (
                "SELECT t.`STAFF_ID`, t.`R_D_HOUR`, t.`DATE` AS stat_date, "
                "t.`YEARS` AS stat_year, t.`MONTHS` AS stat_month "
                "FROM `T_PROJECT_USER_R_D_TIME` t "
                "WHERE t.`TENANT_ID` = %s AND t.`DATE` >= %s AND t.`DATE` < %s"
            )
            for row in self._safe_rows(conn, rd_sql, (tenant_id, year_start, next_year_start)):
                staff_id = self._stringify(row[0])
                hours = self._to_float(row[1])
                stat_date = self._normalize_date(row[2])
                stat_year = self._to_int(row[3])
                stat_month = self._to_int(row[4])
                total_rd_hours += hours
                year_rd_hours_by_staff[staff_id] += hours
                if (stat_date and stat_date.year == year and stat_date.month == month) or (
                    stat_date is None and stat_year == year and stat_month == month
                ):
                    month_rd_hours_by_staff[staff_id] += hours

            wage_data = self._fetch_wage_year_data(conn, tenant_id, year, month, rd_staff_ids=rd_staff_ids)

            abnormal_sql = """
                SELECT COUNT(*)
                FROM (
                    SELECT c.`STAFF_ID` AS staff_id, c.`WORK_DATE` AS work_day
                    FROM `T_ATTENDANCE_GROUP_USER_CLASSES` c
                    WHERE c.`WORK_DATE` >= %s
                      AND c.`WORK_DATE` < %s
                      AND c.`TENANT_ID` = %s
                    GROUP BY c.`STAFF_ID`, c.`WORK_DATE`
                    HAVING SUM(COALESCE(c.`ATTENDANCE_HOUR`, 0)) > 23
                ) t
            """
            row = self._safe_one(conn, abnormal_sql, (year_start, next_year_start, tenant_id))
            abnormal_count = self._to_int(row[0]) if row else 0

            departments_map: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
            for row in active_staff:
                departments_map[(row['dept_id'], row['dept_name'])].append(row)

            all_rows_by_dept: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
            for row in staff_rows:
                all_rows_by_dept[(row['dept_id'], row['dept_name'])].append(row)

            departments: List[Dict[str, Any]] = []
            for (dept_id, dept_name), dept_staff in sorted(departments_map.items(), key=lambda item: item[0][1]):
                source_rows = all_rows_by_dept[(dept_id, dept_name)]
                if not dept_staff and not source_rows:
                    continue
                departments.append(
                    {
                        'id': dept_id,
                        'name': dept_name,
                        'staff_count': len(dept_staff),
                        'entry_count': sum(1 for row in source_rows if self._is_in_year(row.get('entry_date'), year)),
                        'leave_count': sum(1 for row in source_rows if self._is_in_year(row.get('resign_date'), year)),
                        'staff': dept_staff,
                    }
                )

            attendance_groups = self._fetch_attendance_groups(
                conn=conn,
                tenant_id=tenant_id,
                year=year,
                month=month,
                active_staff=active_staff,
                month_rd_hours_by_staff=month_rd_hours_by_staff,
            )

            attendance_detail = {
                '包含考勤组': len(attendance_groups),
                '参与考勤人员': sum(group.get('staff_count', 0) for group in attendance_groups),
                '参与考勤资产': sum(group.get('asset_count', 0) for group in attendance_groups),
            }

            hr_notes: List[str] = []
            member_notes: List[str] = []
            wage_notes: List[str] = []
            attendance_notes: List[str] = []

            if any(str(row.get('education', '')).startswith('编码值:') for row in staff_rows):
                member_notes.append('学历字段在库内为编码值，当前表结构未提供学历字典表，因此员工详情中保留编码原值')
            if any(str(row.get('title', '')).startswith('编码值:') for row in staff_rows):
                member_notes.append('职称字段在库内为编码值，当前表结构未提供职称字典表，因此员工详情中保留编码原值')
            if staff_rows and any(row.get('staff_category') not in (None, '', 'null', 0, '0') for row in staff_rows):
                hr_notes.append('研发口径已按项目研发工时>0的员工并补充 CATEGORY=100/200 的员工统计；若甲方库中的技术/研究人员编码不同，需要同步调整 _category_is_rd')

            member_detail = {
                '该年员工在职人数': f'{len(active_staff)}人',
                '该年入职人数': f'{sum(1 for row in staff_rows if self._is_in_year(row.get("entry_date"), year))}人',
                '该年离职人数': f'{sum(1 for row in staff_rows if self._is_in_year(row.get("resign_date"), year))}人',
                '该年员工研发人员占比': f'{round((len(active_rd_staff_ids) / len(active_staff) * 100), 2) if active_staff else 0}%',
            }

            return {
                'summary': f'员工总数：{len(staff_rows)}',
                'detail': {
                    '该年员工总人数': f'{len(staff_rows)}人',
                    '该年全部人员费用': self._money_text(wage_data['total_staff_cost']),
                    '该年研发人员人均研发工时': self._hours_text(
                        (total_rd_hours / len(active_rd_staff_ids)) if active_rd_staff_ids else 0,
                        suffix='时',
                    ),
                    '该年人员异常情况': abnormal_count,
                },
                'detail_description': self._build_note_text('人事域总览。', hr_notes),
                'member_detail': member_detail,
                'member_description': self._build_note_text('成员模块：部门到员工。', member_notes),
                'departments': departments,
                'wage_detail': wage_data['wage_detail'],
                'wage_description': self._build_note_text('工资模块：直接挂载员工工资。', wage_notes),
                'wage_staff_rows': wage_data['wage_staff_rows'],
                'attendance_detail': attendance_detail,
                'attendance_description': self._build_note_text('考勤模块：考勤组到员工和资产。', attendance_notes),
                'attendance_groups': attendance_groups,
                'active_staff_rows': active_staff,
                'year_rd_hours_by_staff': dict(year_rd_hours_by_staff),
            }

        def _fetch_social_security_supplement_map(
            self,
            conn,
            tenant_id: str,
            target_year: int,
            target_month: int,
            staff_by_id: Dict[str, Dict[str, Any]],
            staff_by_work_num: Dict[str, Dict[str, Any]],
        ) -> Dict[str, str]:
            sql = """
                SELECT
                    s.`STAFF_ID` AS staff_id,
                    s.`WORK_NUM` AS work_num,
                    s.`SUPPLEMENT_TIME` AS supplement_time,
                    s.`YEAR` AS stat_year,
                    s.`MONTH` AS stat_month,
                    s.`HOUSING_PROVIDENT_FUND` AS housing_pf,
                    s.`FIVE_INSURANCE_AMOUNT` AS five_insurance,
                    s.`MEDICAL` AS medical,
                    s.`PENSION` AS pension,
                    s.`UNEMPLOYMENT` AS unemployment,
                    s.`WORK_INJURY` AS work_injury,
                    s.`MATERNITY` AS maternity
                FROM `T_STAFF_SOCIAL_SECURITY_SUPPLEMENT` s
                WHERE s.`TENANT_ID` = %s
            """

            results: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
            for row in self._safe_rows(conn, sql, (tenant_id,)):
                record_year, record_month = self._resolve_record_year_month(row[2], row[3], row[4])
                if (record_year, record_month) != (target_year, target_month):
                    continue

                staff = staff_by_id.get(self._stringify(row[0])) or staff_by_work_num.get(self._stringify(row[1]))
                if not staff:
                    continue
                staff_key = self._stringify(staff.get('id'))
                results[staff_key]['housing_pf'] += self._to_float(row[5])
                results[staff_key]['five_insurance'] += self._to_float(row[6])
                results[staff_key]['medical'] += self._to_float(row[7])
                results[staff_key]['pension'] += self._to_float(row[8])
                results[staff_key]['unemployment'] += self._to_float(row[9])
                results[staff_key]['work_injury'] += self._to_float(row[10])
                results[staff_key]['maternity'] += self._to_float(row[11])

            text_map: Dict[str, str] = {}
            for staff_key, item in results.items():
                parts: List[str] = []
                if item['housing_pf'] > 0:
                    parts.append(f'公积金{self._money_text(item["housing_pf"])}')
                if item['five_insurance'] > 0:
                    parts.append(f'五险{self._money_text(item["five_insurance"])}')
                if item['medical'] > 0:
                    parts.append(f'医疗{self._money_text(item["medical"])}')
                if item['pension'] > 0:
                    parts.append(f'养老{self._money_text(item["pension"])}')
                if item['unemployment'] > 0:
                    parts.append(f'失业{self._money_text(item["unemployment"])}')
                if item['work_injury'] > 0:
                    parts.append(f'工伤{self._money_text(item["work_injury"])}')
                if item['maternity'] > 0:
                    parts.append(f'生育{self._money_text(item["maternity"])}')
                if parts:
                    text_map[staff_key] = f'{target_year}-{target_month:02d} 补缴：' + '，'.join(parts)
            return text_map

        def _fetch_wage_year_data(self, conn, tenant_id: str, year: int, month: int, rd_staff_ids: Optional[set[str]] = None) -> Dict[str, Any]:
            rd_staff_ids = rd_staff_ids or set()
            sql = """
                SELECT
                    w.`STAFF_ID` AS staff_id,
                    w.`WORK_NUM` AS work_num,
                    w.`FULL_NAME` AS staff_name,
                    w.`DEPT_NAME` AS dept_name,
                    w.`WAGE_TIME` AS wage_time,
                    w.`YEAR` AS stat_year,
                    w.`MONTH` AS stat_month,
                    w.`WAGE` AS wage,
                    w.`HOUSING_PROVIDENT_FUND` AS housing_pf,
                    w.`FIVE_INSURANCE_AMOUNT` AS five_insurance,
                    w.`SUPPLEMENT_PENSION` AS supp_old,
                    w.`SUPPLEMENT_MEDICAL` AS supp_medical,
                    w.`BONUS` AS bonus,
                    w.`STAFF_WAGE_BENEFIT_VAL` AS welfare,
                    w.`SHAREHOLDING_MOTIVATE_BENEFIT_AMOUNT` AS stock
                FROM `T_STAFF_WAGE` w
                WHERE w.`TENANT_ID` = %s
                ORDER BY w.`WAGE_TIME` DESC
            """
            rows = self._safe_rows(conn, sql, (tenant_id,))

            staff_rows = self._fetch_staff_rows(conn, tenant_id, year)
            staff_by_id = {self._stringify(row['id']): row for row in staff_rows if row.get('id') not in (None, '', 'null')}
            staff_by_work_num = {self._stringify(row['work_num']): row for row in staff_rows if row.get('work_num') not in (None, '', 'null')}
            active_staff_ids = {
                self._stringify(row['id'])
                for row in staff_rows
                if self._is_active_for_year(row.get('resign_date'), year)
            }
            active_rd_staff_ids = active_staff_ids & rd_staff_ids

            prev_year, prev_month = self._previous_year_month(year, month)
            supplement_detail_map = self._fetch_social_security_supplement_map(
                conn=conn,
                tenant_id=tenant_id,
                target_year=prev_year,
                target_month=prev_month,
                staff_by_id=staff_by_id,
                staff_by_work_num=staff_by_work_num,
            )

            total_human_cost = 0.0
            total_staff_cost = 0.0
            total_rd_human_cost = 0.0

            exact_prev_by_staff: Dict[str, Dict[str, Any]] = {}
            latest_before_context_by_staff: Dict[str, Dict[str, Any]] = {}
            latest_any_by_staff: Dict[str, Dict[str, Any]] = {}

            def better(current: Optional[Dict[str, Any]], candidate: Dict[str, Any]) -> bool:
                if current is None:
                    return True
                return candidate['sort_key'] > current['sort_key']

            for row in rows:
                row_staff_id = self._stringify(row[0])
                row_work_num = self._stringify(row[1])
                row_name = self._stringify(row[2])
                row_dept_name = self._stringify(row[3])
                wage_time = self._normalize_date(row[4])
                record_year, record_month = self._resolve_record_year_month(row[4], row[5], row[6])

                wage = self._to_float(row[7])
                housing_pf = self._to_float(row[8])
                insurance = self._to_float(row[9])
                old_age = self._to_float(row[10])
                medical = self._to_float(row[11])
                bonus = self._to_float(row[12])
                welfare = self._to_float(row[13])
                stock = self._to_float(row[14])

                staff = staff_by_id.get(row_staff_id) or staff_by_work_num.get(row_work_num)
                resolved_staff_id = self._stringify(staff.get('id')) if staff else row_staff_id
                resolved_work_num = self._stringify(staff.get('work_num')) if staff else row_work_num
                resolved_name = self._first_non_empty(staff.get('name') if staff else '', row_name, f'员工_{resolved_staff_id or resolved_work_num}')
                resolved_dept_name = self._first_non_empty(staff.get('dept_name') if staff else '', row_dept_name, '')

                if record_year == year:
                    total_human_cost += wage + bonus
                    total_staff_cost += wage + insurance + housing_pf + bonus + welfare
                    if resolved_staff_id in rd_staff_ids:
                        total_rd_human_cost += wage + bonus

                record = {
                    'id': resolved_staff_id,
                    'staff_ref': resolved_staff_id or resolved_work_num,
                    'name': resolved_name,
                    'work_num': resolved_work_num,
                    'dept_name': resolved_dept_name,
                    'record_year': record_year,
                    'record_month': record_month,
                    'year_month': f'{record_year}-{record_month:02d}' if record_year and record_month else '',
                    'wage_date': wage_time,
                    'last_month_wage': round(wage, 2),
                    'housing_provident_fund': round(housing_pf, 2),
                    'five_insurance_amount': round(insurance, 2),
                    'supplement_old_age_insurance': round(old_age, 2),
                    'supplement_medical_insurance': round(medical, 2),
                    'bonus': round(bonus, 2),
                    'welfare_fee': round(welfare, 2),
                    'shareholding_incentive': round(stock, 2),
                    'repair_insurance_detail': supplement_detail_map.get(resolved_staff_id, ''),
                    'sort_key': (
                        record_year or -1,
                        record_month or -1,
                        self._stringify(wage_time),
                    ),
                }

                staff_key = resolved_staff_id or resolved_work_num
                if not staff_key:
                    continue

                if better(latest_any_by_staff.get(staff_key), record):
                    latest_any_by_staff[staff_key] = record
                if self._record_before_context(record_year, record_month, year, month) and better(latest_before_context_by_staff.get(staff_key), record):
                    latest_before_context_by_staff[staff_key] = record
                if (record_year, record_month) == (prev_year, prev_month) and better(exact_prev_by_staff.get(staff_key), record):
                    exact_prev_by_staff[staff_key] = record

            wage_staff_rows: List[Dict[str, Any]] = []
            candidate_staff_keys = set(latest_any_by_staff.keys()) | set(exact_prev_by_staff.keys()) | set(latest_before_context_by_staff.keys())
            for staff_key in candidate_staff_keys:
                picked = exact_prev_by_staff.get(staff_key) or latest_before_context_by_staff.get(staff_key) or latest_any_by_staff.get(staff_key)
                if not picked:
                    continue

                # 保持工资员工节点集合与原逻辑一致，避免影响其他模块/分支布局；
                # 但“上月工资金额”及同月明细字段严格取当前年月的上一月。
                picked = dict(picked)
                prev_record = exact_prev_by_staff.get(staff_key)
                if prev_record:
                    picked.update(
                        {
                            'record_year': prev_record.get('record_year'),
                            'record_month': prev_record.get('record_month'),
                            'year_month': prev_record.get('year_month', f'{prev_year}-{prev_month:02d}'),
                            'wage_date': prev_record.get('wage_date'),
                            'last_month_wage': prev_record.get('last_month_wage', 0),
                            'housing_provident_fund': prev_record.get('housing_provident_fund', 0),
                            'five_insurance_amount': prev_record.get('five_insurance_amount', 0),
                            'supplement_old_age_insurance': prev_record.get('supplement_old_age_insurance', 0),
                            'supplement_medical_insurance': prev_record.get('supplement_medical_insurance', 0),
                            'bonus': prev_record.get('bonus', 0),
                            'welfare_fee': prev_record.get('welfare_fee', 0),
                            'shareholding_incentive': prev_record.get('shareholding_incentive', 0),
                            'repair_insurance_detail': prev_record.get('repair_insurance_detail', ''),
                        }
                    )

                    picked.pop('sort_key', None)
                    wage_staff_rows.append(picked)

            on_job_count = len(active_staff_ids)
            rd_on_job_count = len(active_rd_staff_ids)
            return {
                'total_staff_cost': round(total_staff_cost, 2),
                'wage_detail': {
                    '该年人工成本': self._money_text(total_human_cost),
                    '该年研发人工成本': self._money_text(total_rd_human_cost),
                    '人均薪资': self._money_text((total_human_cost / on_job_count / 12) if on_job_count else 0),
                    '研发人均薪资': self._money_text((total_rd_human_cost / rd_on_job_count / 12) if rd_on_job_count else 0),
                },
                'wage_staff_rows': sorted(wage_staff_rows, key=lambda item: (item.get('dept_name', ''), item.get('name', ''))),
            }

        def _fetch_device_type_map(self, conn, tenant_id: str) -> Dict[str, str]:
            sql = """
                SELECT d.`ID`, d.`NAME`
                FROM `T_DEVICE_TYPE_CONFIG` d
                WHERE d.`TENANT_ID` = %s
            """
            return {
                self._stringify(row[0]): self._stringify(row[1])
                for row in self._safe_rows(conn, sql, (tenant_id,))
                if row[0] not in (None, '', 'null')
            }

        def _fetch_fixed_asset_base_map(self, conn, tenant_id: str) -> Dict[str, Dict[str, Any]]:
            device_type_map = self._fetch_device_type_map(conn, tenant_id)
            sql = """
                SELECT
                    a.`ID` AS asset_id,
                    a.`NAME` AS asset_name,
                    a.`CODE` AS asset_code,
                    a.`DEVICE_TYPE_CONFIG_ID` AS type_id
                FROM `T_FIXED_ASSETS` a
                WHERE a.`TENANT_ID` = %s
            """
            result: Dict[str, Dict[str, Any]] = {}
            for row in self._safe_rows(conn, sql, (tenant_id,)):
                asset_id = self._stringify(row[0])
                if not asset_id:
                    continue
                result[asset_id] = {
                    'id': asset_id,
                    'name': self._stringify(row[1]),
                    'code': self._stringify(row[2]),
                    'asset_type': device_type_map.get(self._stringify(row[3]), self._stringify(row[3])),
                }
            return result

        def _fetch_intangible_asset_base_map(self, conn, tenant_id: str) -> Dict[str, Dict[str, Any]]:
            sql = """
                SELECT
                    a.`ID` AS asset_id,
                    a.`NAME` AS asset_name,
                    a.`CODE` AS asset_code,
                    a.`ASSETS_TYPE` AS type_code
                FROM `T_INTANGIBLE_ASSETS` a
                WHERE a.`TENANT_ID` = %s
            """
            result: Dict[str, Dict[str, Any]] = {}
            for row in self._safe_rows(conn, sql, (tenant_id,)):
                asset_id = self._stringify(row[0])
                if not asset_id:
                    continue
                result[asset_id] = {
                    'id': asset_id,
                    'name': self._stringify(row[1]),
                    'code': self._stringify(row[2]),
                    'asset_type': self._decode_intangible_asset_type(row[3]),
                }
            return result

        def _fetch_attendance_group_rule_map(self, conn, tenant_id: str) -> Dict[str, str]:
            group_type_map: Dict[str, Any] = {}
            group_sql = """
                SELECT g.`ID`, g.`ATTENDANCE_GROUP_TYPE`
                FROM `T_ATTENDANCE_GROUP` g
                WHERE g.`TENANT_ID` = %s
            """
            for row in self._safe_rows(conn, group_sql, (tenant_id,)):
                group_type_map[self._stringify(row[0])] = row[1]

            sql = """
                SELECT r.`ATTENDANCE_GROUP_ID`, r.`DAYS`, r.`HOURS`
                FROM `T_ATTENDANCE_GROUP_CLASSES` r
                WHERE r.`TENANT_ID` = %s
            """

            grouped_rows: Dict[str, List[Tuple[Any, Any]]] = defaultdict(list)
            for row in self._safe_rows(conn, sql, (tenant_id,)):
                grouped_rows[self._stringify(row[0])].append((row[1], row[2]))

            return {
                group_id: self._format_group_rule(group_type_map.get(group_id), rows)
                for group_id, rows in grouped_rows.items()
            }

        def _fetch_attendance_groups(
            self,
            conn,
            tenant_id: str,
            year: int,
            month: int,
            active_staff: List[Dict[str, Any]],
            month_rd_hours_by_staff: Dict[str, float],
        ) -> List[Dict[str, Any]]:
            groups: List[Dict[str, Any]] = []
            month_start, next_month_start = self._month_range(year, month)
            group_meta: Dict[str, Dict[str, Any]] = {}
            group_sql = """
                SELECT g.`ID`, g.`NAME`, g.`ATTENDANCE_GROUP_TYPE`, g.`REMARK`
                FROM `T_ATTENDANCE_GROUP` g
                WHERE g.`TENANT_ID` = %s
            """
            for row in self._safe_rows(conn, group_sql, (tenant_id,)):
                group_id = self._stringify(row[0])
                group_meta[group_id] = {
                    'id': group_id,
                    'name': self._stringify(row[1]),
                    'group_type': row[2],
                    'note': self._stringify(row[3]),
                }

            rule_map = self._fetch_attendance_group_rule_map(conn, tenant_id)
            staff_map = {self._stringify(row['id']): row for row in active_staff}
            grouped_staff: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

            user_sql = """
                SELECT
                    u.`ATTENDANCE_GROUP_ID`,
                    u.`STAFF_ID`,
                    u.`FULL_NAME`,
                    u.`WORK_NUM`,
                    u.`DEPT_NAME`,
                    u.`REMOVE_STATUS`
                FROM `T_ATTENDANCE_GROUP_USER` u
                WHERE u.`TENANT_ID` = %s
            """
            for row in self._safe_rows(conn, user_sql, (tenant_id,)):
                if self._to_int(row[5]) in self._REMOVED_STATUSES:
                    continue
                group_id = self._stringify(row[0])
                staff_id = self._stringify(row[1])
                base_staff = staff_map.get(staff_id)
                if base_staff is None:
                    continue
                grouped_staff[group_id][staff_id] = {
                    'id': staff_id,
                    'name': self._first_non_empty(base_staff.get('name'), self._stringify(row[2])),
                    'work_num': self._first_non_empty(base_staff.get('work_num'), self._stringify(row[3])),
                    'dept_name': self._first_non_empty(base_staff.get('dept_name'), self._stringify(row[4])),
                    'month_attendance_hours': 0.0,
                    'month_rd_hours': 0.0,
                }

            user_class_sql = """
                SELECT
                    c.`ATTENDANCE_GROUP_ID`,
                    c.`STAFF_ID`,
                    SUM(COALESCE(c.`ATTENDANCE_HOUR`, 0)),
                    SUM(COALESCE(c.`R_D_TOTAL_HOUR`, 0))
                FROM `T_ATTENDANCE_GROUP_USER_CLASSES` c
                WHERE c.`DATE` >= %s
                  AND c.`DATE` < %s
                  AND c.`TENANT_ID` = %s
                GROUP BY c.`ATTENDANCE_GROUP_ID`, c.`STAFF_ID`
            """
            for row in self._safe_rows(conn, user_class_sql, (month_start, next_month_start, tenant_id)):
                group_id = self._stringify(row[0])
                staff_id = self._stringify(row[1])
                base_staff = staff_map.get(staff_id)
                if base_staff is None:
                    continue
                grouped_staff[group_id].setdefault(
                    staff_id,
                    {
                        'id': staff_id,
                        'name': base_staff.get('name', ''),
                        'work_num': base_staff.get('work_num', ''),
                        'dept_name': base_staff.get('dept_name', ''),
                        'month_attendance_hours': 0.0,
                        'month_rd_hours': 0.0,
                    },
                )
                grouped_staff[group_id][staff_id]['month_attendance_hours'] = round(self._to_float(row[2]), 2)
                grouped_staff[group_id][staff_id]['month_rd_hours'] = round(
                    self._to_float(row[3]) or self._to_float(month_rd_hours_by_staff.get(staff_id, 0)),
                    2,
                )

            fixed_asset_meta = self._fetch_fixed_asset_base_map(conn, tenant_id)
            fixed_assets_by_group: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
            fixed_group_sql = """
                SELECT f.`ATTENDANCE_GROUP_ID`, f.`FIXED_ASSETS_ID`, f.`REMOVE_STATUS`
                FROM `T_FIXED_ASSETS_ATTENDANCE_GROUP` f
                WHERE f.`TENANT_ID` = %s
            """
            for row in self._safe_rows(conn, fixed_group_sql, (tenant_id,)):
                if self._to_int(row[2]) in self._REMOVED_STATUSES:
                    continue
                group_id = self._stringify(row[0])
                asset_id = self._stringify(row[1])
                asset_meta = fixed_asset_meta.get(asset_id)
                if not asset_meta:
                    continue
                fixed_assets_by_group[group_id][asset_id] = {
                    **asset_meta,
                    'month_attendance_hours': 0.0,
                    'month_rd_hours': 0.0,
                }

            fixed_class_sql = """
                SELECT
                    c.`ATTENDANCE_GROUP_ID`,
                    c.`FIXED_ASSETS_ID`,
                    SUM(COALESCE(c.`ATTENDANCE_HOUR`, 0)),
                    SUM(COALESCE(c.`R_D_TOTAL_HOUR`, 0))
                FROM `T_FIXED_ASSETS_CLASSES` c
                WHERE c.`DATE` >= %s
                  AND c.`DATE` < %s
                  AND c.`TENANT_ID` = %s
                GROUP BY c.`ATTENDANCE_GROUP_ID`, c.`FIXED_ASSETS_ID`
            """
            for row in self._safe_rows(conn, fixed_class_sql, (month_start, next_month_start, tenant_id)):
                group_id = self._stringify(row[0])
                asset_id = self._stringify(row[1])
                asset_meta = fixed_asset_meta.get(asset_id)
                if not asset_meta:
                    continue
                fixed_assets_by_group[group_id].setdefault(
                    asset_id,
                    {
                        **asset_meta,
                        'month_attendance_hours': 0.0,
                        'month_rd_hours': 0.0,
                    },
                )
                fixed_assets_by_group[group_id][asset_id]['month_attendance_hours'] = round(self._to_float(row[2]), 2)
                fixed_assets_by_group[group_id][asset_id]['month_rd_hours'] = round(self._to_float(row[3]), 2)

            intangible_asset_meta = self._fetch_intangible_asset_base_map(conn, tenant_id)
            intangible_assets_by_group: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
            intangible_group_sql = """
                SELECT i.`ATTENDANCE_GROUP_ID`, i.`INTANGIBLE_ASSETS_ID`, i.`REMOVE_STATUS`
                FROM `T_INTANGIBLE_ASSETS_ATTENDANCE_GROUP` i
                WHERE i.`TENANT_ID` = %s
            """
            for row in self._safe_rows(conn, intangible_group_sql, (tenant_id,)):
                if self._to_int(row[2]) in self._REMOVED_STATUSES:
                    continue
                group_id = self._stringify(row[0])
                asset_id = self._stringify(row[1])
                asset_meta = intangible_asset_meta.get(asset_id)
                if not asset_meta:
                    continue
                intangible_assets_by_group[group_id][asset_id] = {
                    **asset_meta,
                    'month_attendance_hours': 0.0,
                    'month_rd_hours': 0.0,
                }

            intangible_class_sql = """
                SELECT
                    c.`ATTENDANCE_GROUP_ID`,
                    c.`INTANGIBLE_ASSETS_ID`,
                    SUM(COALESCE(c.`ATTENDANCE_HOUR`, 0)),
                    SUM(COALESCE(c.`R_D_TOTAL_HOUR`, 0))
                FROM `T_INTANGIBLE_ASSETS_CLASSES` c
                WHERE c.`DATE` >= %s
                  AND c.`DATE` < %s
                  AND c.`TENANT_ID` = %s
                GROUP BY c.`ATTENDANCE_GROUP_ID`, c.`INTANGIBLE_ASSETS_ID`
            """
            for row in self._safe_rows(conn, intangible_class_sql, (month_start, next_month_start, tenant_id)):
                group_id = self._stringify(row[0])
                asset_id = self._stringify(row[1])
                asset_meta = intangible_asset_meta.get(asset_id)
                if not asset_meta:
                    continue
                intangible_assets_by_group[group_id].setdefault(
                    asset_id,
                    {
                        **asset_meta,
                        'month_attendance_hours': 0.0,
                        'month_rd_hours': 0.0,
                    },
                )
                intangible_assets_by_group[group_id][asset_id]['month_attendance_hours'] = round(self._to_float(row[2]), 2)
                intangible_assets_by_group[group_id][asset_id]['month_rd_hours'] = round(self._to_float(row[3]), 2)

            all_group_ids = (
                set(group_meta.keys())
                | set(grouped_staff.keys())
                | set(fixed_assets_by_group.keys())
                | set(intangible_assets_by_group.keys())
            )
            for group_id in sorted(all_group_ids, key=lambda g: group_meta.get(g, {}).get('name', g)):
                meta = group_meta.get(group_id, {})
                staff_list = sorted(grouped_staff.get(group_id, {}).values(), key=lambda item: item.get('name', ''))
                asset_map: Dict[str, Dict[str, Any]] = {}
                asset_map.update(fixed_assets_by_group.get(group_id, {}))
                asset_map.update(intangible_assets_by_group.get(group_id, {}))
                asset_list = sorted(asset_map.values(), key=lambda item: item.get('name', ''))

                if not staff_list and not asset_list:
                    continue

                groups.append(
                    {
                        'id': group_id,
                        'name': meta.get('name') or f'考勤组_{group_id}',
                        'group_type': meta.get('group_type'),
                        'rule': rule_map.get(group_id, ''),
                        'note': meta.get('note', ''),
                        'staff_count': len(staff_list),
                        'asset_count': len(asset_list),
                        'staff': staff_list,
                        'assets': asset_list,
                    }
                )
            return groups
