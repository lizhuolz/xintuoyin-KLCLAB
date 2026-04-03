# Light System Probe Report

- generated_at: 2026-03-30T20:38:52.326477
- backend: http://127.0.0.1:8000
- frontends: http://127.0.0.1:5173, http://127.0.0.1:5174
- minio_api: http://127.0.0.1:9000
- minio_console: http://127.0.0.1:9001
- all_critical_checks_passed: False
- passed_checks: 2/10

## Ports

- backend_new_session: status=502 ok=False elapsed_ms=5.47
- minio_api_health: status=200 ok=True elapsed_ms=4.64
- minio_console_root: status=200 ok=True elapsed_ms=5.31

## Frontend Proxy

- http://127.0.0.1:5173 root: status=200 ok=True
- http://127.0.0.1:5173 proxy_new_session: status=500 ok=False
- http://127.0.0.1:5173 proxy_kb_list: status=500 ok=False
- http://127.0.0.1:5174 root: status=200 ok=True
- http://127.0.0.1:5174 proxy_new_session: status=500 ok=False
- http://127.0.0.1:5174 proxy_kb_list: status=500 ok=False

## Backend API

- new_session: status=502 ok=False elapsed_ms=5.52

## KB Lifecycle

- create: status=502 ok=False elapsed_ms=5.65

## Stress

- backend_new_session: ok=0/12 failed=12 latency_ms(min/p50/max)=6.16/9.86/11.9
- backend_kb_list: ok=0/8 failed=8 latency_ms(min/p50/max)=6.34/9.1/10.88
- frontend_proxy_new_session: ok=0/8 failed=8 latency_ms(min/p50/max)=8.03/10.79/14.07