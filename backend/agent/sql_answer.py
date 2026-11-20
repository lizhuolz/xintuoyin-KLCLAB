"""Ground SQL answers in evidence; publish only accepted answer candidates."""
import json
import hashlib

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.constants import TAG_NOSTREAM
from agent.node import make_chatbot_node
from agent.sql_answer_prompt import SQL_ANSWER_PROMPT
from agent.sql_answer_checks import unsupported_coverage_claims, validation_feedback, result_receipt, factual_fallback, answer_result_view


def make_sql_answer_node():
    # LangGraph suppresses inner LLM token events carrying TAG_NOSTREAM. The
    # accepted node update still emits normally, so rejected text never leaks.
    def sql_answer_node(state):
        result = None
        for message in reversed(state.get('messages',[])):
            if not isinstance(message,ToolMessage) or message.name!='sql_tool':
                continue
            try:
                result=json.loads(message.content)
            except (ValueError,TypeError):
                break
            if (isinstance(result,dict) and result.get('status')=='empty'
                    and result.get('Access_check') is not False and result.get('data')==[]):
                return {'messages':[AIMessage(
                    content='当前租户内未查询到符合本次条件的登记记录，未返回所问字段的可核对值。',
                    response_metadata={'finish_reason':'deterministic_empty','source':'sql_empty_result'})]}
            break
        from agent.typed_answer import should_render_facts,make_typed_answer
        from agent.node import extract_current_user_question
        if isinstance(result,dict) and should_render_facts(result):
            return make_typed_answer(state,result,state.get('current_question') or extract_current_user_question(state.get('messages',[])))
        temporary = dict(state)
        answer_view = answer_result_view(result)
        if answer_view is not result:
            messages=list(state.get('messages',[]))
            for i in range(len(messages)-1,-1,-1):
                if isinstance(messages[i],ToolMessage) and messages[i].name=='sql_tool':
                    messages[i]=messages[i].model_copy(update={'content':json.dumps(answer_view,ensure_ascii=False)})
                    break
            temporary['messages']=messages
        receipt = result_receipt(answer_view) or ''
        # Extract only the original human question, never a feedback message.
        from agent.node import extract_current_user_question
        question = state.get('current_question') or extract_current_user_question(state.get('messages', []))
        failures = []
        for attempt in range(3):
            # The serving chat template requires system messages at the start.
            # Keep controlled validation feedback in the system prompt and
            # business data/candidate answers in their original message roles.
            feedback = validation_feedback(failures[-1]['codes']) if failures else ''
            if attempt == 2:
                feedback += ' 本次仅输出原问题要求的事实、数据明细与必要计算，不追加范围猜测或核查建议。'
            answer_with_model = make_chatbot_node(
                0, [], system_prompt='\n\n'.join(part for part in
                    (SQL_ANSWER_PROMPT, receipt, feedback) if part),
                stream_answer=False, model_tags=[TAG_NOSTREAM])
            update = answer_with_model(temporary)
            candidates = update.get('messages', [])
            response = candidates[-1] if candidates else None
            if not isinstance(response, AIMessage) or not isinstance(response.content, str):
                return update
            codes = unsupported_coverage_claims(response.content, result, question)
            if not codes:
                if failures:
                    metadata = dict(response.response_metadata)
                    metadata['sql_answer_validation'] = {'attempts':attempt+1, 'repaired':bool(failures),
                                                        'failures':failures}
                    response = response.model_copy(update={'response_metadata':metadata})
                    return dict(update, messages=[*candidates[:-1], response])
                return update
            failures.append({'codes':codes, 'candidate_sha256':hashlib.sha256(response.content.encode()).hexdigest()})
            # Regenerate from the unchanged question and evidence. Appending a
            # rejected assistant answer can anchor the model to repeat it.
        return {'messages':[AIMessage(content=factual_fallback(result),response_metadata={
            'finish_reason':'answer_validation_failed',
            'sql_answer_validation':{'attempts':3,'repaired':False,'failures':failures}})]}
    return sql_answer_node
