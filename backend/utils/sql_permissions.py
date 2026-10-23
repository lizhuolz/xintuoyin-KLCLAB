"""Text2SQL 的租户/项目权限与独立业务资源。"""

import csv
import json
from functools import lru_cache
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import Scope, traverse_scope

RESOURCE_DIR = Path(__file__).resolve().parents[1] / "resources" / "sql_permissions"
ALL_PROJECT_ACCESS = "__ALL_PROJECT_ACCESS__"


class SQLAccessDenied(ValueError):
    """查询无法安全限定到当前用户权限范围。"""


def positive_id(value, name):
    if isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
        raise SQLAccessDenied(f"缺少有效的 {name}")
    return int(value)


@lru_cache(maxsize=1)
def load_table_policy():
    with (RESOURCE_DIR / "table_policy.json").open(encoding="utf-8") as stream:
        policy = json.load(stream)
    return frozenset(policy["allowed_tables"]), frozenset(policy["project_tables"])


@lru_cache(maxsize=1)
def load_type_mapping():
    mapping = {}
    with (RESOURCE_DIR / "type_table.csv").open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            parent, value, description = (
                row.get("PARENT_TYPE_CODE"), row.get("TYPE_VALUE"), row.get("DESCRIPTION")
            )
            if parent and value is not None and description:
                mapping.setdefault(parent, {})[value] = description
    return mapping


# 仅开放无外部副作用的常用 MySQL 内置函数；自定义函数不在此范围内。
READ_FUNCTIONS = frozenset("""
ABS ACOS ADDDATE ASCII ASIN ATAN ATAN2 AVG CASE CAST CEIL CEILING CHAR_LENGTH
CHARACTER_LENGTH COALESCE CONCAT CONCAT_WS CONVERT COS COUNT CURDATE CURRENT_DATE
CURRENT_TIMESTAMP DATE DATE_ADD DATE_FORMAT DATE_SUB DATEDIFF DAY DAYOFMONTH
DAYOFWEEK DAYOFYEAR DENSE_RANK EXISTS EXP EXTRACT FLOOR FORMAT GREATEST GROUP_CONCAT
HOUR IF IFNULL JSON_ARRAY JSON_EXTRACT JSON_LENGTH JSON_OBJECT JSON_UNQUOTE LAG
LAST_DAY LEAD LEAST LEFT LENGTH LN LOG LOG10 LOWER LPAD LTRIM MAX MIN MINUTE
MOD MONTH MONTHNAME NOW NULLIF POWER RANK REPLACE RIGHT ROUND ROW_NUMBER RPAD
RTRIM SIGN SIN SQRT STDDEV STDDEV_POP STDDEV_SAMP STR_TO_DATE SUBSTR SUBSTRING
SUM TAN TIME TIMESTAMP TIMESTAMPDIFF TRIM TRUNCATE UPPER VAR_POP VAR_SAMP
VARIANCE WEEK WEEKDAY WEEKOFYEAR YEAR YEARWEEK
""".split())


class SQLPermissions:
    def __init__(self, tenant_id, staff_id, *, allow_all_projects=False):
        self.tenant_id = positive_id(tenant_id, "tenant_id")
        self.staff_id = None if staff_id is None else positive_id(staff_id, "staff_id")
        self.allow_all_projects = bool(allow_all_projects)
        if self.staff_id is None and not self.allow_all_projects:
            raise SQLAccessDenied("普通用户必须提供 staff_id")
        self.allowed_tables, self.project_tables = load_table_policy()
        self.project_ids = ()
        self.project_names = ()

    def is_project_table(self, name, columns):
        return name in self.project_tables or "PROJECT_ID" in columns

    def type_hint(self, question):
        text = str(question).lower()
        hits = []
        for parent, values in load_type_mapping().items():
            pairs = [(value, desc) for value, desc in values.items() if desc.lower() in text]
            if pairs:
                hits.append((parent, pairs))
        hits.sort(key=lambda hit: len(hit[1]), reverse=True)
        return "\n".join(
            f"- {parent}: " + "; ".join(f"{value}: {desc}" for value, desc in pairs[:30])
            for parent, pairs in hits[:20]
        ) or "N/A"

    def access_hint(self):
        return (
            f"Every business table must be restricted to TENANT_ID = {self.tenant_id}. "
            "For each table containing OPERATER_STATUS, enforce OPERATER_STATUS > 0. "
            "Only read-only SELECT queries are allowed; never query other schemas."
        )

    def project_hint(self):
        if self.allow_all_projects:
            return "All valid projects in the current tenant are accessible."
        if not self.project_ids:
            return "No authorized projects. Return 'I do not know'."
        return (
            "Only these project IDs and names are authorized: "
            + json.dumps(list(zip(self.project_ids, self.project_names)), ensure_ascii=False)
            + ". Filter t_project by ID, project detail tables by PROJECT_ID; "
            "join t_project when a project name is needed. Never use a project outside this list."
        )

    def _project_condition(self, name, columns):
        if not self.is_project_table(name, columns) or self.allow_all_projects:
            return None
        if not self.project_ids:
            raise SQLAccessDenied("当前员工无可访问项目")
        if name == "t_project":
            key = "ID"
        elif "PROJECT_ID" in columns:
            key = "PROJECT_ID"
        else:
            raise SQLAccessDenied(f"表 {name} 的项目权限关联尚未配置，拒绝查询")
        if key not in columns:
            raise SQLAccessDenied(f"表 {name} 缺少项目权限字段")
        return exp.In(
            this=exp.column(key, quoted=True),
            expressions=[exp.Literal.number(value) for value in self.project_ids],
        )

    def restrict_sql(self, sql, table_columns):
        """将每个物理表替换为权限过滤后的派生表，覆盖 JOIN/CTE/子查询/UNION。"""
        try:
            statements = [node for node in sqlglot.parse(sql, read="mysql") if node is not None]
        except sqlglot.errors.SqlglotError as exc:
            raise SQLAccessDenied("SQL 无法安全解析") from exc
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union)):
            raise SQLAccessDenied("仅允许单条只读 SELECT 查询")
        tree = statements[0]
        forbidden = (exp.Into, exp.Lock, exp.DML, exp.DDL, exp.Command, exp.Parameter,
                     exp.SessionParameter, exp.Placeholder, exp.Hint, exp.Dot)
        date_units = {"YEAR", "QUARTER", "MONTH", "WEEK", "DAY", "HOUR", "MINUTE", "SECOND", "MICROSECOND"}
        for node in tree.walk():
            if isinstance(node, forbidden):
                raise SQLAccessDenied("SQL 包含不允许的操作")
            if isinstance(node, exp.Var) and node.name.upper() not in date_units:
                raise SQLAccessDenied("SQL 包含不允许的变量")
            if isinstance(node, exp.Func):
                name = node.name.upper() if isinstance(node, exp.Anonymous) else node.sql_name().upper()
                if name not in READ_FUNCTIONS and not isinstance(node, (exp.And, exp.Or)):
                    raise SQLAccessDenied(f"SQL 函数 {name} 未获准使用")
        for cte in tree.find_all(exp.CTE):
            if not isinstance(cte.this, (exp.Select, exp.Union)):
                raise SQLAccessDenied("不支持此 CTE 类型")
        if any(node.args.get("recursive") for node in tree.find_all(exp.With)):
            raise SQLAccessDenied("不支持递归查询")
        for subquery in tree.find_all(exp.Subquery):
            if not isinstance(subquery.this, (exp.Select, exp.Union)):
                raise SQLAccessDenied("不支持此子查询类型")
        tables = []
        classified_tables = set()
        try:
            for scope in traverse_scope(tree):
                # selected_sources checks duplicate aliases; sources alone can
                # silently overwrite a physical table with a same-named CTE.
                for node, source in scope.selected_sources.values():
                    if not isinstance(node, exp.Table):
                        continue
                    if isinstance(source, exp.Table) and source is node:
                        tables.append(source)
                    elif (
                        isinstance(source, Scope)
                        and not node.db
                        and not node.catalog
                        and scope.cte_sources.get(node.name) is source
                    ):
                        # A CTE reference is safe only after its physical
                        # sources are independently classified and filtered.
                        pass
                    else:
                        raise SQLAccessDenied("无法安全确定查询的数据来源")
                    classified_tables.add(id(node))
        except sqlglot.errors.SqlglotError as exc:
            raise SQLAccessDenied("SQL 数据来源存在歧义") from exc
        if classified_tables != {id(table) for table in tree.find_all(exp.Table)}:
            raise SQLAccessDenied("SQL 包含无法验证权限的数据来源")
        if not tables:
            raise SQLAccessDenied("查询必须访问授权业务表")
        for table in tables:
            name = table.name.lower()
            if table.db or table.catalog or name not in self.allowed_tables:
                raise SQLAccessDenied("查询包含未授权数据库或表")
            if any(value for key, value in table.args.items() if key not in {"this", "alias"}):
                raise SQLAccessDenied("不支持带扩展选项的表访问")
            alias_node = table.args.get("alias")
            if alias_node and alias_node.args.get("columns"):
                raise SQLAccessDenied("不支持表字段别名列表")
            columns = table_columns.get(name)
            if not columns or "TENANT_ID" not in columns:
                raise SQLAccessDenied(f"表 {name} 无可验证的租户字段")
            conditions = [exp.EQ(this=exp.column("TENANT_ID", quoted=True), expression=exp.Literal.number(self.tenant_id))]
            if "OPERATER_STATUS" in columns:
                conditions.append(exp.GT(this=exp.column("OPERATER_STATUS", quoted=True), expression=exp.Literal.number(0)))
            project_condition = self._project_condition(name, columns)
            if project_condition is not None:
                conditions.append(project_condition)
            alias = table.alias_or_name
            filtered = exp.select("*").from_(exp.Table(this=table.this.copy())).where(*conditions)
            replacement = filtered.subquery(alias=alias)
            if alias_node:
                replacement.set("alias", alias_node.copy())
            table.replace(replacement)
        return tree.sql(dialect="mysql")
