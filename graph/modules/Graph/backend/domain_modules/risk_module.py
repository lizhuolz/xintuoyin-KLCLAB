from __future__ import annotations

from collections import defaultdict
from datetime import date
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from ..models.graph_models import GraphNode


class RiskGraphBuilderMixin:

    def build_risk_item_nodes(self, category_key: str, category_name: str, items: List[Dict[str, Any]]) -> List[GraphNode]:
        nodes: List[GraphNode] = []
        for index, item in enumerate(items, start=1):
            risk_id = item.get('id', index)
            risk_text = str(item.get('name') or item.get('content') or '').strip()
            node_name = str(item.get('node_name') or f'风险{index}').strip()
            source_tables_text = str(item.get('source_tables_text') or '').strip()

            basic_detail = {
                '风险分类': category_name,
                '风险名称': risk_text or node_name,
                '风险描述': str(item.get('content') or risk_text or '').strip(),
            }
            if item.get('risk_level_text'):
                basic_detail['风险等级'] = item.get('risk_level_text')
            if item.get('trigger_count') not in (None, '', 'null'):
                basic_detail['触发记录数'] = item.get('trigger_count')
            if item.get('basic_extras') and isinstance(item.get('basic_extras'), dict):
                basic_detail.update({k: v for k, v in item.get('basic_extras', {}).items() if v not in (None, '', 'null')})

            dynamic_detail: Dict[str, Any] = {}
            if source_tables_text:
                dynamic_detail['来源表'] = source_tables_text
            if item.get('classify_id'):
                dynamic_detail['风险分类编号'] = str(item.get('classify_id'))
            if item.get('stat_note'):
                dynamic_detail['说明'] = str(item.get('stat_note'))
            if item.get('dynamic_extras') and isinstance(item.get('dynamic_extras'), dict):
                dynamic_detail.update({k: v for k, v in item.get('dynamic_extras', {}).items() if v not in (None, '', 'null')})

            nodes.append(
                self._node(
                    node_id=f'3_{category_key}_{risk_id}',
                    name=node_name,
                    node_type='3_RISK_ITEM',
                    category='dynamic',
                    level=3,
                    side='left',
                    parent_id=f'2_{category_key}',
                    identity_key=f'RISK_ITEM:{category_key}:{risk_id}',
                    fixed=False,
                    summary=str(item.get('summary') or risk_text or node_name or '风险项'),
                    detail=self._detail(
                        basic=basic_detail,
                        dynamic=dynamic_detail,
                        description='风险叶子节点展示按明细规则逐条计算后的触发结果。',
                    ),
                    children=[],
                    expandable=False,
                    leaf=True,
                )
            )
        return nodes


class RiskRepositoryMixin:

    _RISK_LEVEL_TEXT_MAP = {
        8000: '危险',
        7000: '紧急',
        6000: '潜在风险',
        5000: '观察预警',
        4000: '注意',
    }

    _DECLARATION_KEYWORDS = ('申报', '备查', '加计', '扣除', '高企', '高新', '研发支出')

    def _risk_type_name(self, risk_type: Any) -> str:
        numeric = self._to_int(risk_type)
        mapping = {
            1000: '人事风险',
            3000: '财务风险',
            5000: '申报风险',
            9000: '研发风险',
        }
        if numeric in mapping:
            return mapping[numeric]

        text = self._stringify(risk_type).strip()
        if not text:
            return ''
        if '研发' in text:
            return '研发风险'
        if '人事' in text:
            return '人事风险'
        if '财务' in text:
            return '财务风险'
        if '申报' in text:
            return '申报风险'
        return text

    def _risk_level_text(self, risk_level: Any) -> str:
        numeric = self._to_int(risk_level)
        if numeric in self._RISK_LEVEL_TEXT_MAP:
            return self._RISK_LEVEL_TEXT_MAP[numeric]
        text = self._stringify(risk_level).strip()
        return text if text != '0' else ''

    def _risk_sort_key(self, item: Dict[str, Any]) -> Tuple[int, int, str]:
        index_sort = self._to_int(item.get('index_sort'))
        classify_id = self._to_int(item.get('classify_id') or item.get('id'))
        risk_name = self._stringify(item.get('name'))
        return (
            index_sort if index_sort > 0 else 10 ** 9,
            classify_id if classify_id > 0 else 10 ** 9,
            risk_name,
        )

    def _risk_has_table(self, conn, table_name: str) -> bool:
        checker = getattr(self, '_table_exists', None)
        if not callable(checker):
            return True
        try:
            return bool(checker(conn, table_name))
        except Exception:
            return False

    def _extract_row_date(self, dt_value: Any, year_value: Any = None, month_value: Any = None, day_value: Any = None) -> Optional[date]:
        normalized = self._normalize_date(dt_value)
        if normalized is not None:
            return normalized

        year_int = self._to_int(year_value)
        month_int = self._to_int(month_value)
        day_int = self._to_int(day_value) or 1
        if year_int <= 0 or month_int <= 0:
            return None

        day_int = max(day_int, 1)
        while day_int > 28:
            try:
                return date(year_int, month_int, day_int)
            except ValueError:
                day_int -= 1
        try:
            return date(year_int, month_int, day_int)
        except ValueError:
            return None

    def _date_in_year(self, dt_value: Any, year_value: Any, target_year: int) -> bool:
        normalized = self._normalize_date(dt_value)
        if normalized is not None:
            return normalized.year == target_year
        return self._to_int(year_value) == target_year

    def _split_multi_ids(self, raw_value: Any) -> List[str]:
        text = self._stringify(raw_value).strip()
        if not text:
            return []
        parts = re.split(r'[\s,，;；、|/]+', text)
        cleaned: List[str] = []
        for part in parts:
            token = part.strip()
            if not token or token.lower() == 'null' or token == '0':
                continue
            cleaned.append(token)
        return cleaned

    def _staff_active_in_year(self, entry_value: Any, resign_value: Any, target_year: int) -> bool:
        year_start, next_year_start = self._year_range(target_year)
        entry_date = self._normalize_date(entry_value)
        resign_date = self._normalize_date(resign_value)
        if entry_date is not None and entry_date >= next_year_start:
            return False
        if resign_date is not None and resign_date < year_start:
            return False
        return True

    def _week_key(self, dt: date) -> str:
        iso_year, iso_week, _ = dt.isocalendar()
        return f'{iso_year}-W{iso_week:02d}'

    def _has_consecutive_days(self, day_to_hours: Dict[date, float], threshold: float, days_required: int) -> bool:
        candidate_days = sorted([d for d, h in day_to_hours.items() if self._to_float(h) >= threshold])
        if len(candidate_days) < days_required:
            return False

        streak = 1
        for idx in range(1, len(candidate_days)):
            if (candidate_days[idx] - candidate_days[idx - 1]).days == 1:
                streak += 1
                if streak >= days_required:
                    return True
            else:
                streak = 1
        return False

    def _format_percent(self, numerator: float, denominator: float) -> str:
        if denominator <= 0:
            return '0.00%'
        return f'{round(numerator / denominator * 100, 2):.2f}%'

    def _first_n_join(self, values: Sequence[str], limit: int = 3) -> str:
        filtered = [self._stringify(v).strip() for v in values if self._stringify(v).strip()]
        return '、'.join(filtered[:limit])

    def _safe_staff_name(self, staff_map: Dict[str, Dict[str, Any]], staff_id: str) -> str:
        staff = staff_map.get(self._stringify(staff_id), {})
        name = self._stringify(staff.get('name')).strip()
        if name:
            return name
        return f'员工#{self._stringify(staff_id)}'

    def _load_risk_classify_map(self, conn) -> Tuple[Dict[int, Dict[str, Any]], List[str]]:
        if not self._risk_has_table(conn, 'T_RISK_CLASSIFY'):
            return {}, ['T_RISK_CLASSIFY 不存在，风险分类元数据将使用代码内置规则。']

        sql = """
            SELECT
                c.`ID`,
                c.`RISK_TYPE`,
                c.`CONTENT`,
                c.`INDEX_SORT`,
                c.`RISK_LEVEL`,
                c.`ENABLE_STATUS`
            FROM `T_RISK_CLASSIFY` c
        """
        rows = self._safe_rows(conn, sql)

        classify_map: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            classify_id = self._to_int(row[0])
            if classify_id <= 0:
                continue

            if self._to_int(row[5]) == 7777:
                continue

            content = self._stringify(row[2]).strip()
            classify_map[classify_id] = {
                'id': classify_id,
                'risk_type': row[1],
                'risk_type_name': self._risk_type_name(row[1]),
                'content': content,
                'index_sort': self._to_int(row[3]),
                'risk_level': row[4],
                'risk_level_text': self._risk_level_text(row[4]),
            }

        analysis: List[str] = []
        if not classify_map:
            analysis.append('T_RISK_CLASSIFY 没有可用启用状态的风险分类记录，将使用内置规则名称与级别。')
        return classify_map, analysis

    def _collect_staff_context(self, conn, tenant_id: str, year: int) -> Tuple[Dict[str, Any], List[str]]:
        notes: List[str] = []
        context: Dict[str, Any] = {
            'available': False,
            'staff_map': {},
            'active_staff_ids': set(),
            'formal_staff_ids': set(),
            'external_staff_ids': set(),
            'low_education_staff_ids': set(),
            'aux_or_manager_staff_ids': set(),
            'missing_entry_staff_ids': set(),
        }

        if not self._risk_has_table(conn, 'T_STAFF'):
            notes.append('规则依赖表 T_STAFF 不存在，人事类比例规则无法计算。')
            return context, notes

        type_value_name: Dict[int, str] = {}
        if self._risk_has_table(conn, 'T_TYPE'):
            type_rows = self._safe_rows(
                conn,
                """
                SELECT `TYPE_VALUE`, `TYPE_NAME`, `PARENT_TYPE_CODE`, `TYPE_CODE`
                FROM `T_TYPE`
                WHERE (`ENABLE_STATUS` IS NULL OR `ENABLE_STATUS` <> 7777)
                """,
            )
            for row in type_rows:
                value_int = self._to_int(row[0])
                if value_int <= 0:
                    continue
                type_name = self._stringify(row[1]).strip()
                if not type_name:
                    continue
                # 同一个 TYPE_VALUE 可能跨字典复用，优先保留首个非空中文名称
                type_value_name.setdefault(value_int, type_name)

        rows = self._safe_rows(
            conn,
            """
            SELECT
                s.`ID`,
                s.`FULL_NAME`,
                s.`EMPLOYMENT_METHOD`,
                s.`EDUCATIONAL_BACKGROUND`,
                s.`ENTRY_TIME`,
                s.`RESIGN_TIME`,
                s.`CATEGORY`,
                s.`EXIST_WORK_STATUS`
            FROM `T_STAFF` s
            WHERE s.`TENANT_ID` = %s
              AND (s.`ENABLE_STATUS` IS NULL OR s.`ENABLE_STATUS` <> 7777)
            """,
            (tenant_id,),
        )

        staff_map: Dict[str, Dict[str, Any]] = {}
        active_staff_ids: Set[str] = set()
        formal_staff_ids: Set[str] = set()
        external_staff_ids: Set[str] = set()
        low_education_staff_ids: Set[str] = set()
        aux_or_manager_staff_ids: Set[str] = set()
        missing_entry_staff_ids: Set[str] = set()

        for row in rows:
            staff_id = self._stringify(row[0]).strip()
            if not staff_id:
                continue

            full_name = self._stringify(row[1]).strip() or f'员工_{staff_id}'
            employment_method = self._to_int(row[2])
            education_raw = row[3]
            entry_time = row[4]
            resign_time = row[5]
            category_raw = row[6]
            exist_work_status = self._to_int(row[7])

            education_int = self._to_int(education_raw)
            category_int = self._to_int(category_raw)
            education_name = type_value_name.get(education_int, self._stringify(education_raw))
            category_name = type_value_name.get(category_int, self._stringify(category_raw))

            is_active = self._staff_active_in_year(entry_time, resign_time, year)
            if exist_work_status == 7777:
                is_active = False

            if is_active:
                active_staff_ids.add(staff_id)
                if employment_method == 100:
                    formal_staff_ids.add(staff_id)
                if entry_time in (None, '', 'null'):
                    missing_entry_staff_ids.add(staff_id)

            if employment_method in (200, 300):
                external_staff_ids.add(staff_id)

            education_text = self._stringify(education_name).strip()
            if education_text:
                if any(token in education_text for token in ('高中', '中专', '中技', '职高', '初中', '小学', '以下')):
                    low_education_staff_ids.add(staff_id)
            elif education_int in (100, 200, 300, 400):
                low_education_staff_ids.add(staff_id)

            category_text = self._stringify(category_name).strip()
            if category_text and any(token in category_text for token in ('辅助', '管理')):
                aux_or_manager_staff_ids.add(staff_id)

            staff_map[staff_id] = {
                'id': staff_id,
                'name': full_name,
                'employment_method': employment_method,
                'education': education_raw,
                'education_name': education_name,
                'entry_time': entry_time,
                'resign_time': resign_time,
                'category': category_raw,
                'category_name': category_name,
                'active': is_active,
            }

        context.update(
            {
                'available': True,
                'staff_map': staff_map,
                'active_staff_ids': active_staff_ids,
                'formal_staff_ids': formal_staff_ids,
                'external_staff_ids': external_staff_ids,
                'low_education_staff_ids': low_education_staff_ids,
                'aux_or_manager_staff_ids': aux_or_manager_staff_ids,
                'missing_entry_staff_ids': missing_entry_staff_ids,
            }
        )
        return context, notes

    def _collect_rd_time_context(self, conn, tenant_id: str, year: int) -> Tuple[Dict[str, Any], List[str]]:
        notes: List[str] = []
        context: Dict[str, Any] = {
            'available': False,
            'source_table': 'T_PROJECT_USER_R_D_TIME',
            'daily_hours_by_staff': defaultdict(lambda: defaultdict(float)),
            'weekly_hours_by_staff': defaultdict(lambda: defaultdict(float)),
            'weekly_project_ids_by_staff': defaultdict(lambda: defaultdict(set)),
            'rd_staff_ids': set(),
            'rd_hours_by_staff': defaultdict(float),
            'project_ids_by_staff': defaultdict(set),
        }

        table_name = 'T_PROJECT_USER_R_D_TIME'
        if not self._risk_has_table(conn, table_name):
            notes.append(f'规则依赖表 {table_name} 不存在，研发工时相关规则无法计算。')
            return context, notes

        rows = self._safe_rows(
            conn,
            """
            SELECT
                t.`STAFF_ID`,
                t.`PROJECT_ID`,
                t.`DATE`,
                t.`YEARS`,
                t.`MONTHS`,
                t.`DAYS`,
                t.`R_D_HOUR`
            FROM `T_PROJECT_USER_R_D_TIME` t
            WHERE t.`TENANT_ID` = %s
              AND (t.`ENABLE_STATUS` IS NULL OR t.`ENABLE_STATUS` <> 7777)
            """,
            (tenant_id,),
        )

        daily_hours_by_staff = defaultdict(lambda: defaultdict(float))
        weekly_hours_by_staff = defaultdict(lambda: defaultdict(float))
        weekly_project_ids_by_staff = defaultdict(lambda: defaultdict(set))
        rd_staff_ids: Set[str] = set()
        rd_hours_by_staff = defaultdict(float)
        project_ids_by_staff = defaultdict(set)

        for row in rows:
            staff_id = self._stringify(row[0]).strip()
            project_id = self._stringify(row[1]).strip()
            rd_hour = self._to_float(row[6])
            if not staff_id or rd_hour <= 0:
                continue

            if not self._date_in_year(row[2], row[3], year):
                continue

            row_date = self._extract_row_date(row[2], row[3], row[4], row[5])
            rd_staff_ids.add(staff_id)
            rd_hours_by_staff[staff_id] += rd_hour
            if project_id:
                project_ids_by_staff[staff_id].add(project_id)

            if row_date is not None:
                daily_hours_by_staff[staff_id][row_date] += rd_hour
                week_key = self._week_key(row_date)
                weekly_hours_by_staff[staff_id][week_key] += rd_hour
                if project_id:
                    weekly_project_ids_by_staff[staff_id][week_key].add(project_id)

        context.update(
            {
                'available': True,
                'daily_hours_by_staff': daily_hours_by_staff,
                'weekly_hours_by_staff': weekly_hours_by_staff,
                'weekly_project_ids_by_staff': weekly_project_ids_by_staff,
                'rd_staff_ids': rd_staff_ids,
                'rd_hours_by_staff': rd_hours_by_staff,
                'project_ids_by_staff': project_ids_by_staff,
            }
        )
        return context, notes

    def _collect_attendance_context(self, conn, tenant_id: str, year: int) -> Tuple[Dict[str, Any], List[str]]:
        notes: List[str] = []
        context: Dict[str, Any] = {
            'available': False,
            'source_table': 'T_ATTENDANCE_GROUP_USER_CLASSES',
            'daily_hours_by_staff': defaultdict(lambda: defaultdict(float)),
            'weekly_hours_by_staff': defaultdict(lambda: defaultdict(float)),
            'rd_daily_hours_by_staff': defaultdict(lambda: defaultdict(float)),
            'rd_weekly_hours_by_staff': defaultdict(lambda: defaultdict(float)),
        }

        table_name = 'T_ATTENDANCE_GROUP_USER_CLASSES'
        if not self._risk_has_table(conn, table_name):
            notes.append(f'规则依赖表 {table_name} 不存在，考勤工时相关规则无法计算。')
            return context, notes

        rows = self._safe_rows(
            conn,
            """
            SELECT
                c.`STAFF_ID`,
                c.`DATE`,
                c.`YEARS`,
                c.`MONTHS`,
                c.`DAYS`,
                c.`ATTENDANCE_HOUR`,
                c.`R_D_TOTAL_HOUR`
            FROM `T_ATTENDANCE_GROUP_USER_CLASSES` c
            WHERE c.`TENANT_ID` = %s
              AND (c.`ENABLE_STATUS` IS NULL OR c.`ENABLE_STATUS` <> 7777)
            """,
            (tenant_id,),
        )

        daily_hours_by_staff = defaultdict(lambda: defaultdict(float))
        weekly_hours_by_staff = defaultdict(lambda: defaultdict(float))
        rd_daily_hours_by_staff = defaultdict(lambda: defaultdict(float))
        rd_weekly_hours_by_staff = defaultdict(lambda: defaultdict(float))

        for row in rows:
            staff_id = self._stringify(row[0]).strip()
            attendance_hour = self._to_float(row[5])
            rd_hour = self._to_float(row[6])
            if not staff_id or (attendance_hour <= 0 and rd_hour <= 0):
                continue

            if not self._date_in_year(row[1], row[2], year):
                continue

            row_date = self._extract_row_date(row[1], row[2], row[3], row[4])
            if row_date is None:
                continue

            week_key = self._week_key(row_date)
            if attendance_hour > 0:
                daily_hours_by_staff[staff_id][row_date] += attendance_hour
                weekly_hours_by_staff[staff_id][week_key] += attendance_hour
            if rd_hour > 0:
                rd_daily_hours_by_staff[staff_id][row_date] += rd_hour
                rd_weekly_hours_by_staff[staff_id][week_key] += rd_hour

        context.update(
            {
                'available': True,
                'daily_hours_by_staff': daily_hours_by_staff,
                'weekly_hours_by_staff': weekly_hours_by_staff,
                'rd_daily_hours_by_staff': rd_daily_hours_by_staff,
                'rd_weekly_hours_by_staff': rd_weekly_hours_by_staff,
            }
        )
        return context, notes

    def _collect_wage_context(self, conn, tenant_id: str, year: int) -> Tuple[Dict[str, Any], List[str]]:
        notes: List[str] = []
        context: Dict[str, Any] = {
            'available': False,
            'source_table': 'T_STAFF_WAGE',
            'wage_total_by_staff': defaultdict(float),
            'wage_staff_ids': set(),
            'total_wage_amount': 0.0,
        }

        table_name = 'T_STAFF_WAGE'
        if not self._risk_has_table(conn, table_name):
            notes.append(f'规则依赖表 {table_name} 不存在，工资相关规则无法计算。')
            return context, notes

        rows = self._safe_rows(
            conn,
            """
            SELECT
                w.`STAFF_ID`,
                w.`WAGE_TIME`,
                w.`YEAR`,
                w.`MONTH`,
                w.`WAGE`,
                w.`HOUSING_PROVIDENT_FUND`,
                w.`FIVE_INSURANCE_AMOUNT`,
                w.`BONUS`,
                w.`STAFF_WAGE_BENEFIT_VAL`,
                w.`SHAREHOLDING_MOTIVATE_BENEFIT_AMOUNT`,
                w.`SUPPLEMENT_AMOUNT`
            FROM `T_STAFF_WAGE` w
            WHERE w.`TENANT_ID` = %s
              AND (w.`ENABLE_STATUS` IS NULL OR w.`ENABLE_STATUS` <> 7777)
            """,
            (tenant_id,),
        )

        wage_total_by_staff = defaultdict(float)
        wage_staff_ids: Set[str] = set()
        total_wage_amount = 0.0

        for row in rows:
            staff_id = self._stringify(row[0]).strip()
            if not staff_id:
                continue
            if not self._date_in_year(row[1], row[2], year):
                continue

            wage_amount = (
                self._to_float(row[4])
                + self._to_float(row[5])
                + self._to_float(row[6])
                + self._to_float(row[7])
                + self._to_float(row[8])
                + self._to_float(row[9])
                + self._to_float(row[10])
            )
            if wage_amount <= 0:
                continue

            wage_total_by_staff[staff_id] += wage_amount
            wage_staff_ids.add(staff_id)
            total_wage_amount += wage_amount

        context.update(
            {
                'available': True,
                'wage_total_by_staff': wage_total_by_staff,
                'wage_staff_ids': wage_staff_ids,
                'total_wage_amount': round(total_wage_amount, 2),
            }
        )
        return context, notes

    def _collect_cost_context(self, conn, tenant_id: str, year: int) -> Tuple[Dict[str, Any], List[str]]:
        notes: List[str] = []
        context: Dict[str, Any] = {
            'available': False,
            'source_tables': [],
            'rd_voucher_amount': 0.0,
            'additional_deduction_amount': 0.0,
            'personnel_amount': 0.0,
            'direct_investment_amount': 0.0,
            'total_rd_expense_amount': 0.0,
            'entrust_external_amount': 0.0,
        }

        source_tables: List[str] = []

        if self._risk_has_table(conn, 'T_COST_MANAGE_COST_SECOND'):
            row = self._safe_one(
                conn,
                """
                SELECT
                    COALESCE(SUM(COALESCE(c.`R_D_VOUCHER_AMOUNT`, 0)), 0) AS rd_voucher_amount,
                    COALESCE(SUM(COALESCE(c.`R_D_ADDITIONAL_DEDUCTION_AMOUNT`, 0)), 0) AS additional_deduction_amount
                FROM `T_COST_MANAGE_COST_SECOND` c
                WHERE c.`TENANT_ID` = %s
                  AND c.`YEARS` = %s
                """,
                (tenant_id, year),
            )
            if row is not None:
                context['rd_voucher_amount'] = round(self._to_float(row[0]), 2)
                context['additional_deduction_amount'] = round(self._to_float(row[1]), 2)
            source_tables.append('T_COST_MANAGE_COST_SECOND')
        else:
            notes.append('T_COST_MANAGE_COST_SECOND 不存在，研发凭证总额/加计扣除总额部分规则将无法准确计算。')

        cost_detail_table = ''
        if self._risk_has_table(conn, 'T_HD_COST_STRUCTURE_DETAILS_YEARS'):
            cost_detail_table = 'T_HD_COST_STRUCTURE_DETAILS_YEARS'
            row = self._safe_one(
                conn,
                """
                SELECT
                    COALESCE(SUM(COALESCE(h.`PERSONNEL_AND_LABOR_AMOUNT`, 0)), 0),
                    COALESCE(SUM(COALESCE(h.`DIRECT_INVESTMENT_AMOUNT`, 0)), 0),
                    COALESCE(SUM(COALESCE(h.`TOTAL_AMOUNT`, 0)), 0),
                    COALESCE(SUM(COALESCE(h.`ENTRUSTING_OTHER_EXPENSES_EXTERNAL`, 0)), 0),
                    COALESCE(SUM(COALESCE(h.`ENTRUSTING_OTHER_EXPENSES_EXTERNAL_DOMESTIC`, 0)), 0)
                FROM `T_HD_COST_STRUCTURE_DETAILS_YEARS` h
                WHERE h.`TENANT_ID` = %s
                  AND h.`YEARS` = %s
                """,
                (tenant_id, year),
            )
            if row is not None:
                context['personnel_amount'] = round(self._to_float(row[0]), 2)
                context['direct_investment_amount'] = round(self._to_float(row[1]), 2)
                context['total_rd_expense_amount'] = round(self._to_float(row[2]), 2)
                context['entrust_external_amount'] = round(self._to_float(row[3]) + self._to_float(row[4]), 2)
        elif self._risk_has_table(conn, 'T_HD_COST_STRUCTURE_DETAILS'):
            cost_detail_table = 'T_HD_COST_STRUCTURE_DETAILS'
            row = self._safe_one(
                conn,
                """
                SELECT
                    COALESCE(SUM(COALESCE(h.`PERSONNEL_AND_LABOR_AMOUNT`, 0)), 0),
                    COALESCE(SUM(COALESCE(h.`DIRECT_INVESTMENT_AMOUNT`, 0)), 0),
                    COALESCE(SUM(COALESCE(h.`TOTAL_AMOUNT`, 0)), 0),
                    COALESCE(SUM(COALESCE(h.`ENTRUSTING_OTHER_EXPENSES_EXTERNAL`, 0)), 0),
                    COALESCE(SUM(COALESCE(h.`ENTRUSTING_OTHER_EXPENSES_EXTERNAL_DOMESTIC`, 0)), 0)
                FROM `T_HD_COST_STRUCTURE_DETAILS` h
                WHERE h.`TENANT_ID` = %s
                  AND h.`YEARS` = %s
                """,
                (tenant_id, year),
            )
            if row is not None:
                context['personnel_amount'] = round(self._to_float(row[0]), 2)
                context['direct_investment_amount'] = round(self._to_float(row[1]), 2)
                context['total_rd_expense_amount'] = round(self._to_float(row[2]), 2)
                context['entrust_external_amount'] = round(self._to_float(row[3]) + self._to_float(row[4]), 2)
        else:
            notes.append('T_HD_COST_STRUCTURE_DETAILS_YEARS/T_HD_COST_STRUCTURE_DETAILS 均不存在，部分财务比例规则无法计算。')

        if cost_detail_table:
            source_tables.append(cost_detail_table)

        context['source_tables'] = source_tables
        context['available'] = bool(source_tables)
        return context, notes

    def _collect_voucher_lock_context(self, conn, tenant_id: str, year: int) -> Tuple[Dict[str, Any], List[str]]:
        notes: List[str] = []
        context: Dict[str, Any] = {
            'available': False,
            'source_tables': [],
            'months_with_amount': set(),
            'locked_months': set(),
            'unlocked_months': set(),
        }

        months_with_amount: Set[int] = set()
        locked_months: Set[int] = set()
        source_tables: List[str] = []

        if self._risk_has_table(conn, 'T_VOUCHER'):
            rows = self._safe_rows(
                conn,
                """
                SELECT
                    COALESCE(v.`VOUCHER_MONTH`, MONTH(v.`VOUCHER_DATE`)) AS voucher_month,
                    SUM(COALESCE(v.`DETAILS_AMOUNT`, COALESCE(v.`VOUCHER_AMOUNT`, 0))) AS month_amount,
                    MAX(COALESCE(v.`LOCK_STATUS`, 0)) AS month_lock_status
                FROM `T_VOUCHER` v
                WHERE v.`TENANT_ID` = %s
                  AND (
                      v.`VOUCHER_YEAR` = %s
                      OR (v.`VOUCHER_DATE` IS NOT NULL AND YEAR(v.`VOUCHER_DATE`) = %s)
                  )
                GROUP BY COALESCE(v.`VOUCHER_MONTH`, MONTH(v.`VOUCHER_DATE`))
                """,
                (tenant_id, year, year),
            )
            for row in rows:
                month = self._to_int(row[0])
                amount = self._to_float(row[1])
                lock_status = self._to_int(row[2])
                if 1 <= month <= 12 and amount > 0:
                    months_with_amount.add(month)
                if 1 <= month <= 12 and lock_status == 9999:
                    locked_months.add(month)
            source_tables.append('T_VOUCHER')
        else:
            notes.append('T_VOUCHER 不存在，锁账相关风险无法计算。')

        if self._risk_has_table(conn, 'T_VOUCHER_LOCK'):
            rows = self._safe_rows(
                conn,
                """
                SELECT DISTINCT COALESCE(l.`VOUCHER_MONTH`, MONTH(l.`VOUCHER_DATE`)) AS voucher_month
                FROM `T_VOUCHER_LOCK` l
                WHERE l.`TENANT_ID` = %s
                  AND (
                      l.`VOUCHER_YEAR` = %s
                      OR (l.`VOUCHER_DATE` IS NOT NULL AND YEAR(l.`VOUCHER_DATE`) = %s)
                  )
                  AND COALESCE(l.`LOCK_STATUS`, 0) = 9999
                """,
                (tenant_id, year, year),
            )
            for row in rows:
                month = self._to_int(row[0])
                if 1 <= month <= 12:
                    locked_months.add(month)
            source_tables.append('T_VOUCHER_LOCK')

        unlocked_months = {m for m in months_with_amount if m not in locked_months}
        context.update(
            {
                'available': bool(source_tables),
                'source_tables': source_tables,
                'months_with_amount': months_with_amount,
                'locked_months': locked_months,
                'unlocked_months': unlocked_months,
            }
        )
        return context, notes

    def _collect_project_context(self, conn, tenant_id: str, year: int) -> Tuple[Dict[str, Any], List[str]]:
        notes: List[str] = []
        context: Dict[str, Any] = {
            'available': False,
            'source_tables': [],
            'projects': [],
            'project_cost_map': {},
            'results_projects': set(),
            'acceptance_projects': set(),
            'search_projects': set(),
            'demonstration_projects': set(),
            'research_projects': set(),
        }

        if not self._risk_has_table(conn, 'T_PROJECT'):
            notes.append('T_PROJECT 不存在，项目类风险无法计算。')
            return context, notes

        project_rows = self._safe_rows(
            conn,
            """
            SELECT
                p.`ID`,
                p.`PROJECT_NAME`,
                p.`GENERAL_BUDGET`,
                p.`APPLY_FOR_DATE`,
                p.`START_DATE`,
                p.`END_DATE`,
                p.`APPLY_FOR_USER_IDS`,
                p.`PROJECT_MANAGER_IDS`,
                p.`EXPERT_OPINION_ID`,
                p.`SCIENCE_CONTRACT_ID`
            FROM `T_PROJECT` p
            WHERE p.`TENANT_ID` = %s
              AND (p.`ENABLE_STATUS` IS NULL OR p.`ENABLE_STATUS` <> 7777)
            """,
            (tenant_id,),
        )

        projects: List[Dict[str, Any]] = []
        year_start, next_year_start = self._year_range(year)

        for row in project_rows:
            project_id = self._stringify(row[0]).strip()
            if not project_id:
                continue

            start_date = self._normalize_date(row[4])
            end_date = self._normalize_date(row[5])
            apply_for_date = self._normalize_date(row[3])

            overlap = True
            if start_date is not None and start_date >= next_year_start:
                overlap = False
            if end_date is not None and end_date < year_start:
                overlap = False

            projects.append(
                {
                    'id': project_id,
                    'name': self._stringify(row[1]).strip() or f'项目_{project_id}',
                    'general_budget': self._to_float(row[2]),
                    'apply_for_date': apply_for_date,
                    'start_date': start_date,
                    'end_date': end_date,
                    'apply_user_ids': self._split_multi_ids(row[6]),
                    'manager_ids': self._split_multi_ids(row[7]),
                    'expert_opinion_id': self._stringify(row[8]).strip(),
                    'science_contract_id': self._stringify(row[9]).strip(),
                    'overlap_year': overlap,
                }
            )

        project_cost_map: Dict[str, float] = {}
        if self._risk_has_table(conn, 'T_COST_MANAGE_COST_PROJECT_SECOND'):
            cost_rows = self._safe_rows(
                conn,
                """
                SELECT
                    c.`PROJECT_ID`,
                    SUM(COALESCE(c.`R_D_VOUCHER_AMOUNT`, 0)) AS total_amount
                FROM `T_COST_MANAGE_COST_PROJECT_SECOND` c
                WHERE c.`TENANT_ID` = %s
                  AND c.`YEARS` = %s
                GROUP BY c.`PROJECT_ID`
                """,
                (tenant_id, year),
            )
            for row in cost_rows:
                project_id = self._stringify(row[0]).strip()
                if not project_id:
                    continue
                project_cost_map[project_id] = self._to_float(row[1])

        def distinct_project_set(table_name: str, where_clause: str = '', params: Sequence[Any] = ()) -> Set[str]:
            if not self._risk_has_table(conn, table_name):
                return set()
            sql = f"SELECT DISTINCT t.`PROJECT_ID` FROM `{table_name}` t WHERE t.`TENANT_ID` = %s"
            all_params: List[Any] = [tenant_id]
            if where_clause:
                sql += f" AND {where_clause}"
                all_params.extend(list(params))
            rows = self._safe_rows(conn, sql, tuple(all_params))
            return {self._stringify(row[0]).strip() for row in rows if self._stringify(row[0]).strip()}

        results_projects = distinct_project_set('T_PROJECT_RESULTS')
        acceptance_projects = distinct_project_set('T_PROJECT_ACCEPTANCE', 'COALESCE(t.`TYPE`, 0) = 200')
        search_projects = distinct_project_set('T_PROJECT_SEARCH')
        demonstration_projects = distinct_project_set('T_PROJECT_DEMONSTRATION')
        research_projects = distinct_project_set('T_PROJECT_RESEARCH')

        source_tables = ['T_PROJECT']
        if self._risk_has_table(conn, 'T_COST_MANAGE_COST_PROJECT_SECOND'):
            source_tables.append('T_COST_MANAGE_COST_PROJECT_SECOND')
        for table_name in ('T_PROJECT_RESULTS', 'T_PROJECT_ACCEPTANCE', 'T_PROJECT_SEARCH', 'T_PROJECT_DEMONSTRATION', 'T_PROJECT_RESEARCH'):
            if self._risk_has_table(conn, table_name):
                source_tables.append(table_name)

        context.update(
            {
                'available': True,
                'source_tables': source_tables,
                'projects': projects,
                'project_cost_map': project_cost_map,
                'results_projects': results_projects,
                'acceptance_projects': acceptance_projects,
                'search_projects': search_projects,
                'demonstration_projects': demonstration_projects,
                'research_projects': research_projects,
            }
        )
        return context, notes

    def _collect_declaration_month_context(self, conn, tenant_id: str, year: int) -> Tuple[Dict[str, Any], List[str]]:
        notes: List[str] = []
        context: Dict[str, Any] = {
            'available': False,
            'source_tables': [],
            'declaration_months': set(),
        }

        if not self._risk_has_table(conn, 'T_ANNEX'):
            notes.append('T_ANNEX 不存在，申报/备查文件月份缺失风险无法计算。')
            return context, notes

        year_start, next_year_start = self._year_range(year)
        keyword_clauses: List[str] = []
        params: List[Any] = [tenant_id, year_start, next_year_start]
        for keyword in self._DECLARATION_KEYWORDS:
            cleaned = self._stringify(keyword).strip()
            if not cleaned:
                continue
            keyword_clauses.append(
                "("
                "COALESCE(a.`OLD_NAME`, '') LIKE %s OR "
                "COALESCE(a.`NEW_NAME`, '') LIKE %s OR "
                "COALESCE(a.`DESCRIPTION`, '') LIKE %s OR "
                "COALESCE(a.`GROUP_CODE`, '') LIKE %s OR "
                "COALESCE(g.`NAME`, '') LIKE %s OR "
                "COALESCE(g.`CODE`, '') LIKE %s OR "
                "COALESCE(g.`DESCRIPTION`, '') LIKE %s"
                ")"
            )
            params.extend([f'%{cleaned}%'] * 7)

        if not keyword_clauses:
            notes.append('申报文件关键词为空，无法计算申报文件月份缺失风险。')
            return context, notes

        sql = f"""
            SELECT DISTINCT MONTH(a.`CREATE_TIME`) AS file_month
            FROM `T_ANNEX` a
            LEFT JOIN `T_GROUP` g ON a.`GROUP_ID` = g.`ID`
            WHERE a.`TENANT_ID` = %s
              AND a.`CREATE_TIME` >= %s
              AND a.`CREATE_TIME` < %s
              AND (a.`RELATION_STATUS` IS NULL OR a.`RELATION_STATUS` <> 7777)
              AND (a.`ENABLE_STATUS` IS NULL OR a.`ENABLE_STATUS` <> 7777)
              AND ({' OR '.join(keyword_clauses)})
        """
        rows = self._safe_rows(conn, sql, tuple(params))
        declaration_months = {self._to_int(row[0]) for row in rows if 1 <= self._to_int(row[0]) <= 12}

        source_tables = ['T_ANNEX']
        if self._risk_has_table(conn, 'T_GROUP'):
            source_tables.append('T_GROUP')

        context.update(
            {
                'available': True,
                'source_tables': source_tables,
                'declaration_months': declaration_months,
            }
        )
        return context, notes

    def _collect_missing_subject_voucher_context(self, conn, tenant_id: str, year: int) -> Tuple[Dict[str, Any], List[str]]:
        notes: List[str] = []
        context: Dict[str, Any] = {
            'available': False,
            'source_tables': [],
            'rows': [],
        }

        if not self._risk_has_table(conn, 'T_COST_MANAGE_COST_SUBJECT_SECOND'):
            notes.append('T_COST_MANAGE_COST_SUBJECT_SECOND 不存在，2-3月未入账科目风险无法计算。')
            return context, notes

        has_subject_table = self._risk_has_table(conn, 'T_SUBJECT_CONFIG')
        join_sql = "LEFT JOIN `T_SUBJECT_CONFIG` sc ON sc.`ID` = s.`SUBJECT_CONFIG_ID`" if has_subject_table else ''
        subject_name_expr = "COALESCE(sc.`NAME`, CONCAT('科目#', s.`SUBJECT_CONFIG_ID`))" if has_subject_table else "CONCAT('科目#', s.`SUBJECT_CONFIG_ID`)"

        sql = f"""
            SELECT
                s.`MONTHS` AS stat_month,
                s.`SUBJECT_CONFIG_ID` AS subject_id,
                {subject_name_expr} AS subject_name,
                SUM(COALESCE(s.`ACCOUNTING_STANDARDS_AMOUNT`, 0)) AS accounting_amount,
                SUM(COALESCE(s.`R_D_VOUCHER_AMOUNT`, 0)) AS voucher_amount
            FROM `T_COST_MANAGE_COST_SUBJECT_SECOND` s
            {join_sql}
            WHERE s.`TENANT_ID` = %s
              AND s.`YEARS` = %s
              AND s.`MONTHS` IN (2, 3)
            GROUP BY s.`MONTHS`, s.`SUBJECT_CONFIG_ID`, subject_name
            HAVING SUM(COALESCE(s.`ACCOUNTING_STANDARDS_AMOUNT`, 0)) > 0
               AND SUM(COALESCE(s.`R_D_VOUCHER_AMOUNT`, 0)) <= 0
            ORDER BY s.`MONTHS` ASC, accounting_amount DESC, subject_name ASC
        """
        rows = self._safe_rows(conn, sql, (tenant_id, year))

        normalized_rows: List[Dict[str, Any]] = []
        for row in rows:
            month = self._to_int(row[0])
            subject_name = self._stringify(row[2]).strip()
            accounting_amount = round(self._to_float(row[3]), 2)
            normalized_rows.append(
                {
                    'month': month,
                    'subject_name': subject_name,
                    'accounting_amount': accounting_amount,
                }
            )

        source_tables = ['T_COST_MANAGE_COST_SUBJECT_SECOND']
        if has_subject_table:
            source_tables.append('T_SUBJECT_CONFIG')

        context.update(
            {
                'available': True,
                'source_tables': source_tables,
                'rows': normalized_rows,
            }
        )
        return context, notes

    def _match_classify(self, classify_map: Dict[int, Dict[str, Any]], risk_name: str) -> Optional[Dict[str, Any]]:
        if not classify_map:
            return None
        normalized_name = self._stringify(risk_name).replace('：', '').replace(' ', '').strip()
        if not normalized_name:
            return None

        best: Optional[Dict[str, Any]] = None
        best_score = -1
        for info in classify_map.values():
            content = self._stringify(info.get('content')).replace('：', '').replace(' ', '').strip()
            if not content:
                continue

            score = 0
            if content in normalized_name or normalized_name in content:
                score += 5
            overlap_tokens = [token for token in ('研发', '人事', '财务', '工时', '工资', '凭证', '预算', '项目', '锁账', '加计扣除') if token in normalized_name and token in content]
            score += len(overlap_tokens)

            if score > best_score:
                best_score = score
                best = info

        if best_score <= 0:
            return None
        return best

    def _build_detected_item(
        self,
        *,
        rule_no: int,
        category_name: str,
        rule_name: str,
        risk_level: int,
        trigger_count: int,
        formula: str,
        source_tables: Sequence[str],
        samples: Sequence[str] = (),
        basic_extras: Optional[Dict[str, Any]] = None,
        dynamic_extras: Optional[Dict[str, Any]] = None,
        classify_map: Optional[Dict[int, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        classify_info = self._match_classify(classify_map or {}, rule_name)

        level_value = risk_level
        level_text = self._risk_level_text(risk_level)
        classify_id = ''
        index_sort = rule_no
        if classify_info is not None:
            classify_id = self._stringify(classify_info.get('id'))
            index_sort = self._to_int(classify_info.get('index_sort')) or rule_no
            classify_level = self._to_int(classify_info.get('risk_level'))
            if classify_level > 0:
                level_value = classify_level
                level_text = self._risk_level_text(classify_level)

        sample_text = self._first_n_join(samples, limit=3)
        stat_note = formula
        if sample_text:
            stat_note = f'{formula}；样例：{sample_text}'

        return {
            'id': f'R{rule_no:02d}',
            'classify_id': classify_id,
            'name': rule_name,
            'content': rule_name,
            'index_sort': index_sort,
            'risk_level': level_value,
            'risk_level_text': level_text,
            'category_name': category_name,
            'trigger_count': self._to_int(trigger_count),
            'source_tables': sorted({self._stringify(v).strip() for v in source_tables if self._stringify(v).strip()}),
            'source_tables_text': '、'.join(sorted({self._stringify(v).strip() for v in source_tables if self._stringify(v).strip()})),
            'stat_note': stat_note,
            'summary': f'命中 {self._to_int(trigger_count)} 条',
            'basic_extras': basic_extras or {},
            'dynamic_extras': dynamic_extras or {},
        }

    def _build_risk_category_payload(
        self,
        category_name: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        sorted_items = sorted(items, key=self._risk_sort_key)
        top_text = [self._stringify(item.get('name')) for item in sorted_items[:3]]
        while len(top_text) < 3:
            top_text.append('')

        visible_items: List[Dict[str, Any]] = []
        for index, item in enumerate(sorted_items[:3], start=1):
            visible_item = dict(item)
            visible_item['node_name'] = self._stringify(item.get('name')) or f'风险{index}'
            visible_item['summary'] = self._stringify(item.get('name'))
            visible_items.append(visible_item)

        detail = {
            f'本年{category_name}点数量': len(sorted_items),
            '风险一': top_text[0],
            '风险二': top_text[1],
            '风险三': top_text[2],
        }
        detail_analysis: Dict[str, Any] = {
            '统计口径': '按风险明细规则逐条执行检测；每条规则命中后记为 1 个风险点。',
        }
        total_trigger_count = sum(self._to_int(item.get('trigger_count')) for item in sorted_items)
        if total_trigger_count:
            detail_analysis['触发明细记录数'] = total_trigger_count
        if not sorted_items:
            detail_analysis['说明'] = '本年未检测到该类风险。'

        return {
            'count': len(sorted_items),
            'summary': f'本年{category_name}：{len(sorted_items)}个',
            'detail': detail,
            'detail_analysis': detail_analysis,
            'detail_description': f'{category_name}按风险规则展示前 3 个已触发风险。',
            'items': visible_items,
        }

    def fetch_risk_domain(self, conn, tenant_id: str, year: int) -> Dict[str, Any]:
        classify_map, classify_analysis = self._load_risk_classify_map(conn)
        analysis_notes: List[str] = [note for note in classify_analysis if note]

        staff_ctx, staff_notes = self._collect_staff_context(conn, tenant_id, year)
        rd_ctx, rd_notes = self._collect_rd_time_context(conn, tenant_id, year)
        attendance_ctx, attendance_notes = self._collect_attendance_context(conn, tenant_id, year)
        wage_ctx, wage_notes = self._collect_wage_context(conn, tenant_id, year)
        cost_ctx, cost_notes = self._collect_cost_context(conn, tenant_id, year)
        voucher_lock_ctx, voucher_notes = self._collect_voucher_lock_context(conn, tenant_id, year)
        project_ctx, project_notes = self._collect_project_context(conn, tenant_id, year)
        declaration_ctx, declaration_notes = self._collect_declaration_month_context(conn, tenant_id, year)
        subject_gap_ctx, subject_gap_notes = self._collect_missing_subject_voucher_context(conn, tenant_id, year)

        for group in (staff_notes, rd_notes, attendance_notes, wage_notes, cost_notes, voucher_notes, project_notes, declaration_notes, subject_gap_notes):
            analysis_notes.extend([note for note in group if note])

        staff_map: Dict[str, Dict[str, Any]] = staff_ctx.get('staff_map', {}) or {}
        active_staff_ids: Set[str] = set(staff_ctx.get('active_staff_ids', set()) or set())
        formal_staff_ids: Set[str] = set(staff_ctx.get('formal_staff_ids', set()) or set())
        external_staff_ids: Set[str] = set(staff_ctx.get('external_staff_ids', set()) or set())
        low_education_staff_ids: Set[str] = set(staff_ctx.get('low_education_staff_ids', set()) or set())
        aux_or_manager_staff_ids: Set[str] = set(staff_ctx.get('aux_or_manager_staff_ids', set()) or set())
        missing_entry_staff_ids: Set[str] = set(staff_ctx.get('missing_entry_staff_ids', set()) or set())

        rd_staff_ids: Set[str] = set(rd_ctx.get('rd_staff_ids', set()) or set())
        rd_daily_hours_by_staff: Dict[str, Dict[date, float]] = rd_ctx.get('daily_hours_by_staff', {}) or {}
        rd_weekly_hours_by_staff: Dict[str, Dict[str, float]] = rd_ctx.get('weekly_hours_by_staff', {}) or {}
        rd_weekly_project_ids_by_staff: Dict[str, Dict[str, Set[str]]] = rd_ctx.get('weekly_project_ids_by_staff', {}) or {}

        attendance_daily_hours_by_staff: Dict[str, Dict[date, float]] = attendance_ctx.get('daily_hours_by_staff', {}) or {}
        attendance_weekly_hours_by_staff: Dict[str, Dict[str, float]] = attendance_ctx.get('weekly_hours_by_staff', {}) or {}
        attendance_rd_daily_hours_by_staff: Dict[str, Dict[date, float]] = attendance_ctx.get('rd_daily_hours_by_staff', {}) or {}
        attendance_rd_weekly_hours_by_staff: Dict[str, Dict[str, float]] = attendance_ctx.get('rd_weekly_hours_by_staff', {}) or {}

        wage_total_by_staff: Dict[str, float] = wage_ctx.get('wage_total_by_staff', {}) or {}
        wage_staff_ids: Set[str] = set(wage_ctx.get('wage_staff_ids', set()) or set())
        total_wage_amount = self._to_float(wage_ctx.get('total_wage_amount'))

        rd_voucher_amount = self._to_float(cost_ctx.get('rd_voucher_amount'))
        additional_deduction_amount = self._to_float(cost_ctx.get('additional_deduction_amount'))
        personnel_amount = self._to_float(cost_ctx.get('personnel_amount'))
        direct_investment_amount = self._to_float(cost_ctx.get('direct_investment_amount'))
        total_rd_expense_amount = self._to_float(cost_ctx.get('total_rd_expense_amount'))
        entrust_external_amount = self._to_float(cost_ctx.get('entrust_external_amount'))

        months_with_amount: Set[int] = set(voucher_lock_ctx.get('months_with_amount', set()) or set())
        locked_months: Set[int] = set(voucher_lock_ctx.get('locked_months', set()) or set())
        unlocked_months: Set[int] = set(voucher_lock_ctx.get('unlocked_months', set()) or set())
        declaration_months: Set[int] = set(declaration_ctx.get('declaration_months', set()) or set())

        projects: List[Dict[str, Any]] = list(project_ctx.get('projects', []) or [])
        project_cost_map: Dict[str, float] = dict(project_ctx.get('project_cost_map', {}) or {})
        results_projects: Set[str] = set(project_ctx.get('results_projects', set()) or set())
        acceptance_projects: Set[str] = set(project_ctx.get('acceptance_projects', set()) or set())
        search_projects: Set[str] = set(project_ctx.get('search_projects', set()) or set())
        demonstration_projects: Set[str] = set(project_ctx.get('demonstration_projects', set()) or set())
        research_projects: Set[str] = set(project_ctx.get('research_projects', set()) or set())

        missing_subject_rows: List[Dict[str, Any]] = list(subject_gap_ctx.get('rows', []) or [])

        detected_items: List[Dict[str, Any]] = []
        not_computable_rules: List[str] = []

        def append_rule(
            rule_no: int,
            category_name: str,
            level: int,
            rule_name: str,
            triggered: bool,
            trigger_count: int,
            formula: str,
            source_tables: Sequence[str],
            samples: Sequence[str] = (),
            basic_extras: Optional[Dict[str, Any]] = None,
            dynamic_extras: Optional[Dict[str, Any]] = None,
        ) -> None:
            if not triggered:
                return
            detected_items.append(
                self._build_detected_item(
                    rule_no=rule_no,
                    category_name=category_name,
                    rule_name=rule_name,
                    risk_level=level,
                    trigger_count=trigger_count,
                    formula=formula,
                    source_tables=source_tables,
                    samples=samples,
                    basic_extras=basic_extras,
                    dynamic_extras=dynamic_extras,
                    classify_map=classify_map,
                )
            )

        # R01 研发风险：连续 5 天研发工时 >= 12 小时
        if rd_ctx.get('available') or attendance_ctx.get('available'):
            rd_daily_source = attendance_rd_daily_hours_by_staff if attendance_rd_daily_hours_by_staff else rd_daily_hours_by_staff
            rd_source_tables_r01: List[str] = []
            if attendance_rd_daily_hours_by_staff:
                rd_source_tables_r01.append(attendance_ctx.get('source_table', 'T_ATTENDANCE_GROUP_USER_CLASSES'))
            elif rd_ctx.get('available'):
                rd_source_tables_r01.append(rd_ctx.get('source_table', 'T_PROJECT_USER_R_D_TIME'))
            violators_r01 = [
                staff_id
                for staff_id, day_map in rd_daily_source.items()
                if self._has_consecutive_days(day_map, threshold=12, days_required=5)
            ]
            append_rule(
                1,
                '研发风险',
                4000,
                '员工连续5天研发工时超过12小时',
                bool(violators_r01),
                len(violators_r01),
                '按考勤组人员考勤明细（R_D_TOTAL_HOUR）汇总到“员工-日期”，判断连续 5 天每日研发工时 >= 12 小时。',
                rd_source_tables_r01,
                [self._safe_staff_name(staff_map, sid) for sid in sorted(violators_r01)],
            )
        else:
            not_computable_rules.append('R01: 员工连续5天研发工时超过12小时')

        # R02 人事风险：连续 5 天考勤工时 >= 12 小时
        if attendance_ctx.get('available'):
            violators_r02 = [
                staff_id
                for staff_id, day_map in attendance_daily_hours_by_staff.items()
                if self._has_consecutive_days(day_map, threshold=12, days_required=5)
            ]
            append_rule(
                2,
                '人事风险',
                5000,
                '员工连续5天考勤工时超过12小时',
                bool(violators_r02),
                len(violators_r02),
                '按 T_ATTENDANCE_GROUP_USER_CLASSES 汇总到“员工-日期”，判断连续 5 天每日考勤工时 >= 12 小时。',
                [attendance_ctx.get('source_table', 'T_ATTENDANCE_GROUP_USER_CLASSES')],
                [self._safe_staff_name(staff_map, sid) for sid in sorted(violators_r02)],
            )
        else:
            not_computable_rules.append('R02: 员工连续5天考勤工时超过12小时')

        # R03 人事风险：有研发工时但无工资单
        if rd_ctx.get('available') and wage_ctx.get('available'):
            violators_r03 = sorted(list(rd_staff_ids - wage_staff_ids))
            append_rule(
                3,
                '人事风险',
                4000,
                '存在研发工时投入但未添加工资表单',
                bool(violators_r03),
                len(violators_r03),
                '按年度研发工时员工集合减去工资表员工集合。',
                [rd_ctx.get('source_table', 'T_PROJECT_USER_R_D_TIME'), wage_ctx.get('source_table', 'T_STAFF_WAGE')],
                [self._safe_staff_name(staff_map, sid) for sid in violators_r03],
            )
        else:
            not_computable_rules.append('R03: 研发工时投入未添加工资表单')

        # R04 人事风险：有工资单但无研发工时（注意）
        if rd_ctx.get('available') and wage_ctx.get('available'):
            violators_r04 = sorted(list(wage_staff_ids - rd_staff_ids))
            append_rule(
                4,
                '人事风险',
                4000,
                '存在研发人员工资表单但无实际研发工时投入（注意）',
                bool(violators_r04),
                len(violators_r04),
                '按年度工资员工集合减去研发工时员工集合。',
                [rd_ctx.get('source_table', 'T_PROJECT_USER_R_D_TIME'), wage_ctx.get('source_table', 'T_STAFF_WAGE')],
                [self._safe_staff_name(staff_map, sid) for sid in violators_r04],
            )
        else:
            not_computable_rules.append('R04: 研发人员工资表单但无研发工时投入（注意）')

        # R05 研发风险：每周研发工时 >= 70 小时
        if rd_ctx.get('available') or attendance_ctx.get('available'):
            rd_weekly_source = attendance_rd_weekly_hours_by_staff if attendance_rd_weekly_hours_by_staff else rd_weekly_hours_by_staff
            rd_source_tables_r05: List[str] = []
            if attendance_rd_weekly_hours_by_staff:
                rd_source_tables_r05.append(attendance_ctx.get('source_table', 'T_ATTENDANCE_GROUP_USER_CLASSES'))
            elif rd_ctx.get('available'):
                rd_source_tables_r05.append(rd_ctx.get('source_table', 'T_PROJECT_USER_R_D_TIME'))
            violators_r05: List[str] = []
            for staff_id, week_map in rd_weekly_source.items():
                if any(self._to_float(hours) >= 70 for hours in week_map.values()):
                    violators_r05.append(staff_id)
            append_rule(
                5,
                '研发风险',
                5000,
                '员工每周研发工时超过70小时',
                bool(violators_r05),
                len(violators_r05),
                '按考勤组人员考勤明细（R_D_TOTAL_HOUR）按周汇总，判断周总研发工时 >= 70 小时。',
                rd_source_tables_r05,
                [self._safe_staff_name(staff_map, sid) for sid in sorted(violators_r05)],
            )
        else:
            not_computable_rules.append('R05: 员工每周研发工时超过70小时')

        # R06 人事风险：每周考勤工时 >= 70 小时
        if attendance_ctx.get('available'):
            violators_r06: List[str] = []
            for staff_id, week_map in attendance_weekly_hours_by_staff.items():
                if any(self._to_float(hours) >= 70 for hours in week_map.values()):
                    violators_r06.append(staff_id)
            append_rule(
                6,
                '人事风险',
                7000,
                '员工每周考勤工时超过70小时',
                bool(violators_r06),
                len(violators_r06),
                '按 ISO 周汇总 T_ATTENDANCE_GROUP_USER_CLASSES 员工考勤工时，判断周总工时 >= 70 小时。',
                [attendance_ctx.get('source_table', 'T_ATTENDANCE_GROUP_USER_CLASSES')],
                [self._safe_staff_name(staff_map, sid) for sid in sorted(violators_r06)],
            )
        else:
            not_computable_rules.append('R06: 员工每周考勤工时超过70小时')

        # R07 人事风险：外聘人员占比 > 50%
        if staff_ctx.get('available'):
            active_count = len(active_staff_ids)
            external_active_count = len(active_staff_ids & external_staff_ids)
            ratio = (external_active_count / active_count) if active_count else 0.0
            append_rule(
                7,
                '人事风险',
                4000,
                '研发人员外聘占比超过50%',
                active_count > 0 and ratio > 0.5,
                external_active_count,
                '按 T_STAFF：外聘人数(兼职+临时聘用) / 当年在职员工总人数。',
                ['T_STAFF'],
                [],
                basic_extras={
                    '外聘在职人数': external_active_count,
                    '在职员工总人数': active_count,
                    '外聘占比': self._format_percent(external_active_count, active_count),
                },
            )
            if active_count == 0:
                analysis_notes.append('R07 分母为 0（当年在职员工数为 0），规则未触发。')
        else:
            not_computable_rules.append('R07: 研发人员外聘占比超过50%')

        # R08 人事风险：研发活动人员占比 >= 70%
        if staff_ctx.get('available') and rd_ctx.get('available'):
            active_count = len(active_staff_ids)
            active_rd_count = len(active_staff_ids & rd_staff_ids)
            ratio = (active_rd_count / active_count) if active_count else 0.0
            append_rule(
                8,
                '人事风险',
                7000,
                '从事研发活动人员占比达到或超过70%',
                active_count > 0 and ratio >= 0.7,
                active_rd_count,
                '按 T_PROJECT_USER_R_D_TIME 与 T_STAFF：当年有研发工时员工数 / 当年在职员工数。',
                ['T_PROJECT_USER_R_D_TIME', 'T_STAFF'],
                [],
                basic_extras={
                    '研发活动人数': active_rd_count,
                    '在职员工总人数': active_count,
                    '研发活动占比': self._format_percent(active_rd_count, active_count),
                },
            )
            if active_count == 0:
                analysis_notes.append('R08 分母为 0（当年在职员工数为 0），规则未触发。')
        else:
            not_computable_rules.append('R08: 从事研发活动人员占比达到或超过70%')

        # R09 人事风险：高中及以下学历占比 > 50%
        if staff_ctx.get('available'):
            active_count = len(active_staff_ids)
            low_edu_active_count = len(active_staff_ids & low_education_staff_ids)
            ratio = (low_edu_active_count / active_count) if active_count else 0.0
            append_rule(
                9,
                '人事风险',
                4000,
                '研发人员高中及以下学历占比超过50%',
                active_count > 0 and ratio > 0.5,
                low_edu_active_count,
                '按 T_STAFF：学历字段判定为高中及以下人数 / 当年在职员工数。',
                ['T_STAFF', 'T_TYPE'],
                [],
                basic_extras={
                    '高中及以下人数': low_edu_active_count,
                    '在职员工总人数': active_count,
                    '占比': self._format_percent(low_edu_active_count, active_count),
                },
            )
            if active_count == 0:
                analysis_notes.append('R09 分母为 0（当年在职员工数为 0），规则未触发。')
        else:
            not_computable_rules.append('R09: 高中及以下学历占比超过50%')

        # R10 人事风险：人员数据缺失（在职员工档案记录人数 <= 2）
        if staff_ctx.get('available'):
            active_count = len(active_staff_ids)
            samples_r10 = [self._safe_staff_name(staff_map, sid) for sid in sorted(active_staff_ids)]
            append_rule(
                10,
                '人事风险',
                4000,
                '人员档案数据缺失（在职员工档案记录人数<=2）',
                active_count <= 2,
                active_count,
                '按 T_STAFF：统计当年在职员工档案记录人数，命中条件为 <= 2 人。',
                ['T_STAFF'],
                samples_r10,
                basic_extras={
                    '当年在职员工档案记录人数': active_count,
                },
            )
        else:
            not_computable_rules.append('R10: 人员档案数据缺失（在职员工档案记录人数<=2）')

        rd_wage_amount = round(sum(self._to_float(wage_total_by_staff.get(staff_id)) for staff_id in rd_staff_ids), 2)
        formal_wage_amount = round(sum(self._to_float(wage_total_by_staff.get(staff_id)) for staff_id in formal_staff_ids), 2)

        # R11 人事风险：研发活动人员薪资 / 正式员工薪资 > 52.04%
        if rd_ctx.get('available') and wage_ctx.get('available'):
            ratio = (rd_wage_amount / formal_wage_amount) if formal_wage_amount else 0.0
            append_rule(
                11,
                '人事风险',
                6000,
                '研发活动人员薪资占正式员工薪资总额比例超过52.04%',
                formal_wage_amount > 0 and ratio >= 0.5204,
                len(rd_staff_ids),
                '按 T_STAFF_WAGE + T_STAFF + T_PROJECT_USER_R_D_TIME：有研发工时员工工资总额 / 正式员工工资总额。',
                ['T_STAFF_WAGE', 'T_PROJECT_USER_R_D_TIME'],
                [],
                basic_extras={
                    '研发活动人员工资总额': rd_wage_amount,
                    '正式员工工资总额': formal_wage_amount,
                    '占比': self._format_percent(rd_wage_amount, formal_wage_amount),
                },
            )
            if formal_wage_amount <= 0:
                analysis_notes.append('R11 分母为 0（正式员工工资总额为 0），规则未触发。')
        else:
            not_computable_rules.append('R11: 研发活动人员薪资占正式员工薪资总额比例超过52.04%')

        # R12 财务风险：委外凭证金额占比 > 60%
        if cost_ctx.get('available'):
            ratio = (entrust_external_amount / rd_voucher_amount) if rd_voucher_amount else 0.0
            append_rule(
                12,
                '财务风险',
                6000,
                '委外研发凭证金额占研发凭证总额比例超过60%',
                rd_voucher_amount > 0 and ratio > 0.6,
                1 if rd_voucher_amount > 0 and ratio > 0.6 else 0,
                '按 T_HD_COST_STRUCTURE_DETAILS(_YEARS) 委外金额 / T_COST_MANAGE_COST_SECOND 研发凭证金额。',
                cost_ctx.get('source_tables', []),
                [],
                basic_extras={
                    '委外研发金额': round(entrust_external_amount, 2),
                    '研发凭证总额': round(rd_voucher_amount, 2),
                    '占比': self._format_percent(entrust_external_amount, rd_voucher_amount),
                },
            )
            if rd_voucher_amount <= 0:
                analysis_notes.append('R12 分母为 0（研发凭证总额为 0），规则未触发。')
        else:
            not_computable_rules.append('R12: 委外研发凭证金额占比超过60%')

        # R13 财务风险：存在未锁账月份
        if voucher_lock_ctx.get('available'):
            unlocked_sorted = sorted(list(unlocked_months))
            append_rule(
                13,
                '财务风险',
                4000,
                '当年存在凭证金额但未锁账月份',
                bool(unlocked_sorted),
                len(unlocked_sorted),
                '按 T_VOUCHER/T_VOUCHER_LOCK：当年有凭证金额的月份中，LOCK_STATUS 非 9999 的月份。',
                voucher_lock_ctx.get('source_tables', []),
                [f'{month}月' for month in unlocked_sorted],
                basic_extras={
                    '有凭证金额月份数': len(months_with_amount),
                    '已锁账月份数': len(locked_months),
                    '未锁账月份': '、'.join([f'{month}月' for month in unlocked_sorted]),
                },
            )
        else:
            not_computable_rules.append('R13: 当年存在凭证金额但未锁账月份')

        # R14 财务风险：人员人工费用占比 > 60%
        if cost_ctx.get('available'):
            ratio = (personnel_amount / rd_voucher_amount) if rd_voucher_amount else 0.0
            append_rule(
                14,
                '财务风险',
                5000,
                '人员人工费用投入占研发凭证总额比例超过60%',
                rd_voucher_amount > 0 and ratio > 0.6,
                1 if rd_voucher_amount > 0 and ratio > 0.6 else 0,
                '按 T_HD_COST_STRUCTURE_DETAILS(_YEARS) 人员人工费用 / T_COST_MANAGE_COST_SECOND 研发凭证金额。',
                cost_ctx.get('source_tables', []),
                [],
                basic_extras={
                    '人员人工费用': round(personnel_amount, 2),
                    '研发凭证总额': round(rd_voucher_amount, 2),
                    '占比': self._format_percent(personnel_amount, rd_voucher_amount),
                },
            )
            if rd_voucher_amount <= 0:
                analysis_notes.append('R14 分母为 0（研发凭证总额为 0），规则未触发。')
        else:
            not_computable_rules.append('R14: 人员人工费用占研发凭证总额比例超过60%')

        # R15 研发风险：项目实际支出超预算 80%+
        if project_ctx.get('available'):
            violated_projects_r15: List[str] = []
            for project in projects:
                if not project.get('overlap_year'):
                    continue
                budget = self._to_float(project.get('general_budget'))
                executed = self._to_float(project_cost_map.get(self._stringify(project.get('id')), 0))
                if budget > 0 and executed > budget * 1.8:
                    violated_projects_r15.append(self._stringify(project.get('name')))
            append_rule(
                15,
                '研发风险',
                7000,
                '项目实际支出超出预算80%以上',
                bool(violated_projects_r15),
                len(violated_projects_r15),
                '按 T_PROJECT.GENERAL_BUDGET 与 T_COST_MANAGE_COST_PROJECT_SECOND.R_D_VOUCHER_AMOUNT 对比，执行额 > 1.8 * 预算额。',
                ['T_PROJECT', 'T_COST_MANAGE_COST_PROJECT_SECOND'],
                violated_projects_r15,
            )
        else:
            not_computable_rules.append('R15: 项目实际支出超出预算80%以上')

        # R16 研发风险：申请人/负责人在职区间与项目周期不匹配
        if project_ctx.get('available') and staff_ctx.get('available'):
            violated_projects_r16: List[str] = []
            violated_relations = 0
            for project in projects:
                if not project.get('overlap_year'):
                    continue

                start_date = project.get('start_date')
                end_date = project.get('end_date')
                if start_date is None or end_date is None:
                    continue

                related_staff_ids = set(project.get('apply_user_ids', []) + project.get('manager_ids', []))
                if not related_staff_ids:
                    continue

                project_hit = False
                for staff_id in related_staff_ids:
                    staff = staff_map.get(self._stringify(staff_id), {})
                    if not staff:
                        continue
                    entry_date = self._normalize_date(staff.get('entry_time'))
                    resign_date = self._normalize_date(staff.get('resign_time'))
                    if (entry_date is not None and entry_date > end_date) or (resign_date is not None and resign_date < start_date):
                        violated_relations += 1
                        project_hit = True
                if project_hit:
                    violated_projects_r16.append(self._stringify(project.get('name')))

            append_rule(
                16,
                '研发风险',
                7000,
                '项目申请人/负责人在职时间超出项目周期',
                bool(violated_projects_r16),
                violated_relations,
                '按 T_PROJECT(申请人/负责人/项目周期) 与 T_STAFF(入离职日期) 比对在职区间是否覆盖项目周期。',
                ['T_PROJECT', 'T_STAFF'],
                violated_projects_r16,
                basic_extras={
                    '命中项目数量': len(violated_projects_r16),
                    '命中人员关系数量': violated_relations,
                },
            )
        else:
            not_computable_rules.append('R16: 项目申请人/负责人在职时间超出项目周期')

        # R17 研发风险：申请日期与开始日期间隔 > 3 个月
        if project_ctx.get('available'):
            violated_projects_r17: List[str] = []
            for project in projects:
                if not project.get('overlap_year'):
                    continue
                apply_date = project.get('apply_for_date')
                start_date = project.get('start_date')
                if apply_date is None or start_date is None:
                    continue
                if (start_date - apply_date).days > 90:
                    violated_projects_r17.append(self._stringify(project.get('name')))

            append_rule(
                17,
                '研发风险',
                5000,
                '项目申请日期与项目开始日期间隔超过3个月',
                bool(violated_projects_r17),
                len(violated_projects_r17),
                '按 T_PROJECT.APPLY_FOR_DATE 与 START_DATE 比较，差值 > 90 天。',
                ['T_PROJECT'],
                violated_projects_r17,
            )
        else:
            not_computable_rules.append('R17: 项目申请日期与项目开始日期间隔超过3个月')

        # R18 研发风险：同一人员同周参与 >= 3 个研发项目
        if rd_ctx.get('available'):
            violators_r18: List[str] = []
            hit_week_count = 0
            for staff_id, week_projects in rd_weekly_project_ids_by_staff.items():
                matched_weeks = [week_key for week_key, project_ids in week_projects.items() if len(project_ids) >= 3]
                if matched_weeks:
                    violators_r18.append(staff_id)
                    hit_week_count += len(matched_weeks)

            append_rule(
                18,
                '研发风险',
                7000,
                '人员单周研发工时同时投入3个及以上项目',
                bool(violators_r18),
                hit_week_count,
                '按 T_PROJECT_USER_R_D_TIME 统计员工-周的参与项目数，命中条件为 >= 3 个项目。',
                [rd_ctx.get('source_table', 'T_PROJECT_USER_R_D_TIME')],
                [self._safe_staff_name(staff_map, sid) for sid in sorted(violators_r18)],
                basic_extras={
                    '命中员工数量': len(violators_r18),
                    '命中员工周次数': hit_week_count,
                },
            )
        else:
            not_computable_rules.append('R18: 人员单周研发工时同时投入3个及以上项目')

        # R19 审计类规则（并入财务）：加计扣除金额尾数过于整齐（近似千位整）
        if cost_ctx.get('available'):
            approx_thousand = False
            if additional_deduction_amount > 0:
                rounded = round(additional_deduction_amount / 1000)
                approx_thousand = abs(additional_deduction_amount - rounded * 1000) <= 0.01

            append_rule(
                19,
                '财务风险',
                5000,
                '加计扣除金额尾数呈整千特征（审计关注）',
                approx_thousand,
                1 if approx_thousand else 0,
                '按 T_COST_MANAGE_COST_SECOND 年度加计扣除总额判断末三位是否近似 000。',
                ['T_COST_MANAGE_COST_SECOND'],
                [],
                basic_extras={
                    '年度加计扣除总额': round(additional_deduction_amount, 2),
                },
                dynamic_extras={
                    '说明': '该规则属于审计侧观察项，当前并入财务风险分类展示。',
                },
            )
        else:
            not_computable_rules.append('R19: 加计扣除金额尾数呈整千特征')

        # R20 审计类规则（并入财务）：申报文件月份缺失
        if declaration_ctx.get('available') and voucher_lock_ctx.get('available'):
            reference_months = sorted(list(months_with_amount | locked_months))
            missing_decl_months = [month for month in reference_months if month not in declaration_months]
            append_rule(
                20,
                '财务风险',
                6000,
                '申报备查文件存在月份缺失（审计关注）',
                bool(missing_decl_months),
                len(missing_decl_months),
                '以凭证有金额或已锁账月份为基准，核对 T_ANNEX/T_GROUP 申报备查相关文件月份是否覆盖。',
                list(declaration_ctx.get('source_tables', [])) + list(voucher_lock_ctx.get('source_tables', [])),
                [f'{month}月' for month in missing_decl_months],
                basic_extras={
                    '基准月份': '、'.join([f'{month}月' for month in reference_months]),
                    '申报文件月份': '、'.join([f'{month}月' for month in sorted(list(declaration_months))]),
                    '缺失月份': '、'.join([f'{month}月' for month in missing_decl_months]),
                },
                dynamic_extras={
                    '说明': '该规则属于审计侧潜在风险，当前并入财务风险分类展示。',
                },
            )
        else:
            not_computable_rules.append('R20: 申报备查文件月份缺失')

        # R21 财务风险：2月/3月存在自动核算金额但无研发凭证
        if subject_gap_ctx.get('available'):
            samples_r21 = [f"{row.get('month')}月-{self._stringify(row.get('subject_name'))}" for row in missing_subject_rows]
            append_rule(
                21,
                '财务风险',
                8000,
                '2月/3月存在科目金额但未录入研发凭证',
                bool(missing_subject_rows),
                len(missing_subject_rows),
                '按 T_COST_MANAGE_COST_SUBJECT_SECOND：2-3 月 ACCOUNTING_STANDARDS_AMOUNT > 0 且 R_D_VOUCHER_AMOUNT <= 0。',
                subject_gap_ctx.get('source_tables', []),
                samples_r21,
            )
        else:
            not_computable_rules.append('R21: 2月/3月存在科目金额但未录入研发凭证')

        # R22 研发风险：项目执行关键材料缺失
        if project_ctx.get('available'):
            violated_projects_r22: List[str] = []
            for project in projects:
                if not project.get('overlap_year'):
                    continue
                project_id = self._stringify(project.get('id'))
                has_results = project_id in results_projects
                has_acceptance = project_id in acceptance_projects
                has_expert = bool(self._stringify(project.get('expert_opinion_id')).strip())
                has_search = project_id in search_projects
                has_demo = project_id in demonstration_projects
                has_research = project_id in research_projects

                if not (has_results and has_acceptance and has_expert and has_search and has_demo and has_research):
                    violated_projects_r22.append(self._stringify(project.get('name')))

            append_rule(
                22,
                '研发风险',
                6000,
                '项目执行文件缺失（成果/结题验收/鉴定意见/检索/论证/调研）',
                bool(violated_projects_r22),
                len(violated_projects_r22),
                '按 T_PROJECT 与项目成果/验收/检索/论证/调研相关表逐项核验是否齐备。',
                project_ctx.get('source_tables', []),
                violated_projects_r22,
            )
        else:
            not_computable_rules.append('R22: 项目执行文件缺失')

        # R23 财务风险：研发加计扣除金额 > 研发凭证金额
        if cost_ctx.get('available'):
            append_rule(
                23,
                '财务风险',
                8000,
                '研发加计扣除金额超过研发凭证金额',
                additional_deduction_amount > rd_voucher_amount and rd_voucher_amount >= 0,
                1 if additional_deduction_amount > rd_voucher_amount and rd_voucher_amount >= 0 else 0,
                '按 T_COST_MANAGE_COST_SECOND 年度汇总：R_D_ADDITIONAL_DEDUCTION_AMOUNT > R_D_VOUCHER_AMOUNT。',
                ['T_COST_MANAGE_COST_SECOND'],
                [],
                basic_extras={
                    '研发加计扣除金额': round(additional_deduction_amount, 2),
                    '研发凭证金额': round(rd_voucher_amount, 2),
                },
            )
        else:
            not_computable_rules.append('R23: 研发加计扣除金额超过研发凭证金额')

        # R24 人事风险：存在研发人员工资表单但无实际研发工时投入（观察预警）
        if rd_ctx.get('available') and wage_ctx.get('available'):
            violators_r23 = sorted(list(wage_staff_ids - rd_staff_ids))
            append_rule(
                24,
                '人事风险',
                5000,
                '存在研发人员工资表单但无实际研发工时投入（观察预警）',
                bool(violators_r23),
                len(violators_r23),
                '按年度工资员工集合减去研发工时员工集合。',
                [rd_ctx.get('source_table', 'T_PROJECT_USER_R_D_TIME'), wage_ctx.get('source_table', 'T_STAFF_WAGE')],
                [self._safe_staff_name(staff_map, sid) for sid in violators_r23],
            )
        else:
            not_computable_rules.append('R24: 研发人员工资表单但无实际研发工时投入（观察预警）')

        # R25 研发风险：直接投入（材料）费用占比 > 60%
        if cost_ctx.get('available'):
            ratio = (direct_investment_amount / total_rd_expense_amount) if total_rd_expense_amount else 0.0
            append_rule(
                25,
                '研发风险',
                5000,
                '直接投入（材料）费用占研发支出总额比例超过60%',
                total_rd_expense_amount > 0 and ratio > 0.6,
                1 if total_rd_expense_amount > 0 and ratio > 0.6 else 0,
                '按 T_HD_COST_STRUCTURE_DETAILS(_YEARS)：DIRECT_INVESTMENT_AMOUNT / TOTAL_AMOUNT。',
                cost_ctx.get('source_tables', []),
                [],
                basic_extras={
                    '直接投入（材料）费用': round(direct_investment_amount, 2),
                    '研发支出总额': round(total_rd_expense_amount, 2),
                    '占比': self._format_percent(direct_investment_amount, total_rd_expense_amount),
                },
            )
            if total_rd_expense_amount <= 0:
                analysis_notes.append('R25 分母为 0（研发支出总额为 0），规则未触发。')
        else:
            not_computable_rules.append('R25: 直接投入（材料）费用占研发支出总额比例超过60%')

        # R26 人事风险：直接研发人员工资占比 >= 80%
        if rd_ctx.get('available') and wage_ctx.get('available'):
            ratio = (rd_wage_amount / total_wage_amount) if total_wage_amount else 0.0
            append_rule(
                26,
                '人事风险',
                5000,
                '直接研发人员工资薪金占企业工资薪金总额达到80%及以上',
                total_wage_amount > 0 and ratio >= 0.8,
                len(rd_staff_ids),
                '按 T_STAFF_WAGE + T_PROJECT_USER_R_D_TIME：有研发工时员工工资总额 / 企业工资总额，阈值 >= 80%。',
                ['T_STAFF_WAGE', 'T_PROJECT_USER_R_D_TIME'],
                [],
                basic_extras={
                    '研发活动人员工资总额': rd_wage_amount,
                    '企业工资总额': round(total_wage_amount, 2),
                    '占比': self._format_percent(rd_wage_amount, total_wage_amount),
                },
            )
            if total_wage_amount <= 0:
                analysis_notes.append('R26 分母为 0（企业工资总额为 0），规则未触发。')
        else:
            not_computable_rules.append('R26: 直接研发人员工资占企业工资总额达到80%及以上')

        # R27 财务风险：辅助/管理人员研发薪资占比 > 50%
        if rd_ctx.get('available') and wage_ctx.get('available') and staff_ctx.get('available'):
            aux_manager_rd_wage = round(
                sum(
                    self._to_float(wage_total_by_staff.get(staff_id))
                    for staff_id in (rd_staff_ids & aux_or_manager_staff_ids)
                ),
                2,
            )
            ratio = (aux_manager_rd_wage / rd_wage_amount) if rd_wage_amount else 0.0
            append_rule(
                27,
                '财务风险',
                7000,
                '辅助/管理人员研发薪资占研发人员薪资总额比例超过50%',
                rd_wage_amount > 0 and ratio > 0.5,
                len(rd_staff_ids & aux_or_manager_staff_ids),
                '按 T_STAFF 类别标签 + T_STAFF_WAGE + T_PROJECT_USER_R_D_TIME：辅助/管理且有研发工时员工工资总额 / 研发活动员工工资总额。',
                ['T_STAFF', 'T_STAFF_WAGE', 'T_PROJECT_USER_R_D_TIME', 'T_TYPE'],
                [self._safe_staff_name(staff_map, sid) for sid in sorted(rd_staff_ids & aux_or_manager_staff_ids)],
                basic_extras={
                    '辅助/管理研发薪资总额': aux_manager_rd_wage,
                    '研发活动人员薪资总额': rd_wage_amount,
                    '占比': self._format_percent(aux_manager_rd_wage, rd_wage_amount),
                },
            )
            if rd_wage_amount <= 0:
                analysis_notes.append('R27 分母为 0（研发活动人员薪资总额为 0），规则未触发。')
        else:
            not_computable_rules.append('R27: 辅助/管理人员研发薪资占比超过50%')

        if not_computable_rules:
            analysis_notes.append('以下规则因表结构或数据不足未计算：' + '；'.join(not_computable_rules))

        category_items: Dict[str, List[Dict[str, Any]]] = {
            '研发风险': [],
            '人事风险': [],
            '财务风险': [],
        }
        unsupported_type_counter: Dict[str, int] = {}
        for item in detected_items:
            category_name = self._stringify(item.get('category_name')).strip()
            if category_name in category_items:
                category_items[category_name].append(item)
            else:
                key = category_name or '未识别风险'
                unsupported_type_counter[key] = unsupported_type_counter.get(key, 0) + 1

        rd_payload = self._build_risk_category_payload('研发风险', category_items['研发风险'])
        hr_payload = self._build_risk_category_payload('人事风险', category_items['人事风险'])
        financial_payload = self._build_risk_category_payload('财务风险', category_items['财务风险'])

        total_supported = rd_payload['count'] + hr_payload['count'] + financial_payload['count']

        detail_analysis: Dict[str, Any] = {
            '统计口径': '风险点总数按“风险明细规则逐条检测”统计，仅纳入研发风险、人事风险、财务风险三类。',
            '数据来源说明': '数据库字段基于《数据库所有表.xlsx》中的真实表结构（人员/考勤/工资/项目/凭证/加计扣除/附件等表）逐条计算。',
        }

        if unsupported_type_counter:
            unsupported_text = '；'.join([f'{k}:{v}个' for k, v in unsupported_type_counter.items()])
            analysis_notes.append('检测到当前模块未展示的风险类型：' + unsupported_text)

        if analysis_notes:
            detail_analysis['无法统计或未纳入部分'] = ' | '.join([note for note in analysis_notes if note])

        return {
            'summary': f'本年总风险点：{total_supported}个',
            'detail': {
                '本年隐藏风险点数量': total_supported,
                '研发风险点数量': rd_payload['count'],
                '人事风险点数量': hr_payload['count'],
                '财务风险点数量': financial_payload['count'],
            },
            'detail_analysis': detail_analysis,
            'detail_description': '风险点模块按风险明细规则逐条执行检测，并分别展示研发、人事、财务三类风险。',
            'rd_risks': rd_payload,
            'hr_risks': hr_payload,
            'financial_risks': financial_payload,
        }
