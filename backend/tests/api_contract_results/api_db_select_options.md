# api_db_select_options

## success

- status: PASS
- method: GET
- path: /api/db/select_options
- notes: 数据库显式配置接口应返回候选表、字段说明和推荐选中结果。

### request
```json
{
  "question": "我们公司的总员工是多少"
}
```

### response
```json
{
  "code": 0,
  "msg": "获取数据库显式可选字段成功",
  "data": {
    "question": "我们公司的总员工是多少",
    "selected_tables": [
      "employee"
    ],
    "options": [
      {
        "table_name": "employee",
        "table_comment": "员工信息表",
        "column_comments": [
          "id: 主键",
          "name: 姓名",
          "department: 部门"
        ],
        "selected": true
      },
      {
        "table_name": "attendance",
        "table_comment": "考勤表",
        "column_comments": [
          "employee_id: 员工ID",
          "status: 状态"
        ],
        "selected": false
      }
    ],
    "total": 2
  }
}
```
