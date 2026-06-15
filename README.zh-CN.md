# 🚀 CoRaCommit

[English](README.md) | 中文

CoRaCMG 是一个用于自动生成 commit message 的 VS Code 扩展。它会从提交信息语料库中检索相似示例，并结合大语言模型，根据 Git diff 生成提交信息。

本项目使用的 RAG 语料和 embedding 资源来自 ApacheCM 数据集。

## ✨ 概览

CoRaCommit 由三层运行组件组成：

- **VS Code 扩展**：收集 Git diff，并展示生成的 commit message。
- **Node API 服务**：负责编排检索、prompt 构造、LLM 调用、反馈和模型评分。
- **Python 后端**：提供 embedding、FAISS 检索、SQLite 文本查询和可选评估接口。

完整 RAG 语料来自 **ApacheCM 数据集**。仓库提交的 `resource_demo/` 是从 ApacheCM 抽取的小型示例，只用于 quickstart 和 smoke test。

## ⚡ 快速开始

### 📦 前置依赖

- Conda 或 Miniconda
- `coracommit_env` 环境中的 Python 3.10.x
- Node.js 18+ 和 npm
- VS Code 1.85+

### 1. 克隆仓库

```bash
git clone https://github.com/T-rresa/CoRaCommit.git
cd CoRaCommit
```

### 2. 创建 `coracommit_env`

```powershell
conda env create -f fusion_search/environment.yml
conda activate coracommit_env
```

### 3. 验证 demo RAG 资源

仓库内置了小型的 `resource_demo/`，它已经是后端可加载格式。先验证资源能被 backend resource manager 读取：

```powershell
conda run -n coracommit_env python fusion_search/verify_backend_resources.py --resource-dir ../resource_demo --models codebert
```

期望输出包含：

```text
[INFO] docs.db rows=32
[INFO] codebert: index_ntotal=32 doc_ids=32 top_commit_id=0
[DONE] Backend resources are loadable.
```

### 4. 启动 Python 后端（demo 资源）

PowerShell：

```powershell
cd backend
$env:RESOURCE_PATH="..\resource_demo"
$env:EMBEDDING_MODEL="codebert"
conda run -n coracommit_env python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

cmd.exe：

```bash
cd backend
set RESOURCE_PATH=..\resource_demo
set EMBEDDING_MODEL=codebert
conda run -n coracommit_env python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

检查服务：

```powershell
curl http://127.0.0.1:8000/api/health
```

### 5. 启动 Node API

打开第二个终端：

```powershell
cd node_service
npm ci
$env:PORT="3001"
$env:RETRIEVAL_BACKEND_URL="http://127.0.0.1:8000"
$env:EVALUATION_BACKEND_URL="http://127.0.0.1:8000"
npm run start
```

检查服务：

```powershell
curl http://127.0.0.1:3001/api/health
```

再验证 Node 能调用 Python 检索后端：

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:3001/api/similarity-search" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"diff":"diff --git a/a.txt b/a.txt\n+hello"}'
```

响应中应包含 `matches` 数组。

### 6. 运行 VS Code 扩展

打开第三个终端：

```powershell
cd vscode_extension
npm ci
npm run compile
```

在 VS Code 中打开 `vscode_extension/`，按 `F5` 启动扩展宿主。扩展默认连接本地 Node API：`http://localhost:3001/api`。

## 🧩 后端运行模式

### 单 Python 后端

推荐用于本地开发。`app.main` 在一个进程中提供检索、embedding 和评估接口：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Node 侧两个后端 URL 都指向同一个服务：

```bash
set RETRIEVAL_BACKEND_URL=http://127.0.0.1:8000
set EVALUATION_BACKEND_URL=http://127.0.0.1:8000
```

### 拆分检索和评估后端

推荐用于接近生产部署的场景。在线检索和后台评估分开运行：

```bash
uvicorn app.main_retrieval:app --host 127.0.0.1 --port 8000
uvicorn app.main_evaluation:app --host 127.0.0.1 --port 8001
```

Node 侧配置为：

```bash
set RETRIEVAL_BACKEND_URL=http://127.0.0.1:8000
set EVALUATION_BACKEND_URL=http://127.0.0.1:8001
```

## 🗂️ 数据和 RAG 资源

生产检索语料来自 ApacheCM 数据集。原始输入是 JSONL 文件，每条记录至少包含：

- `diff`
- `message`
- `repo`
- `commit_sha`

将 ApacheCM 全量文件放到：

```text
fusion_search/data/raw/apachecm/full.jsonl
```

构建完整 RAG 资源：

```bash
cd fusion_search
conda activate coracommit_env
python main.py build-index codebert
python main.py build-index jina
python main.py export-backend --output-dir ../resource
python verify_backend_resources.py --resource-dir ../resource --models codebert jina
```

如果只想快速验证仓库内置 demo 资源，可在仓库根目录运行：

```powershell
conda run -n coracommit_env python fusion_search/verify_backend_resources.py --resource-dir ../resource_demo --models codebert
```

资源目录结构：

```text
resource/
  docs.db
  docs.jsonl
  embeddings/
    codebert.doc_ids.npy
    codebert.vecs.npy
    jina.doc_ids.npy
    jina.vecs.npy
  faiss/
    codebert.index
    jina.index
```

后端返回的 `commit_id` 是源数据顺序 id（`0`、`1`、`2`、...）。`docs.db` 和 `embeddings/*.doc_ids.npy` 必须使用同一套 id。

## 🧱 仓库结构

```text
backend/          FastAPI 检索、embedding 和评估服务
node_service/     Node API、LLM 编排、反馈队列、评分逻辑
vscode_extension/ VS Code 扩展
fusion_search/    ApacheCM embedding 和资源导出脚本
experiment/       实验脚本和配置
resource_demo/    已提交的小型 quickstart 资源
```

## 🐳 Docker 部署

先生成或准备好 `resource/`，然后运行：

```bash
docker compose -f docker-compose.deploy.yml up -d --build
```

Compose 会启动检索后端、评估后端、Node API、Node worker、Redis 和 MySQL。完整部署说明见 `DEPLOY.md`。
