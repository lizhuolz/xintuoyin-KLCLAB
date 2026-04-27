
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pymysql

from ..domain_modules.declaration_module import DeclarationRepositoryMixin
from ..domain_modules.finance_module import FinanceRepositoryMixin
from ..domain_modules.hr_module import HrRepositoryMixin
from ..domain_modules.project_module import ProjectRepositoryMixin
from ..domain_modules.risk_module import RiskRepositoryMixin


class GraphRepository(
    HrRepositoryMixin,
    FinanceRepositoryMixin,
    ProjectRepositoryMixin,
    DeclarationRepositoryMixin,
    RiskRepositoryMixin,
):

    _SCHEMA_CACHE_ATTR = '_graph_schema_cache'

    def warmup_schema_cache(self, conn) -> None:
        self._get_schema_cache(conn)

    def _get_database_name(self, conn) -> Optional[str]:
        db_name = getattr(conn, 'db', None)
        if isinstance(db_name, bytes):
            try:
                db_name = db_name.decode('utf-8')
            except Exception:
                db_name = None
        if isinstance(db_name, str) and db_name.strip():
            return db_name.strip()

        row = self._safe_one(conn, 'SELECT DATABASE()')
        if row and row[0]:
            return str(row[0]).strip()
        return None

    def _build_schema_cache(self, conn) -> Dict[str, Any]:
        database_name = self._get_database_name(conn)
        cache: Dict[str, Any] = {
            'database': database_name,
            'tables': {},
            'table_lookup': {},
        }
        if not database_name:
            return cache

        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    '''
                    SELECT TABLE_NAME, COLUMN_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s
                    ORDER BY TABLE_NAME, ORDINAL_POSITION
                    ''',
                    (database_name,),
                )
                rows = cursor.fetchall()
        except pymysql.MySQLError:
            return cache

        for row in rows:
            table_name = str(row[0])
            column_name = str(row[1])
            table_meta = cache['tables'].setdefault(
                table_name,
                {
                    'columns': [],
                    'lower_map': {},
                },
            )
            table_meta['columns'].append(column_name)
            table_meta['lower_map'][column_name.lower()] = column_name
            cache['table_lookup'][table_name.lower()] = table_name
        return cache

    def _get_schema_cache(self, conn) -> Dict[str, Any]:
        cache = getattr(conn, self._SCHEMA_CACHE_ATTR, None)
        if cache is None:
            cache = self._build_schema_cache(conn)
            try:
                setattr(conn, self._SCHEMA_CACHE_ATTR, cache)
            except Exception:
                pass
        return cache

    def _get_table_meta(self, conn, table_name: str) -> Optional[Dict[str, Any]]:
        if not table_name:
            return None
        cache = self._get_schema_cache(conn)
        actual_name = cache.get('table_lookup', {}).get(table_name.lower())
        if actual_name:
            return cache.get('tables', {}).get(actual_name)
        return None


    def _table_exists(self, conn, table_name: str) -> bool:
        if not table_name:
            return False
        table_meta = self._get_table_meta(conn, table_name)
        if table_meta is not None:
            return True
        try:
            with conn.cursor() as cursor:
                cursor.execute('SHOW TABLES LIKE %s', (table_name,))
                return cursor.fetchone() is not None
        except pymysql.MySQLError:
            return False

    def _pick_table(self, conn, candidates: Sequence[str]) -> Optional[str]:
        cache = self._get_schema_cache(conn)
        table_lookup = cache.get('table_lookup', {})
        for table in candidates:
            actual_name = table_lookup.get(str(table).lower())
            if actual_name:
                return actual_name
        for table in candidates:
            if self._table_exists(conn, table):
                return table
        return None

    def _get_columns(self, conn, table_name: str) -> List[str]:
        table_meta = self._get_table_meta(conn, table_name)
        if table_meta is not None:
            return list(table_meta.get('columns', []))
        try:
            with conn.cursor() as cursor:
                cursor.execute(f'SHOW COLUMNS FROM `{table_name}`')
                rows = cursor.fetchall()
        except pymysql.MySQLError:
            return []
        return [str(row[0]) for row in rows]

    def _pick_column(self, conn, table_name: str, candidates: Sequence[str]) -> Optional[str]:
        columns = self._get_columns(conn, table_name)
        if not columns:
            return None
        lower_map = {col.lower(): col for col in columns}
        for candidate in candidates:
            if candidate in columns:
                return candidate
            lowered = candidate.lower()
            if lowered in lower_map:
                return lower_map[lowered]
        return None

    def _col_expr(self, conn, table_name: str, table_alias: str, candidates: Sequence[str], alias: str) -> Tuple[str, Optional[str]]:
        column = self._pick_column(conn, table_name, candidates)
        if column:
            return f"{table_alias}.`{column}` AS `{alias}`", column
        return f"NULL AS `{alias}`", None

    def _safe_rows(self, conn, sql: str, params: Sequence[Any] = ()) -> List[Tuple[Any, ...]]:
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return list(cursor.fetchall())
        except pymysql.MySQLError:
            return []

    def _safe_one(self, conn, sql: str, params: Sequence[Any] = ()) -> Optional[Tuple[Any, ...]]:
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()
        except pymysql.MySQLError:
            return None

    def _to_float(self, value: Any) -> float:
        if value in (None, '', 'null'):
            return 0.0
        try:
            return float(value)
        except Exception:
            return 0.0

    def _to_int(self, value: Any) -> int:
        if value in (None, '', 'null'):
            return 0
        try:
            return int(float(value))
        except Exception:
            return 0

    def _stringify(self, value: Any) -> str:
        if value is None:
            return ''
        if isinstance(value, (datetime, date)):
            return value.strftime('%Y-%m-%d')
        return str(value)

    def _normalize_date(self, value: Any) -> Optional[date]:
        if value in (None, '', 'null'):
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip()
        if not text:
            return None
        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M:%S'):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _year_range(self, year: int) -> Tuple[date, date]:
        return date(year, 1, 1), date(year + 1, 1, 1)

    def _month_range(self, year: int, month: int) -> Tuple[date, date]:
        if month == 12:
            return date(year, 12, 1), date(year + 1, 1, 1)
        return date(year, month, 1), date(year, month + 1, 1)

    def _date_overlaps_range(self, start_value: Any, end_value: Any, range_start: date, range_end: date) -> bool:
        start_date = self._normalize_date(start_value)
        end_date = self._normalize_date(end_value)

        if start_date and end_date and end_date < start_date:
            start_date, end_date = end_date, start_date

        if start_date and end_date:
            return start_date < range_end and end_date >= range_start
        if start_date:
            return start_date < range_end
        if end_date:
            return end_date >= range_start
        return False

    def _is_active_for_year(self, resign_date: Any, year: int) -> bool:
        normalized = self._normalize_date(resign_date)
        year_start, _ = self._year_range(year)
        return normalized is None or normalized >= year_start

    def _is_in_year(self, dt: Any, year: int) -> bool:
        normalized = self._normalize_date(dt)
        return normalized is not None and normalized.year == year

    def _category_is_rd(self, category: Any) -> bool:
        numeric = self._to_int(category)
        if numeric in (100, 200):
            return True
        text = str(category or '').strip().lower()
        if any(token in text for token in ['技术', '研究', '研发', 'rd']):
            return True
        return False

    def _status_bucket(self, status: Any) -> str:
        text = str(status or '').strip().lower()
        if not text:
            return 'unknown'
        if any(k in text for k in ['进行', '在研', '研发中', '执行', 'active', 'progress', 'running']):
            return 'progress'
        if any(k in text for k in ['完成', '结题', '验收', 'closed', 'done', 'finish', 'complete']):
            return 'completed'
        if any(k in text for k in ['草稿', 'draft', '拟立项', '待提交']):
            return 'draft'
        return 'other'

    def _project_status_text(self, status: Any) -> str:
        numeric = self._to_int(status)
        numeric_mapping = {
            0: '草稿',
            1000: '未开始',
            2000: '进行中',
            9999: '已完成',
        }
        if numeric in numeric_mapping:
            return numeric_mapping[numeric]
        return str(status or '').strip()

    def _project_status_bucket(self, status: Any) -> str:
        numeric = self._to_int(status)
        if numeric == 0:
            return 'draft'
        if numeric == 1000:
            return 'not_started'
        if numeric == 2000:
            return 'progress'
        if numeric == 9999:
            return 'completed'

        text = str(status or '').strip().lower()
        if not text:
            return 'unknown'
        if any(token in text for token in ['草稿', 'draft', '待提交', '拟立项']):
            return 'draft'
        if any(token in text for token in ['未开始', '待启动', 'pending']):
            return 'not_started'
        if any(token in text for token in ['进行', '在研', '研发中', '执行', 'active', 'progress', 'running']):
            return 'progress'
        if any(token in text for token in ['完成', '结题', '验收', 'closed', 'done', 'finish', 'complete']):
            return 'completed'
        return 'other'

    def _fixed_asset_source_text(self, source_type: Any) -> str:
        mapping = {
            1000: '自购',
            2000: '经营租赁',
        }
        numeric = self._to_int(source_type)
        if numeric in mapping:
            return mapping[numeric]
        text = self._stringify(source_type)
        return text if text != '0' else ''

    def _intangible_asset_type_text(self, asset_type: Any) -> str:
        mapping = {
            100: '专利',
            200: '软著',
            300: '非专利技术',
        }
        numeric = self._to_int(asset_type)
        if numeric in mapping:
            return mapping[numeric]
        text = self._stringify(asset_type)
        return text if text != '0' else ''

    def _intangible_asset_source_text(self, source_type: Any) -> str:
        mapping = {
            1000: '自购',
            2000: '自行研发',
            3000: '投资者购入',
        }
        numeric = self._to_int(source_type)
        if numeric in mapping:
            return mapping[numeric]
        text = self._stringify(source_type)
        return text if text != '0' else ''

    def _first_non_empty(self, *values: Any, default: Any = '') -> Any:
        for value in values:
            if value not in (None, '', 'null'):
                return value
        return default

    def _top_name(self, data: Dict[str, float]) -> str:
        if not data:
            return ''
        return max(data.items(), key=lambda item: item[1])[0]

    def fetch_current_user(self, conn) -> Optional[Dict[str, Any]]:
        row = self._safe_one(
            conn,
            """
            SELECT TENANT_ID, LEGAL_PERSON_NAME, CODE, NAME
            FROM T_ENTERPRISE
            WHERE TENANT_ID=3
            LIMIT 1
            """,
        )
        if not row:
            return None
        return {
            'user_id': self._stringify(row[0]),
            'username': self._stringify(row[1]),
            'enterprise_id': self._stringify(row[2]),
            'enterprise_name': self._stringify(row[3]),
        }
