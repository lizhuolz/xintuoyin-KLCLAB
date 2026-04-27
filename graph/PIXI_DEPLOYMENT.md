# Pixi migration deployment

本项目是一个 Flask 壳层应用，融合了 `modules/Graph` 的数据库图谱和 `modules/xintuoyin` 的文件抽取图谱。迁移时建议使用根目录的 `pixi.toml` 统一创建运行环境。

## 1. 安装环境

```bash
pixi install
```

当前机器未安装 `pixi`，因此本仓库暂未生成 `pixi.lock`。在目标机器执行 `pixi install` 后，建议提交生成的 `pixi.lock`，后续部署可复用完全一致的解析结果。

## 2. 必要环境变量

数据库配置建议在部署机通过环境变量注入：

```bash
export DB_HOST="your-mysql-host"
export DB_PORT="3306"
export DB_USER="your-user"
export DB_PASSWORD="your-password"
export DB_NAME="your-db"
export DB_CHARSET="utf8mb4"
```

系统外图谱抽取需要可访问的 OpenAI 兼容接口：

```bash
export EXTERNAL_GRAPH_API_BASE="http://your-model-server/v1"
export EXTERNAL_GRAPH_MODEL_PATH="your-model-name-or-path"
export EXTERNAL_GRAPH_EXTRACT_TIMEOUT_SECONDS="180"
```

`pixi.toml` 已设置部署默认值：

- `APP_HOST=0.0.0.0`
- `APP_PORT=5002`
- `FLASK_DEBUG=false`

如需固定修改监听地址或端口，建议直接调整 `pixi.toml` 中的 `[activation.env]` 或 `serve` 任务。

## 3. 启动

开发/普通部署启动：

```bash
pixi run start
```

使用 Gunicorn 启动：

```bash
pixi run serve
```

单独启动 Graph 后端：

```bash
pixi run graph-backend
```

单独启动原 xintuoyin 服务：

```bash
pixi run xintuoyin-standalone
```

## 4. 迁移检查

确认 Python 依赖可导入：

```bash
pixi run check-imports
```

确认 `.xls` 转换依赖可用：

```bash
pixi run check-soffice
```

`modules/xintuoyin/getgraph/main.py` 会通过 `soffice` 将旧版 `.xls` 转为 `.xlsx`，所以 `pixi.toml` 中包含了 `libreoffice`。文档、图片和 PDF 抽取还依赖 `docling`、`rapidocr-onnxruntime`、`pypdfium2`、`pillow`，这些依赖已补齐到 Pixi 配置中。

## 5. 注意事项

- 不建议把数据库账号密码写入 `pixi.toml`。
- 目标机器需要能访问 MySQL 和 `EXTERNAL_GRAPH_API_BASE`。
- 如果目标机器无法联网，先在可联网环境执行 `pixi install` 生成 `pixi.lock`，再结合内网包缓存或镜像源部署。
- GPU OCR 不是必需项；代码在 `torch` 不可用或 CUDA 不可用时会回退到 CPU。
