# R&D Cat API View

基于 **Vue 3 + FastAPI + LangGraph** 的智能化 AI Agent 交互平台，支持 RAG、SQL 自动查询及多 Agent 协作。

## 🚀 快速启动

项目已集成一键部署脚本，支持后端、前端及内网穿透同步启动。

### 1. 启动服务
```bash
# 自动启动 Backend, Frontend 和 Cloudflare Tunnel
./start_server.sh
```
*启动后脚本会自动输出 Cloudflare 公网演示链接。*

### 2. 停止服务
```bash
# 安全停止所有相关进程
./stop_server.sh
```

### 3. 查看日志
- 后端日志：`tail -f logs/backend.log`
- 前端日志：`tail -f logs/frontend.log`
- 隧道日志：`tail -f logs/tunnel.log`

## 🛠️ 技术要点
- **Agent 编排**: 使用 LangGraph 构建复杂的工具调用流（Local/Web/SQL）。
- **智能 SQL**: 支持数据库选表、SQL 生成及自动纠错（Self-Correction）。
- **全栈架构**: 
  - 前端: Vue 3, Vite, Element Plus, Pinia.
  - 后端: FastAPI, Gunicorn, LangChain, LlamaIndex.
- **环境要求**: Python 3.11+, Node.js 18+。

## 📂 核心目录
- `backend/`: FastAPI 业务逻辑与 Agent 实现。
- `frontend/`: Vue 3 交互界面。
- `documents/`: RAG 知识库原始文档。
- `start_server.sh`: 全栈一键启动脚本。
