# 自动生成 Commit Message 插件后端部署文档

## 1. 准备工作
- 购买云服务器 (推荐 Ubuntu 20.04/22.04, 2核8G以上; 如果使用 SQLite 优化版，2核4G即可)
- 确保服务器已安装 Docker 和 Docker Compose
- 本地项目准备就绪

## 2. 数据转换 (关键步骤)
为了大幅降低内存占用，请先在本地将 `docs.jsonl` 转换为 `docs.db` (SQLite)：

```bash
# 在项目根目录下运行
python convert_docs_to_sqlite.py resource
```
这将在 `resource/` 目录下生成 `docs.db` 文件。

## 3. 文件上传
将以下文件/目录上传到服务器的同一目录下（例如 `/opt/auto_gen_msg`）：

1. `backend/` 目录 (包含代码和 Dockerfile)
2. `node_service/` 目录
3. `resource/` 目录 (**务必包含生成的 `docs.db`**; 可排除 `docs.jsonl` 和 `bm25_diff_index.pkl` 以减小体积)
4. `docker-compose.yml` 文件

建议文件结构：
```
/opt/auto_gen_msg/
├── docker-compose.yml
├── backend/
│   ├── app/
│   ├── Dockerfile
│   └── requirements.txt
├── node_service/
│   ├── src/
│   ├── Dockerfile
│   ├── package.json
│   └── package-lock.json
└── resource/
    ├── docs.db       <-- 转换后的数据库文件
    ├── bm25/
    ├── faiss/
    └── embeddings/
```

## 4. 部署步骤

### 3.1 检查环境
```bash
docker --version
docker-compose --version
```

### 3.2 启动服务
在 `/opt/auto_gen_msg` 目录下执行：

```bash
# 构建镜像并后台启动
# 首次构建可能需要几分钟下载基础镜像和依赖
docker-compose up -d --build
```

### 3.3 架构说明
部署后会启动 6 个服务：

1. `retrieval-backend`：在线检索与向量编码服务，优先服务生成请求。
2. `evaluation-backend`：反馈评估服务，仅供后台 worker 调用。
3. `node-api`：对外提供插件访问接口。
4. `node-worker`：异步消费反馈评估队列。
5. `redis`：任务队列与“系统忙闲”状态存储。
6. `mysql`：反馈日志、模型评分和统计数据存储。

其中，在线生成链路与后台评估链路被拆分到不同 Python 服务中，避免高峰期评估任务与生成请求争抢同一计算资源。

### 3.4 验证服务
查看在线检索服务日志，确认模型加载完成：
```bash
docker logs -f auto_gen_msg_retrieval
```
当看到 `Resources loaded successfully.` 和 `Uvicorn running on ...` 字样时，表示启动成功。

测试健康检查接口：
```bash
curl http://localhost:8000/api/health
# 在线检索服务应返回 {"status":"ok", ...}

curl http://localhost:8001/api/health
# 评估服务应返回 {"status":"ok", ...}

curl http://localhost:3001/api/health
# Node API 应返回 {"status":"ok", ...}
```

## 4. 维护与配置

### 切换模型
如果需要切换到 `jina` 模型，修改 `docker-compose.yml` 中两个 Python 服务的环境变量：
```yaml
environment:
  - EMBEDDING_MODEL=jina
```
然后重启容器：
```bash
docker-compose up -d
```

### 主链路优先调度参数
以下参数可用于控制“高峰期优先响应生成请求、空闲期再执行反馈评估”的策略：

```yaml
EVAL_WORKER_CONCURRENCY=1
EVAL_JOB_DELAY_MS=300000
EVAL_BUSY_CHECK_INTERVAL_MS=15000
EVAL_CPU_THRESHOLD=0.75
ONLINE_BUSY_TTL_SECONDS=30
```

建议含义如下：

1. `EVAL_WORKER_CONCURRENCY`：评估 worker 并发数，建议保持较低。
2. `EVAL_JOB_DELAY_MS`：反馈任务默认延迟执行时间。
3. `EVAL_BUSY_CHECK_INTERVAL_MS`：worker 检查系统繁忙状态的轮询间隔。
4. `EVAL_CPU_THRESHOLD`：当服务器 CPU 负载高于该阈值时，评估任务主动等待。
5. `ONLINE_BUSY_TTL_SECONDS`：在线生成请求写入繁忙标记的过期时间。

### 更新代码
1. 上传新的代码到 `backend` 或 `node_service` 目录
2. 重新构建并重启：
```bash
docker-compose up -d --build
```
