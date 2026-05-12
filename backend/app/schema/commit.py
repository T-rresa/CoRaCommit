from pydantic import BaseModel, Field
from typing import List, Optional

# --- 1. Commit Suggestion ---
class CommitSuggestionRequest(BaseModel):
    diff: str = Field(..., description="The git diff content")
    model: Optional[str] = Field(None, description="Model name to use (e.g., gpt-4)")
    template: Optional[str] = Field(None, description="Commit message template style")
    language: Optional[str] = Field("en", description="Output language (e.g., en, zh)")
    format: Optional[str] = Field("conventional", description="Commit message format (e.g., conventional, karma)")
    apiKey: Optional[str] = Field(None, description="API Key for the model provider")
    templateText: Optional[str] = Field(None, description="Custom template content provided by user")

class CommitSuggestionResponse(BaseModel):
    suggestion: str = Field(..., description="Generated commit message")
    confidence: float = Field(..., description="Confidence score between 0 and 1")

# --- 2. Embedding & Retrieval ---
class EmbeddingRequest(BaseModel):
    text: str = Field(..., description="Text to encode")
    model: Optional[str] = Field("codebert", description="Embedding model to use (codebert, jina)")

class EmbeddingResponse(BaseModel):
    vector: List[float] = Field(..., description="Dense vector embedding")

class RetrievalRequest(BaseModel):
    vector: List[float] = Field(..., description="Query vector")
    query_text: Optional[str] = Field(None, description="Original query text for lexical search")
    model: Optional[str] = Field("codebert", description="Target index model (codebert, jina)")
    top_k: Optional[int] = Field(1, description="Number of results to return")

class TextRetrievalRequest(BaseModel):
    text: str = Field(..., description="Original query text to encode and retrieve")
    model: Optional[str] = Field("codebert", description="Target index model (codebert, jina)")
    top_k: Optional[int] = Field(1, description="Number of results to return")

class SimilarityMatch(BaseModel):
    commit_id: str
    message: str
    diff: str
    similarity_score: float

class SimilaritySearchResponse(BaseModel):
    matches: List[SimilarityMatch]

# --- 3. Model Config ---
class ModelInfo(BaseModel):
    name: str
    description: str
    available: bool

class ModelConfigResponse(BaseModel):
    models: List[ModelInfo]

# --- 4. Template Config ---
class TemplateInfo(BaseModel):
    name: str
    description: str

class TemplateConfigResponse(BaseModel):
    templates: List[TemplateInfo]

# --- 5. Health ---
class HealthResponse(BaseModel):
    status: str
    version: str
