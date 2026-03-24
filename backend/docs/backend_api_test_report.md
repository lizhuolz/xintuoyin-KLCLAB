# 后端 API 边界与压力测试报告

- 基于报告：`/home/lyq/xintuoyin-KLCLAB/backend/tests/artifacts/api_stress_report.json`
- 测试时间：`2026-03-25T00:23:38.475738`
- 测试基址：`http://127.0.0.1:8000`
- 说明：本轮为真实接口的轻量压力测试，不是满负载压测；其中 `/api/chat` 因依赖模型服务，仅做低并发验证。

## 1. 汇总表

| 接口 | 成功状态 | 边界状态 | 压力结果 | 备注 |
| --- | --- | --- | --- | --- |
| `/api/chat/new_session` | `200` | `-` | `20/20 ok, p50=9.73ms, max=11.74ms` |  |
| `/api/chat` | `200` | `missing_message:422; unsafe_message:400` | `2/2 ok, p50=7748.6ms, max=7748.6ms` | stream_done=True |
| `/api/chat/{conversation_id}/title` | `200` | `not_found:404` | `15/15 ok, p50=9.36ms, max=17.25ms` |  |
| `/api/upload` | `200` | `negative_message_index:400` | `5/5 ok, p50=12.02ms, max=15.21ms` |  |
| `/api/history/list` | `200` | `invalid_start_time:400; search_hit:200; search_miss:200` | `20/20 ok, p50=32.76ms, max=54.37ms` |  |
| `/api/history/{conversation_id}` | `200` | `not_found:404` | `15/15 ok, p50=9.45ms, max=16.02ms` |  |
| `/api/chat/{conversation_id}/thinking` | `200` | `not_found_message:404; not_found_conversation:404` | `10/10 ok, p50=10.13ms, max=13.78ms` |  |
| `/api/chat/{conversation_id} [DELETE]` | `404` | `not_found:404` | `0/5 ok, p50=10.39ms, max=11.89ms` | 含失败样本 |
| `/api/history/batch_delete` | `200` | `ids_not_list:400` | `5/5 ok, p50=10.81ms, max=11.64ms` |  |
| `/api/chat/feedback` | `200` | `invalid_type:400; negative_message_index:400; dislike_without_detail:400; toggle_like_off:200` | `4/4 ok, p50=15.52ms, max=16.81ms` |  |
| `/api/feedback/upload_pictures` | `200` | `negative_message_index:400` | `3/3 ok, p50=15.54ms, max=17.41ms` |  |
| `/api/feedback/list` | `200` | `type_filter:200; invalid_start_time:400` | `10/10 ok, p50=16.37ms, max=22.62ms` |  |
| `/api/feedback/{feedback_id}` | `200` | `not_found:404` | `10/10 ok, p50=9.04ms, max=11.06ms` |  |
| `/api/feedback/detail/{date}/{id}` | `200` | `not_found:404` | `10/10 ok, p50=10.23ms, max=14.55ms` |  |
| `/api/feedback/process` | `200` | `missing_id:400; collect_true:200` | `3/3 ok, p50=10.69ms, max=13.69ms` |  |
| `/api/feedback/batch_delete` | `200` | `ids_not_list:400` | `5/5 ok, p50=11.05ms, max=12.85ms` |  |
| `/api/feedback/{date}/{id} [DELETE]` | `200` | `not_found:404` | `0/5 ok, p50=10.12ms, max=11.56ms` | 含失败样本 |
| `/api/kb/list` | `200` | `-` | `15/15 ok, p50=14.07ms, max=23.31ms` |  |
| `/api/kb/create` | `200` | `missing_name:422` | `3/3 ok, p50=11.63ms, max=11.96ms` |  |
| `/api/kb/{id}` | `200` | `not_found:404` | `10/10 ok, p50=10.38ms, max=17.47ms` |  |
| `/api/kb/update` | `200` | `invalid_users_json:400; not_found:404` | `5/5 ok, p50=12.03ms, max=16.33ms` |  |
| `/api/kb/{id}/upload` | `200` | `not_found:404` | `3/3 ok, p50=15.38ms, max=17.93ms` |  |
| `/api/kb/{id}/files` | `200` | `not_found:404` | `10/10 ok, p50=13.0ms, max=17.03ms` |  |
| `/api/kb/{id}/delete_files` | `200` | `filenames_not_list:400; not_found:404` | `5/5 ok, p50=10.13ms, max=12.27ms` |  |
| `/api/kb/{id}/delete_file` | `200` | `not_found_kb:404` | `5/5 ok, p50=11.24ms, max=13.94ms` |  |
| `/api/kb/{id} [DELETE]` | `200` | `not_found:404` | `0/5 ok, p50=9.81ms, max=12.95ms` | 含失败样本 |

## 2. 关键结论

- 所有读接口在本地环境下响应稳定，绝大多数 `p50` 在 `9ms` 到 `33ms` 之间。
- `/api/chat` 明显慢于其他接口，非流式轻压测两次均成功，单次约 `6s-11s`。
- 所有参数边界测试均符合实现预期，`400/404/422` 分层清晰。
- 删除类接口对“不存在资源”路径是稳定的，但新会话未持久化即删除会返回 `404`。
- 反馈和知识库接口具有落盘副作用，压力测试已使用隔离数据，并在测试后做了清理。

## 3. 复杂接口样例

### `/api/chat`

成功样例摘要：

```json
{
  "code": 0,
  "msg": "发送对话成功",
  "data": {
    "message_index": 0,
    "question": "请根据附件告诉我项目代号和交付日期",
    "files": [
      "probe.txt"
    ],
    "uploaded_files": [
      {
        "file_id": "file_1774369418587_0",
        "filename": "probe.txt",
        "url": "/api/static/chat_uploads/2026-03-25/1774369418483/0/probe.txt",
        "relative_path": "2026-03-25/1774369418483/0/probe.txt"
      }
    ],
    "file_contexts": [
      {
        "filename": "probe.txt",
        "text": "项目代号：北极星 交付日期：2026-04-15 负责人：测试机器人"
      }
    ],
    "web_search": false,
    "db_version": null,
    "answer": "根据文件`probe.txt`的内容，项目代号是“北极星”，交付日期是“2026-04-15”。",
    "resource": [],
    "recommend_answer": [
      "项目的具体内容是什么？",
      "项目的负责人是谁？",
      "项目的预算是多少？"
    ],
    "feedback": null,
    "thinking_text": "这次回答没有额外调用工具，我直接根据已有上下文完成了回复。",
    "thinking_steps": [],
    "created_at": "1774369429718",
    "updated_at": "1774369429718",
    "createdAt": "2026/03/25 00:23:49",
    "updatedAt": "2026/03/25 00:23:49"
  }
}
```
边界样例摘要：

```json
{
  "missing_message": {
    "status": 422,
    "body": {
      "detail": [
        {
          "type": "missing",
          "loc": [
            "body",
            "message"
          ],
          "msg": "Field required",
          "input": null
        }
      ]
    }
  },
  "unsafe_message": {
    "status": 400,
    "body": {
      "code": 1,
      "msg": "发送对话失败",
      "data": {
        "reason": "输入包含违规内容，已被防火墙拦截: BanSubstrings (score: 1.0)"
      }
    }
  }
}
```

### `/api/chat/feedback`

成功样例摘要：

```json
{
  "code": 0,
  "msg": "提交反馈成功",
  "data": {
    "id": "fb_1774369418483_0",
    "conversation_id": "1774369418483",
    "message_index": 0,
    "type": "like",
    "state": "like",
    "reasons": [],
    "comment": "",
    "pictures": [],
    "name": "王颖奇",
    "enterprise": "图湃（北京）医疗科技",
    "phone": "15323720032",
    "time": "1774369453285",
    "update_time": "1774369453285",
    "createdAt": "2026/03/25 00:24:13",
    "updatedAt": "2026/03/25 00:24:13",
    "process_status": "未处理"
  }
}
```
边界样例摘要：

```json
{
  "invalid_type": {
    "status": 400,
    "body": {
      "code": 1,
      "msg": "提交反馈失败",
      "data": {
        "reason": "type 仅支持 like 或 dislike"
      }
    }
  },
  "negative_message_index": {
    "status": 400,
    "body": {
      "code": 1,
      "msg": "提交反馈失败",
      "data": {
        "reason": "message_index 不能为负数"
      }
    }
  },
  "dislike_without_detail": {
    "status": 400,
    "body": {
      "code": 1,
      "msg": "提交反馈失败",
      "data": {
        "reason": "点踩反馈必须填写原因、描述或上传截图"
      }
    }
  },
  "toggle_like_off": {
    "status": 200,
    "body": {
      "code": 0,
      "msg": "提交反馈成功",
      "data": {
        "id": "fb_1774369418483_0",
        "conversation_id": "1774369418483",
        "message_index": 0,
        "type": "like",
        "state": null,
        "reasons": [],
        "comment": "",
        "pictures": [],
        "name": "王颖奇",
        "enterprise": "图湃（北京）医疗科技",
        "phone": "15323720032",
        "time": "1774369453285",
        "update_time": "1774369453339",
        "createdAt": "2026/03/25 00:24:13",
        "updatedAt": "2026/03/25 00:24:13",
        "process_status": "未处理"
      }
    }
  }
}
```

### `/api/feedback/process`

成功样例摘要：

```json
{
  "code": 0,
  "msg": "处理反馈成功",
  "data": {
    "id": "fb_1774369418483_0",
    "conversation_id": "1774369418483",
    "message_index": 0,
    "type": "dislike",
    "state": "dislike",
    "time": "1774369453285",
    "update_time": "1774369453501",
    "createdAt": "2026/03/25 00:24:13",
    "updatedAt": "2026/03/25 00:24:13",
    "reasons": [],
    "comment": "答案不够完整",
    "pictures": [
      "probe.png",
      "probe_1.png",
      "probe_2.png",
      "probe_3.png",
      "probe_4.png"
    ],
    "name": "王颖奇",
    "enterprise": "图湃（北京）医疗科技",
    "phone": "15323720032",
    "question": "请根据附件告诉我项目代号和交付日期",
    "answer": "根据文件`probe.txt`的内容，项目代号是“北极星”，交付日期是“2026-04-15”。",
    "process_status": "已处理",
    "processor": "api_probe",
    "processed_at": "1774369453737",
    "processedAt": "2026/03/25 00:24:13",
    "process_result": "已处理(未收录)"
  }
}
```
边界样例摘要：

```json
{
  "missing_id": {
    "status": 400,
    "body": {
      "code": 1,
      "msg": "处理反馈失败",
      "data": {
        "reason": "id 不能为空"
      }
    }
  },
  "collect_true": {
    "status": 200,
    "body": {
      "code": 0,
      "msg": "处理反馈成功",
      "data": {
        "id": "fb_1774369418483_0",
        "conversation_id": "1774369418483",
        "message_index": 0,
        "type": "dislike",
        "state": "dislike",
        "time": "1774369453285",
        "update_time": "1774369453501",
        "createdAt": "2026/03/25 00:24:13",
        "updatedAt": "2026/03/25 00:24:13",
        "reasons": [],
        "comment": "答案不够完整",
        "pictures": [
          "probe.png",
          "probe_1.png",
          "probe_2.png",
          "probe_3.png",
          "probe_4.png"
        ],
        "name": "王颖奇",
        "enterprise": "图湃（北京）医疗科技",
        "phone": "15323720032",
        "question": "请根据附件告诉我项目代号和交付日期",
        "answer": "根据文件`probe.txt`的内容，项目代号是“北极星”，交付日期是“2026-04-15”。",
        "process_status": "已处理",
        "processor": "api_probe",
        "processed_at": "1774369453755",
        "processedAt": "2026/03/25 00:24:13",
        "process_result": "已收录"
      }
    }
  }
}
```

### `/api/kb/update`

成功样例摘要：

```json
{
  "code": 0,
  "msg": "更新知识库成功",
  "data": {
    "id": "kb_1774369484814",
    "name": "API探针知识库",
    "category": "个人知识库",
    "model": "openai",
    "remark": "API探针更新",
    "enabled": true,
    "users": [
      {
        "name": "tester",
        "phone": "123",
        "categoryName": "demo"
      }
    ],
    "fileCount": 0,
    "url": "个人知识库/王颖奇/API探针知识库",
    "physical_path": "个人知识库/王颖奇/API探针知识库",
    "owner_info": "图湃（北京）医疗科技/技术部",
    "created_at": "1774369484815",
    "updated_at": "1774369485008",
    "createdAt": "2026/03/25 00:24:44",
    "updatedAt": "2026/03/25 00:24:45"
  }
}
```
边界样例摘要：

```json
{
  "invalid_users_json": {
    "status": 400,
    "body": {
      "code": 1,
      "msg": "更新知识库失败",
      "data": {
        "reason": "users 字段不是合法 JSON"
      }
    }
  },
  "not_found": {
    "status": 404,
    "body": {
      "code": 1,
      "msg": "更新知识库失败",
      "data": {
        "id": "not_exists_for_probe"
      }
    }
  }
}
```
