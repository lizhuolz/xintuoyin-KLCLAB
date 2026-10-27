# SQL 日期函数校验兼容性修复

## 问题与范围

用户已授权修复后端日期函数兼容性校验。sqlglot 27.29.0 将 MySQL `YEAR(START_DATE)`、`DATE(START_DATE)` 等解析为包含 `TsOrDsToDate` 的表达式；现有按函数名检查的白名单不认识其内部名称 `TS_OR_DS_TO_DATE`。因此有数据访问权限的用户也会在实际执行 SQL 前被拒绝。

同类问题涉及 `DAYOFMONTH`、`DAYOFWEEK`、`DAYOFYEAR`、`WEEKOFYEAR`、`DATE_FORMAT`、`MONTHNAME` 以及带时分秒格式的 `STR_TO_DATE`。

本次仅修改 `backend/utils/sql_permissions.py` 的日期表达式兼容性判断，另加测试和本说明。不变更接口、登录、依赖、租户/项目权限、SQL 业务筛选和数据库连接配置。截图中模型生成 `PROJECT_STATUS != 3` 的状态码语义错误与本问题独立，本次不处理。

## 实现设计

保留原 `READ_FUNCTIONS` 白名单，额外允许七个经过核对的 sqlglot 日期表达式的精确类型：`TsOrDsToDate`、`DayOfMonth`、`DayOfWeek`、`DayOfYear`、`WeekOfYear`、`TimeToStr`、`StrToTime`。

按精确类型匹配，避免泛化允许所有日期或所有函数节点。继续遍历全部子节点：日期函数包裹 `SLEEP`、`LOAD_FILE`、自定义函数等仍然拒绝。内部规范函数名直接出现在输入中时，sqlglot 可能将其解析成同一已知类型；输出必须仍为已核对的 MySQL 日期运算。

所有查询继续执行现有单条只读检查、表白名单、租户过滤、有效记录过滤和普通用户项目授权过滤。管理员只放开项目成员关系限制，不跳过 SQL 函数检查。

## 实施与验证

1. 独立 Git 分支 `fix/sql-date-function-compatibility-20261027`，基于此前历史留存修复提交 `75ad9ad`。源文件修改前核对 SHA-256 与运行目录一致。
2. 先在旧实现运行新日期回归，确认正常日期表达式被错误拒绝，再实现最小兼容逻辑。
3. 测试年份/月/日/周/格式化/日期解析等表达式；执行 SQLite 合成数据查询，核对年份结果和租户、项目、有效状态隔离；验证嵌套危险函数、未知函数、跨库、多语句仍被拒绝。
4. 运行既有 SQL 权限和相关后端回归；独立代码审查。
5. Git 提交后备份原文件和回滚脚本，SHA 检查通过再应用。只用 dlx 普通账号重启后端，保留 vLLM 运行。
6. 用只读查询验证真实 MySQL 日期表达式，使用合成提问验证后端 SSE 能正常完成；不删除或更改用户现有记录。

回滚以部署时生成的备份和校验脚本为准。旧版本恢复后会再次拒绝这些日期表达式；业务数据不需要迁移。
