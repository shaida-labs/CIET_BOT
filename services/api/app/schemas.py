from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


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
    content: str = Field(min_length=1, max_length=3000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    language: Language = "en"
    channel: Channel = "website"
    conversation_id: str | None = Field(default=None, max_length=36)
    user_ref: str | None = Field(default=None, max_length=255)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=10)


class ChatMessageOut(BaseModel):
    id: str
    role: Literal["assistant"]
    content: str
    language: Language
    created_at: datetime
    confidence: Confidence
    citations: list[Citation] = Field(default_factory=list)


class ChatResponse(BaseModel):
    conversation_id: str
    message: ChatMessageOut
    route: Route


class FeedbackIn(BaseModel):
    message_id: str = Field(min_length=36, max_length=36)
    rating: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackOut(BaseModel):
    id: str
    message_id: str
    rating: Literal["up", "down"]
    comment: str | None = None
    message_content: str
    conversation_id: str
    created_at: datetime


class HandoffTicketIn(BaseModel):
    conversation_id: str = Field(min_length=36, max_length=36)
    contact: str = Field(min_length=3, max_length=255)
    contact_consent: Literal[True]


class HandoffTicketUpdateIn(BaseModel):
    status: Literal["open", "in_progress", "resolved", "closed"]
    internal_note: str | None = Field(default=None, max_length=4000)


class HandoffTicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    status: str
    contact: str | None
    contact_consent: bool
    internal_note: str | None
    resolved_by_id: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LoginIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str = Field(
        min_length=3,
        max_length=255,
        pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
        validation_alias=AliasChoices("email", "username"),
    )
    password: str = Field(min_length=8, max_length=72)


class AuthSessionOut(BaseModel):
    authenticated: Literal[True] = True
    email: str | None = None
    role: str | None = None


class GenericMessageOut(BaseModel):
    message: str


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=8, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


class ForgotPasswordIn(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    new_password: str = Field(min_length=8, max_length=72)


class AdminInvitationIn(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    role: Literal["admin", "viewer", "admissions_admin", "placement_admin", "content_admin"]


class AcceptInvitationIn(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    password: str = Field(min_length=8, max_length=72)


class FAQIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=10000)
    language: Language = "en"
    source: str = Field(default="Verified FAQ", min_length=1, max_length=255)
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
    name: str = Field(min_length=1, max_length=180)
    value: str = Field(min_length=1, max_length=10000)
    unit: str | None = Field(default=None, max_length=40)
    verified_by: str = Field(min_length=1, max_length=180)
    source: str = Field(default="Verified Metrics", min_length=1, max_length=255)
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
    domain: str = Field(
        min_length=1,
        max_length=255,
        pattern=(
            r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*"
            r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
        ),
    )
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
    citations: list[Citation] = Field(default_factory=list)
