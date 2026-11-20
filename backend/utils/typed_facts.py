"""Typed, source-bound numeric facts and deterministic presentation."""
import datetime,json
from decimal import Decimal,InvalidOperation,localcontext
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.scope import traverse_scope

class FactError(ValueError):pass

def _origin(column,scope,known_columns,seen=frozenset()):
    key=(id(scope),column.table.lower(),column.name.lower())
    if key in seen:return None
    seen=seen|{key};sources={a.lower():v for a,(_,v) in scope.selected_sources.items()}
    if column.table and column.table.lower() not in sources:return None
    choices=[sources[column.table.lower()]] if column.table else list(sources.values())
    found=[]
    for source in choices:
        if isinstance(source,exp.Table):
            # A JOIN does not make every unqualified column belong to every
            # input table. Resolve against schema before assigning fact types.
            if column.name.upper() in known_columns.get(source.name.lower(),set()):
                found.append((source.name,column.name))
        elif isinstance(source.expression,exp.Select):
            selects=source.expression.selects
            matches=[p for p in selects if p.alias_or_name.lower()==column.name.lower()]
            node=matches[0] if len(matches)==1 else None
            if isinstance(node,exp.Alias):node=node.this
            if isinstance(node,exp.Column):found.append(_origin(node,source,known_columns,seen))
            elif any(isinstance(p,exp.Star) or (isinstance(p,exp.Column) and p.is_star) for p in selects):
                found.append(_origin(exp.column(column.name),source,known_columns,seen))
    found=[x for x in found if x is not None]
    return found[0] if len(found)==1 else None

def describe_result(result,catalog,contract=None,compiled=None,type_codes=None):
    fields=result.get('fields',[]);entities=catalog['entities'];origins={}
    known_columns={e['table'].lower():{c.upper() for c in e['attributes']} for e in entities.values()}
    for relation in catalog['relations'].values():
        if relation['kind']=='association':
            known_columns.setdefault(relation['table'].lower(),set()).update(
                c.upper() for c in relation['left_columns']+relation['right_columns'])
    try:
        scopes=list(traverse_scope(sqlglot.parse_one(result['executed_sql'],read='mysql')))
        root=scopes[-1]
        if isinstance(root.expression,exp.Select) and len(root.expression.selects)==len(fields):
            for i,node in enumerate(root.expression.selects):
                if isinstance(node,exp.Alias):node=node.this
                if isinstance(node,exp.Column):origins[i]=_origin(node,root,known_columns)
    except (ValueError,AttributeError,sqlglot.errors.SqlglotError):pass
    identities={}
    for eid,e in entities.items():
        for key in e['key']:identities[e['table'].lower(),key.upper()]=(eid,key,'entity')
    for r in catalog['relations'].values():
        if r['kind']=='foreign_key':
            left=entities[r['left']];right=entities[r['right']]
            for col,key in zip(r['left_columns'],r['right_columns']):
                if key in right['key']:identities[left['table'].lower(),col.upper()]=(r['right'],key,'reference')
        elif r['kind']=='association':
            for side in ['left','right']:
                for col,key in zip(r[side+'_columns'],entities[r[side]]['key']):identities[r['table'].lower(),col.upper()]=(r[side],key,'reference')
    proofs={p['field']:p for p in (compiled or {}).get('fields',[])};specs=[];mapped={}
    numeric_codes={0,1,2,3,4,5,8,9,13,16,246};date_codes={7,10,11,12,14}
    for i,field in enumerate(fields):
        code=(type_codes or {}).get(field);proof=proofs.get(field,{})
        kind='number' if code in numeric_codes else 'date' if code in date_codes else 'text'
        if proof.get('kind')=='relation_boolean':kind='boolean'
        origin=origins.get(i)
        if proof.get('kind')=='attribute' and len(proof.get('source_columns',[]))==1:
            table,column=proof['source_columns'][0]
            if column.upper() in known_columns.get(table.lower(),set()):origin=(table,column)
        identity=identities.get((origin[0].lower(),origin[1].upper())) if origin else None
        if identity:kind='identifier';mapped.setdefault(identity[0],{})[identity[1]]=(field,identity[2])
        elif kind=='number' and origin is None:
            # Keep the database value visible, but do not authorize arithmetic
            # merely because MySQL reports a numeric storage type. This also
            # covers computed/ambiguous identifier projections.
            kind='unverified_number'
        specs.append({'field':field,'label':proof.get('label') or field,'type':kind,'origin':origin,'proof':proof or None})
    counts=[]
    for eid,components in mapped.items():
        e=entities[eid]
        if not all(k in components for k in e['key']):continue
        values={tuple(str(row[components[k][0]]) for k in e['key']) for row in result.get('data',[]) if all(row.get(components[k][0]) is not None for k in e['key'])}
        referenced=any(components[k][1]=='reference' for k in e['key'])
        counts.append({'id':('reference_count:' if referenced else 'entity_count:')+eid,'label':e['label']+('引用键去重数' if referenced else '去重实体数'),'value':len(values),'key_fields':[components[k][0] for k in e['key']],'type':'reference_count' if referenced else 'entity_count'})
    return {'version':1,'answer_mode':(contract or {}).get('answer_mode','data'),'contract':contract,
            'compiled':compiled is not None,'fields':specs,'entity_counts':counts,
            'row_count':{'value':len(result.get('data',[])),'type':'record_count','unit':'条记录'}}

def _number(value):
    if value is None:raise FactError('NULL cannot be silently converted to zero')
    try:return Decimal(str(value))
    except InvalidOperation:raise FactError('Operand is not a numeric fact')

def _cell(value):
    if value is None:return 'NULL'
    if value=='':return '空字符串'
    return str(value).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('|','\\|').replace('\n','<br>')

def inventory(result):
    meta=result['typed_evidence'];fields=result.get('fields',[]);specs={s['field']:s for s in meta['fields']};refs={};columns={}
    for c,f in enumerate(fields):
        s=specs[f];columns['column:'+str(c)]={'label':s['label'],'type':s['type'],'values':[r.get(f) for r in result.get('data',[])]}
        for i,row in enumerate(result.get('data',[])):
            refs['cell:'+str(i)+':'+str(c)]={'label':s['label'],'type':s['type'],'value':row.get(f)}
    for i,s in enumerate(result.get('global_summaries',[])):
        refs['summary:'+str(i)]={'label':s['field'],'type':'number','value':s['value']}
    refs['row_count']={'label':'返回记录数','type':'record_count','value':len(result.get('data',[]))}
    for item in meta.get('entity_counts',[]):refs[item['id']]=item
    return {'facts':refs,'columns':columns}

def render_plan(result,plan,question):
    """No model-authored factual prose, values, labels, units or row filtering."""
    if not isinstance(plan,dict) or set(plan)-{'fields','summaries','calculations'}:raise FactError('Answer document only accepts typed calculations')
    calculations=plan.get('calculations',[])
    if not isinstance(calculations,list) or len(calculations)>8:raise FactError('Invalid calculation list')
    inv=inventory(result);refs=inv['facts'];columns=inv['columns'];specs={s['field']:s for s in result['typed_evidence']['fields']}
    source_fields=result.get('fields',[]);rows=result.get('data',[])
    requested=plan.get('fields',list(columns))
    if not isinstance(requested,list) or not requested or len(set(requested))!=len(requested) or any(x not in columns for x in requested):raise FactError('Invalid output field references')
    fields=[source_fields[int(x.split(':')[1])] for x in requested]
    def display(field,value):
        if specs[field]['type']=='boolean' and value is not None:return '是' if bool(int(value)) else '否'
        return _cell(value)
    lines=[]
    if fields and rows:
        lines=['| '+' | '.join(_cell(specs[f]['label']) for f in fields)+' |',
               '| '+' | '.join('---' for _ in fields)+' |']
        lines+=['| '+' | '.join(display(f,row.get(f)) for f in fields)+' |' for row in rows]
    summaries=plan.get('summaries',['summary:'+str(i) for i in range(len(result.get('global_summaries',[])))])
    if not isinstance(summaries,list) or any(x not in refs for x in summaries):raise FactError('Invalid summary references')
    for ref in dict.fromkeys(summaries):
        s=refs[ref];text=_cell(s['value'])+(' 条记录' if s['type']=='record_count' else '')
        lines+=['',_cell(s['label'])+'：'+text]
    trace=[]
    for calc in calculations:
        if not isinstance(calc,dict) or set(calc)-{'operation','arguments','requested_by','precision','rounding_evidence'}:raise FactError('Unknown calculation properties')
        evidence=calc.get('requested_by','')
        if not isinstance(evidence,str) or not evidence or evidence not in question:raise FactError('Additional fact requires an original-question request span')
        op=calc.get('operation');args=calc.get('arguments',[])
        if not isinstance(args,list) or not all(isinstance(a,str) for a in args):raise FactError('Operands must be fact references')
        with localcontext() as context:
            context.prec=50
            if op=='show' and len(args)==1 and args[0] in refs:
                fact=refs[args[0]];value=fact['value'];label=fact['label'];typ=fact['type']
            elif op in ['sum','distinct_count'] and len(args)==1 and args[0] in columns:
                fact=columns[args[0]]
                if op=='sum':
                    if fact['type']!='number':raise FactError('SUM requires a measure, not an identity/text/count')
                    value=sum((_number(v) for v in fact['values']),Decimal(0));label=fact['label']+'合计';typ='number'
                else:
                    value=len({str(v) for v in fact['values'] if v is not None});label=fact['label']+'去重值数';typ='value_count'
            elif op in ['subtract','percent','equal','date_diff'] and len(args)==2 and all(a in refs for a in args):
                a,b=[refs[x] for x in args]
                if op=='equal':value='是' if a['value']==b['value'] or (a['type']==b['type']=='number' and _number(a['value'])==_number(b['value'])) else '否';label=a['label']+'与'+b['label']+'是否相等';typ='boolean'
                elif op=='date_diff':
                    value=(datetime.date.fromisoformat(str(a['value'])[:10])-datetime.date.fromisoformat(str(b['value'])[:10])).days;label=a['label']+'减'+b['label']+'天数';typ='number'
                else:
                    if a['type']!='number' or b['type']!='number':raise FactError('Arithmetic requires two numeric measures')
                    av,bv=_number(a['value']),_number(b['value'])
                    value=av-bv if op=='subtract' else (av/bv*100 if bv else None)
                    label=a['label']+('减' if op=='subtract' else '占')+b['label']+('差额' if op=='subtract' else '百分比');typ='percent' if op=='percent' else 'number'
            else:raise FactError('Invalid operator, arity or source reference')
        precision=calc.get('precision')
        if precision is not None:
            rounding=calc.get('rounding_evidence','')
            if not isinstance(precision,int) or not 0<=precision<=12 or not rounding or rounding not in question or str(precision) not in rounding:raise FactError('Precision needs explicit question evidence')
            if isinstance(value,(Decimal,int)) and typ not in ['entity_count','record_count','value_count']:value=format(Decimal(value),'.'+str(precision)+'f')
        text='无法计算' if value is None else _cell(value)
        if typ=='percent' and value is not None:text+='%'
        if typ=='record_count':text+=' 条记录'
        lines+=['',_cell(label)+'：'+text];trace.append({'operation':op,'arguments':args,'type':typ,'value':str(value),'requested_by':evidence})
    if result.get('truncated'):lines+=['','查询结果已截断，以上仅为实际返回的数据。']
    return '\n'.join(lines),trace
