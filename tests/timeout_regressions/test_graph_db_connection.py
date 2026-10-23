#!/usr/bin/env python3
"""Offline regression tests; never import project modules or open a connection.

--source-root selects config.py and db/connection.py (original or staged).
--reference-root supplies the unchanged provider/service function bodies.
All database connections are memory stubs; upload behavior is covered separately
by test_graph_upload_regression.py.
"""

import argparse
import ast
import contextlib
import dataclasses
import hashlib
import io
import json
import math
import sys
import threading
import time
import types
from datetime import datetime
from pathlib import Path


CONFIG = "graph/modules/Graph/backend/config.py"
CONNECTION = "graph/modules/Graph/backend/db/connection.py"
PROVIDER = "graph/modules/Graph/backend/providers/sql_provider.py"
SERVICE = "graph/modules/Graph/backend/services/graph_service.py"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    sources = {
        rel: ((args.source_root if rel in (CONFIG, CONNECTION) else args.reference_root) / rel).read_text()
        for rel in (CONFIG, CONNECTION, PROVIDER, SERVICE)
    }
    results = []

    def run_case(name, function):
        try:
            details = function()
            results.append({"case": name, "passed": True, "details": details})
        except AssertionError as exc:
            results.append({"case": name, "passed": False, "assertion": str(exc)})

    def execute(nodes, namespace):
        module = ast.Module(
            body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)] + nodes,
            type_ignores=[],
        )
        exec(compile(ast.fix_missing_locations(module), "<project-function-body>", "exec"), namespace)

    def node(rel, name):
        return next(
            item for item in ast.parse(sources[rel]).body
            if isinstance(item, (ast.FunctionDef, ast.ClassDef)) and item.name == name
        )

    def config(environment):
        def getenv(key, default=None):
            if any(word in key.lower() for word in ("password", "passwd", "token", "secret")):
                return "OFFLINE_FIXTURE_ONLY"
            return environment.get(key, default)

        namespace = {
            "dataclass": dataclasses.dataclass,
            "os": types.SimpleNamespace(getenv=getenv),
            "math": math,
            "__name__": "__main__",
        }
        declarations = [
            item for item in ast.parse(sources[CONFIG]).body
            if isinstance(item, (ast.FunctionDef, ast.ClassDef))
        ]
        exec(compile(ast.Module(body=declarations, type_ignores=[]), "<project-config>", "exec"), namespace)
        return namespace["Settings"]()

    class OfflineMySQLError(Exception):
        pass

    def connection_function(settings, connect):
        namespace = {
            "settings": settings,
            "pymysql": types.SimpleNamespace(connect=connect, MySQLError=OfflineMySQLError),
        }
        execute([node(CONNECTION, "get_mysql_connection")], namespace)
        return namespace["get_mysql_connection"]

    def collect_connect(environment):
        captured = {}
        sentinel = object()

        def connect(**kwargs):
            captured.update(kwargs)
            return sentinel

        returned = connection_function(config(environment), connect)()
        assert returned is sentinel, "successful connection must be returned unchanged"
        return captured

    def required_timeouts(environment, expected):
        kwargs = collect_connect(environment)
        actual = {key: kwargs.get(key) for key in expected}
        assert actual == expected, f"expected finite timeouts {expected}; actual {actual}"
        return actual

    defaults = dict(connect_timeout=5, read_timeout=10, write_timeout=10)
    run_case("default_connection_timeouts_5_10_10", lambda: required_timeouts({}, defaults))
    run_case(
        "positive_fractional_timeout_environment",
        lambda: required_timeouts(
            {"DB_CONNECT_TIMEOUT": "0.25", "DB_READ_TIMEOUT": "0.5", "DB_WRITE_TIMEOUT": "0.75"},
            dict(connect_timeout=0.25, read_timeout=0.5, write_timeout=0.75),
        ),
    )
    for value in ("0", "-1", "nan", "inf", "bad_value"):
        run_case(
            "invalid_timeout_environment_" + value,
            lambda value=value: required_timeouts(
                {"DB_CONNECT_TIMEOUT": value, "DB_READ_TIMEOUT": value, "DB_WRITE_TIMEOUT": value}, defaults,
            ),
        )

    def host_precedence():
        actual = config({"DB_HOST": "192.0.2.11", "DB_MYSQL_HOST": "192.0.2.22"}).db_host
        assert actual == "192.0.2.11", "explicit graph DB_HOST must win"
        return {"host": actual}

    def host_fallback():
        actual = config({"DB_MYSQL_HOST": "192.0.2.22"}).db_host
        assert actual == "192.0.2.22", f"DB_MYSQL_HOST fallback expected 192.0.2.22; actual {actual}"
        return {"host": actual}

    def empty_host_fallback():
        actual = config({"DB_HOST": "", "DB_MYSQL_HOST": "183.69.145.186"}).db_host
        assert actual == "183.69.145.186", f"empty DB_HOST must fall back to the new IP; actual {actual!r}"
        return {"host": actual}

    run_case("DB_HOST_has_priority", host_precedence)
    run_case("DB_MYSQL_HOST_fallback", host_fallback)
    run_case("empty_DB_HOST_fallback_to_new_ip", empty_host_fallback)

    def silent_error():
        def fail(**kwargs):
            raise OfflineMySQLError("synthetic authentication failure; OFFLINE_FIXTURE_ONLY")

        out, err = io.StringIO(), io.StringIO()
        start = time.monotonic()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            value = connection_function(config({}), fail)()
        assert value is None and not out.getvalue() and not err.getvalue(), "MySQLError must return None without printing"
        assert time.monotonic() - start < 1, "failure should not trigger retries or sleeps"
        return {"returned_none": True, "stdout_bytes": 0, "stderr_bytes": 0}

    run_case("mysql_error_returns_none_silently", silent_error)

    @dataclasses.dataclass
    class CurrentUser:
        user_id: str
        username: str
        enterprise_id: str
        enterprise_name: str

    clock = {"simulated_seconds": 0, "connect_calls": 0}
    configured_budget = collect_connect({}).get("connect_timeout", 10)

    def blackhole(**kwargs):
        clock["connect_calls"] += 1
        clock["simulated_seconds"] += kwargs.get("connect_timeout", 10)
        raise OfflineMySQLError("offline simulated connect timeout")

    provider_namespace = dict(
        GraphRepository=object, GraphTreeBuilder=object, NodeDetailResolver=object,
        RLock=threading.RLock, time=time.time, datetime=datetime, CurrentUser=CurrentUser,
        get_chat_current_user=lambda: None, get_mysql_connection=connection_function(config({}), blackhole),
    )
    execute([node(PROVIDER, "SQLGraphProvider")], provider_namespace)
    provider = provider_namespace["SQLGraphProvider"]()
    service_class = node(SERVICE, "GraphService")
    service_class.body = [
        item for item in service_class.body
        if (isinstance(item, ast.FunctionDef) and item.name in ("get_graph", "_make_graph_cache_key", "_load_graph_uncached"))
        or (isinstance(item, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id in ("INTERNAL_GRAPH_ID", "INTERNAL_GRAPH_NAME")
            for target in item.targets
        ))
    ]
    service_namespace = dict(
        get_sql_provider=lambda: provider, _GRAPH_CACHE_TTL=60,
        _graph_cache={}, _graph_cache_lock=threading.Lock(), time=time,
    )
    execute([service_class], service_namespace)
    GraphService = service_namespace["GraphService"]

    def assert_wait():
        assert clock["connect_calls"] == 2, "reference provider makes two sequential connection attempts"
        assert clock["simulated_seconds"] == 2 * configured_budget, "both attempts must use the configured finite timeout"

    def two_connections():
        clock.update(simulated_seconds=0, connect_calls=0)
        graph = GraphService.get_graph()
        assert_wait()
        assert graph["status"] == "unavailable", "failed database must preserve unavailable status"
        return dict(clock, graph_status=graph["status"], wait_is_simulated=True)

    run_case("existing_get_graph_retries_failed_connection_twice", two_connections)

    summary = {
        "source_root": str(args.source_root), "reference_root": str(args.reference_root),
        "cases": results,
        "source_sha256": {rel: hashlib.sha256(text.encode()).hexdigest() for rel, text in sources.items()},
        "safety": {"network_requests": 0, "real_sql_statements": 0, "project_module_imports": 0, "production_file_writes": 0},
        "limitations": [
            "Upload status, persistence and SQL-failure handling are covered by test_graph_upload_regression.py, not this suite.",
            "Wait durations are simulated, not measured live endpoint latency.",
            "Read/write timeouts constrain individual operations, not the whole graph request.",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    args.report.chmod(0o600)
    failed = [item["case"] for item in results if not item["passed"]]
    print(json.dumps({"report": str(args.report), "cases": len(results), "passed": len(results) - len(failed), "failed": failed}))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
