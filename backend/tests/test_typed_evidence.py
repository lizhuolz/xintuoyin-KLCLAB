"""Schema-renaming metamorphic tests; no benchmark cases, business fields or oracles."""
import copy,json,random,sqlite3,string,unittest
from unittest.mock import Mock,patch
from langchain_core.messages import AIMessage,HumanMessage,ToolMessage
from utils.typed_query import compile_contract,ContractError,load_catalog,catalog_view
from utils.typed_facts import describe_result,render_plan,FactError


def binding(value):return {'value':str(value),'evidence':str(value)}

class CompiledContractTests(unittest.TestCase):
    def schema(self,seed):
        rng=random.Random(seed)
        names=['x'+''.join(rng.choices(string.ascii_lowercase,k=12)) for _ in range(9)]
        a,b,c,d,key,attr,left,right,other=names
        e={'A':{'table':a,'key':[key],'label':'对象甲','attributes':{key:{'type':'int','label':'甲键'},attr:{'type':'text','label':'登记属性'}}},
           'B':{'table':b,'key':[key],'label':'对象乙','attributes':{key:{'type':'int','label':'乙键'}}}}
        r={'R':{'kind':'association','table':c,'left':'A','right':'B','left_columns':[left],'right_columns':[right],'label':'实际关系'},
           'S':{'kind':'association','table':d,'left':'A','right':'B','left_columns':[left],'right_columns':[right],'label':'另一种关系'}}
        con=sqlite3.connect(':memory:');self.addCleanup(con.close)
        con.execute(f'CREATE TABLE {a}({key} INT PRIMARY KEY,{attr} TEXT)');con.execute(f'INSERT INTO {a} VALUES(11,?)',('[37]',))
        con.execute(f'CREATE TABLE {b}({key} INT PRIMARY KEY)');con.execute(f'INSERT INTO {b} VALUES(37)')
        for t in [c,d]:con.execute(f'CREATE TABLE {t}({left} INT,{right} INT)')
        con.execute(f'INSERT INTO {d} VALUES(11,37)')
        return {'entities':e,'relations':r},con,names
    def plan(self,attr):return {'mode':'fixed','answer_mode':'data',
        'bindings':{'a':{'entity':'A','key':[binding(11)]},'b':{'entity':'B','key':[binding(37)]}},
        'facts':[{'op':'attribute','subject':'a','property':attr},
                 {'op':'relation_exists','relation':'R','left':'a','right':'b'}]}
    def test_attribute_and_distinct_relationships_remain_separate_under_32_full_renamings(self):
        for seed in range(32):
            with self.subTest(seed=seed):
                cat,con,names=self.schema(seed);plan=self.plan(names[5]);original=copy.deepcopy(plan)
                compiled=compile_contract(plan,cat,'对象11与对象37');row=con.execute(compiled['sql']).fetchone()
                self.assertEqual(row,('[37]',0));self.assertEqual(plan,original)
                self.assertEqual(compiled['fields'][1]['kind'],'relation_boolean')
                self.assertEqual(compiled['fields'][1]['relation'],'R')
                self.assertNotIn([names[0],names[5]],compiled['fields'][1]['source_columns'])
                plan['facts'][1]['relation']='S'
                self.assertEqual(con.execute(compile_contract(plan,cat,'对象11与对象37')['sql']).fetchone(),('[37]',1))
    def test_renamed_relation_reference_keys_do_not_claim_verified_entity_population(self):
        for seed in range(8):
            cat,con,n=self.schema(seed);a,b,c,d,key,attr,left,right,other=n
            con.executemany(f'INSERT INTO {c} VALUES(?,?)',[(11,37),(11,41),(12,37),(12,41)])
            sql=f'SELECT r.{left} AS a,r.{right} AS b FROM {c} r'
            rows=[dict(zip(['a','b'],r)) for r in con.execute(sql).fetchall()]
            result={'status':'ok','fields':['a','b'],'data':rows,'executed_sql':sql}
            meta=describe_result(result,cat,type_codes={'a':3,'b':3})
            self.assertEqual(meta['row_count']['value'],4)
            self.assertEqual([f['type'] for f in meta['fields']],['identifier','identifier'])
            self.assertEqual({f['value'] for f in meta['entity_counts']},{2})
            self.assertTrue(all(f['type']=='reference_count' for f in meta['entity_counts']))

    def test_serialized_catalog_keeps_physical_proofs_while_prompt_view_is_logical(self):
        import tempfile
        from pathlib import Path
        cat,con,n=self.schema(7)
        columns={e['table']:set(e['attributes']) for e in cat['entities'].values()}
        for r in cat['relations'].values():columns[r['table']]=set(r['left_columns']+r['right_columns'])
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'catalog.json';p.write_text(json.dumps(cat))
            loaded=load_catalog(columns,p)
        view=catalog_view(loaded,[n[0]])
        self.assertNotIn('left_columns',view['relations']['R'])
        self.assertEqual(loaded['relations']['R']['table'],n[2])
        self.assertEqual(con.execute(compile_contract(self.plan(n[5]),loaded,'11与37')['sql']).fetchone(),('[37]',0))

    def test_supported_operations_cannot_bypass_compilation_using_a_mode_flag(self):
        cat,con,n=self.schema(12);plan=self.plan(n[5]);plan['mode']='sql'
        compiled=compile_contract(plan,cat,'11与37')
        self.assertIsNotNone(compiled);self.assertEqual(con.execute(compiled['sql']).fetchone(),('[37]',0))
    def test_unsupported_requirement_preserves_whole_question_on_normal_sql_path(self):
        cat,con,n=self.schema(13);plan=self.plan(n[5]);plan['facts'].append({'op':'sql','request':'还要汇总'})
        self.assertIsNone(compile_contract(plan,cat,'11与37，还要汇总'))

    def test_relation_endpoint_types_are_checked_before_any_sql_exists(self):
        cat,con,n=self.schema(9);cat['relations']['R']['right']='A'
        with self.assertRaisesRegex(ContractError,'endpoint type mismatch'):
            compile_contract(self.plan(n[5]),cat,'对象11与对象37')
    def test_display_property_and_identifier_representation_are_distinct_after_renaming(self):
        for seed in range(16):
            cat,con,n=self.schema(seed+100);a,b,c,d,key,attr,left,right,display=n
            con.execute(f'ALTER TABLE {a} ADD COLUMN {display} TEXT');con.execute(f'UPDATE {a} SET {display}=?',('显示对象',))
            e=cat['entities']['A'];e['attributes'][display]={'label':'角色姓名','type':'text'}
            e['properties']={'logical_role':{'label':'角色','representations':{'value':display,'identity':attr}}}
            plan=self.plan(attr);plan['facts'][0]['property']='logical_role'
            self.assertEqual(con.execute(compile_contract(plan,cat,'11与37')['sql']).fetchone(),('显示对象',0))
            plan['facts'][0]['representation']='identity'
            with self.assertRaises(ContractError):compile_contract(plan,cat,'11与37')
            plan['facts'][0]['property']=attr
            with self.assertRaises(ContractError):compile_contract(plan,cat,'11与37')
    def test_neighbor_endpoints_expose_keys_without_hydrating_unselected_properties(self):
        cat,con,n=self.schema(11);view=catalog_view(cat,[n[0]])
        self.assertTrue(view['entities']['A']['properties']);self.assertEqual(view['entities']['B']['properties'],{})
        self.assertTrue(view['entities']['B']['key'])

    def test_association_records_are_not_silently_retyped_as_endpoint_entities(self):
        cat,con,n=self.schema(10)
        cat['entities']['link']={'table':n[2],'label':'关联记录','key':['record_key'],'attributes':{'record_key':{'label':'编号','type':'int'}},'kind':'association_record'}
        cat['relations']['record_to_endpoint']={'kind':'foreign_key','left':'link','right':'A','left_columns':[n[6]],'right_columns':[n[4]],'label':'记录到对象'}
        view=catalog_view(cat,[n[0],n[2]])
        self.assertNotIn('link',view['entities']);self.assertNotIn('record_to_endpoint',view['relations']);self.assertIn('R',view['relations'])

    def test_missing_anchor_produces_no_rows_instead_of_invented_entity_attributes(self):
        cat,con,n=self.schema(1);plan=self.plan(n[5]);plan['bindings']['a']['key']=[binding(99)]
        self.assertIsNone(con.execute(compile_contract(plan,cat,'对象99、11与37')['sql']).fetchone())
    def test_keys_must_be_literal_evidence_and_not_substrings_or_guesses(self):
        cat,con,n=self.schema(2);p=self.plan(n[5])
        for question in ['对象111与对象37','对象甲与对象37']:
            with self.assertRaises(ContractError):compile_contract(p,cat,question)
        p['bindings']['a']['key'][0]['value']='12'
        with self.assertRaises(ContractError):compile_contract(p,cat,'11、12、37')
    def test_literal_evidence_can_include_its_original_question_context(self):
        cat,con,n=self.schema(8);p=self.plan(n[5])
        p['bindings']['a']['key'][0]['evidence']='对象编号 11'
        self.assertEqual(con.execute(compile_contract(p,cat,'对象编号 11与对象37')['sql']).fetchone(),('[37]',0))

    def test_unknown_operations_relations_and_proof_injection_fail_closed(self):
        cat,con,n=self.schema(3)
        for mutation in [{'op':'raw_sql','sql':'SELECT 1'}, {'op':'relation_exists','relation':'unknown','left':'a','right':'b'}]:
            with self.assertRaises(ContractError):compile_contract(dict(self.plan(n[5]),facts=[mutation]),cat,'11与37')
        p=self.plan(n[5]);p['facts'][1]['proof']={'kind':'attribute'}
        with self.assertRaises(ContractError):compile_contract(p,cat,'11与37')
    def test_composite_primary_keys_are_not_reduced_to_one_component(self):
        cat,con,n=self.schema(4);entity=cat['entities']['A'];entity['key'].append('second_key');entity['attributes']['second_key']={'type':'text','label':'第二键'}
        with self.assertRaises(ContractError):compile_contract(self.plan(n[5]),cat,'11与37')
    def test_free_sql_mode_cannot_attach_compiler_proofs(self):
        cat,con,n=self.schema(5)
        self.assertIsNone(compile_contract({'mode':'sql','facts':[]},cat,'任意问题'))
        self.assertIsNone(compile_contract({'facts':[{'op':'sql','request':'任意问题'}],'bindings':{'draft':'unused'}},cat,'任意问题'))


class TypedFactTests(unittest.TestCase):
    def result(self):
        return {'status':'ok','truncated':False,'fields':['a','b','amount'],
          'data':[{'a':11,'b':37,'amount':'12.50'},{'a':11,'b':41,'amount':'7.50'},
                  {'a':12,'b':37,'amount':'3.00'},{'a':12,'b':41,'amount':'5.00'}],
          'typed_evidence':{'version':1,'fields':[{'field':'a','label':'甲键','type':'identifier'},
             {'field':'b','label':'乙键','type':'identifier'},{'field':'amount','label':'数值','type':'number'}],
             'entity_counts':[{'id':'entity_count:B','label':'对象乙去重实体数','type':'entity_count','value':2}]}}
    def test_record_count_and_entity_count_have_immutable_distinct_labels(self):
        r=self.result();text,proofs=render_plan(r,{'calculations':[
          {'operation':'show','arguments':['row_count'],'requested_by':'条数'},
          {'operation':'show','arguments':['entity_count:B'],'requested_by':'实体数'}]},'列条数和实体数')
        self.assertIn('返回记录数：4 条记录',text);self.assertIn('对象乙去重实体数：2',text)
        self.assertEqual([p['type'] for p in proofs],['record_count','entity_count'])
    def test_model_cannot_supply_a_literal_value_label_unit_or_factual_prose(self):
        for plan in [{'text':'共有4个人'},{'calculations':[{'operation':'show','arguments':['row_count'],'requested_by':'条数','label':'人数'}]},
                     {'calculations':[{'operation':'subtract','arguments':['cell:0:2','999'],'requested_by':'差额'}]}]:
            with self.assertRaises(FactError):render_plan(self.result(),plan,'条数与差额')
    def test_named_scalar_fact_selection_preserves_record_count_type(self):
        text,_=render_plan(self.result(),{'summaries':['row_count'],'calculations':[]},'条数')
        self.assertIn('返回记录数：4 条记录',text)
    def test_machine_document_mode_does_not_append_conversational_instructions(self):
        from agent.node import make_chatbot_node
        model=Mock();bound=Mock();model.bind.return_value=bound
        bound.invoke.return_value=AIMessage(content='{"calculations":[]}')
        with patch('langchain_openai.ChatOpenAI',return_value=model):
            make_chatbot_node(0,[],system_prompt='machine document',machine_output=True)(
                {'select_model':'synthetic','messages':[HumanMessage(content='输入')]})
        model.bind.assert_called_once_with(response_format={'type':'json_object'})
        self.assertEqual(bound.invoke.call_args.args[0][0].content,'machine document')

    def test_numeric_operators_do_not_accept_identity_or_text_fields(self):
        for arg in ['column:0','column:1']:
            with self.assertRaises(FactError):render_plan(self.result(),{'calculations':[{'operation':'sum','arguments':[arg],'requested_by':'合计'}]},'合计')
    def test_decimal_calculations_retain_precision_and_do_not_mutate_evidence(self):
        r=self.result();original=copy.deepcopy(r)
        text,proof=render_plan(r,{'calculations':[{'operation':'sum','arguments':['column:2'],'requested_by':'合计'}]},'数值合计')
        self.assertIn('28.00',text);self.assertEqual(r,original)
    def test_zero_denominator_is_explicitly_not_calculable(self):
        r=self.result();r['data'][1]['amount']='0'
        text,_=render_plan(r,{'calculations':[{'operation':'percent','arguments':['cell:0:2','cell:1:2'],'requested_by':'比例'}]},'比例')
        self.assertIn('无法计算',text)
    def test_null_measure_is_not_silently_replaced_with_zero(self):
        r=self.result();r['data'][0]['amount']=None
        with self.assertRaises(FactError):render_plan(r,{'calculations':[{'operation':'sum','arguments':['column:2'],'requested_by':'合计'}]},'合计')
    def test_relation_false_is_rendered_from_its_boolean_type(self):
        r=self.result();r['typed_evidence']['fields'][0]['type']='boolean'
        for row in r['data']:row['a']=0
        text,_=render_plan(r,{'calculations':[]},'结果')
        self.assertIn('否',text)
    def test_summary_flag_cannot_free_form_a_numeric_result(self):
        from agent.typed_answer import should_render_facts
        r=self.result();r['typed_evidence']['answer_mode']='summary'
        self.assertTrue(should_render_facts(r))
    def test_rejected_document_and_internal_json_do_not_stream_to_user(self):
        from agent.sql_answer import make_sql_answer_node
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        from langgraph.constants import TAG_NOSTREAM
        from langgraph.graph import StateGraph,START,END,MessagesState
        model=FakeListChatModel(responses=['{"text":"错误人数4"}','{"calculations":[]}'],disable_streaming=True,tags=[TAG_NOSTREAM])
        def factory(*a,**kw):return lambda state:{'messages':[model.invoke(state['messages'])]}
        state={'messages':[HumanMessage(content='列明细'),ToolMessage(content=json.dumps(self.result()),name='sql_tool',tool_call_id='synthetic')]}
        with patch('agent.typed_answer.make_chatbot_node',side_effect=factory):
            g=StateGraph(MessagesState);g.add_node('answer',make_sql_answer_node());g.add_edge(START,'answer');g.add_edge('answer',END)
            events=list(g.compile().stream(state,stream_mode='messages'))
        visible=''.join(m.content for m,_ in events)
        self.assertIn('数值',visible);self.assertNotIn('错误人数',visible);self.assertNotIn('calculations',visible)

if __name__=='__main__':unittest.main()
