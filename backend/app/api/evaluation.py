from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from ..evaluation.service import EvaluationService

router = APIRouter()
eval_service = EvaluationService()

class EvaluationRequest(BaseModel):
    generated_message: str
    ground_truth: str
    model_name: Optional[str] = "codebert"
    alpha: Optional[float] = 0.7
    beta: Optional[float] = 0.3

class EvaluationResponse(BaseModel):
    similarity_score: float
    semantic_score: float
    lexical_score: float
    alpha: float
    beta: float

class CandidateModel(BaseModel):
    model: str
    generated_message: str

class MultiModelEvaluationRequest(BaseModel):
    candidates: List[CandidateModel]
    ground_truth: str
    selected_model: str
    is_edited: bool
    alpha: Optional[float] = 0.7
    beta: Optional[float] = 0.3
    lambda_val: Optional[float] = 0.7
    w1: Optional[float] = 0.6
    w2: Optional[float] = 0.4
    s1: Optional[float] = 0.9
    s2: Optional[float] = 0.6

class ModelMetrics(BaseModel):
    semantic_score: float
    lexical_score: float
    sim_score: float
    user_preference: float
    single_score: float
    compare_score: float
    final_score: float

class EvaluatedCandidate(BaseModel):
    model: str
    generated_message: str
    metrics: ModelMetrics

@router.post("/evaluate", response_model=EvaluationResponse)
def evaluate_similarity(req: EvaluationRequest):
    try:
        result = eval_service.evaluate(
            generated_message=req.generated_message,
            ground_truth=req.ground_truth,
            model_name=req.model_name,
            alpha=req.alpha,
            beta=req.beta
        )
        return EvaluationResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/evaluate-multi", response_model=List[EvaluatedCandidate])
def evaluate_multi_model(req: MultiModelEvaluationRequest):
    try:
        # Convert Pydantic models to dicts for the service
        candidates_dict = [c.dict() for c in req.candidates]
        
        results = eval_service.evaluate_multi_model(
            candidates=candidates_dict,
            ground_truth=req.ground_truth,
            selected_model=req.selected_model,
            is_edited=req.is_edited,
            alpha=req.alpha,
            beta=req.beta,
            lambda_val=req.lambda_val,
            w1=req.w1,
            w2=req.w2,
            s1=req.s1,
            s2=req.s2
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
