import copy,json,unittest
from unittest.mock import Mock,patch
from langchain_core.messages import AIMessage,HumanMessage,ToolMessage
from agent.sql_answer_checks import answer_result_view
from agent.sql_answer import make_sql_answer_node

class ResultViewTests(unittest.TestCase):
    def result(self,sql='SELECT label,amount,SUM(amount) OVER() overall FROM invoices'):
        return {'status':'ok','truncated':False,'fields':['label','amount','overall'],
                'data':[{'label':'alpha','amount':'12.00','overall':'30.00'},
                        {'label':'beta','amount':'18.00','overall':'30.00'}], 'executed_sql':sql}
    def test_global_total_is_removed_from_detail_rows_without_changing_source(self):
        raw=self.result();before=copy.deepcopy(raw);view=answer_result_view(raw)
        self.assertEqual(raw,before);self.assertEqual(view['fields'],['label','amount'])
        self.assertEqual(view['data'],[{'label':'alpha','amount':'12.00'},{'label':'beta','amount':'18.00'}])
        self.assertEqual(view['global_summaries'][0]['value'],'30.00')
    def test_partitioned_running_ranking_and_row_dependent_values_stay_in_rows(self):
        for expr in ['SUM(amount) OVER(PARTITION BY category)','SUM(amount) OVER(ORDER BY id)',
                     'ROW_NUMBER() OVER()','amount/SUM(amount) OVER()']:
            raw=self.result('SELECT label,amount,'+expr+' overall FROM invoices')
            self.assertIs(answer_result_view(raw),raw)
    def test_nonconstant_or_unknown_projection_width_is_not_reclassified(self):
        raw=self.result();raw['data'][1]['overall']='31.00'
        self.assertIs(answer_result_view(raw),raw)
        raw=self.result('SELECT * FROM invoices');self.assertIs(answer_result_view(raw),raw)
    def test_equal_group_ratios_are_not_misclassified_as_a_global_total(self):
        raw=self.result('SELECT label,amount,SUM(amount)/SUM(SUM(amount)) OVER() overall FROM invoices GROUP BY label,amount')
        for row in raw['data']:row['amount']='20.00';row['overall']='0.50'
        self.assertIs(answer_result_view(raw),raw)
    def test_only_model_input_is_transformed_without_mutating_graph_evidence(self):
        raw=self.result();state={'messages':[HumanMessage(content='列每类金额和合计'),
            ToolMessage(content=json.dumps(raw),name='sql_tool',tool_call_id='view-test')]}
        answer=Mock(return_value={'messages':[AIMessage(content='alpha12，beta18，合计30。')]})
        original=list(state['messages'])
        with patch('agent.sql_answer.make_chatbot_node',return_value=answer):make_sql_answer_node()(state)
        viewed=json.loads(answer.call_args.args[0]['messages'][-1].content)
        self.assertIn('global_summaries',viewed);self.assertNotIn('overall',viewed['data'][0])
        self.assertEqual(state['messages'],original)
        answer.assert_called_once()

    def test_transformed_view_does_not_stream_internal_tool_or_review_messages(self):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        from langgraph.constants import TAG_NOSTREAM
        from langgraph.graph import StateGraph,START,END,MessagesState
        good='alpha12，beta18，合计30。'
        model=FakeListChatModel(responses=[good],
                                disable_streaming=True,tags=[TAG_NOSTREAM])
        state={'messages':[HumanMessage(content='列每类金额和合计'),
            ToolMessage(content=json.dumps(self.result()),name='sql_tool',tool_call_id='view-stream')]}
        def factory(*args,**kwargs):return lambda s:{'messages':[model.invoke(s['messages'])]}
        with patch('agent.sql_answer.make_chatbot_node',side_effect=factory):
            g=StateGraph(MessagesState);g.add_node('answer',make_sql_answer_node())
            g.add_edge(START,'answer');g.add_edge('answer',END)
            events=list(g.compile().stream(state,stream_mode='messages'))
        self.assertEqual(''.join(m.content for m,_ in events),good)

if __name__=='__main__':unittest.main()
