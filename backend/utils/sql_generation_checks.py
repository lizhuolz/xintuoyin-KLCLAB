"""Generation diagnostics; authorization and SQL rewriting stay in SQLPermissions."""
from decimal import Decimal, InvalidOperation
import re

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope


# Entity identities describe the schema, not test questions or expected answers.
ENTITY_IDENTITIES = {
    'project': ('t_project', {'ID', 'PROJECT_NAME', 'PROJECT_RESEARCH_SERIAL_NO', 'PROJECT_RESEARCH_NO'},
                ('项目', 'project', 'projects')),
    'staff': ('t_staff', {'ID', 'FULL_NAME', 'WORK_NUM'},
              ('项目成员', '参与成员', '员工', '人员', '成员', 'employee', 'employees', 'staff', 'member', 'members')),
    'milestone': ('t_project_milestone', {'ID', 'NAME'}, ('里程碑', 'milestone', 'milestones')),
    'result': ('t_project_results', {'ID', 'NAME'}, ('研发成果', '成果', 'achievement', 'achievements')),
}


class SQLGenerationError(ValueError):
    """The model must correct a query before it is executed."""


def _listed_entity(question):
    """Infer an unambiguous requested row entity; do not widen explicit projections."""
    question = question or ''
    if re.search(r'(?:只|仅)(?:需|要)?(?:列|返回|展示|输出|报告)|\bonly\b', question, re.I):
        return None
    marker = re.search(r'有哪些|哪些|哪个|哪几个|哪位|每个|各个|逐位|逐个|\b(?:which|list|each)\b', question, re.I)
    if not marker:
        return None
    nouns = {term: kind for kind, (_, _, terms) in ENTITY_IDENTITIES.items() for term in terms}
    attributes = ['研究内容', '技术风险', '风险点', '内容', '字段', '指标', '月份', '年份', '年度', '季度', '日期', '部门', '状态', '类型', '费用', '工号',
                  'month', 'months', 'year', 'years', 'department', 'departments']
    words = sorted(list(nouns) + attributes, key=len, reverse=True)
    token = re.compile('|'.join(re.escape(word) for word in words), re.I)
    tail = re.split(r'[，,。；;？?]', question[marker.end():], maxsplit=1)[0]
    if re.match(r'人(?:$|没有|已|未|在|的|参与|同时|符合|至少|拥有|是|不)', tail):
        return 'staff'
    found = token.search(tail)
    if found:
        kind = nouns.get(found.group().lower())
    else:
        # Ellipsis: "未删除项目中，开始日期在2024年的有哪些？"
        prefix = question[:marker.start()]
        if re.search(r'(?:内容|风险点|技术风险|字段|指标|月份|年份|年度|季度|日期|部门|状态|类型)\s*(?:都|还)?$', prefix):
            return None
        mentions = list(token.finditer(prefix))
        entity_mentions = [m for m in mentions if m.group().lower() in nouns]
        kind = nouns.get(entity_mentions[-1].group().lower()) if entity_mentions else None
    if kind and re.search(r'汇总|分组|统计|\b(?:group|count|aggregate)\b', question, re.I):
        # Aggregate-only questions do not need individual identities. A question
        # explicitly requesting identity columns still needs those columns.
        if not re.search(r'(?:项目|员工|人员|成员|里程碑|成果)(?:ID|编号|名称|姓名)|\b(?:id|name)\b', question, re.I):
            return None
    return kind


def validate_entity_identity_projection(sql, question, table_columns):
    """Requested object lists must expose identity, not only hidden/filter columns.

    This diagnostic feeds the existing bounded generation retry. Authorization
    runs first; no SQL is rewritten and no data is fetched by this checker.
    """
    kind = _listed_entity(question)
    if not kind:
        return
    table, identity, _ = ENTITY_IDENTITIES[kind]
    known = {str(k).lower(): {str(c).upper() for c in v} for k, v in (table_columns or {}).items()}
    identity = identity & known.get(table, set())
    if not identity:
        return
    scopes = list(traverse_scope(sqlglot.parse_one(sql, read='mysql')))
    if not scopes or not any(isinstance(v, exp.Table) and v.name.lower() == table
                             for scope in scopes for v in scope.sources.values()):
        return

    def sources(scope):
        return {alias: source for alias, (_, source) in scope.selected_sources.items()}

    def source_value(source, name, seen):
        if isinstance(source, exp.Table):
            actual = source.name.lower()
            return {(actual, name.upper())} if name.upper() in known.get(actual, set()) else set()
        key = (id(source), name.lower())
        if key in seen or len(seen) > 20:
            return set()
        seen = seen | {key}
        if isinstance(source.expression, exp.Union):
            names = [item.lower() for item in source.expression.named_selects]
            if name.lower() not in names:
                return set()
            index = names.index(name.lower())
            branches = [value(branch.expression.selects[index], branch, seen)
                        for branch in source.union_scopes]
            return set.intersection(*branches) if branches else set()
        found = [item for item in source.expression.selects if item.alias_or_name.lower() == name.lower()]
        if found:
            return set().union(*(value(item, source, seen) for item in found))
        if any(isinstance(item, exp.Star) or (isinstance(item, exp.Column) and item.is_star)
               for item in source.expression.selects):
            return set().union(*(source_value(child, name, seen) for child in sources(source).values()))
        return set()

    def value(node, scope, seen=frozenset()):
        selected = sources(scope)
        if isinstance(node, (exp.Alias, exp.Paren, exp.Cast, exp.TryCast, exp.Order)):
            return value(node.this, scope, seen)
        if isinstance(node, exp.Star) or (isinstance(node, exp.Column) and node.is_star):
            selected_sources = [selected.get(node.table)] if isinstance(node, exp.Column) and node.table else list(selected.values())
            return set().union(*(source_value(source, name, seen) for source in selected_sources if source is not None for name in identity))
        if isinstance(node, exp.Column):
            if node.table:
                selected_sources = [selected[node.table]] if node.table in selected else []
            else:
                selected_sources = list(selected.values())
            candidates = [source_value(source, node.name, seen) for source in selected_sources]
            candidates = [candidate for candidate in candidates if candidate]
            return candidates[0] if len(candidates) == 1 else set()
        if isinstance(node, (exp.Concat, exp.Coalesce, exp.GroupConcat, exp.Distinct)):
            children = list(node.expressions)
            if node.this is not None:
                children.append(node.this)
            return set().union(*(value(child, scope, seen) for child in children))
        if isinstance(node, exp.Case):
            branches = [item.args.get('true') for item in node.args.get('ifs', [])]
            branches.append(node.args.get('default'))
            return set().union(*(value(child, scope, seen) for child in branches if child is not None))
        # IDs in COUNT, predicates or other computations are not returned IDs.
        return set()

    def arms(scope):
        if isinstance(scope.expression, exp.Union):
            return [arm for child in scope.union_scopes for arm in arms(child)]
        return [scope]

    for scope in arms(scopes[-1]):
        if not isinstance(scope.expression, exp.Select):
            continue
        projections = scope.expression.selects
        # A UNION may intentionally append a subtotal row to object details.
        if isinstance(scopes[-1].expression, exp.Union) and any(item.find(exp.AggFunc) for item in projections):
            continue
        returned = set().union(*(value(item, scope) for item in projections))
        if not any(actual == table and column in identity for actual, column in returned):
            raise SQLGenerationError(
                '原问题要求识别并列出对象，但最终SELECT仅返回属性，未返回可识别对象的字段。'
                f'请按题意在最终输出中包含 {table} 的ID、名称或原始编号（{", ".join(sorted(identity))}）；'
                '仅在WHERE、JOIN、COUNT或CTE内部使用标识不等于返回标识。保留原筛选范围和所有权限条件。')


def nonexistent_generated_tables(sql, known_tables, allowed_tables):
    """Return missing physical names only after the guard's table denial.

    Existing forbidden tables, any foreign schema, and unknown catalog state
    must remain authorization failures. CTE names are not physical tables.
    """
    if known_tables is None:
        return []
    tree=sqlglot.parse_one(sql,read='mysql')
    if not isinstance(tree,(exp.Select,exp.Union)):
        return []
    missing=set()
    for scope in traverse_scope(tree):
        for source in scope.sources.values():
            if not isinstance(source,exp.Table):continue
            if source.db or source.catalog:return []
            name=source.name.lower()
            if name in known_tables and name not in allowed_tables:return []
            if name not in known_tables:missing.add(name)
    return sorted(missing)


def validate_requested_literals(sql, question):
    """Quoted user values must not gain/lose whitespace in an equality filter."""
    if not question:
        return
    quoted=[]
    for pattern in [r'“([^”]+)”',r'「([^」]+)」',r'"([^"\n]+)"',r"'([^'\n]+)'"]:
        quoted.extend(re.findall(pattern,question))
    if not quoted:
        return
    normalize=lambda value:re.sub(r'\s+','',value)
    tree=sqlglot.parse_one(sql,read='mysql')
    for predicate in tree.find_all(exp.EQ):
        column,literal=predicate.this,predicate.expression
        if isinstance(literal,exp.Column):column,literal=literal,column
        if not isinstance(column,exp.Column) or not isinstance(literal,exp.Literal) or not literal.is_string:
            continue
        value=literal.this
        for original in quoted:
            if value!=original and normalize(value)==normalize(original):
                raise SQLGenerationError(
                    f'原问题明确给出的文字为 {original!r}，SQL却将其改成 {value!r}。'
                    '不能擅自插入或删除名称中的空格。请保留原始文字；若明确给了唯一ID，'
                    '可用ID定位，不要额外附加推测或改写的名称条件。用户明确要求的文字条件不能丢弃。')


def _conjuncts(node):
    if isinstance(node, exp.Paren):
        yield from _conjuncts(node.this)
    elif isinstance(node, exp.And):
        yield from _conjuncts(node.this)
        yield from _conjuncts(node.expression)
    else:
        yield node


def _number(node):
    if not isinstance(node, exp.Literal):
        return None
    try:
        return Decimal(node.this)
    except InvalidOperation:
        return None


def validate_optional_scope_filters(sql, tenant_id):
    """Reject redundant scope checks that null-reject a LEFT JOIN's optional row.

    This does not rewrite SQL or grant access. The authorization guard runs first.
    A genuinely required relationship can be expressed with INNER JOIN; optional
    rows need their scope filters in ON or the guarded child subquery.
    """
    tree = sqlglot.parse_one(sql, read='mysql')
    for scope in traverse_scope(tree):
        select = scope.expression
        if not isinstance(select, exp.Select) or not select.args.get('where'):
            continue
        optional = {join.this.alias_or_name.lower() for join in select.args.get('joins', [])
                    if str(join.args.get('side', '')).upper() == 'LEFT'}
        for predicate in _conjuncts(select.args['where'].this):
            # OR/EXISTS and nested selects are intentionally not traversed here:
            # they may preserve nulls or introduce an independent alias scope.
            if not isinstance(predicate, (exp.EQ, exp.GT)):
                continue
            column, value = predicate.this, predicate.expression
            if isinstance(predicate, exp.EQ) and isinstance(value, exp.Column):
                column, value = value, column
            if not isinstance(column, exp.Column) or column.table.lower() not in optional:
                continue
            redundant = ((isinstance(predicate, exp.EQ) and column.name.upper() == 'TENANT_ID'
                          and _number(value) == Decimal(tenant_id))
                         or (isinstance(predicate, exp.GT) and column.name.upper() == 'OPERATER_STATUS'
                             and _number(value) == 0))
            if redundant:
                raise SQLGenerationError(
                    f'LEFT JOIN 的可空侧 {column.sql(dialect="mysql")} 的权限条件位于 WHERE，'
                    '会过滤没有关联记录的对象。请将该条件移到对应 JOIN 的 ON 或子查询中；'
                    '原权限校验仍会限定租户和未删除范围。若业务只需要存在关联记录，请改用 INNER JOIN。'
                    '不能删除用户要求的无记录对象，也不能放宽业务筛选。')


def validate_independent_staff_metrics(sql):
    """Keep per-employee participation counts and recorded-hour measures independent.

    Inline many-side joins can either multiply hours or silently restrict them to
    membership rows. Request explicit aggregations; never rewrite the user's SQL.
    """
    tree = sqlglot.parse_one(sql, read='mysql')
    required = {'t_staff', 't_project_user', 't_project_user_r_d_time'}
    for scope in traverse_scope(tree):
        select = scope.expression
        if not isinstance(select, exp.Select):
            continue
        tables = {alias.lower(): source.name.lower() for alias,source in scope.sources.items()
                  if isinstance(source, exp.Table)}
        if not required <= set(tables.values()):
            continue
        groups = select.args.get('group')
        if not groups or not any(isinstance(c,exp.Column) and c.name.upper()=='ID'
                                and tables.get(c.table.lower())=='t_staff' for c in groups.expressions):
            continue
        sums = [n for n in select.find_all(exp.Sum) if n.find_ancestor(exp.Select) is select]
        counts = [n for n in select.find_all(exp.Count) if n.find_ancestor(exp.Select) is select]
        hours = any(c.name.upper()=='R_D_HOUR' and tables.get(c.table.lower())=='t_project_user_r_d_time'
                    for n in sums for c in n.find_all(exp.Column))
        projects = any((c.name.upper()=='PROJECT_ID' and tables.get(c.table.lower())=='t_project_user')
                       or (c.name.upper()=='ID' and tables.get(c.table.lower())=='t_project')
                       for n in counts for c in n.find_all(exp.Column))
        if hours and projects:
            raise SQLGenerationError(
                '按员工同时统计参与项目数和研发小时，不能在同一个成员关系/工时明细展开JOIN上直接COUNT和SUM。'
                '这会重复累计工时，或把工时范围意外限制到成员关系。请按问题要求分别聚合参与项目和工时事实，'
                '再按员工ID合并；有效项目范围在各自聚合中核验。若明确只问实际参与项目的工时，'
                '请在工时聚合中保留该范围。不能删除指标或改用有工时项目数代替参与项目数。')


def validate_optional_time_filters(sql):
    """Filter an optional relation's time window before the LEFT JOIN.

    WHERE(time_window OR child.ID IS NULL) still loses a parent that has records
    outside that window: the join matched those rows, so no null row is created.
    """
    tree=sqlglot.parse_one(sql,read='mysql')
    comparisons=(exp.EQ,exp.GT,exp.GTE,exp.LT,exp.LTE,exp.Between,exp.In)
    for scope in traverse_scope(tree):
        select=scope.expression
        if not isinstance(select,exp.Select) or not select.args.get('where'):continue
        optional={j.this.alias_or_name.lower() for j in select.args.get('joins',[])
                  if str(j.args.get('side','')).upper()=='LEFT'}
        for predicate in select.args['where'].find_all(*comparisons):
            if predicate.find_ancestor(exp.Select) is not select:continue
            if not any(True for _ in predicate.find_all(exp.Literal)):continue
            for column in predicate.find_all(exp.Column):
                name=column.name.upper()
                temporal=name in {'DATE','TIME','YEARS','MONTHS'} or name.endswith(('_DATE','_TIME'))
                if column.table.lower() in optional and temporal:
                    raise SQLGenerationError(
                        f'LEFT JOIN可空侧时间条件 {column.sql(dialect="mysql")} 位于WHERE。'
                        '即使加OR 子表ID IS NULL，也会丢失有其他时间记录但没有目标时间记录的对象。'
                        '若要保留没有目标时间记录的对象，请先在ON或子查询中限定时间，再LEFT JOIN；'
                        '若只要有目标时间记录的对象，请用INNER JOIN。若明确只要目标记录或从未记录对象，'
                        '用EXISTS/NOT EXISTS或UNION表达原范围，不能放宽日期条件。')


def validate_project_absence_grain(sql):
    """Require explicit quantifiers for project absence tested per member.

    An unmatched member is not proof that the project has no fact rows. Queries
    returning members and explicit EXISTS expressions remain valid alternatives.
    """
    tree=sqlglot.parse_one(sql,read='mysql')
    for scope in traverse_scope(tree):
        select=scope.expression
        if not isinstance(select,exp.Select) or not select.args.get('where'):continue
        tables={alias.lower():source.name.lower() for alias,source in scope.sources.items()
                if isinstance(source,exp.Table)}
        projects={a for a,t in tables.items() if t=='t_project'}
        members={a for a,t in tables.items() if t in {'t_staff','t_project_user'}}
        hours={a for a,t in tables.items() if t=='t_project_user_r_d_time'}
        projected=[c for item in select.expressions for c in item.find_all(exp.Column)]
        if not projects or not members or not hours or not projected:continue
        if not all(c.table.lower() in projects for c in projected):continue
        absent={p.this.table.lower() for p in select.args['where'].find_all(exp.Is)
                if p.find_ancestor(exp.Select) is select and isinstance(p.expression,exp.Null)
                and isinstance(p.this,exp.Column) and p.this.name.upper()=='ID'
                and not p.find_ancestor(exp.Not)}
        for join in select.args.get('joins',[]):
            alias=join.this.alias_or_name.lower()
            if str(join.args.get('side','')).upper()!='LEFT' or alias not in hours & absent:continue
            on=join.args.get('on')
            if on is None:continue
            for predicate in on.find_all(exp.EQ):
                a,b=predicate.this,predicate.expression
                if not isinstance(a,exp.Column) or not isinstance(b,exp.Column):continue
                if b.table.lower()==alias:a,b=b,a
                if a.table.lower()==alias and a.name.upper()=='STAFF_ID' and b.table.lower() in members:
                    raise SQLGenerationError(
                        '只返回项目的查询用按成员STAFF_ID关联工时后的NULL来判断项目无工时，'
                        '会把“有成员无记录”误作“整个项目无记录”。请明确问题的量词：'
                        '整个项目没有任何记录时，成员存在与项目工时不存在是两个独立条件，'
                        '用按PROJECT_ID关联的NOT EXISTS检查工时；若问题要求至少一个成员无记录，'
                        '请用明确的EXISTS成员及其NOT EXISTS工时表达，不要更改原问题范围。')
