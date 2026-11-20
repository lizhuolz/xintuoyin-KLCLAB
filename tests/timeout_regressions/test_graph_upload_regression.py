"""Isolated graph upload regressions; no database, MinIO, model, or service calls.

XTY_SOURCE_ROOT selects the complete project source tree (defaults to production).
XTY_GRAPH_APP optionally selects a staged graph/app.py while importing unchanged
modules from XTY_SOURCE_ROOT. All workspaces are created beneath a new /tmp root.
Run this file in its own Python process because dependency stubs are process-wide.
"""
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT = Path(os.environ.get('XTY_SOURCE_ROOT', '/data2/dlx/projects/xty')).resolve()
SOURCE = Path(os.environ.get('XTY_GRAPH_APP', str(PROJECT / 'graph/app.py'))).resolve()
RUN = Path(tempfile.mkdtemp(prefix='xty-graph-upload-regression-'))
ROOT = RUN / 'graph'
ROOT.mkdir()
shutil.copyfile(SOURCE, ROOT / 'app.py')
(ROOT / 'modules').symlink_to(PROJECT / 'graph/modules', target_is_directory=True)
sys.dont_write_bytecode = True
def prohibit_external_io(event, args):
    if event in {'socket.connect', 'socket.bind', 'subprocess.Popen'}:
        raise AssertionError('External I/O is forbidden')
sys.addaudithook(prohibit_external_io)
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('graph_upload_regression_app', ROOT / 'app.py')
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
app.app.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False)
app.app.logger.disabled = True
from modules.Graph.backend.services.graph_service import GraphService
import modules.Graph.backend.api.routes as routes
import modules.Graph.backend.db.connection as connection
import modules.Graph.backend.providers.sql_provider as provider
import pymysql

def deny_sql(*args, **kwargs):
    raise AssertionError('Real SQL access is forbidden')
connection.get_mysql_connection = deny_sql
provider.get_mysql_connection = deny_sql

class UploadRegression(unittest.TestCase):
    def setUp(self):
        self.directory = RUN / self._testMethodName
        external = self.directory / 'external'
        internal = self.directory / 'internal'
        mapping = {'WORKSPACE_DIR': external, 'UPLOAD_FOLDER': external / 'uploads', 'OUTPUT_FILE': external / 'output_graph.json', 'META_FILE': external / 'workspace_meta.json', 'CURRENT_DB_FILE': external / 'current_db.txt', 'EXTERNAL_GRAPH_INDEX_FILE': external / 'graph_index.json', 'INTERNAL_BINDING_DIR': internal, 'INTERNAL_BINDING_UPLOAD_FOLDER': internal / 'uploads', 'INTERNAL_BINDING_GRAPH_FILE': internal / 'internal_binding_graph.json', 'INTERNAL_BINDING_META_FILE': internal / 'workspace_meta.json'}
        for name, value in mapping.items():
            self.assertTrue(value.resolve().is_relative_to(self.directory))
            setattr(app, name, value)
        app.UPLOAD_FOLDER.mkdir(parents=True)
        app.INTERNAL_BINDING_UPLOAD_FOLDER.mkdir(parents=True)
        app.CURRENT_DB_FILE.write_text('output_graph.json')
        self.sql_calls = 0
        self.prime_calls = 0
        self.sql_mode = 'ready'
        def sql_graph():
            self.sql_calls += 1
            if self.sql_mode == 'exception':
                raise pymysql.err.OperationalError(2003, 'synthetic_database_error')
            if self.sql_mode == 'unavailable':
                return {'nodes': [], 'links': [], 'status': 'unavailable'}
            return {'nodes': [{'id': 'sql1', 'name': 'synthetic_sql_node'}], 'links': [], 'status': 'ready'}
        def prime(*args):
            self.prime_calls += 1
        def extract(path, output):
            if path.name.startswith('bad'):
                return {'file': path.name, 'status': 'failed', 'returncode': 1, 'error': 'synthetic_extraction_failure'}
            return {'file': path.name, 'status': 'ok', 'returncode': 0, 'graph': {'nodes': [{'id': 'n1', 'name': 'synthetic_A'}, {'id': 'n2', 'name': 'synthetic_B'}], 'links': [{'source': 'n1', 'target': 'n2', 'relation': 'test_relation'}]}}
        GraphService.get_graph = staticmethod(sql_graph)
        routes.prime_combined_graph_cache = prime
        app.run_extractor = extract
        app._stage_file_for_chat = lambda path: app._make_graph_local_file_id(app._infer_graph_local_scope(path), path.name)

    def post(self, files=('good.md',), default='true', graph_id=None):
        data = {'file': [(io.BytesIO(b'synthetic test content'), name) for name in files]}
        if default is not None:
            data['isDefault'] = default
        if graph_id is not None:
            data['graphId'] = graph_id
        with app.app.test_client() as client:
            response = client.post('/upload', data=data, content_type='multipart/form-data')
        return response, response.get_json(silent=True) or {}

    def seed_graph(self, name, ids):
        app.save_graph_file(app.WORKSPACE_DIR / f'{name}.json', {
            'nodes': [{'id': key, 'name': key} for key in ids], 'links': []})

    def graph_ids(self, name):
        with app.app.test_client() as client:
            response = client.get('/get_graph', query_string={'graphId': name})
        self.assertEqual(response.status_code, 200)
        return {node['id'] for node in response.get_json()['data']['nodes']}

    def switch_while_extracting(self, name):
        original = app.run_extractor
        def extract(path, output):
            result = original(path, output)
            # Exercise the real switch route during the long-running extraction.
            with app.app.test_client() as client:
                response = client.post('/external/workspace/switch_db', json={'db_name': f'{name}.json'})
            self.assertEqual(response.status_code, 200)
            return result
        app.run_extractor = extract

    def test_new_and_append_have_distinct_targets_and_preserve_existing_nodes(self):
        self.seed_graph('existing', ['old1', 'old2'])
        _, new = self.post(default='false')
        _, appended = self.post(default='false', graph_id='existing.json')
        self.assertEqual(new['code'], 0)
        self.assertEqual(appended['code'], 0)
        self.assertNotEqual(new['data']['graphId'], appended['data']['graphId'])
        self.assertEqual(new['data']['graph']['node_count'], 2)
        self.assertEqual(appended['data']['graph']['node_count'], 4)
        self.assertEqual(self.graph_ids(new['data']['graphId']), {'n1', 'n2'})
        self.assertEqual(self.graph_ids('existing'), {'old1', 'old2', 'n1', 'n2'})

    def test_repeat_upload_keeps_existing_deduplication(self):
        _, new = self.post(default='false')
        graph_id = new['data']['graphId']
        _, repeated = self.post(default='false', graph_id=graph_id)
        self.assertEqual(repeated['code'], 0)
        self.assertEqual(repeated['data']['graphId'], graph_id)
        self.assertEqual(repeated['data']['graph'], {'node_count': 2, 'link_count': 1})
        self.assertEqual(self.graph_ids(graph_id), {'n1', 'n2'})

    def test_append_keeps_target_when_selection_changes_during_extraction(self):
        self.seed_graph('graph_a', ['a1'])
        self.seed_graph('graph_b', ['b1', 'b2'])
        self.switch_while_extracting('graph_b')
        _, payload = self.post(default='false', graph_id='graph_a')
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['graphId'], 'graph_a')
        self.assertEqual(self.graph_ids('graph_a'), {'a1', 'n1', 'n2'})
        self.assertEqual(self.graph_ids('graph_b'), {'b1', 'b2'})
        self.assertEqual(payload['data']['workspace']['node_count'], 3)
        self.assertEqual(payload['data']['graph']['node_count'], 3)
        self.assertEqual(app.get_current_db_name(), 'graph_b.json')
        self.assertIn('graph_a', app.read_external_graph_index())
        self.assertNotIn('graph_b', app.read_external_graph_index())

    def test_new_graph_keeps_target_when_selection_changes_during_extraction(self):
        self.seed_graph('graph_b', ['b1'])
        self.switch_while_extracting('graph_b')
        _, payload = self.post(default='false')
        self.assertEqual(payload['code'], 0)
        self.assertTrue(payload['data']['graphId'].startswith('new_graph_'))
        self.assertEqual(self.graph_ids(payload['data']['graphId']), {'n1', 'n2'})
        self.assertEqual(self.graph_ids('graph_b'), {'b1'})
        self.assertEqual(payload['data']['workspace']['node_count'], 2)

    def test_failed_append_returns_requested_graph_even_after_switch(self):
        self.seed_graph('graph_a', ['a1'])
        self.seed_graph('graph_b', ['b1', 'b2'])
        self.switch_while_extracting('graph_b')
        _, payload = self.post(('bad.md',), default='false', graph_id='graph_a')
        self.assertEqual(payload['code'], 422)
        self.assertEqual(payload['data']['graphId'], 'graph_a')
        self.assertEqual(payload['data']['graph']['node_count'], 1)
        self.assertEqual(payload['data']['workspace']['node_count'], 1)
        self.assertEqual(self.graph_ids('graph_a'), {'a1'})
        self.assertEqual(self.graph_ids('graph_b'), {'b1', 'b2'})

    def test_failed_new_graph_does_not_undo_another_selection(self):
        self.seed_graph('graph_a', ['a1'])
        self.seed_graph('graph_b', ['b1', 'b2'])
        app.CURRENT_DB_FILE.write_text('graph_a.json')
        self.switch_while_extracting('graph_b')
        _, payload = self.post(('bad.md',), default='false')
        self.assertEqual(payload['code'], 422)
        self.assertEqual(app.get_current_db_name(), 'graph_b.json')
        self.assertEqual(list(app.WORKSPACE_DIR.glob('new_graph_*.json')), [])
        self.assertEqual(self.graph_ids('graph_a'), {'a1'})
        self.assertEqual(self.graph_ids('graph_b'), {'b1', 'b2'})

    def test_failed_new_graph_restores_previous_selection_without_switch(self):
        self.seed_graph('graph_a', ['a1'])
        app.CURRENT_DB_FILE.write_text('graph_a.json')
        _, payload = self.post(('bad.md',), default='false')
        self.assertEqual(payload['code'], 422)
        self.assertEqual(app.get_current_db_name(), 'graph_a.json')
        self.assertEqual(payload['data']['graphId'], 'graph_a')
        self.assertEqual(payload['data']['workspace']['node_count'], 1)
        self.assertEqual(list(app.WORKSPACE_DIR.glob('new_graph_*.json')), [])

    def test_new_graph_does_not_reuse_an_existing_millisecond_id(self):
        from unittest.mock import patch
        self.seed_graph('new_graph_1234000', ['old'])
        with patch('time.time', return_value=1234):
            _, payload = self.post(default='false')
        self.assertEqual(payload['code'], 0)
        self.assertNotEqual(payload['data']['graphId'], 'new_graph_1234000')
        self.assertEqual(self.graph_ids('new_graph_1234000'), {'old'})
        self.assertEqual(self.graph_ids(payload['data']['graphId']), {'n1', 'n2'})

    def test_invalid_and_missing_graph_ids_preserve_error_contract(self):
        for graph_id, expected in [('missing', 404), ('../outside', 400), ('workspace_meta', 400)]:
            with self.subTest(graph_id=graph_id):
                response, payload = self.post(default='false', graph_id=graph_id)
                self.assertEqual(response.status_code, expected)
                self.assertEqual(payload['code'], expected)
        self.assertEqual(app.get_current_db_name(), 'output_graph.json')

    def assert_saved_binding(self):
        graph = app.read_internal_binding_graph()
        self.assertEqual(len(graph['nodes']), 2)
        self.assertEqual(len(graph['links']), 1)

    def test_saved_extraction_survives_sql_exception(self):
        self.sql_mode = 'exception'
        response, payload = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assert_saved_binding()
        self.assertEqual(payload['data']['graph']['node_count'], 2)
        self.assertTrue(payload['data'].get('warnings'))
        self.assertEqual(self.prime_calls, 0)

    def test_unavailable_sql_reports_partial_graph_warning(self):
        self.sql_mode = 'unavailable'
        response, payload = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assert_saved_binding()
        self.assertTrue(payload['data'].get('warnings'))
        self.assertEqual(self.prime_calls, 0)

    def test_all_extract_failures_skip_sql_and_preserve_422(self):
        self.sql_mode = 'exception'
        response, payload = self.post(('bad.md',))
        self.assertEqual(self.sql_calls, 0)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 422)
        self.assertEqual(payload['data']['preprocess_results'][0]['error'], 'synthetic_extraction_failure')
        self.assertFalse(app.INTERNAL_BINDING_GRAPH_FILE.exists())

    def test_partial_extraction_retains_207_despite_sql_error(self):
        self.sql_mode = 'exception'
        response, payload = self.post(('good.md', 'bad.md'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 207)
        self.assert_saved_binding()
        self.assertEqual([x['status'] for x in payload['data']['preprocess_results']], ['ok', 'failed'])
        self.assertTrue(payload['data'].get('warnings'))

    def test_successful_sql_merge_keeps_combined_counts(self):
        response, payload = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertEqual(payload['data']['binding_graph']['node_count'], 2)
        self.assertEqual(payload['data']['graph']['node_count'], 3)
        self.assertEqual(self.prime_calls, 1)
        self.assertFalse(payload['data'].get('warnings'))

    def test_external_upload_does_not_query_sql(self):
        self.sql_mode = 'exception'
        response, payload = self.post(default='false')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['code'], 0)
        self.assertEqual(self.sql_calls, 0)
        self.assertEqual(len(app.read_graph()['nodes']), 2)

    def test_omitted_flag_preserves_internal_default(self):
        response, payload = self.post(default=None)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['data']['isDefault'])
        self.assert_saved_binding()
        self.assertEqual(self.sql_calls, 1)

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(UploadRegression)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = {'source': str(SOURCE), 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'temp_directory': str(RUN), 'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'passed': result.wasSuccessful(), 'coverage': 'Real Flask multipart upload, local graph writes/merge, statuses; model/SQL/MinIO/cache priming stubbed; network and subprocess prohibited'}
    (RUN / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))
    raise SystemExit(0 if result.wasSuccessful() else 1)
