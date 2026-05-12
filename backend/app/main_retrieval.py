import logging
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import embedding, retrieval
from app.core.resources import resource_manager
from app.schema.commit import HealthResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting retrieval service...")
    try:
        resource_path = os.getenv("RESOURCE_PATH", "resource")
        logger.info(f"Initializing retrieval resources from {resource_path}...")
        resource_manager.initialize(resource_path)
        logger.info("Retrieval service ready.")
        yield
    except Exception as error:
        logger.error(f"Retrieval startup failed: {error}")
        logger.error(traceback.format_exc())
        raise error
    finally:
        logger.info("Stopping retrieval service...")


app = FastAPI(title="Auto Gen Message Retrieval Backend", lifespan=lifespan)
app.include_router(retrieval.router, prefix="/api")
app.include_router(embedding.router, prefix="/api")


@app.get("/api/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", version="1.0.0-python-retrieval")
