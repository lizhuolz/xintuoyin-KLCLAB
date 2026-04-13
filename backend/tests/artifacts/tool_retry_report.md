# Tool Retry Report

- generated_at: 2026-04-09 13:33:04
- command: `CUDA_VISIBLE_DEVICES='' python -m unittest tests.test_tool_retry -v`
- result: 4/4 passed

## Covered Cases

- meta tool reasoning fallback retry
- duplicate tool call dedupe
- current user question extraction
- route_after_chatbot_local SQL misclassification guard

## Notes

- 该组测试覆盖 calculator / 工具重试相关回归。
- 运行时需显式设置 `CUDA_VISIBLE_DEVICES=''`。