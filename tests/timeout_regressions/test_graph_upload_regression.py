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

    def post(self, files=('good.md',), default='true'):
        data = {'file': [(io.BytesIO(b'synthetic test content'), name) for name in files]}
        if default is not None:
            data['isDefault'] = default
        with app.app.test_client() as client:
            response = client.post('/upload', data=data, content_type='multipart/form-data')
        return response, response.get_json(silent=True) or {}

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
