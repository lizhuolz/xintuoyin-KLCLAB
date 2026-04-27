from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..models.graph_models import GraphNode


class FinanceGraphBuilderMixin:

    def build_finance_fixed_asset_nodes(self, assets: List[Dict[str, Any]]) -> List[GraphNode]:
        nodes: List[GraphNode] = []
        for asset in assets:
            asset_id = asset.get('id', asset.get('code', 'unknown'))
            nodes.append(
                self._node(
                    node_id=f'3_FIN_FIXED_ASSET_{asset_id}',
                    name=asset.get('name', f'固定资产_{asset_id}'),
                    node_type='3_FIN_FIXED_ASSET',
                    category='dynamic',
                    level=3,
                    side='right',
                    parent_id='2_FIXED_ASSETS',
                    identity_key=f'FIN_FIXED_ASSET:{asset_id}',
                    fixed=False,
                    summary=f"该年折旧：{asset.get('year_depreciation', 0)}",
                    detail=self._detail(
                        basic={
                            '资产名称': asset.get('name', ''),
                            '资产类型': asset.get('asset_type', ''),
                            '资产编码': asset.get('code', ''),
                            '规格型号': asset.get('specification', ''),
                            '资产已折旧金额': asset.get('depreciated_amount', 0),
                            '该年折旧金额': asset.get('year_depreciation', 0),
                        }
                    ),
                    children=[],
                    expandable=False,
                    leaf=True,
                )
            )
        return nodes

    def build_finance_intangible_asset_nodes(self, assets: List[Dict[str, Any]]) -> List[GraphNode]:
        nodes: List[GraphNode] = []
        for asset in assets:
            asset_id = asset.get('id', asset.get('code', 'unknown'))
            nodes.append(
                self._node(
                    node_id=f'3_FIN_INTANGIBLE_ASSET_{asset_id}',
                    name=asset.get('name', f'无形资产_{asset_id}'),
                    node_type='3_FIN_INTANGIBLE_ASSET',
                    category='dynamic',
                    level=3,
                    side='right',
                    parent_id='2_INTANGIBLE_ASSETS',
                    identity_key=f'FIN_INTANGIBLE_ASSET:{asset_id}',
                    fixed=False,
                    summary=f"该年摊销：{asset.get('year_amortization', 0)}",
                    detail=self._detail(
                        basic={
                            '资产名称': asset.get('name', ''),
                            '资产类型': asset.get('asset_type', ''),
                            '资产编码': asset.get('code', ''),
                            '规格型号': asset.get('specification', ''),
                        }
                    ),
                    children=[],
                    expandable=False,
                    leaf=True,
                )
            )
        return nodes

    def build_finance_material_nodes(self, materials: List[Dict[str, Any]]) -> List[GraphNode]:
        nodes: List[GraphNode] = []
        for item in materials:
            item_id = item.get('id') or item.get('name') or 'unknown'
            nodes.append(
                self._node(
                    node_id=f'3_FIN_MATERIAL_{item_id}',
                    name=item.get('name', f'材料_{item_id}'),
                    node_type='3_FIN_MATERIAL_ITEM',
                    category='dynamic',
                    level=3,
                    side='right',
                    parent_id='2_MATERIAL_CONSUMPTION',
                    identity_key=f'FIN_MATERIAL:{item.get("name", item_id)}',
                    fixed=False,
                    summary=f"金额：{item.get('amount', 0)}",
                    detail=self._detail(
                        basic={
                            '材料名称': item.get('name', ''),
                            '今年材料消耗金额': item.get('amount', 0),
                            '今年材料消耗数量': item.get('quantity', 0),
                        }
                    ),
                    children=[],
                    expandable=False,
                    leaf=True,
                )
            )
        return nodes

    def build_finance_fuel_nodes(self, fuels: List[Dict[str, Any]]) -> List[GraphNode]:
        nodes: List[GraphNode] = []
        for item in fuels:
            item_id = item.get('id') or item.get('name') or 'unknown'
            nodes.append(
                self._node(
                    node_id=f'3_FIN_FUEL_{item_id}',
                    name=item.get('name', f'燃料_{item_id}'),
                    node_type='3_FIN_FUEL_ITEM',
                    category='dynamic',
                    level=3,
                    side='right',
                    parent_id='2_MATERIAL_CONSUMPTION',
                    identity_key=f'FIN_FUEL:{item.get("name", item_id)}',
                    fixed=False,
                    summary=f"金额：{item.get('amount', 0)}",
                    detail=self._detail(
                        basic={
                            '燃料名称': item.get('name', ''),
                            '今年燃料消耗金额': item.get('amount', 0),
                            '今年燃料消耗数量': item.get('quantity', 0),
                        }
                    ),
                    children=[],
                    expandable=False,
                    leaf=True,
                )
            )
        return nodes


class FinanceRepositoryMixin:

    def _build_empty_finance_domain(self) -> Dict[str, Any]:
        return {
            'detail': {
                '该年研发投入成本': 0,
                '该年研发费用类型成本top1': '',
                '该年研发项目金额成本top1': '',
                '该年超预算项目数量': 0,
            },
            'fixed_assets': {
                'detail': {
                    '固定资产数量': 0,
                    '今年预计折旧': 0,
                    '去年已折旧金额': 0,
                    '该年研发预计投入金额': 0,
                    '去年已折旧研发金额': 0,
                },
                'assets': [],
            },
            'intangible_assets': {
                'detail': {
                    '该年预计摊销金额': 0,
                    '去年已摊销金额': 0,
                    '该年研发预计投入金额': 0,
                    '去年已摊销研发金额': 0,
                },
                'assets': [],
            },
            'material_management': {
                'detail': {
                    '今年燃料消耗总金额': 0,
                    '今年燃料消耗种类': 0,
                    '今年燃料消耗数量No.1': '',
                    '今年燃料消耗金额No.1': '',
                    '今年材料消耗总金额': 0,
                    '今年材料消耗种类': 0,
                    '今年材料消耗数量No.1': '',
                    '今年材料消耗金额No.1': '',
                },
                'materials': [],
                'fuels': [],
            },
            'power_management': {
                'detail': {
                    '该年动力消耗金额': 0,
                    '去年动力消耗金额': 0,
                }
            },
            'financial_voucher': {
                'detail': {
                    '该年凭证金额': 0,
                    '该未结账月数量': 0,
                    '去年未结账月数量': 0,
                }
            },
            'expense_management': {
                'detail': {
                    '研发口径总额': 0,
                    '高企口径总额': 0,
                    '会计口径总额': 0,
                }
            },
            'invoice_management': {
                'detail': {
                    '该年发票总额': 0,
                    '去年发票总额': 0,
                    '该年发票税额': 0,
                    '去年发票税额': 0,
                }
            },
            'special_income_management': {
                'detail': {
                    '该年特殊收入总额': 0,
                    '去年特殊收入总额': 0,
                }
            },
        }

    def _round2(self, value: Any) -> float:
        return round(self._to_float(value), 2)

    def _summary_label(self, name: str, value: Any) -> str:
        cleaned_name = self._stringify(name)
        amount = self._round2(value)
        if not cleaned_name:
            return ''
        return f'{cleaned_name}：{amount}'

    def _intangible_type_name(self, value: Any) -> str:
        mapping = {
            100: '专利',
            200: '软著',
            300: '非专利技术',
        }
        numeric = self._to_int(value)
        if numeric in mapping:
            return mapping[numeric]
        return self._stringify(value)

    def _month_end_exclusive(self, year: int, month: int) -> date:
        _, end = self._month_range(year, month)
        return end

    def _sum_amount_with_keywords(
        self,
        conn,
        table: str,
        tenant_id: str,
        year: int,
        keywords: Sequence[str],
        amount_col: str,
        year_col: str,
        name_candidates: Sequence[str],
    ) -> float:
        actual_amount_col = amount_col
        actual_year_col = year_col
        name_col = name_candidates[0]
        like_sql = ' OR '.join([f"COALESCE(`{name_col}`, '') LIKE %s" for _ in keywords])
        sql = (
            f"SELECT SUM(COALESCE(`{actual_amount_col}`, 0)) "
            f"FROM `{table}` WHERE `{actual_year_col}` = %s AND `TENANT_ID` = %s AND ({like_sql})"
        )
        params: List[Any] = [year, tenant_id]
        params.extend([f'%{keyword}%' for keyword in keywords])
        row = self._safe_one(conn, sql, params)
        return self._round2(row[0] if row else 0)

    def _fetch_device_type_map(self, conn, tenant_id: str) -> Dict[str, str]:
        sql = 'SELECT ID, NAME FROM `T_DEVICE_TYPE_CONFIG` WHERE `TENANT_ID` = %s'
        rows = self._safe_rows(conn, sql, (tenant_id,))
        return {self._stringify(row[0]): self._stringify(row[1]) for row in rows}

    def _fetch_fixed_asset_payload(self, conn, tenant_id: str, year: int, current_month: int) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        type_map = self._fetch_device_type_map(conn, tenant_id)
        dep_stats: Dict[str, Dict[str, float]] = {}
        dep_rows = self._safe_rows(
            conn,
            """
            SELECT
                FIXED_ASSETS_ID,
                SUM(CASE WHEN (YEARS < %s OR (YEARS = %s AND MONTHS <= %s)) THEN COALESCE(VAL, 0) ELSE 0 END) AS accumulated_amount,
                SUM(CASE WHEN YEARS = %s THEN COALESCE(VAL, 0) ELSE 0 END) AS current_year_amount,
                SUM(CASE WHEN YEARS = %s THEN COALESCE(VAL, 0) ELSE 0 END) AS previous_year_amount
            FROM `T_FIXED_ASSETS_DEPRECIATION`
            WHERE TENANT_ID = %s
            GROUP BY FIXED_ASSETS_ID
            """,
            (year, year, current_month, year, year - 1, tenant_id),
        )
        dep_stats = {
            self._stringify(row[0]): {
                'accumulated_amount': self._round2(row[1]),
                'current_year_amount': self._round2(row[2]),
                'previous_year_amount': self._round2(row[3]),
            }
            for row in dep_rows
        }

        rows = self._safe_rows(
            conn,
            f'''
            SELECT
                ID,
                NAME,
                DEVICE_TYPE_CONFIG_ID,
                CODE,
                SPECIFICATION_MODEL
            FROM `T_FIXED_ASSETS`
            WHERE TENANT_ID = %s
            ORDER BY NAME ASC, ID ASC
            ''',
            (tenant_id,),
        )

        assets: List[Dict[str, Any]] = []
        total_current_year = 0.0
        total_previous_year = 0.0
        for row in rows:
            asset_id = self._stringify(row[0])
            stat = dep_stats.get(asset_id, {})
            current_year_amount = self._round2(stat.get('current_year_amount', 0))
            previous_year_amount = self._round2(stat.get('previous_year_amount', 0))
            accumulated_amount = self._round2(stat.get('accumulated_amount', 0))
            assets.append(
                {
                    'id': asset_id,
                    'name': self._stringify(row[1]),
                    'asset_type': type_map.get(self._stringify(row[2]), self._stringify(row[2])),
                    'code': self._stringify(row[3]),
                    'specification': self._stringify(row[4]),
                    'depreciated_amount': accumulated_amount,
                    'year_depreciation': current_year_amount,
                }
            )
            total_current_year += current_year_amount
            total_previous_year += previous_year_amount

        current_rd_amount = self._sum_amount_with_keywords(
            conn,
            table='T_VOUCHER',
            tenant_id=tenant_id,
            year=year,
            keywords=['折旧', '设备租赁', '租赁'],
            amount_col='DETAILS_AMOUNT',
            year_col='VOUCHER_YEAR',
            name_candidates=['SUBJECT_CONFIG_NAME', 'COST_CONFIG_NAME'],
        )
        previous_rd_amount = self._sum_amount_with_keywords(
            conn,
            table='T_VOUCHER',
            tenant_id=tenant_id,
            year=year - 1,
            keywords=['折旧', '设备租赁', '租赁'],
            amount_col='DETAILS_AMOUNT',
            year_col='VOUCHER_YEAR',
            name_candidates=['SUBJECT_CONFIG_NAME', 'COST_CONFIG_NAME'],
        )

        detail = {
            '固定资产数量': len(assets),
            '今年预计折旧': self._round2(total_current_year),
            '去年已折旧金额': self._round2(total_previous_year),
            '该年研发预计投入金额': current_rd_amount,
            '去年已折旧研发金额': previous_rd_amount,
        }
        return detail, assets

    def _fetch_intangible_asset_payload(self, conn, tenant_id: str, year: int) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        amort_stats: Dict[str, Dict[str, float]] = {}
        amort_rows = self._safe_rows(
            conn,
            """
            SELECT
                INTANGIBLE_ASSETS_ID,
                SUM(CASE WHEN YEARS = %s THEN COALESCE(VAL, 0) ELSE 0 END) AS current_year_amount,
                SUM(CASE WHEN YEARS = %s THEN COALESCE(VAL, 0) ELSE 0 END) AS previous_year_amount
            FROM `T_INTANGIBLE_ASSETS_AMORTIZATION`
            WHERE TENANT_ID = %s
            GROUP BY INTANGIBLE_ASSETS_ID
            """,
            (year, year - 1, tenant_id),
        )
        amort_stats = {
            self._stringify(row[0]): {
                'current_year_amount': self._round2(row[1]),
                'previous_year_amount': self._round2(row[2]),
            }
            for row in amort_rows
        }

        rows = self._safe_rows(
            conn,
            f'''
            SELECT
                ID,
                NAME,
                ASSETS_TYPE,
                CODE,
                SOURCE_TYPE
            FROM `T_INTANGIBLE_ASSETS`
            WHERE TENANT_ID = %s
            ORDER BY NAME ASC, ID ASC
            ''',
            (tenant_id,),
        )

        assets: List[Dict[str, Any]] = []
        total_current_year = 0.0
        total_previous_year = 0.0
        for row in rows:
            asset_id = self._stringify(row[0])
            stat = amort_stats.get(asset_id, {})
            current_year_amount = self._round2(stat.get('current_year_amount', 0))
            previous_year_amount = self._round2(stat.get('previous_year_amount', 0))
            assets.append(
                {
                    'id': asset_id,
                    'name': self._stringify(row[1]),
                    'asset_type': self._intangible_type_name(row[2]),
                    'code': self._stringify(row[3]),
                    'specification': self._stringify(row[4]),
                    'year_amortization': current_year_amount,
                }
            )
            total_current_year += current_year_amount
            total_previous_year += previous_year_amount

        current_rd_amount = self._sum_amount_with_keywords(
            conn,
            table='T_VOUCHER',
            tenant_id=tenant_id,
            year=year,
            keywords=['无形资产摊销', '摊销'],
            amount_col='DETAILS_AMOUNT',
            year_col='VOUCHER_YEAR',
            name_candidates=['SUBJECT_CONFIG_NAME', 'COST_CONFIG_NAME'],
        )
        previous_rd_amount = self._sum_amount_with_keywords(
            conn,
            table='T_VOUCHER',
            tenant_id=tenant_id,
            year=year - 1,
            keywords=['无形资产摊销', '摊销'],
            amount_col='DETAILS_AMOUNT',
            year_col='VOUCHER_YEAR',
            name_candidates=['SUBJECT_CONFIG_NAME', 'COST_CONFIG_NAME'],
        )

        detail = {
            '该年预计摊销金额': self._round2(total_current_year),
            '去年已摊销金额': self._round2(total_previous_year),
            '该年研发预计投入金额': current_rd_amount,
            '去年已摊销研发金额': previous_rd_amount,
        }
        return detail, assets

    def _fetch_named_consumption_items(
        self,
        conn,
        table: str,
        tenant_id: str,
        year: int,
        quantity_col: str,
    ) -> List[Dict[str, Any]]:
        rows = self._safe_rows(
            conn,
            f'''
            SELECT
                NAME,
                SUM(COALESCE(AMOUNT, 0)) AS total_amount,
                SUM(COALESCE(`{quantity_col}`, 0)) AS total_quantity,
                MIN(ID) AS sample_id
            FROM `{table}`
            WHERE TENANT_ID = %s AND YEARS = %s
            GROUP BY NAME
            HAVING COALESCE(NAME, '') <> ''
            ORDER BY total_amount DESC, total_quantity DESC, NAME ASC
            ''',
            (tenant_id, year),
        )
        return [
            {
                'id': self._stringify(row[3]) or self._stringify(row[0]),
                'name': self._stringify(row[0]),
                'amount': self._round2(row[1]),
                'quantity': self._round2(row[2]),
            }
            for row in rows
        ]

    def _fetch_material_management_payload(self, conn, tenant_id: str, year: int) -> Dict[str, Any]:
        materials = self._fetch_named_consumption_items(conn, 'T_PROJECT_MATERIAL', tenant_id, year, 'USE_QUANTITY')
        fuels = self._fetch_named_consumption_items(conn, 'T_PROJECT_FUEL', tenant_id, year, 'CONSUME_QUANTITY')

        material_total = self._round2(sum(item['amount'] for item in materials))
        fuel_total = self._round2(sum(item['amount'] for item in fuels))
        material_top_qty = max(materials, key=lambda item: item['quantity'], default=None)
        material_top_amt = max(materials, key=lambda item: item['amount'], default=None)
        fuel_top_qty = max(fuels, key=lambda item: item['quantity'], default=None)
        fuel_top_amt = max(fuels, key=lambda item: item['amount'], default=None)

        return {
            'detail': {
                '今年燃料消耗总金额': fuel_total,
                '今年燃料消耗种类': len(fuels),
                '今年燃料消耗数量No.1': self._summary_label(fuel_top_qty['name'], fuel_top_qty['quantity']) if fuel_top_qty else '',
                '今年燃料消耗金额No.1': self._summary_label(fuel_top_amt['name'], fuel_top_amt['amount']) if fuel_top_amt else '',
                '今年材料消耗总金额': material_total,
                '今年材料消耗种类': len(materials),
                '今年材料消耗数量No.1': self._summary_label(material_top_qty['name'], material_top_qty['quantity']) if material_top_qty else '',
                '今年材料消耗金额No.1': self._summary_label(material_top_amt['name'], material_top_amt['amount']) if material_top_amt else '',
            },
            'materials': materials,
            'fuels': fuels,
        }

    def _fetch_power_management_detail(self, conn, tenant_id: str, year: int) -> Dict[str, Any]:
        total_current = 0.0
        total_previous = 0.0
        row = self._safe_one(
            conn,
            """
            SELECT
                SUM(CASE WHEN YEARS = %s THEN COALESCE(TOTAL_AMOUNT, 0) ELSE 0 END),
                SUM(CASE WHEN YEARS = %s THEN COALESCE(TOTAL_AMOUNT, 0) ELSE 0 END)
            FROM `T_PROJECT_POWER_CALCULATE`
            WHERE TENANT_ID = %s
            """,
            (year, year - 1, tenant_id),
        )
        total_current = self._round2(row[0] if row else 0)
        total_previous = self._round2(row[1] if row else 0)

        return {
            'detail': {
                '该年动力消耗金额': total_current,
                '去年动力消耗金额': total_previous,
            }
        }

    def _fetch_financial_voucher_detail(self, conn, tenant_id: str, year: int, current_month: int) -> Dict[str, Any]:
        amount_row = self._safe_one(
            conn,
            f'''
            SELECT SUM(COALESCE(DETAILS_AMOUNT, COALESCE(VOUCHER_AMOUNT, 0)))
            FROM `T_VOUCHER`
            WHERE TENANT_ID = %s AND VOUCHER_YEAR = %s
            ''',
            (tenant_id, year),
        )
        total_amount = self._round2(amount_row[0] if amount_row else 0)

        current_rows = self._safe_rows(
            conn,
            f'''
            SELECT DISTINCT VOUCHER_MONTH
            FROM `T_VOUCHER`
            WHERE TENANT_ID = %s
              AND VOUCHER_YEAR = %s
              AND VOUCHER_MONTH < %s
              AND COALESCE(LOCK_STATUS, 0) <> 9999
            ''',
            (tenant_id, year, current_month),
        )
        previous_rows = self._safe_rows(
            conn,
            f'''
            SELECT DISTINCT VOUCHER_MONTH
            FROM `T_VOUCHER`
            WHERE TENANT_ID = %s
              AND VOUCHER_YEAR = %s
              AND COALESCE(LOCK_STATUS, 0) <> 9999
            ''',
            (tenant_id, year - 1),
        )

        return {
            'detail': {
                '该年凭证金额': total_amount,
                '该未结账月数量': len(current_rows),
                '去年未结账月数量': len(previous_rows),
            }
        }

    def _fetch_expense_management_detail(self, conn, tenant_id: str, year: int) -> Dict[str, Any]:
        row = self._safe_one(
            conn,
            f'''
            SELECT
                SUM(COALESCE(R_D_ADDITIONAL_DEDUCTION_AMOUNT, 0)),
                SUM(COALESCE(R_D_VOUCHER_AMOUNT, 0)),
                SUM(COALESCE(HIGH_TECH_COLLECTION_AMOUNT, 0)),
                SUM(COALESCE(ACCOUNTING_STANDARDS_AMOUNT, 0))
            FROM `T_COST_MANAGE_COST_SECOND`
            WHERE TENANT_ID = %s AND YEARS = %s
            ''',
            (tenant_id, year),
        )
        rd_additional = self._round2(row[0] if row else 0)
        rd_voucher = self._round2(row[1] if row else 0)
        high_tech = self._round2(row[2] if row else 0)
        accounting = self._round2(row[3] if row else 0)

        rd_total = rd_additional if rd_additional != 0 else rd_voucher
        return {
            'detail': {
                '研发口径总额': rd_total,
                '高企口径总额': high_tech,
                '会计口径总额': accounting,
            }
        }

    def _fetch_invoice_management_detail(self, conn, tenant_id: str, year: int) -> Dict[str, Any]:
        row = self._safe_one(
            conn,
            f'''
            SELECT
                SUM(CASE WHEN YEARS = %s THEN COALESCE(INVOICE_TOTAL_AMOUNT, COALESCE(INVOICE_AMOUNT, 0)) ELSE 0 END),
                SUM(CASE WHEN YEARS = %s THEN COALESCE(INVOICE_TOTAL_AMOUNT, COALESCE(INVOICE_AMOUNT, 0)) ELSE 0 END),
                SUM(CASE WHEN YEARS = %s THEN COALESCE(INVOICE_TAX_AMOUNT, 0) ELSE 0 END),
                SUM(CASE WHEN YEARS = %s THEN COALESCE(INVOICE_TAX_AMOUNT, 0) ELSE 0 END)
            FROM `T_INVOICE`
            WHERE TENANT_ID = %s
            ''',
            (year, year - 1, year, year - 1, tenant_id),
        )

        return {
            'detail': {
                '该年发票总额': self._round2(row[0] if row else 0),
                '去年发票总额': self._round2(row[1] if row else 0),
                '该年发票税额': self._round2(row[2] if row else 0),
                '去年发票税额': self._round2(row[3] if row else 0),
            }
        }

    def _fetch_special_income_detail(self, conn, tenant_id: str, year: int) -> Dict[str, Any]:
        row = self._safe_one(
            conn,
            f'''
            SELECT
                SUM(CASE WHEN YEAR(SALE_TIME) = %s THEN COALESCE(AMOUNT, 0) ELSE 0 END),
                SUM(CASE WHEN YEAR(SALE_TIME) = %s THEN COALESCE(AMOUNT, 0) ELSE 0 END)
            FROM `T_SPECIAL_INCOME`
            WHERE TENANT_ID = %s
            ''',
            (year, year - 1, tenant_id),
        )

        return {
            'detail': {
                '该年特殊收入总额': self._round2(row[0] if row else 0),
                '去年特殊收入总额': self._round2(row[1] if row else 0),
            }
        }

    def _fetch_finance_root_detail(self, conn, tenant_id: str, year: int) -> Dict[str, Any]:
        rd_input_cost = 0.0
        top_subject = ''
        top_project = ''
        row = self._safe_one(
            conn,
            """
            SELECT SUM(COALESCE(R_D_VOUCHER_AMOUNT, 0))
            FROM `T_COST_MANAGE_COST_SUBJECT_SECOND`
            WHERE TENANT_ID = %s AND YEARS = %s
            """,
            (tenant_id, year),
        )
        rd_input_cost = self._round2(row[0] if row else 0)

        top_subject_row = self._safe_one(
            conn,
            """
            SELECT
                COALESCE(sc.NAME, CONCAT('科目#', s.SUBJECT_CONFIG_ID)) AS subject_name,
                SUM(COALESCE(s.R_D_VOUCHER_AMOUNT, 0)) AS total_amount
            FROM `T_COST_MANAGE_COST_SUBJECT_SECOND` s
            LEFT JOIN `T_SUBJECT_CONFIG` sc ON sc.ID = s.SUBJECT_CONFIG_ID
            WHERE s.TENANT_ID = %s AND s.YEARS = %s
            GROUP BY s.SUBJECT_CONFIG_ID, subject_name
            ORDER BY total_amount DESC, subject_name ASC
            LIMIT 1
            """,
            (tenant_id, year),
        )
        if top_subject_row:
            top_subject = self._summary_label(top_subject_row[0], top_subject_row[1])

        top_project_row = self._safe_one(
            conn,
            """
            SELECT
                COALESCE(p.PROJECT_NAME, CONCAT('项目#', s.PROJECT_ID)) AS project_name,
                SUM(COALESCE(s.R_D_VOUCHER_AMOUNT, 0)) AS total_amount
            FROM `T_COST_MANAGE_COST_SUBJECT_PROJECT_SECOND` s
            LEFT JOIN `T_PROJECT` p ON p.ID = s.PROJECT_ID
            WHERE s.TENANT_ID = %s AND s.YEARS = %s
            GROUP BY s.PROJECT_ID, project_name
            ORDER BY total_amount DESC, project_name ASC
            LIMIT 1
            """,
            (tenant_id, year),
        )
        if top_project_row:
            top_project = self._summary_label(top_project_row[0], top_project_row[1])

        over_budget_count = self._fetch_over_budget_project_count(conn, tenant_id, year)
        return {
            '该年研发投入成本': rd_input_cost,
            '该年研发费用类型成本top1': top_subject,
            '该年研发项目金额成本top1': top_project,
            '该年超预算项目数量': over_budget_count,
        }

    def _fetch_over_budget_project_count(self, conn, tenant_id: str, year: int) -> int:
        year_start = date(year, 1, 1)
        next_year_start = date(year + 1, 1, 1)
        rows = self._safe_rows(
            conn,
            f'''
            SELECT
                p.ID,
                p.GENERAL_BUDGET,
                COALESCE(SUM(COALESCE(c.R_D_VOUCHER_AMOUNT, 0)), 0) AS executed_amount
            FROM `T_PROJECT` p
            LEFT JOIN `T_COST_MANAGE_COST_PROJECT_SECOND` c
              ON c.PROJECT_ID = p.ID
             AND c.TENANT_ID = p.TENANT_ID
            WHERE p.TENANT_ID = %s
              AND COALESCE(p.START_DATE, %s) < %s
              AND COALESCE(p.END_DATE, %s) >= %s
            GROUP BY p.ID, p.GENERAL_BUDGET
            ''',
            (tenant_id, year_start, next_year_start, next_year_start, year_start),
        )
        count = 0
        for _, budget, executed in rows:
            if self._to_float(budget) > 0 and self._to_float(executed) > self._to_float(budget):
                count += 1
        return count

    def fetch_finance_domain(self, conn, tenant_id: str, year: int, current_month: int = 12) -> Dict[str, Any]:
        result = self._build_empty_finance_domain()

        result['detail'] = self._fetch_finance_root_detail(conn, tenant_id, year)

        fixed_detail, fixed_assets = self._fetch_fixed_asset_payload(conn, tenant_id, year, current_month)
        result['fixed_assets'] = {
            'detail': fixed_detail,
            'assets': fixed_assets,
        }

        intangible_detail, intangible_assets = self._fetch_intangible_asset_payload(conn, tenant_id, year)
        result['intangible_assets'] = {
            'detail': intangible_detail,
            'assets': intangible_assets,
        }

        result['material_management'] = self._fetch_material_management_payload(conn, tenant_id, year)
        result['power_management'] = self._fetch_power_management_detail(conn, tenant_id, year)
        result['financial_voucher'] = self._fetch_financial_voucher_detail(conn, tenant_id, year, current_month)
        result['expense_management'] = self._fetch_expense_management_detail(conn, tenant_id, year)
        result['invoice_management'] = self._fetch_invoice_management_detail(conn, tenant_id, year)
        result['special_income_management'] = self._fetch_special_income_detail(conn, tenant_id, year)
        return result
