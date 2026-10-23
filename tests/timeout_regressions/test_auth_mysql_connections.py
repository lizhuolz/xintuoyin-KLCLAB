"""Bounded auth connection regressions; no project import or production network.

Run with the project's Pixi Python:
    python -B tests/timeout_regressions/test_auth_mysql_connections.py \
        --source-root . --report /tmp/auth-mysql-regressions.json

Eight AST/stub checks cover ownership, cleanup and auth degradation. Two real
PyMySQL cases use a temporary 127.0.0.1 MySQL-protocol fixture, exclusively dummy
credentials, no real database, no Redis and no model. Only finite source timeout
values are scaled to --io-timeout; missing/None source values remain None.
"""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import contextlib
import hashlib
import inspect
import io
import json
import os
import socket
import struct
from pathlib import Path
import threading
import time
import types

import pymysql


class LoopbackMysqlFixture:
    """Minimal protocol fixture; silent greeting or first silent COM_PING only."""

    def __init__(self, mode, hold):
        self.mode = mode
        self.hold = hold
        self.stop = threading.Event()
        self.ping_seen = threading.Event()
        self.accepted = 0
        self.completed_handshakes = 0
        self.server_forced_close = False
        self.errors = []
        self.clients = []
        self.workers = []
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.listener.bind(('127.0.0.1', 0))
            self.listener.listen(4)
            self.listener.settimeout(0.05)
        except BaseException:
            self.listener.close()
            raise
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self._accept, daemon=True)

    @staticmethod
    def _send(client, payload, sequence):
        client.sendall(len(payload).to_bytes(3, 'little') + bytes([sequence]) + payload)

    @staticmethod
    def _receive(client):
        def read_exact(size):
            chunks = bytearray()
            while len(chunks) < size:
                chunk = client.recv(size - len(chunks))
                if not chunk:
                    raise EOFError('fixture peer closed')
                chunks.extend(chunk)
            return bytes(chunks)

        header = read_exact(4)
        size = int.from_bytes(header[:3], 'little')
        if size > 65536:
            raise ValueError('fixture oversized packet')
        return read_exact(size)

    def _accept(self):
        while not self.stop.is_set():
            try:
                client, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.accepted += 1
            number = self.accepted
            self.clients.append(client)
            client.settimeout(self.hold + 1)
            worker = threading.Thread(target=self._serve, args=(client, number), daemon=True)
            self.workers.append(worker)
            worker.start()

    def _serve(self, client, number):
        try:
            if self.mode == 'silent_greeting':
                self.server_forced_close = not self.stop.wait(self.hold)
                return
            # HandshakeV10, synthetic salt, dummy login only; no actual DB exists.
            capabilities = 1 | 8 | 512 | 8192 | 32768
            greeting = (
                b'\x0a8.0.0-fixture\0' + struct.pack('<I', number)
                + b'12345678\0' + struct.pack('<H', capabilities & 65535)
                + struct.pack('<BHHB', 33, 2, capabilities >> 16, 21)
                + b'\0' * 10 + b'abcdefghijkl\0'
            )
            self._send(client, greeting, 0)
            self._receive(client)  # Discard synthetic authentication response.
            self._send(client, b'\x00\x00\x00\x02\x00\x00\x00', 2)
            self.completed_handshakes += 1
            while not self.stop.is_set():
                command = self._receive(client)
                if command[:1] == b'\x01':  # COM_QUIT
                    return
                if command[:1] == b'\x0e':  # COM_PING
                    self.ping_seen.set()
                    if number == 1:
                        self.server_forced_close = not self.stop.wait(self.hold)
                        return
                elif command[:1] == b'\x03':  # Connection initialization only.
                    statement = command[1:].upper()
                    if not (statement.startswith(b'SET NAMES ') or statement.startswith(b'SET AUTOCOMMIT')):
                        raise ValueError('unexpected non-initialization query')
                else:
                    raise ValueError('unexpected fixture command')
                self._send(client, b'\x00\x00\x00\x00\x00\x00\x00', 1)
        except (EOFError, ConnectionError, socket.timeout):
            pass
        except OSError:
            if not self.stop.is_set():
                self.errors.append('unexpected_socket_error')
        except Exception as exc:
            self.errors.append(type(exc).__name__)
        finally:
            client.close()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.listener.close()
        self.thread.join(1)
        for client in self.clients:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client.close()
        for worker in self.workers:
            worker.join(1)
        if self.thread.is_alive() or any(worker.is_alive() for worker in self.workers):
            raise RuntimeError('loopback fixture failed to stop')


def real_driver_checks(namespace, io_timeout, deadline, server_hold):
    results = {}
    for mode, name in [
        ('silent_greeting', 'real_driver_silent_handshake_has_finite_read_timeout'),
        ('silent_ping', 'real_driver_stale_ping_recovers_before_server_forced_close'),
    ]:
        with LoopbackMysqlFixture(mode, server_hold) as fixture:
            created = []
            calls = []

            def connect(**kwargs):
                safe = dict(kwargs)
                safe.update(host='127.0.0.1', port=fixture.port, user='fixture_user',
                            password='fixture_only', db='fixture_db', connect_timeout=1)
                # Preserve missing/None values: the old helper must remain unbounded.
                for key in ['read_timeout', 'write_timeout']:
                    if isinstance(safe.get(key), (int, float)) and safe[key] > 0:
                        safe[key] = io_timeout
                calls.append({key: safe.get(key) for key in ['read_timeout', 'write_timeout']})
                connection = pymysql.connect(**safe)
                created.append(connection)
                return connection

            ns = namespace(connect)
            outcome = 'returned'
            timeout_error = False
            error_code = None
            if mode == 'silent_ping':
                first = ns['_get_mysql_conn']()
                assert fixture.completed_handshakes == 1
            started = time.monotonic()
            try:
                ns['_get_mysql_conn']()
            except pymysql.MySQLError as exc:
                outcome = type(exc).__name__
                error_code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
                timeout_error = 'timed out' in str(exc).lower()
            elapsed = time.monotonic() - started
            result = {
                'driver': 'actual installed PyMySQL', 'transport': '127.0.0.1 TCP',
                'elapsed_seconds': round(elapsed, 4), 'deadline_seconds': deadline,
                'scaled_finite_read_timeout_seconds': io_timeout,
                'source_supplied_finite_read_timeout': calls[0]['read_timeout'] is not None,
                'accepted_tcp_connections': fixture.accepted,
                'completed_protocol_handshakes': fixture.completed_handshakes,
                'server_forced_close_before_client_completed': fixture.server_forced_close,
                'ping_received': fixture.ping_seen.is_set(),
                'outcome': outcome, 'error_code': error_code,
                'driver_error_identifies_timeout': timeout_error,
                'fixture_errors': list(fixture.errors),
            }
            if mode == 'silent_greeting':
                result['passed'] = (elapsed < deadline and timeout_error and fixture.accepted == 1
                                    and not fixture.server_forced_close and not fixture.errors)
            else:
                result['passed'] = (elapsed < deadline and outcome == 'returned'
                                    and fixture.ping_seen.is_set() and fixture.accepted == 2
                                    and not fixture.server_forced_close and not fixture.errors)
            results[name] = result
            for connection in created:
                try:
                    connection.close()
                except pymysql.MySQLError:
                    pass
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--io-timeout', type=float, default=0.1,
                        help='Scale finite source read/write timeouts for real loopback tests.')
    parser.add_argument('--deadline', type=float, default=0.45,
                        help='Maximum client completion time accepted by loopback tests.')
    parser.add_argument('--server-hold', type=float, default=0.8,
                        help='Independent bound before unresponsive fixture closes its socket.')
    args = parser.parse_args()
    if not 0 < args.io_timeout * 3 < args.deadline < args.server_hold:
        parser.error('Require 0 < io-timeout * 3 < deadline < server-hold.')
    source = (args.source_root / 'backend/services/user_auth.py').read_text()
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {
        '_get_mysql_conn', '_query_tenant_name', '_determine_role', 'get_user_by_token',
    }]
    selected = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)] + functions, type_ignores=[])
    code = compile(ast.fix_missing_locations(selected), '<original-auth-functions>', 'exec')
    observations = {}

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, *args):
            pass

        def fetchone(self):
            return ('OFFLINE_COMPANY_FIXTURE',)

    class Connection:
        def __init__(self, number, parameters):
            self.number = number
            self.parameters = parameters
            self.closed = False
            self.fail_ping = False

        def ping(self, reconnect=False):
            if self.fail_ping:
                raise TimeoutError('offline stale connection')

        def close(self):
            self.closed = True

        def cursor(self):
            return Cursor()

    def namespace(factory, redis_get=None):
        def getenv(name, default=None):
            # All connection parameters are fixture values, never production credentials.
            fixtures = {'DB_MYSQL_HOST': '127.0.0.1', 'DB_MYSQL_PORT': '1',
                        'DB_MYSQL_USER': 'fixture_user', 'DB_MYSQL_PASSWORD': 'OFFLINE_ONLY',
                        'DB_MYSQL_NAME': 'fixture_db'}
            return fixtures.get(name, default)

        value = {
            'os': types.SimpleNamespace(getenv=getenv),
            'pymysql': types.SimpleNamespace(connect=factory),
            '_mysql_conn': None, '_mysql_local': threading.local(),
            'ROLE_GUEST': 'guest', 'ROLE_USER': 'user', 'ROLE_ENTERPRISE_ADMIN': 'enterprise_admin',
            '_token_cache': {}, 'TOKEN_CACHE_TTL': 300, 'time': time, 'json': json,
            'REDIS_TOKEN_PREFIX': 'offline-session:',
            '_get_redis': lambda: types.SimpleNamespace(get=redis_get or (lambda key: json.dumps({
                'roleName': '超级管理员', 'tenantId': 1, 'staffId': 2, 'id': 3,
            }))),
        }
        exec(code, value)
        return value

    def basic_factory():
        made = []

        def connect(**kwargs):
            connection = Connection(len(made) + 1, kwargs)
            made.append(connection)
            return connection

        return connect, made

    factory, made = basic_factory()
    ns = namespace(factory)
    first = ns['_get_mysql_conn']()
    second = ns['_get_mysql_conn']()
    defaults = inspect.signature(pymysql.connections.Connection).parameters
    observations['connection_timeouts'] = {
        'connect_timeout': first.parameters.get('connect_timeout'),
        'read_timeout': first.parameters.get('read_timeout', defaults['read_timeout'].default),
        'write_timeout': first.parameters.get('write_timeout', defaults['write_timeout'].default),
        'explicit_read_timeout': 'read_timeout' in first.parameters,
        'explicit_write_timeout': 'write_timeout' in first.parameters,
    }
    same_thread_reuse = first is second
    first.fail_ping = True
    replacement = ns['_get_mysql_conn']()
    observations['stale_connection_replaced'] = replacement is not first
    observations['stale_connection_closed'] = first.closed

    factory, made = basic_factory()
    ns = namespace(factory)
    first_ready, release = threading.Event(), threading.Event()

    def first_thread():
        connection = ns['_get_mysql_conn']()
        first_ready.set()
        if not release.wait(2):
            raise TimeoutError('fixture thread hold exceeded')
        return connection.number

    with ThreadPoolExecutor(max_workers=2) as executor:
        future = executor.submit(first_thread)
        try:
            assert first_ready.wait(1)
            other = executor.submit(ns['_get_mysql_conn']).result(timeout=1)
        finally:
            release.set()
        first_number = future.result(timeout=1)
    observations['thread_ownership'] = {
        'two_distinct_threads_used': True,
        'same_connection_object': first_number == other.number,
        'connection_count': len(made),
    }

    # Prove simultaneous entry into ping on one connection, without real sockets.
    lock = threading.Lock()
    blocking = threading.Event()
    both_entered, release = threading.Event(), threading.Event()
    total_entries = [0]
    active_by_connection, max_by_connection = {}, {}
    made = []

    class OverlapConnection(Connection):
        def ping(self, reconnect=False):
            if not blocking.is_set():
                return
            with lock:
                active_by_connection[self.number] = active_by_connection.get(self.number, 0) + 1
                max_by_connection[self.number] = max(max_by_connection.get(self.number, 0), active_by_connection[self.number])
                total_entries[0] += 1
                if total_entries[0] >= 2:
                    both_entered.set()
            try:
                if not release.wait(2):
                    raise TimeoutError('fixture concurrent ping hold exceeded')
            finally:
                with lock:
                    active_by_connection[self.number] -= 1

    def overlap_factory(**kwargs):
        with lock:
            connection = OverlapConnection(len(made) + 1, kwargs)
            made.append(connection)
            return connection

    ns = namespace(overlap_factory)
    ready = threading.Barrier(2, timeout=1)
    # Seed one worker first so original shared-global initialization cannot race.
    first_seeded = threading.Event()

    def overlap_worker(index):
        if index:
            assert first_seeded.wait(1)
        ns['_get_mysql_conn']()
        if not index:
            first_seeded.set()
        ready.wait()
        blocking.set()
        ns['_get_mysql_conn']()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(overlap_worker, index) for index in range(2)]
        try:
            assert both_entered.wait(1)
        finally:
            release.set()
        for future in futures:
            future.result(timeout=1)
    observations['concurrent_ping'] = {
        'max_concurrent_calls_on_one_connection': max(max_by_connection.values()),
        'simultaneous_ping_calls_total': total_entries[0],
        'real_network_operations': 0,
    }

    # Fresh auth: Redis GET completes immediately, then company enrichment reaches ping.
    redis_done, ping_entered, release = threading.Event(), threading.Event(), threading.Event()
    made = []

    class BlockingConnection(Connection):
        def ping(self, reconnect=False):
            ping_entered.set()
            configured = self.parameters.get('read_timeout')
            # Scale a finite driver timeout to 50ms; otherwise hold until explicit release.
            wait_seconds = 0.05 if configured is not None else 2
            if not release.wait(wait_seconds):
                raise TimeoutError('offline simulated read timeout')

    def blocking_factory(**kwargs):
        cls = BlockingConnection if not made else Connection
        connection = cls(len(made) + 1, kwargs)
        made.append(connection)
        return connection

    def redis_get(key):
        redis_done.set()
        return json.dumps({'roleName': '超级管理员', 'tenantId': 1, 'staffId': 2, 'id': 3})

    ns = namespace(blocking_factory, redis_get)

    def fresh_auth():
        ns['_get_mysql_conn']()  # Seed this worker's connection before the fresh lookup.
        return ns['get_user_by_token']('offline-only')

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fresh_auth)
        try:
            assert redis_done.wait(1) and ping_entered.wait(1)
            time.sleep(0.12)
            completed_without_manual_release = future.done()
        finally:
            release.set()
        user = future.result(timeout=1)
    observations['fresh_auth_company_lookup'] = {
        'redis_get_finished_before_mysql_ping_wait': redis_done.is_set(),
        'cached_mysql_ping_entered': ping_entered.is_set(),
        'auth_completed_before_manual_release': completed_without_manual_release,
        'eventually_recognized_role': user.get('role'),
        'waits_are_simulated_and_bounded': True,
        'finite_read_timeout_scaled_to_seconds': 0.05,
    }

    def unavailable(**kwargs):
        raise TimeoutError('offline company database unavailable')

    ns = namespace(unavailable)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        degraded_user = ns['get_user_by_token']('offline-degraded')

    timeout_values = observations['connection_timeouts']
    checks = {
        'finite_read_and_write_timeouts': all(isinstance(timeout_values[name], (int, float)) and timeout_values[name] > 0
                                              for name in ['read_timeout', 'write_timeout']),
        'connections_are_not_shared_between_threads': not observations['thread_ownership']['same_connection_object'],
        'no_simultaneous_ping_on_one_connection': observations['concurrent_ping']['max_concurrent_calls_on_one_connection'] == 1,
        'finite_read_timeout_ends_simulated_auth_stall': completed_without_manual_release,
        'stale_connection_is_closed_before_replacement': observations['stale_connection_closed'],
        'same_thread_connection_reuse_preserved': same_thread_reuse,
        'optional_company_error_preserves_authenticated_role': degraded_user.get('role') == 'enterprise_admin',
    }
    # Model PyMySQL's documented reconnect=True path without network: one internal
    # connect attempt is made before this helper regains control on failure.
    reconnect_options = []
    internal_reconnects = []
    made = []

    class ReconnectConnection(Connection):
        def ping(self, reconnect=False):
            reconnect_options.append(reconnect)
            if reconnect:
                internal_reconnects.append(True)
            raise TimeoutError('fixture stale connection and reconnect unavailable')

    def reconnect_factory(**kwargs):
        connection = ReconnectConnection(len(made) + 1, kwargs)
        made.append(connection)
        return connection

    ns = namespace(reconnect_factory)
    ns['_get_mysql_conn']()
    ns['_get_mysql_conn']()
    observations['single_owner_reconnect'] = {
        'ping_reconnect_options': reconnect_options,
        'helper_reconnect_attempts_after_stale_ping': len(made) - 1,
        'simulated_sdk_internal_reconnect_attempts': len(internal_reconnects),
    }
    checks['stale_ping_disables_sdk_reconnect_and_helper_rebuilds_once'] = (
        reconnect_options == [False] and len(made) == 2 and not internal_reconnects
    )
    loopback = real_driver_checks(namespace, args.io_timeout, args.deadline, args.server_hold)
    checks.update({name: result['passed'] for name, result in loopback.items()})
    report = {
        'source_root': str(args.source_root), 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'offline_observations': observations, 'candidate_regression_checks': checks,
        'real_driver_loopback_observations': loopback,
        'test_layers': {'ast_stub_checks': 8, 'actual_pymysql_loopback_checks': 2},
        'passed': all(checks.values()),
        'safety': {'external_network_operations': 0, 'loopback_only': True,
                   'real_sql_statements': 0, 'fixture_initialization_commands_only': True,
                   'real_token_reads': 0, 'business_rows_read': 0, 'production_module_imports': 0, 'production_file_writes': 0},
        'limitations': ['Eight AST/stub checks do not measure real socket timeouts; two additional cases run actual PyMySQL against a local protocol fixture.',
                        'Only finite source read/write timeouts are shortened for loopback tests; absent/None timeouts remain None.',
                        'No production network failure or exact production 5-second recovery duration is recreated.',
                        'Per-operation driver timeouts do not establish a whole-request deadline.',
                        'This test does not deploy code or change already-running production connections.'],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    args.report.chmod(0o600)
    print(json.dumps({'report': str(args.report), 'checks': len(checks), 'passed': sum(checks.values()),
                      'failed': [name for name, passed in checks.items() if not passed]}))
    return 0 if all(checks.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
