import os
import logging
import traceback
import time
from fastapi import FastAPI
from fastapi import Request
from contextlib import asynccontextmanager
from app.schema.commit import HealthResponse
from app.api import retrieval, embedding, evaluation
from app.core.resources import resource_manager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load resources once
    logger.info("Starting up application...")
    try:
        resource_path = os.getenv("RESOURCE_PATH", "resource")
        logger.info(f"Initializing resources from {resource_path}...")
        
        # 暂时注释掉资源加载，先测试服务能否启动
        resource_manager.initialize(resource_path)
        
        logger.info("Startup complete.")
        yield
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        logger.error(traceback.format_exc())
        # 可以在这里抛出异常，或者让服务继续运行（虽然功能不可用）以便查看日志
        raise e
    finally:
        logger.info("Shutting down...")
        # Shutdown
        pass

app = FastAPI(title="Auto Gen Message Backend (Basic Services)", lifespan=lifespan)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    print(
        "REQUEST_TIMING "
        f"method={request.method} "
        f"path={request.url.path} "
        f"status={response.status_code} "
        f"duration_ms={elapsed_ms:.2f}"
    )
    return response

# Include routers (Only Retrieval & Embedding)
app.include_router(retrieval.router, prefix="/api")
app.include_router(embedding.router, prefix="/api")
app.include_router(evaluation.router, prefix="/api/evaluation")

# Health
@app.get("/api/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", version="1.0.0-python-basic")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
