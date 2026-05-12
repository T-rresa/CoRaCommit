import time
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from ..schema.commit import EmbeddingRequest
from ..core.resources import resource_manager

router = APIRouter()

@router.post("/embedding/encode")
def encode_text(req: EmbeddingRequest):
    started = time.perf_counter()
    model_name = req.model if req.model else "codebert"

    get_encoder_started = time.perf_counter()
    encoder = resource_manager.get_embedding_model(model_name)
    get_encoder_elapsed = time.perf_counter() - get_encoder_started
    
    if not encoder:
        raise HTTPException(status_code=400, detail=f"Model {model_name} not supported or failed to initialize")

    encode_started = time.perf_counter()
    vector = encoder.encode(req.text)
    encode_elapsed = time.perf_counter() - encode_started

    tolist_started = time.perf_counter()
    vector_list = vector.tolist()
    tolist_elapsed = time.perf_counter() - tolist_started

    response_started = time.perf_counter()
    response = JSONResponse(content={"vector": vector_list})
    response_elapsed = time.perf_counter() - response_started
    total_elapsed = time.perf_counter() - started

    print(
        "EMBEDDING_TIMING "
        f"model={model_name} "
        f"text_length={len(req.text or '')} "
        f"get_encoder_ms={get_encoder_elapsed * 1000:.2f} "
        f"encode_ms={encode_elapsed * 1000:.2f} "
        f"tolist_ms={tolist_elapsed * 1000:.2f} "
        f"response_ms={response_elapsed * 1000:.2f} "
        f"total_ms={total_elapsed * 1000:.2f}"
    )

    return response
