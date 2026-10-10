"""Oracle AI schemas"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class Source(BaseModel):
    """Schema for a RAG source referenced in an Oracle response"""
    title: str
    file_path: str
    similarity: float


class OracleQuery(BaseModel):
    """Schema for Oracle AI query"""
    question: str = Field(..., min_length=1, max_length=5000, description="Question à poser à l'Oracle")
    context: Optional[str] = Field(None, max_length=10000, description="Contexte additionnel pour la question")
    ai_provider: Literal["kiro", "shai", "openai", "opcp_companion"] = Field(default="shai", description="Fournisseur d'IA à utiliser")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0, description="Température pour la génération")
    max_tokens: Optional[int] = Field(default=2000, ge=100, le=8000, description="Nombre maximum de tokens")


class OracleResponse(BaseModel):
    """Schema for Oracle AI response"""
    id: int
    question: str
    answer: str
    ai_provider: str
    context: Optional[str]
    created_at: datetime
    user_id: Optional[int]
    processing_time: float
    tokens_used: Optional[int]
    sources: Optional[List[Source]] = None


class OracleHistoryItem(BaseModel):
    """Schema for Oracle history item"""
    id: int
    question: str
    answer: str
    ai_provider: str
    created_at: datetime
    processing_time: float


class OracleAnalysisRequest(BaseModel):
    """Schema for internal Oracle analysis request"""
    analysis_type: Literal["forum_summary", "event_prediction", "user_sentiment", "custom"]
    parameters: Optional[dict] = Field(default_factory=dict)
    ai_provider: Literal["kiro", "shai", "openai", "opcp_companion"] = Field(default="kiro")


class ForumAnalysisResponse(BaseModel):
    """Schema for forum analysis response"""
    summary: str
    job_loss_prediction_5y: float = Field(..., description="Pourcentage estimé de perte d'emploi à 5 ans")
    job_loss_prediction_10y: float = Field(..., description="Pourcentage estimé de perte d'emploi à 10 ans")
    job_loss_prediction_20y: float = Field(..., description="Pourcentage estimé de perte d'emploi à 20 ans")
    key_topics: List[str]
    sentiment: str
    confidence: float
