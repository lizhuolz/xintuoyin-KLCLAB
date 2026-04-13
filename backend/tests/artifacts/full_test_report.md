# Full Test Report

- generated_at: 2026-04-09 13:32:44
- conda_env: xtyAgent
- cpu_only_for_tests: true

## Suites

- full_unittest_discover: 85/86 passed, 1 flaky failure observed
- api_contract_suite: 82/82 passed
- tool_retry_suite: 4/4 passed

## Findings

- 首次 `python -m unittest discover -s tests -p "test*.py" -v` 运行中，`test_api_history_batch_delete` 出现 1 次偶发失败。
- 同一用例单独复测通过，`python tests/run_api_contract_tests.py` 也得到 `82/82` 全通过，说明当前更像顺序相关或环境抖动，而不是稳定功能回归。
- `tests.test_tool_retry` 需要在 `CUDA_VISIBLE_DEVICES=''` 下运行，否则会被当前机器的 CUDA 设备索引异常打断。

## Artifacts

- contract summary json: /home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/SUMMARY.json
- contract summary md: /home/lyq/xintuoyin-KLCLAB/backend/tests/api_contract_results/SUMMARY.md
- full report json: /home/lyq/xintuoyin-KLCLAB/backend/tests/artifacts/full_test_report.json
- full report md: /home/lyq/xintuoyin-KLCLAB/backend/tests/artifacts/full_test_report.md