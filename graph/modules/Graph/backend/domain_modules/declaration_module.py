
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..models.graph_models import GraphNode


class DeclarationGraphBuilderMixin:

    def build_declaration_file_nodes(
        self,
        parent_id: str,
        prefix: str,
        files: List[Dict[str, Any]],
        side: str = 'left',
    ) -> List[GraphNode]:
        nodes: List[GraphNode] = []
        for item in files or []:
            file_id = item.get('id', item.get('name', 'unknown'))
            basic = {'文件名称': item.get('name', f'文件_{file_id}')}
            if item.get('source_table'):
                basic['来源表'] = item.get('source_table')
            if item.get('created_at'):
                basic['创建时间'] = item.get('created_at')
            if item.get('path'):
                basic['文件路径'] = item.get('path')

            dynamic: Dict[str, Any] = {}
            if item.get('stat_note'):
                dynamic['统计口径'] = item.get('stat_note')
            if item.get('matched_by'):
                dynamic['匹配方式'] = item.get('matched_by')
            if item.get('row_count') not in (None, '', 'null'):
                dynamic['关联记录数'] = item.get('row_count')

            nodes.append(
                self._node(
                    node_id=f'4_{prefix}_{file_id}',
                    name=item.get('name', f'文件_{file_id}'),
                    node_type=f'4_{prefix}',
                    category='dynamic',
                    level=4,
                    side=side,
                    parent_id=parent_id,
                    identity_key=f'{prefix}:{file_id}',
                    fixed=False,
                    summary=item.get('summary', '文件节点'),
                    detail=self._detail(
                        basic=basic,
                        dynamic=dynamic,
                        description=item.get('description', '文件节点'),
                    ),
                    children=[],
                )
            )
        return nodes


class DeclarationRepositoryMixin:

    _DECLARATION_KEYWORDS = ('申报', '备查', '加计', '扣除', '高企', '高新', '研发支出')

    # =========================
    # 公共 SQL 小工具
    # =========================
    def _decl_year_bounds(self, year: int) -> Tuple[date, date]:
        return self._year_range(year)

    def _decl_year_filter(
        self,
        conn,
        table_name: str,
        alias: str,
        tenant_id: str,
        year: int,
        allow_create_time: bool = True,
    ) -> Tuple[List[str], List[Any]]:
        clauses: List[str] = [
            f"{alias}.`TENANT_ID` = %s",
            f"({alias}.`ENABLE_STATUS` IS NULL OR {alias}.`ENABLE_STATUS` <> 7777)",
            f"({alias}.`RELATION_STATUS` IS NULL OR {alias}.`RELATION_STATUS` <> 7777)",
            f"{alias}.`YEARS` = %s",
        ]
        params: List[Any] = [tenant_id, year]
        return clauses, params

    def _decl_sum_year(
        self,
        conn,
        table_name: str,
        amount_candidates: Sequence[str],
        tenant_id: str,
        year: int,
        extra_where: str = '',
        extra_params: Sequence[Any] = (),
        allow_create_time: bool = True,
    ) -> Optional[float]:
        amount_col = amount_candidates[0]

        clauses, params = self._decl_year_filter(
            conn=conn,
            table_name=table_name,
            alias='t',
            tenant_id=tenant_id,
            year=year,
            allow_create_time=allow_create_time,
        )
        if not clauses:
            return None
        if extra_where:
            clauses.append(extra_where)
            params.extend(list(extra_params))

        sql = f"""
            SELECT COALESCE(SUM(t.`{amount_col}`), 0)
            FROM `{table_name}` t
            WHERE {' AND '.join(clauses)}
        """
        row = self._safe_one(conn, sql, tuple(params))
        if row is None:
            return None
        return self._to_float(row[0])

    def _decl_count_year_rows(
        self,
        conn,
        table_name: str,
        tenant_id: str,
        year: int,
        extra_where: str = '',
        extra_params: Sequence[Any] = (),
        allow_create_time: bool = True,
    ) -> Optional[int]:
        clauses, params = self._decl_year_filter(
            conn=conn,
            table_name=table_name,
            alias='t',
            tenant_id=tenant_id,
            year=year,
            allow_create_time=allow_create_time,
        )
        if not clauses:
            return None
        if extra_where:
            clauses.append(extra_where)
            params.extend(list(extra_params))

        sql = f"""
            SELECT COUNT(1)
            FROM `{table_name}` t
            WHERE {' AND '.join(clauses)}
        """
        row = self._safe_one(conn, sql, tuple(params))
        if row is None:
            return None
        return self._to_int(row[0])

    def _decl_count_year_distinct(
        self,
        conn,
        table_name: str,
        distinct_candidates: Sequence[str],
        tenant_id: str,
        year: int,
        extra_where: str = '',
        extra_params: Sequence[Any] = (),
        allow_create_time: bool = True,
    ) -> Optional[int]:
        distinct_col = distinct_candidates[0]

        clauses, params = self._decl_year_filter(
            conn=conn,
            table_name=table_name,
            alias='t',
            tenant_id=tenant_id,
            year=year,
            allow_create_time=allow_create_time,
        )
        if not clauses:
            return None

        clauses.append(f"t.`{distinct_col}` IS NOT NULL")
        clauses.append(f"CAST(t.`{distinct_col}` AS CHAR) <> ''")
        if extra_where:
            clauses.append(extra_where)
            params.extend(list(extra_params))

        sql = f"""
            SELECT COUNT(DISTINCT t.`{distinct_col}`)
            FROM `{table_name}` t
            WHERE {' AND '.join(clauses)}
        """
        row = self._safe_one(conn, sql, tuple(params))
        if row is None:
            return None
        return self._to_int(row[0])

    def _decl_pick_first_metric(self, candidates: Sequence[Tuple[Optional[float], str]]) -> Tuple[float, str]:
        for value, source in candidates:
            if value is not None:
                return self._to_float(value), source
        return 0.0, ''

    def _decl_pick_first_count(self, candidates: Sequence[Tuple[Optional[int], str]]) -> Tuple[int, str]:
        for value, source in candidates:
            if value is not None:
                return self._to_int(value), source
        return 0, ''

    def _decl_format_amount(self, value: float) -> str:
        return f'{value:.2f}'

    def _decl_make_analysis(self, mapping: Dict[str, str]) -> Dict[str, Any]:
        return {k: v for k, v in mapping.items() if v}

    # =========================
    # 申报文件 / 备查文件
    # =========================
    def _fetch_annex_files_by_keywords(
        self,
        conn,
        tenant_id: str,
        year: int,
        keywords: Sequence[str],
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], str]:
        keyword_clauses: List[str] = []
        params: List[Any] = [tenant_id]
        year_start, next_year_start = self._decl_year_bounds(year)
        params.extend([year_start, next_year_start])
        for keyword in keywords:
            cleaned = str(keyword or '').strip()
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
            return [], '未提供有效的文件匹配关键词。'

        sql = f"""
            SELECT
                a.`ID` AS file_id,
                a.`OLD_NAME` AS old_name,
                a.`NEW_NAME` AS new_name,
                a.`CREATE_TIME` AS create_time,
                a.`PATH` AS file_path,
                a.`GROUP_CODE` AS annex_group_code,
                g.`NAME` AS group_name,
                g.`CODE` AS group_code
            FROM `T_ANNEX` a
            LEFT JOIN `T_GROUP` g ON a.`GROUP_ID` = g.`ID`
            WHERE a.`TENANT_ID` = %s
              AND a.`CREATE_TIME` >= %s
              AND a.`CREATE_TIME` < %s
              AND (a.`RELATION_STATUS` IS NULL OR a.`RELATION_STATUS` <> 7777)
              AND (a.`ENABLE_STATUS` IS NULL OR a.`ENABLE_STATUS` <> 7777)
              AND ({' OR '.join(keyword_clauses)})
            ORDER BY a.`CREATE_TIME` DESC, a.`ID` DESC
            LIMIT {int(limit)}
        """
        rows = self._safe_rows(conn, sql, tuple(params))
        files: List[Dict[str, Any]] = []
        for row in rows:
            file_id = self._stringify(row[0])
            old_name = self._stringify(row[1])
            new_name = self._stringify(row[2])
            created_at = self._stringify(row[3])
            path = self._stringify(row[4])
            annex_group_code = self._stringify(row[5])
            group_name = self._stringify(row[6]) if len(row) > 6 else ''
            group_code = self._stringify(row[7]) if len(row) > 7 else ''

            display_name = old_name or new_name or path or f'附件_{file_id}'
            matched_fields = [field for field in [group_name, group_code, annex_group_code] if field]
            files.append(
                {
                    'id': file_id,
                    'name': display_name,
                    'created_at': created_at,
                    'path': path,
                    'source_table': 'T_ANNEX',
                    'summary': '附件文件',
                    'description': '来自通用附件表的年度文件记录。',
                    'matched_by': '文件名/分组关键词匹配',
                    'stat_note': '按 T_ANNEX 与 T_GROUP 的文件名、分组代码、描述关键词匹配抽取。',
                    'row_count': 1,
                    'group_name': group_name,
                    'group_code': group_code or annex_group_code,
                    'extra': ' / '.join(matched_fields),
                }
            )

        if files:
            return files, '文件数量优先按 T_ANNEX/T_GROUP 的关键词匹配统计。'
        return [], 'T_ANNEX 中未命中对应关键词文件；如业务侧未规范文件命名，可能存在漏记。'

    def _fetch_table_backed_report_files(
        self,
        conn,
        tenant_id: str,
        year: int,
        definitions: Sequence[Tuple[str, Sequence[str]]],
    ) -> Tuple[List[Dict[str, Any]], str]:
        files: List[Dict[str, Any]] = []
        for name, table_candidates in definitions:
            chosen_table = ''
            row_count = 0
            for table_name in table_candidates:
                count = self._decl_count_year_rows(conn, table_name, tenant_id, year)
                if count is None or count <= 0:
                    continue
                chosen_table = table_name
                row_count = count
                break

            if not chosen_table:
                continue

            files.append(
                {
                    'id': f'{chosen_table}:{year}',
                    'name': name,
                    'source_table': chosen_table,
                    'summary': f'记录数：{row_count}',
                    'description': '未发现独立文件实体表时，按该年存在数据的报表类型生成图谱叶子节点。',
                    'stat_note': '该节点不是物理附件，而是按“年度有数据的报表类型”生成的逻辑文件节点。',
                    'matched_by': '报表数据落库',
                    'row_count': row_count,
                }
            )

        if files:
            return files, '缺少专用申报文件实体表时，文件数量按“有年度数据的报表类型数”回填。'
        return [], '相关报表表在该年度无数据，无法构造逻辑文件节点。'

    def _fetch_system_generated_files(self, conn, tenant_id: str, year: int, limit: int = 50) -> Tuple[List[Dict[str, Any]], str]:
        params: List[Any] = [tenant_id, year]
        sql = f"""
            SELECT
                t.`ID` AS file_id,
                t.`SERVICE_CODE` AS service_code,
                t.`CREATE_TIME` AS create_time
            FROM `T_REVIEW_DOCUMENTS_QUEUE` t
            WHERE t.`TENANT_ID` = %s
              AND t.`YEAR` = %s
              AND (t.`EXE_STATUS` IS NULL OR t.`EXE_STATUS` <> 7777)
              AND (t.`ENABLE_STATUS` IS NULL OR t.`ENABLE_STATUS` <> 7777)
            ORDER BY t.`CREATE_TIME` DESC, t.`ID` DESC
            LIMIT {int(limit)}
        """
        rows = self._safe_rows(conn, sql, tuple(params))
        files: List[Dict[str, Any]] = []
        for row in rows:
            file_id = self._stringify(row[0])
            service_code = self._stringify(row[1]).strip()
            created_at = self._stringify(row[2]) if len(row) > 2 else ''
            display_name = service_code or f'系统生成备查文件_{file_id}'
            files.append(
                {
                    'id': file_id,
                    'name': display_name,
                    'created_at': created_at,
                    'source_table': 'T_REVIEW_DOCUMENTS_QUEUE',
                    'summary': '系统生成任务',
                    'description': '来自备查文件生成队列表的系统生成记录。',
                    'matched_by': '队列表年度记录',
                    'stat_note': '按 T_REVIEW_DOCUMENTS_QUEUE 的年度任务记录统计系统生成文件数量。',
                    'row_count': 1,
                }
            )

        if files:
            return files, '系统生成数量直接按 T_REVIEW_DOCUMENTS_QUEUE 年度记录统计。'
        return [], 'T_REVIEW_DOCUMENTS_QUEUE 在该年度无生成记录。'

    # =========================
    # 主域装配
    # =========================
    def fetch_declaration_domain(self, conn, tenant_id: str, year: int) -> Dict[str, Any]:
        # 1) 顶层指标
        ad_total, ad_total_source = self._decl_pick_first_metric(
            [
                (
                    self._decl_sum_year(conn, 'T_AD_ADDITIONAL_DEDUCTION_YEARS', ['AMOUNT'], tenant_id, year),
                    'T_AD_ADDITIONAL_DEDUCTION_YEARS.AMOUNT',
                ),
                (
                    self._decl_sum_year(conn, 'T_AD_ADDITIONAL_DEDUCTION', ['AMOUNT'], tenant_id, year),
                    'T_AD_ADDITIONAL_DEDUCTION.AMOUNT',
                ),
                (
                    self._decl_sum_year(
                        conn,
                        'T_AD_EXPENDITURE_ASSISTANCE_TOTAL_YEARS',
                        ['ADDITIONAL_DEDUCTION_TOTAL'],
                        tenant_id,
                        year,
                    ),
                    'T_AD_EXPENDITURE_ASSISTANCE_TOTAL_YEARS.ADDITIONAL_DEDUCTION_TOTAL',
                ),
                (
                    self._decl_sum_year(
                        conn,
                        'T_AD_EXPENDITURE_ASSISTANCE_TOTAL',
                        ['ADDITIONAL_DEDUCTION_TOTAL'],
                        tenant_id,
                        year,
                    ),
                    'T_AD_EXPENDITURE_ASSISTANCE_TOTAL.ADDITIONAL_DEDUCTION_TOTAL',
                ),
            ]
        )

        deductible_project_count, project_count_source = self._decl_pick_first_count(
            [
                (
                    self._decl_count_year_distinct(
                        conn,
                        'T_AD_ADDITIONAL_DEDUCTION_YEARS',
                        ['ADDITIONAL_DEDUCTION_PROJECT_ID', 'ADDITIONAL_DEDUCTION_PROJECT_NAME'],
                        tenant_id,
                        year,
                    ),
                    'T_AD_ADDITIONAL_DEDUCTION_YEARS 按项目去重',
                ),
                (
                    self._decl_count_year_distinct(
                        conn,
                        'T_AD_ADDITIONAL_DEDUCTION',
                        ['ADDITIONAL_DEDUCTION_PROJECT_ID'],
                        tenant_id,
                        year,
                    ),
                    'T_AD_ADDITIONAL_DEDUCTION 按项目去重',
                ),
                (
                    self._decl_count_year_distinct(
                        conn,
                        'T_COST_MANAGE_DETAIL_ADDITIONAL_DEDUCTION',
                        ['PROJECT_ID'],
                        tenant_id,
                        year,
                        extra_where='COALESCE(t.`AMOUNT`, 0) <> 0',
                    ),
                    'T_COST_MANAGE_DETAIL_ADDITIONAL_DEDUCTION 按 PROJECT_ID 去重',
                ),
            ]
        )

        rd_collection_amount, rd_collection_source = self._decl_pick_first_metric(
            [
                (
                    self._decl_sum_year(conn, 'T_AD_EXPENDITURE_ASSISTANCE', ['TAX_LAW_AMOUNT'], tenant_id, year),
                    'T_AD_EXPENDITURE_ASSISTANCE.TAX_LAW_AMOUNT',
                ),
                (
                    self._decl_sum_year(conn, 'T_COST_MANAGE_DETAIL_ADDITIONAL_DEDUCTION', ['AMOUNT'], tenant_id, year),
                    'T_COST_MANAGE_DETAIL_ADDITIONAL_DEDUCTION.AMOUNT',
                ),
            ]
        )

        hightech_allowed_amount, hightech_allowed_source = self._decl_pick_first_metric(
            [
                (
                    self._decl_sum_year(
                        conn,
                        'T_HD_EXPENDITURE_ASSISTANCE_TOTAL_YEARS',
                        ['HIGH_TECH_TOTAL_AMOUNT'],
                        tenant_id,
                        year,
                    ),
                    'T_HD_EXPENDITURE_ASSISTANCE_TOTAL_YEARS.HIGH_TECH_TOTAL_AMOUNT',
                ),
                (
                    self._decl_sum_year(
                        conn,
                        'T_HD_EXPENDITURE_ASSISTANCE_TOTAL',
                        ['HIGH_TECH_TOTAL_AMOUNT'],
                        tenant_id,
                        year,
                    ),
                    'T_HD_EXPENDITURE_ASSISTANCE_TOTAL.HIGH_TECH_TOTAL_AMOUNT',
                ),
            ]
        )

        hightech_collection_amount, hightech_collection_source = self._decl_pick_first_metric(
            [
                (
                    self._decl_sum_year(conn, 'T_HD_EXPENDITURE_ASSISTANCE', ['TAX_LAW_AMOUNT'], tenant_id, year),
                    'T_HD_EXPENDITURE_ASSISTANCE.TAX_LAW_AMOUNT',
                ),
                (
                    self._decl_sum_year(
                        conn,
                        'T_HD_COST_STRUCTURE_DETAILS_YEARS',
                        ['INTERNAL_RESEARCH_EXPENSES'],
                        tenant_id,
                        year,
                    ),
                    'T_HD_COST_STRUCTURE_DETAILS_YEARS.INTERNAL_RESEARCH_EXPENSES（兜底）',
                ),
            ]
        )

        # 2) 申报文件
        annex_ad_files, annex_ad_note = self._fetch_annex_files_by_keywords(
            conn,
            tenant_id,
            year,
            ['加计扣除', '加计', '扣除', '研发支出辅助'],
        )
        fallback_ad_files, fallback_ad_note = self._fetch_table_backed_report_files(
            conn,
            tenant_id,
            year,
            [
                ('加计扣除报', ['T_AD_ADDITIONAL_DEDUCTION_YEARS', 'T_AD_ADDITIONAL_DEDUCTION']),
                ('研发支出辅助表', ['T_AD_EXPENDITURE_ASSISTANCE']),
                ('研发支出辅助汇总表', ['T_AD_EXPENDITURE_ASSISTANCE_TOTAL']),
                ('研发支出辅助汇总表（年）', ['T_AD_EXPENDITURE_ASSISTANCE_TOTAL_YEARS']),
                ('加计扣除年比率表', ['T_AD_ANNUAL_RATIO']),
                ('费用明细-加计扣除', ['T_COST_MANAGE_DETAIL_ADDITIONAL_DEDUCTION']),
            ],
        )
        additional_deduction_files = annex_ad_files or fallback_ad_files
        additional_files_note = annex_ad_note if annex_ad_files else fallback_ad_note

        annex_hd_files, annex_hd_note = self._fetch_annex_files_by_keywords(
            conn,
            tenant_id,
            year,
            ['高企', '高新', '优惠情况', '费用结构'],
        )
        fallback_hd_files, fallback_hd_note = self._fetch_table_backed_report_files(
            conn,
            tenant_id,
            year,
            [
                ('高企费用结构明细表', ['T_HD_COST_STRUCTURE_DETAILS_YEARS', 'T_HD_COST_STRUCTURE_DETAILS']),
                ('高企研发支出辅助表', ['T_HD_EXPENDITURE_ASSISTANCE']),
                ('高企研发支出辅助汇总表', ['T_HD_EXPENDITURE_ASSISTANCE_TOTAL_YEARS', 'T_HD_EXPENDITURE_ASSISTANCE_TOTAL']),
                ('高企优惠情况明细表', ['T_HD_PROMOTION_DETAILS_YEARS', 'T_HD_PROMOTION_DETAILS']),
            ],
        )
        high_tech_files = annex_hd_files or fallback_hd_files
        hightech_files_note = annex_hd_note if annex_hd_files else fallback_hd_note

        declaration_file_count = len(additional_deduction_files) + len(high_tech_files)

        # 3) 备查文件
        enterprise_upload_files, enterprise_upload_note = self._fetch_annex_files_by_keywords(
            conn,
            tenant_id,
            year,
            ['备查', '留存', '辅助账', '辅助明细', '研发支出'],
        )
        system_generated_files, system_generated_note = self._fetch_system_generated_files(
            conn,
            tenant_id,
            year,
        )
        backup_file_count = len(enterprise_upload_files) + len(system_generated_files)

        return {
            'summary': f'加计扣除总额：{self._decl_format_amount(ad_total)}',
            'detail': {
                '本年研发费用加计扣除总额': ad_total,
                '本年可享受研发费用加计扣除项目数量': deductible_project_count,
            },
            'detail_description': '申报备查总览。',
            'detail_analysis': self._decl_make_analysis(
                {
                    '加计扣除总额口径': f'优先取 {ad_total_source}。' if ad_total_source else '未找到可直接汇总研发费用加计扣除总额的年度表，当前返回 0。',
                    '项目数量口径': f'优先取 {project_count_source}。' if project_count_source else '未找到能与年度直接关联的项目统计表，当前返回 0。',
                }
            ),
            'declaration_files': {
                'detail': {
                    '本年研发费用加计扣除总额': ad_total,
                    '本年申报文件数量': declaration_file_count,
                    '本年研发归集金额': rd_collection_amount,
                    '本年高企归集金额': hightech_collection_amount,
                },
                'detail_description': '申报文件汇总。',
                'detail_analysis': self._decl_make_analysis(
                    {
                        '申报文件数量口径': '优先按附件表命中的真实文件统计；若无专用文件记录，则按“有年度数据的报表类型数”回填。',
                        '研发归集金额口径': f'优先取 {rd_collection_source}。' if rd_collection_source else '库表中未发现稳定的“研发归集金额”年度口径字段，当前返回 0。',
                        '高企归集金额口径': f'优先取 {hightech_collection_source}。' if hightech_collection_source else '库表中未发现稳定的“高企归集金额”年度口径字段，当前返回 0。',
                    }
                ),
                'additional_deduction_detail': {
                    '本年研发费用加计扣除总额': ad_total,
                    '该年文件数量': len(additional_deduction_files),
                    '本年研发归集金额': rd_collection_amount,
                },
                'additional_deduction_description': '加计扣除相关报表。',
                'additional_deduction_analysis': self._decl_make_analysis(
                    {
                        '统计说明': additional_files_note,
                        '加计扣除总额来源': ad_total_source,
                        '研发归集金额来源': rd_collection_source,
                    }
                ),
                'additional_deduction_files': additional_deduction_files,
                'high_tech_detail': {
                    '允许计入高新企业认定金额': hightech_allowed_amount,
                    '该年文件数量': len(high_tech_files),
                    '本年高企归集金额': hightech_collection_amount,
                },
                'high_tech_description': '高企相关报表。',
                'high_tech_analysis': self._decl_make_analysis(
                    {
                        '统计说明': hightech_files_note,
                        '允许计入高新企业认定金额来源': hightech_allowed_source,
                        '高企归集金额来源': hightech_collection_source,
                    }
                ),
                'high_tech_files': high_tech_files,
            },
            'backup_files': {
                'detail': {
                    '本年备查文件数量': backup_file_count,
                    '本年可享受研发费用加计扣除项目数量': deductible_project_count,
                },
                'detail_description': '备查文件汇总。',
                'detail_analysis': self._decl_make_analysis(
                    {
                        '备查文件数量口径': '备查文件数量 = 企业文件上传数量 + 系统文件生成数量。',
                        '项目数量来源': project_count_source,
                    }
                ),
                'enterprise_upload_detail': {
                    '本年备查-企业文件上传数量': len(enterprise_upload_files),
                    '本年可享受研发费用加计扣除项目数量': deductible_project_count,
                },
                'enterprise_upload_description': '企业文件上传。',
                'enterprise_upload_analysis': self._decl_make_analysis(
                    {
                        '统计说明': enterprise_upload_note,
                        '风险提示': '企业上传文件依赖 T_ANNEX/T_GROUP 的命名或分组匹配；若业务未规范命名，统计结果可能偏小。'
                        if enterprise_upload_files or 'T_ANNEX' in enterprise_upload_note
                        else enterprise_upload_note,
                    }
                ),
                'enterprise_upload_files': enterprise_upload_files,
                'system_generated_detail': {
                    '本年备查-系统文件生成数量': len(system_generated_files),
                    '本年可享受研发费用加计扣除项目数量': deductible_project_count,
                },
                'system_generated_description': '系统生成。',
                'system_generated_analysis': self._decl_make_analysis(
                    {
                        '统计说明': system_generated_note,
                        '项目数量来源': project_count_source,
                    }
                ),
                'system_generated_files': system_generated_files,
            },
        }
