from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


Language = Literal["en", "te", "hi"]
Channel = Literal["website", "whatsapp", "admin"]
Route = Literal["faq", "metric", "rag", "website", "fallback"]
Confidence = Literal["verified", "high", "medium", "low"]


class Citation(BaseModel):
    document_id: str | None = None
    title: str
    section: str | None = None
    url: str | None = None


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    language: Language = "en"
    channel: Channel = "website"
    conversation_id: str | None = None
    user_ref: str | None = None
    history: list[HistoryMessage] = []


class ChatMessageOut(BaseModel):
    id: str
    role: Literal["assistant"]
    content: str
    created_at: datetime
    confidence: Confidence
    citations: list[Citation] = []


class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessageOut
    route: Route


class FeedbackIn(BaseModel):
    message_id: str
    rating: Literal["up", "down"]
    comment: str | None = None


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class FAQIn(BaseModel):
    question: str
    answer: str
    language: Language = "en"
    source: str = "Verified FAQ"
    is_active: bool = True


class FAQOut(FAQIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    updated_at: datetime


class PaginatedFAQs(BaseModel):
    items: list[FAQOut]
    total: int
    page: int
    page_size: int


class MetricIn(BaseModel):
    name: str
    value: str
    unit: str | None = None
    verified_by: str
    source: str = "Verified Metrics"
    is_sensitive_stat: bool = True


class MetricOut(MetricIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    updated_at: datetime


class PaginatedMetrics(BaseModel):
    items: list[MetricOut]
    total: int
    page: int
    page_size: int


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    source: str
    file_path: str
    mime_type: str
    checksum: str | None = None
    size_bytes: int = 0
    status: str
    error_message: str | None = None
    uploaded_at: datetime


class PaginatedDocuments(BaseModel):
    items: list[DocumentOut]
    total: int
    page: int
    page_size: int


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    document_id: str
    status: str
    progress: int
    attempts: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class DomainIn(BaseModel):
    domain: str
    is_active: bool = True


class DomainOut(DomainIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime


class AuditLogOut(BaseModel):
    id: str
    actor_id: str | None
    action: str
    entity_type: str
    entity_id: str | None
    ip_address: str | None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class AnalyticsSummary(BaseModel):
    total_queries: int
    failed_queries: int
    avg_response_ms: int
    website_usage: int
    whatsapp_usage: int
    user_satisfaction: float
    popular_questions: list[dict]
    document_usage: list[dict]
    daily_usage: list[dict] = []
    monthly_usage: list[dict] = []
    failed_questions: list[dict] = []
    channel_analytics: list[dict] = []
    confidence_trends: list[dict] = []
    source_usage: list[dict] = []


class RetrievalResult(BaseModel):
    answer: str
    route: Route
    confidence: Confidence
    score: float
    citations: list[Citation] = []
