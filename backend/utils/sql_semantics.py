"""Schema-grounded SQL shape diagnostics; never change authorization or answers."""

import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope

from utils.sql_generation_checks import SQLGenerationError


def normalize_dummy_source(tree):
    """Remove only MySQL's bare, unquoted, unaliased dummy FROM source.

    Qualified/quoted names and joins still go through ordinary table checks.
    A CTE named dual is a real query scope and is never removed. After this
    normalization the guard still requires at least one authorized business table.
    """
    for scope in list(traverse_scope(tree)):
        select = scope.expression
        if not isinstance(select, exp.Select) or select.args.get('joins'):
            continue
        source = select.args.get('from') or select.args.get('from_')
        table = source.this if source is not None else None
        if (isinstance(table, exp.Table) and table.name.lower() == 'dual'
                and not table.db and not table.catalog and not table.alias
                and not table.this.args.get('quoted')
                and isinstance(scope.sources.get(table.alias_or_name), exp.Table)
                and not any(v for k, v in table.args.items() if k != 'this')):
            select.set('from', None)
            select.set('from_', None)
    return tree


def _local_nodes(node):
    """Exclude nested query and window scopes from ordinary aggregation."""
    yield node
    for child in node.iter_expressions():
        if isinstance(child, (exp.Select, exp.Subquery, exp.Window)):
            continue
        yield from _local_nodes(child)


def _unaggregated_columns(node):
    if isinstance(node, (exp.AggFunc, exp.Window, exp.Select, exp.Subquery)):
        return []
    found = [node] if isinstance(node, exp.Column) else []
    for child in node.iter_expressions():
        found.extend(_unaggregated_columns(child))
    return found


def _conjuncts(node):
    if isinstance(node, (exp.Where, exp.Paren)):
        return _conjuncts(node.this)
    if isinstance(node, exp.And):
        return _conjuncts(node.this) + _conjuncts(node.expression)
    return [node] if node is not None else []


def _singleton_source(source, known, depth=0):
    """Prove at-most-one row for a derived source, without executing it."""
    if isinstance(source, exp.Table) or depth > 10:
        return False
    select = source.expression
    if not isinstance(select, exp.Select):
        return False
    limit = select.args.get('limit')
    if limit is not None and isinstance(limit.expression, exp.Literal):
        try:
            if int(limit.expression.this) <= 1: return True
        except ValueError:
            pass
    if not select.args.get('group') and any(isinstance(n, exp.AggFunc)
            for p in select.selects for n in _local_nodes(p) if not isinstance(p, exp.Window)):
        return True
    selected = source.selected_sources
    if not selected:
        return True
    if len(selected) != 1 or select.args.get('joins'):
        return False
    alias, (_, child) = next(iter(selected.items()))
    if not isinstance(child, exp.Table):
        return _singleton_source(child, known, depth+1)
    if 'ID' not in known.get(child.name.lower(), set()):
        return False
    for predicate in _conjuncts(select.args.get('where')):
        if not isinstance(predicate, exp.EQ): continue
        for column, value in [(predicate.this,predicate.expression),(predicate.expression,predicate.this)]:
            if (isinstance(column,exp.Column) and column.name.upper()=='ID'
                    and (not column.table or column.table.lower()==alias.lower())
                    and isinstance(value,exp.Literal)):
                return True
    return False


def validate_aggregate_shape(sql, table_columns):
    """Reject arbitrary detail values collapsed by ordinary SUM/COUNT/etc.

    Group keys, constant-constrained columns, and columns functionally fixed by
    an ID key remain legal. ID is the existing business schema's entity key;
    unknown derived sources are handled conservatively and can be regenerated.
    """
    known = {t.lower(): {c.upper() for c in cols} for t, cols in table_columns.items()}
    for scope in traverse_scope(sqlglot.parse_one(sql, read='mysql')):
        select = scope.expression
        if not isinstance(select, exp.Select):
            continue
        group = select.args.get('group')
        if group is not None and (group.args.get('rollup') or group.args.get('cube') or group.args.get('grouping_sets')):
            if not any(isinstance(n, exp.Grouping) for p in select.selects for n in _local_nodes(p)):
                raise SQLGenerationError('汇总行必须显式区分于真实NULL分组。请用窗口函数保留明细和总数，'
                                         '或返回GROUPING标志标明每条明细/小计/总计；不要返回无标记ROLLUP/CUBE。')
        projections = [p.this if isinstance(p, exp.Alias) else p for p in select.selects]
        ordinary_aggregates = any(isinstance(n, exp.AggFunc) and not isinstance(n, exp.Grouping)
                                  for p in projections for n in _local_nodes(p)
                                  if not isinstance(p, exp.Window))
        if not ordinary_aggregates:
            continue
        sources = {alias.lower(): source for alias, (_, source) in scope.selected_sources.items()}
        def column_key(column):
            if column.table:
                return column.table.lower(), column.name.upper()
            matches = [alias for alias, source in sources.items()
                       if isinstance(source, exp.Table) and column.name.upper() in known.get(source.name.lower(), set())]
            if len(matches) == 1:
                return matches[0], column.name.upper()
            if len(sources) == 1:
                return next(iter(sources)), column.name.upper()
            return '', column.name.upper()
        fixed = {(alias,'ID') for alias,source in sources.items() if _singleton_source(source,known)}
        equalities = []
        predicates = _conjuncts(select.args.get('where'))
        for join in select.args.get('joins') or []:
            # INNER joins establish equality for the surviving rows. LEFT JOIN
            # nullable sides do not establish an unconditional equivalence.
            if not join.args.get('side'):
                predicates += _conjuncts(join.args.get('on'))
        for predicate in predicates:
            if not isinstance(predicate, exp.EQ):
                continue
            a, b = predicate.this, predicate.expression
            if isinstance(a, exp.Column) and isinstance(b, exp.Column):
                equalities.append((column_key(a), column_key(b)))
            for column, value in [(a, b), (b, a)]:
                if isinstance(column, exp.Column) and isinstance(value, (exp.Literal, exp.Boolean)):
                    fixed.add(column_key(column))
        group_expressions = []
        aliases = {p.alias.lower(): p.this for p in select.selects if isinstance(p, exp.Alias)}
        for expression in group.expressions if group is not None else []:
            if isinstance(expression, exp.Column) and not expression.table and expression.name.lower() in aliases:
                expression = aliases[expression.name.lower()]
            group_expressions.append(expression)
            if isinstance(expression, exp.Column):
                fixed.add(column_key(expression))
        for _ in range(len(equalities) + 1):
            old = set(fixed)
            for a, b in equalities:
                if a in fixed: fixed.add(b)
                if b in fixed: fixed.add(a)
            if old == fixed: break
        group_sql = {e.sql(dialect='mysql').lower() for e in group_expressions}
        bad = []
        for projection in projections:
            if projection.sql(dialect='mysql').lower() in group_sql:
                continue
            if isinstance(projection, exp.Star):
                bad.append('*');continue
            for column in _unaggregated_columns(projection):
                key = column_key(column)
                if key not in fixed and (key[0], 'ID') not in fixed:
                    bad.append(column.sql(dialect='mysql'))
        if bad:
            raise SQLGenerationError('普通聚合与未分组明细列混用会把多个对象压成一行：'
                                     + ', '.join(sorted(set(bad)))
                                     + '。请按所需明细粒度GROUP BY，或使用SUM/COUNT OVER()保留全部明细，'
                                     '或分别聚合后关联。仅添加列名不代表保留了对象列表。')
