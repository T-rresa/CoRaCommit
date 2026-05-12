import time
from fastapi import APIRouter, HTTPException
from ..schema.commit import RetrievalRequest, SimilaritySearchResponse, TextRetrievalRequest
from ..retrieval.hybrid import HybridRetriever
from ..core.resources import resource_manager

router = APIRouter()
hybrid_retriever = HybridRetriever()

@router.post("/retrieval/search", response_model=SimilaritySearchResponse)
def search_index(req: RetrievalRequest):
    results = hybrid_retriever.search(
        vector=req.vector, 
        query_text=req.query_text, 
        model_name=req.model if req.model else "codebert", 
        top_k=req.top_k
    )
    return SimilaritySearchResponse(matches=results)


@router.post("/retrieval/search-by-text", response_model=SimilaritySearchResponse)
def search_index_by_text(req: TextRetrievalRequest):
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

    search_started = time.perf_counter()
    results = hybrid_retriever.search(
        vector=vector.tolist(),
        query_text=req.text,
        model_name=model_name,
        top_k=req.top_k,
    )
    search_elapsed = time.perf_counter() - search_started
    total_elapsed = time.perf_counter() - started

    print(
        "TEXT_RETRIEVAL_TIMING "
        f"model={model_name} "
        f"text_length={len(req.text or '')} "
        f"get_encoder_ms={get_encoder_elapsed * 1000:.2f} "
        f"encode_ms={encode_elapsed * 1000:.2f} "
        f"search_ms={search_elapsed * 1000:.2f} "
        f"total_ms={total_elapsed * 1000:.2f}"
    )

    return SimilaritySearchResponse(matches=results)
