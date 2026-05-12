import logging
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import evaluation
from app.core.resources import resource_manager
from app.schema.commit import HealthResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting evaluation service...")
    try:
        resource_path = os.getenv("RESOURCE_PATH", "resource")
        logger.info(f"Initializing evaluation resources from {resource_path}...")
        resource_manager.initialize(resource_path)
        logger.info("Evaluation service ready.")
        yield
    except Exception as error:
        logger.error(f"Evaluation startup failed: {error}")
        logger.error(traceback.format_exc())
        raise error
    finally:
        logger.info("Stopping evaluation service...")


app = FastAPI(title="Auto Gen Message Evaluation Backend", lifespan=lifespan)
app.include_router(evaluation.router, prefix="/api/evaluation")


@app.get("/api/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", version="1.0.0-python-evaluation")
