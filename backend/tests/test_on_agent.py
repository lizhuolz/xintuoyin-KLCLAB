import importlib.util
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / 'backend'
REPORT_DIR = Path(__file__).resolve().parent / 'reports'
REPORT_DIR.mkdir(parents=True, exist_ok=True)
BASE_URL = os.environ.get('AGENT_BASE_URL', 'http://127.0.0.1:8069').rstrip('/')
TIMEOUT = float(os.environ.get('AGENT_TEST_TIMEOUT', '180'))


REQUIREMENTS: List[Dict[str, Any]] = [
    {
        'id': 'REQ-THINKING',
        'source_rows': '43-53',
        'module': '企业端-思考过程',
        'name': '思考过程展示与开关',
        'backend_scope': 'Agent 在推理时输出思考过程，并支持开关。',
        'status': 'not_testable_via_current_api',
        'reason': '/api/chat 当前仅返回 text/plain 最终回答，不返回独立思考过程流或开关状态。',
    },
    {
        'id': 'REQ-WEB',
        'source_rows': '54-61',
        'module': '企业端-联网功能',
        'name': '联网实时检索',
        'backend_scope': '根据 web_search 开关进行实时信息检索。',
        'status': 'partially_testable',
        'reason': '当前 /api/chat 仅暴露 web_search 布尔开关，不返回检索来源或执行细节，结果受外部网络与模型行为影响。',
    },
    {
        'id': 'REQ-SOURCE',
        'source_rows': '62-72',
        'module': '参考来源',
        'name': '参考来源展示与合规过滤',
        'backend_scope': '回答带来源标注、来源卡片与合规过滤。',
        'status': 'not_testable_via_current_api',
        'reason': '/api/chat 当前不返回引用来源结构化字段，也不返回来源卡片元数据。',
    },
    {
        'id': 'REQ-DB',
        'source_rows': '73-83',
        'module': '链接数据库',
        'name': '自然语言转 SQL 与数据库查询',
        'backend_scope': '按选定数据库执行查询并返回结果。',
        'status': 'partially_testable',
        'reason': '当前公开接口仅暴露 db_version 提示词注入能力，未暴露 SQL、权限判断、结果集或数据库选择列表。',
    },
    {
        'id': 'REQ-FILE',
        'source_rows': '86-100',
        'module': '上传文件--解析文件',
        'name': '文件解析、结构提取与基于附件问答',
        'backend_scope': '解析上传文件并将内容注入对话上下文。',
        'status': 'live_testable',
        'reason': '当前 /api/chat 支持 files 上传，并在后端解析 txt/pdf/docx/xlsx/xls。',
    },
    {
        'id': 'REQ-KB',
        'source_rows': '195-213',
        'module': '企业端-动态知识库',
        'name': '动态知识库问答',
        'backend_scope': '上传知识库文件后，按分类进行检索问答。',
        'status': 'live_testable',
        'reason': '当前后端提供 KB 创建、上传、删除与 /api/chat 的 kb_category 检索入口。',
    },
    {
        'id': 'REQ-HISTORY',
        'source_rows': '221-230',
        'module': '企业端-历史对话',
        'name': '历史对话落盘、删除与新会话隔离',
        'backend_scope': '对话持久化、删除以及不同会话的上下文隔离。',
        'status': 'partially_testable',
        'reason': '当前后端支持落盘与删除，但未提供列表、搜索、批量删除等公开 API。',
    },
]


@dataclass
class AgentCase:
    case_id: str
    requirement_id: str
    name: str
    prompt: str
    expected_all: List[str] = field(default_factory=list)
    expected_any: List[str] = field(default_factory=list)
    forbidden: List[str] = field(default_factory=list)
    files: List[Dict[str, Any]] = field(default_factory=list)
    kb_setup: Optional[Dict[str, Any]] = None
    kb_category: Optional[str] = None
    web_search: bool = False
    db_version: Optional[str] = None
    user_identity: str = 'agent_test'
    validator: Optional[str] = None
    notes: str = ''


LIVE_CASES: List[AgentCase] = [
    AgentCase(
        case_id='CASE-FILE-TXT',
        requirement_id='REQ-FILE',
        name='TXT 附件解析与引用',
        prompt='我上传了一个文件。请告诉我里面的项目代号和上线日期。',
        expected_all=['北极星', '2026年4月15日'],
        files=[
            {
                'filename': 'project.txt',
                'content': '项目代号：北极星。上线日期：2026年4月15日。负责人：林州。',
                'content_type': 'text/plain',
            }
        ],
        notes='验证 txt 文件内容是否被注入问答上下文。',
    ),
    AgentCase(
        case_id='CASE-FILE-MULTI',
        requirement_id='REQ-FILE',
        name='多文件联合解析',
        prompt='请根据我上传的两个文件，分别告诉我研发负责人和测试负责人是谁。',
        expected_all=['张敏', '李卓'],
        files=[
            {
                'filename': 'rd.txt',
                'content': '研发负责人：张敏。',
                'content_type': 'text/plain',
            },
            {
                'filename': 'qa.txt',
                'content': '测试负责人：李卓。',
                'content_type': 'text/plain',
            },
        ],
        notes='验证多个附件是否被同时拼接进上下文。',
    ),
    AgentCase(
        case_id='CASE-FILE-XLSX',
        requirement_id='REQ-FILE',
        name='Excel 解析能力',
        prompt='我上传了一个Excel文件。请告诉我它包含哪些工作表名称。',
        expected_all=['Sheet1', 'Sheet3'],
        files=[
            {
                'filename': 'AI用例.xlsx',
                'source_path': str(REPO_ROOT / 'AI用例.xlsx'),
                'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            }
        ],
        notes='按需求 Excel 应可解析工作表信息；当前环境缺少 openpyxl，预计可能失败。',
    ),
    AgentCase(
        case_id='CASE-KB-BASIC',
        requirement_id='REQ-KB',
        name='动态知识库问答',
        prompt='知识库里提到的报销审批时限是多久？',
        expected_any=['3个工作日'],
        kb_setup={
            'name_prefix': 'agent_kb_',
            'category_prefix': 'agent_test_category_',
            'files': [
                {
                    'filename': 'policy.txt',
                    'content': '差旅报销制度：普通报销审批时限为3个工作日，加急流程为1个工作日。',
                    'content_type': 'text/plain',
                }
            ],
        },
        notes='验证 KB 创建、文件上传、索引刷新后，聊天接口是否能基于 kb_category 检索。',
    ),
    AgentCase(
        case_id='CASE-HISTORY-PERSIST',
        requirement_id='REQ-HISTORY',
        name='历史对话落盘',
        prompt='请回复一句：历史记录测试成功。',
        expected_any=['历史记录测试成功'],
        validator='history_file_created',
        notes='验证对话完成后 backend/history_storage 下是否生成对应会话文件。',
    ),
    AgentCase(
        case_id='CASE-HISTORY-ISOLATION',
        requirement_id='REQ-HISTORY',
        name='新会话不继承旧上下文',
        prompt='上一轮会话里我说过什么暗号？如果你不知道，请直接说不知道。',
        expected_any=['不知道', '无法确定', '不清楚'],
        validator='history_isolation',
        notes='先在旧会话写入暗号，再用新会话提问，验证不会继承旧会话上下文。',
    ),
]


def load_env_exports(env_file: Path) -> None:
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line.startswith('export '):
            continue
        content = line[7:].strip()
        if '=' not in content:
            continue
        key, value = content.split('=', 1)
        value = value.strip().strip('"').strip("'")
        if ' # ' in value:
            value = value.split(' # ')[0].strip()
        os.environ.setdefault(key.strip(), value)


MANUAL_OR_UNTESTABLE_CASES: List[Dict[str, Any]] = [
    {
        'requirement_id': 'REQ-THINKING',
        'name': '思考过程展示/关闭',
        'reason': '当前 API 不返回思考过程流，无法通过 /api/chat 自动核对。',
        'suggestion': '如需测试，需后端新增结构化字段或单独流通道。',
    },
    {
        'requirement_id': 'REQ-WEB',
        'name': '联网实时数据与时效性',
        'reason': '结果依赖外部网络与模型调用，且当前接口不返回来源元数据，自动断言稳定性差。',
        'suggestion': '建议增加引用来源、抓取时间戳与是否走联网链路的结构化字段。',
    },
    {
        'requirement_id': 'REQ-SOURCE',
        'name': '参考来源弹窗/来源卡片/合规过滤',
        'reason': '当前 API 不返回来源列表、来源标题、副标题、过滤原因。',
        'suggestion': '建议新增 sources 字段与过滤日志。',
    },
    {
        'requirement_id': 'REQ-DB',
        'name': 'NL2SQL、权限判断、无数据和断链处理',
        'reason': '公开接口未返回 SQL、结果集、错误码或数据库元信息，无法对需求逐项自动核验。',
        'suggestion': '建议提供数据库查询专用接口或调试字段。',
    },
]


class AgentTester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.http_client = httpx.Client(timeout=TIMEOUT)
        self.local_client: Optional[TestClient] = None
        self.mode = 'http'
        self.history_dir = BACKEND_DIR / 'history_storage'
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        self.http_client.close()
        if self.local_client is not None:
            self.local_client.close()

    def _load_local_client(self) -> None:
        if self.local_client is not None:
            self.mode = 'testclient'
            return

        load_env_exports(BACKEND_DIR / 'script' / 'setting.sh')
        load_env_exports(BACKEND_DIR / 'script' / 'env.sh')
        load_env_exports(BACKEND_DIR / 'env.sh')

        if str(BACKEND_DIR) not in sys.path:
            sys.path.insert(0, str(BACKEND_DIR))

        spec = importlib.util.spec_from_file_location('agent_app_live_test', BACKEND_DIR / 'app.py')
        if spec is None or spec.loader is None:
            raise RuntimeError('failed to load backend/app.py for local test client')

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.local_client = TestClient(module.app)
        self.mode = 'testclient'

    def _request(self, method: str, path: str, **kwargs):
        if self.mode == 'http':
            return self.http_client.request(method, f'{self.base_url}{path}', **kwargs)
        return self.local_client.request(method, path, **kwargs)

    def check_backend(self) -> Dict[str, Any]:
        url = f'{self.base_url}/api/kb/list'
        response = self._request('GET', '/api/kb/list')
        if response.status_code != 200:
            self._load_local_client()
            response = self._request('GET', '/api/kb/list')
        return {
            'url': url,
            'status_code': response.status_code,
            'ok': response.status_code == 200,
            'body_preview': response.text[:500],
            'mode': self.mode,
        }

    def create_kb(self, name: str, category: str) -> Dict[str, Any]:
        response = self._request(
            'POST',
            '/api/kb/create',
            data={'name': name, 'model': 'openai', 'category': category},
        )
        payload = response.json()
        if response.status_code != 201 or not payload.get('success'):
            raise RuntimeError(f'create_kb failed: {response.status_code} {response.text}')
        return payload['data']

    def upload_kb_file(self, kb_id: str, file_spec: Dict[str, Any]) -> Dict[str, Any]:
        content = self._resolve_file_content(file_spec)
        response = self._request(
            'POST',
            f'/api/kb/{kb_id}/upload',
            files={'file': (file_spec['filename'], content, file_spec['content_type'])},
        )
        payload = response.json()
        if response.status_code != 201 or not payload.get('success'):
            raise RuntimeError(f'upload_kb_file failed: {response.status_code} {response.text}')
        return payload['data']

    def delete_kb(self, kb_id: str) -> None:
        try:
            self._request('DELETE', f'/api/kb/{kb_id}')
        except Exception:
            pass

    def delete_history(self, conversation_id: str) -> None:
        try:
            self._request('DELETE', f'/api/chat/{conversation_id}')
        except Exception:
            pass

    def chat(
        self,
        prompt: str,
        conversation_id: str,
        *,
        files: Optional[List[Dict[str, Any]]] = None,
        web_search: bool = False,
        db_version: Optional[str] = None,
        kb_category: Optional[str] = None,
        user_identity: str = 'agent_test',
    ) -> Dict[str, Any]:
        data = {
            'message': prompt,
            'conversation_id': conversation_id,
            'system_prompt': '你是一个严格依据上下文回答的助手。',
            'web_search': str(web_search).lower(),
            'user_identity': user_identity,
        }
        if db_version:
            data['db_version'] = db_version
        if kb_category:
            data['kb_category'] = kb_category

        upload_files: List[Any] = []
        for file_spec in files or []:
            upload_files.append(
                ('files', (file_spec['filename'], self._resolve_file_content(file_spec), file_spec['content_type']))
            )

        response = self._request('POST', '/api/chat', data=data, files=upload_files)
        return {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'text': response.text,
        }

    @staticmethod
    def _resolve_file_content(file_spec: Dict[str, Any]) -> bytes:
        if 'source_path' in file_spec:
            return Path(file_spec['source_path']).read_bytes()
        content = file_spec.get('content', b'')
        return content if isinstance(content, bytes) else str(content).encode('utf-8')


def evaluate_text_case(case: AgentCase, text: str) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    ok = True
    for keyword in case.expected_all:
        passed = keyword in text
        checks.append({'type': 'expected_all', 'keyword': keyword, 'passed': passed})
        ok = ok and passed
    if case.expected_any:
        passed_any = any(keyword in text for keyword in case.expected_any)
        checks.append({'type': 'expected_any', 'keywords': case.expected_any, 'passed': passed_any})
        ok = ok and passed_any
    for keyword in case.forbidden:
        passed = keyword not in text
        checks.append({'type': 'forbidden', 'keyword': keyword, 'passed': passed})
        ok = ok and passed
    return {'passed': ok, 'checks': checks}


def run_case(tester: AgentTester, case: AgentCase) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        'case_id': case.case_id,
        'requirement_id': case.requirement_id,
        'name': case.name,
        'notes': case.notes,
        'prompt': case.prompt,
        'expected_all': case.expected_all,
        'expected_any': case.expected_any,
        'status': 'failed',
    }
    kb_cleanup_id: Optional[str] = None
    try:
        if case.kb_setup:
            suffix = uuid.uuid4().hex[:8]
            kb_name = f"{case.kb_setup['name_prefix']}{suffix}"
            kb_category = f"{case.kb_setup['category_prefix']}{suffix}"
            kb = tester.create_kb(kb_name, kb_category)
            kb_cleanup_id = kb['id']
            for file_spec in case.kb_setup['files']:
                tester.upload_kb_file(kb_cleanup_id, file_spec)
            time.sleep(2)
            case_kb_category = kb_category
            result['kb_setup'] = {'id': kb_cleanup_id, 'name': kb_name, 'category': kb_category}
        else:
            case_kb_category = case.kb_category

        if case.validator == 'history_isolation':
            old_conv = f'agent_old_{uuid.uuid4().hex[:8]}'
            old_resp = tester.chat('记住这个暗号：极光-7429。只回复“记住了”。', old_conv)
            result['history_seed'] = {'conversation_id': old_conv, 'response': old_resp['text'][:300]}

        conversation_id = f"agent_case_{case.case_id.lower()}_{uuid.uuid4().hex[:8]}"
        chat_result = tester.chat(
            case.prompt,
            conversation_id,
            files=case.files,
            web_search=case.web_search,
            db_version=case.db_version,
            kb_category=case_kb_category,
            user_identity=case.user_identity,
        )
        result['conversation_id'] = conversation_id
        result['response_status'] = chat_result['status_code']
        result['response_headers'] = {
            'content-type': chat_result['headers'].get('content-type', ''),
            'x-request-id': chat_result['headers'].get('x-request-id', ''),
        }
        result['response_text'] = chat_result['text']

        if chat_result['status_code'] != 200:
            result['status'] = 'failed'
            result['failure_reason'] = f"unexpected status {chat_result['status_code']}"
            return result

        evaluation = evaluate_text_case(case, chat_result['text'])
        result['checks'] = evaluation['checks']
        passed = evaluation['passed']

        if case.validator == 'history_file_created':
            history_path = BACKEND_DIR / 'history_storage' / f'{conversation_id}.json'
            exists = history_path.exists()
            content_preview = ''
            if exists:
                content_preview = history_path.read_text(encoding='utf-8', errors='ignore')[:500]
            result['history_file'] = {'path': str(history_path), 'exists': exists, 'content_preview': content_preview}
            passed = passed and exists
            result.setdefault('checks', []).append({'type': 'history_file_created', 'passed': exists})
        elif case.validator == 'history_isolation':
            isolation_ok = all(token not in chat_result['text'] for token in ['极光-7429', '7429'])
            result.setdefault('checks', []).append({'type': 'history_isolation', 'passed': isolation_ok})
            passed = passed and isolation_ok

        result['status'] = 'passed' if passed else 'failed'
        if not passed:
            result['failure_reason'] = 'content check failed'
        return result
    except Exception as exc:
        result['status'] = 'error'
        result['failure_reason'] = str(exc)
        return result
    finally:
        if kb_cleanup_id:
            tester.delete_kb(kb_cleanup_id)
        if result.get('conversation_id'):
            tester.delete_history(result['conversation_id'])


def build_markdown_report(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append('# Agent Capability Test Report')
    lines.append('')
    lines.append('## Backend Probe')
    lines.append('')
    probe = report['probe']
    lines.append(f"- Base URL: `{report['base_url']}`")
    lines.append(f"- Health check: `{probe['status_code']}`")
    lines.append(f"- Reachable: `{probe['ok']}`")
    lines.append('')
    lines.append('## Extracted Requirements')
    lines.append('')
    for item in report['requirements']:
        lines.append(f"- `{item['id']}` | {item['module']} | {item['name']} | {item['status']}")
        lines.append(f"  Scope: {item['backend_scope']}")
        lines.append(f"  Source rows: {item['source_rows']}")
        lines.append(f"  Note: {item['reason']}")
    lines.append('')
    lines.append('## Executed Cases Summary')
    lines.append('')
    summary = report['summary']
    lines.append(f"- Total live cases: `{summary['total']}`")
    lines.append(f"- Passed: `{summary['passed']}`")
    lines.append(f"- Failed: `{summary['failed']}`")
    lines.append(f"- Errors: `{summary['errors']}`")
    lines.append('')
    lines.append('## Case Details')
    lines.append('')
    for case in report['case_results']:
        lines.append(f"### {case['case_id']} {case['name']}")
        lines.append('')
        lines.append(f"- Requirement: `{case['requirement_id']}`")
        lines.append(f"- Status: `{case['status']}`")
        lines.append(f"- Prompt: `{case['prompt']}`")
        if case.get('expected_all'):
            lines.append(f"- Expected all: `{case['expected_all']}`")
        if case.get('expected_any'):
            lines.append(f"- Expected any: `{case['expected_any']}`")
        if case.get('failure_reason'):
            lines.append(f"- Failure reason: `{case['failure_reason']}`")
        lines.append('')
        lines.append('```text')
        lines.append((case.get('response_text') or '')[:2000].rstrip())
        lines.append('```')
        if case.get('checks'):
            lines.append('')
            for check in case['checks']:
                if check['type'] == 'expected_all':
                    lines.append(f"- expected_all `{check['keyword']}` -> `{check['passed']}`")
                elif check['type'] == 'expected_any':
                    lines.append(f"- expected_any `{check['keywords']}` -> `{check['passed']}`")
                elif check['type'] == 'forbidden':
                    lines.append(f"- forbidden `{check['keyword']}` -> `{check['passed']}`")
                else:
                    lines.append(f"- {check['type']} -> `{check['passed']}`")
        lines.append('')
    lines.append('## Unmet Or Untestable Requirements')
    lines.append('')
    unmet = list(report['manual_or_untestable'])
    for case in report['case_results']:
        if case['status'] != 'passed':
            unmet.append(
                {
                    'requirement_id': case['requirement_id'],
                    'name': case['name'],
                    'reason': case.get('failure_reason', 'content check failed'),
                    'suggestion': 'See case details and actual response above.',
                }
            )
    if unmet:
        for item in unmet:
            lines.append(f"- `{item['requirement_id']}` | {item['name']} | {item['reason']}")
            lines.append(f"  Suggestion: {item['suggestion']}")
    else:
        lines.append('- None')
    lines.append('')
    return '\n'.join(lines) + '\n'


def main() -> int:
    tester = AgentTester(BASE_URL)
    try:
        probe = tester.check_backend()
        report: Dict[str, Any] = {
            'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'base_url': BASE_URL,
            'probe': probe,
            'requirements': REQUIREMENTS,
            'manual_or_untestable': MANUAL_OR_UNTESTABLE_CASES,
            'case_results': [],
        }

        if not probe['ok']:
            report['summary'] = {'total': 0, 'passed': 0, 'failed': 0, 'errors': 0}
        else:
            for case in LIVE_CASES:
                report['case_results'].append(run_case(tester, case))
            report['summary'] = {
                'total': len(report['case_results']),
                'passed': sum(1 for item in report['case_results'] if item['status'] == 'passed'),
                'failed': sum(1 for item in report['case_results'] if item['status'] == 'failed'),
                'errors': sum(1 for item in report['case_results'] if item['status'] == 'error'),
            }

        json_path = REPORT_DIR / 'agent_test_report.json'
        md_path = REPORT_DIR / 'agent_test_report.md'
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        md_path.write_text(build_markdown_report(report), encoding='utf-8')

        print(f'JSON report: {json_path}')
        print(f'Markdown report: {md_path}')
        print(json.dumps(report['summary'], ensure_ascii=False))
        return 0 if report['summary']['failed'] == 0 and report['summary']['errors'] == 0 else 1
    finally:
        tester.close()


if __name__ == '__main__':
    raise SystemExit(main())
