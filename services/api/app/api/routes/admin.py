import uuid
import asyncio
from collections import Counter

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import Role, current_user, require_roles
from app.db.session import get_session
from app.models import (
    AdminUser,
    AllowedDomain,
    AnalyticsEvent,
    AuditLog,
    Channel,
    ConversationMessage,
    Document,
    DocumentChunk,
    FAQ,
    Feedback,
    HandoffTicket,
    IngestionJob,
    Metric,
    now,
)
from app.schemas import (
    AnalyticsSummary,
    AuditLogOut,
    DocumentOut,
    DomainIn,
    DomainOut,
    FAQIn,
    FAQOut,
    FeedbackOut,
    HandoffTicketOut,
    HandoffTicketUpdateIn,
    JobOut,
    MetricIn,
    MetricOut,
    PaginatedDocuments,
    PaginatedFAQs,
    PaginatedMetrics,
)
from app.services.audit import write_audit
from app.services.cache import invalidate_knowledge_cache
from app.services.pinecone_service import PineconeService, PineconeUnavailableError
from app.services.storage import StorageService
from app.services.upload_security import read_upload_limited, validate_filename, validate_upload
from app.workers.tasks import process_document

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(current_user)])

# CIET has intentionally small, function-specific administrative roles. Super admins
# are implicitly accepted by require_roles. Keep these dependencies explicit so a
# general content editor cannot change verified placement metrics or operational
# security settings.
faq_admin = require_roles(Role.content_admin, Role.admissions_admin)
metric_admin = require_roles(Role.placement_admin)
document_admin = require_roles(Role.content_admin)
super_admin = require_roles(Role.super_admin)


@router.get("/faqs", response_model=list[FAQOut], dependencies=[Depends(faq_admin)])
async def list_faqs(
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[FAQ]:
    return list((await session.scalars(select(FAQ).order_by(FAQ.updated_at.desc()).limit(limit))).all())


@router.get("/faqs/page", response_model=PaginatedFAQs, dependencies=[Depends(faq_admin)])
async def page_faqs(
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedFAQs:
    statement = select(FAQ)
    count_statement = select(func.count(FAQ.id))
    if q:
        condition = or_(FAQ.question.ilike(f"%{q}%"), FAQ.answer.ilike(f"%{q}%"), FAQ.source.ilike(f"%{q}%"))
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    total = await session.scalar(count_statement) or 0
    items = (
        await session.scalars(statement.order_by(FAQ.updated_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).all()
    return PaginatedFAQs(items=list(items), total=total, page=page, page_size=page_size)


@router.post("/faqs", response_model=FAQOut)
async def create_faq(
    payload: FAQIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(faq_admin),
) -> FAQ:
    faq = FAQ(**payload.model_dump())
    session.add(faq)
    await session.flush()
    await write_audit(session, action="create", entity_type="faq", entity_id=faq.id, user=user, request=request)
    await session.commit()
    await invalidate_knowledge_cache(get_settings())
    await session.refresh(faq)
    return faq


@router.put("/faqs/{faq_id}", response_model=FAQOut)
async def update_faq(
    faq_id: str,
    payload: FAQIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(faq_admin),
) -> FAQ:
    faq = await session.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    for key, value in payload.model_dump().items():
        setattr(faq, key, value)
    await write_audit(session, action="update", entity_type="faq", entity_id=faq.id, user=user, request=request)
    await session.commit()
    await invalidate_knowledge_cache(get_settings())
    await session.refresh(faq)
    return faq


@router.delete("/faqs/{faq_id}", status_code=204)
async def delete_faq(
    faq_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(faq_admin),
) -> None:
    faq = await session.get(FAQ, faq_id)
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    await session.delete(faq)
    await write_audit(session, action="delete", entity_type="faq", entity_id=faq_id, user=user, request=request)
    await session.commit()
    await invalidate_knowledge_cache(get_settings())


@router.get("/metrics", response_model=list[MetricOut], dependencies=[Depends(metric_admin)])
async def list_metrics(
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[Metric]:
    return list((await session.scalars(select(Metric).order_by(Metric.updated_at.desc()).limit(limit))).all())


@router.get("/metrics/page", response_model=PaginatedMetrics, dependencies=[Depends(metric_admin)])
async def page_metrics(
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedMetrics:
    statement = select(Metric)
    count_statement = select(func.count(Metric.id))
    if q:
        condition = or_(Metric.name.ilike(f"%{q}%"), Metric.value.ilike(f"%{q}%"), Metric.source.ilike(f"%{q}%"))
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    total = await session.scalar(count_statement) or 0
    items = (
        await session.scalars(statement.order_by(Metric.updated_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).all()
    return PaginatedMetrics(items=list(items), total=total, page=page, page_size=page_size)


@router.post("/metrics", response_model=MetricOut)
async def create_metric(
    payload: MetricIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(metric_admin),
) -> Metric:
    metric = Metric(**payload.model_dump())
    session.add(metric)
    await session.flush()
    await write_audit(session, action="create", entity_type="metric", entity_id=metric.id, user=user, request=request)
    await session.commit()
    await invalidate_knowledge_cache(get_settings())
    await session.refresh(metric)
    return metric


@router.put("/metrics/{metric_id}", response_model=MetricOut)
async def update_metric(
    metric_id: str,
    payload: MetricIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(metric_admin),
) -> Metric:
    metric = await session.get(Metric, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    for key, value in payload.model_dump().items():
        setattr(metric, key, value)
    await write_audit(session, action="update", entity_type="metric", entity_id=metric.id, user=user, request=request)
    await session.commit()
    await invalidate_knowledge_cache(get_settings())
    await session.refresh(metric)
    return metric


@router.delete("/metrics/{metric_id}", status_code=204)
async def delete_metric(
    metric_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(metric_admin),
) -> None:
    metric = await session.get(Metric, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    await session.delete(metric)
    await write_audit(session, action="delete", entity_type="metric", entity_id=metric_id, user=user, request=request)
    await session.commit()
    await invalidate_knowledge_cache(get_settings())


@router.get("/documents", response_model=list[DocumentOut], dependencies=[Depends(document_admin)])
async def list_documents(
    limit: int = Query(default=200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> list[Document]:
    return list(
        (await session.scalars(select(Document).order_by(Document.uploaded_at.desc()).limit(limit))).all()
    )


@router.get("/documents/page", response_model=PaginatedDocuments, dependencies=[Depends(document_admin)])
async def page_documents(
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedDocuments:
    statement = select(Document)
    count_statement = select(func.count(Document.id))
    if q:
        condition = or_(Document.title.ilike(f"%{q}%"), Document.source.ilike(f"%{q}%"), Document.status.ilike(f"%{q}%"))
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    total = await session.scalar(count_statement) or 0
    items = (
        await session.scalars(statement.order_by(Document.uploaded_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).all()
    return PaginatedDocuments(items=list(items), total=total, page=page, page_size=page_size)


@router.post("/documents", response_model=DocumentOut)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    user: AdminUser = Depends(document_admin),
) -> Document:
    filename = validate_filename(file.filename)
    content = await read_upload_limited(file, settings.max_upload_bytes)
    checksum = await validate_upload(file, content, session, settings)
    key = f"documents/{uuid.uuid4()}-{filename}"
    path = await StorageService(settings).put(key, content, file.content_type or "application/octet-stream")
    document = Document(
        title=filename,
        source="Admin upload",
        file_path=path,
        mime_type=file.content_type or "application/octet-stream",
        checksum=checksum,
        size_bytes=len(content),
        status="queued",
        uploaded_by_id=user.id,
    )
    session.add(document)
    await session.flush()
    job = IngestionJob(document_id=document.id, status="queued", progress=0)
    session.add(job)
    await write_audit(
        session,
        action="upload",
        entity_type="document",
        entity_id=document.id,
        user=user,
        request=request,
        metadata={"filename": filename},
    )
    await session.commit()
    await invalidate_knowledge_cache(settings)
    process_document.delay(document.id)
    await session.refresh(document)
    return document


@router.get(
    "/documents/{document_id}/job",
    response_model=JobOut,
    dependencies=[Depends(document_admin)],
)
async def document_job(document_id: str, session: AsyncSession = Depends(get_session)) -> IngestionJob:
    job = await session.scalar(select(IngestionJob).where(IngestionJob.document_id == document_id))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/documents/{document_id}/reprocess", response_model=JobOut)
async def reprocess_document(
    document_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    user: AdminUser = Depends(document_admin),
) -> IngestionJob:
    document = await session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    job = await session.scalar(select(IngestionJob).where(IngestionJob.document_id == document_id))
    if not job:
        job = IngestionJob(document_id=document_id)
        session.add(job)
    job.status = "queued"
    job.progress = 0
    job.error_message = None
    document.status = "queued"
    await write_audit(session, action="reprocess", entity_type="document", entity_id=document_id, user=user, request=request)
    await session.commit()
    await invalidate_knowledge_cache(settings)
    process_document.delay(document.id)
    return job


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    user: AdminUser = Depends(document_admin),
) -> None:
    document = await session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        pinecone = PineconeService(settings)
        await pinecone.ensure_index_compatible()
        await asyncio.to_thread(pinecone.delete_document, document_id)
    except PineconeUnavailableError:
        # A document that never reached indexed state has no acknowledged
        # vector to remove, so it must remain removable after an ingestion
        # outage. Indexed documents fail explicitly to avoid orphaning data.
        if document.status == "indexed":
            raise HTTPException(
                status_code=503,
                detail="Document vectors could not be deleted because Pinecone is unavailable",
            ) from None
    await StorageService(settings).delete(document.file_path)
    await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    await session.delete(document)
    await write_audit(session, action="delete", entity_type="document", entity_id=document_id, user=user, request=request)
    await session.commit()
    await invalidate_knowledge_cache(settings)


@router.post("/knowledge/refresh", status_code=202)
async def refresh_knowledge(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    user: AdminUser = Depends(document_admin),
) -> dict[str, int | str]:
    documents = (await session.scalars(select(Document))).all()
    queued = 0
    for document in documents:
        job = await session.scalar(select(IngestionJob).where(IngestionJob.document_id == document.id))
        if not job:
            job = IngestionJob(document_id=document.id)
            session.add(job)
        job.status = "queued"
        job.progress = 0
        job.error_message = None
        document.status = "queued"
        document.error_message = None
        process_document.delay(document.id)
        queued += 1
    await write_audit(
        session,
        action="refresh",
        entity_type="knowledge_base",
        entity_id=None,
        user=user,
        request=request,
        metadata={"documents_queued": queued},
    )
    await session.commit()
    await invalidate_knowledge_cache(settings)
    return {"status": "queued", "documents": queued}


@router.get("/analytics", response_model=AnalyticsSummary)
async def analytics(session: AsyncSession = Depends(get_session)) -> AnalyticsSummary:
    total = await session.scalar(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.event_type == "query_answered")) or 0
    failed = await session.scalar(
        select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.event_type == "query_answered", AnalyticsEvent.route == "fallback")
    ) or 0
    avg = await session.scalar(select(func.avg(AnalyticsEvent.latency_ms)).where(AnalyticsEvent.latency_ms.is_not(None))) or 0
    website = await session.scalar(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.channel == Channel.website)) or 0
    whatsapp = await session.scalar(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.channel == Channel.whatsapp)) or 0
    ratings = (await session.scalars(select(Feedback.rating))).all()
    satisfaction = (ratings.count("up") / len(ratings)) if ratings else 0.0
    queries = (await session.scalars(select(AnalyticsEvent.query).where(AnalyticsEvent.query.is_not(None)).limit(500))).all()
    popular = [{"query": q, "count": c} for q, c in Counter(queries).most_common(8)]
    failed_queries = (
        await session.scalars(
            select(AnalyticsEvent.query).where(AnalyticsEvent.route == "fallback", AnalyticsEvent.query.is_not(None)).limit(200)
        )
    ).all()
    channels = [
        {"channel": "website", "count": website},
        {"channel": "whatsapp", "count": whatsapp},
    ]
    confidence_rows = (await session.scalars(select(AnalyticsEvent.confidence_score).where(AnalyticsEvent.confidence_score.is_not(None)).limit(500))).all()
    return AnalyticsSummary(
        total_queries=total,
        failed_queries=failed,
        avg_response_ms=int(avg),
        website_usage=website,
        whatsapp_usage=whatsapp,
        user_satisfaction=round(satisfaction, 3),
        popular_questions=popular,
        document_usage=[],
        failed_questions=[{"query": q, "count": c} for q, c in Counter(failed_queries).most_common(8)],
        channel_analytics=channels,
        confidence_trends=[{"bucket": "recent", "average": round(float(sum(confidence_rows) / len(confidence_rows)), 3)}] if confidence_rows else [],
        source_usage=[],
    )


@router.get("/conversations", dependencies=[Depends(super_admin)])
async def conversation_logs(session: AsyncSession = Depends(get_session)) -> list[dict]:
    messages = (
        await session.scalars(select(ConversationMessage).order_by(ConversationMessage.created_at.desc()).limit(200))
    ).all()
    groups = {}
    for msg in messages:
        groups.setdefault(msg.conversation_id, []).append(msg)
    sorted_groups = sorted(groups.values(), key=lambda g: g[0].created_at, reverse=True)
    flattened = []
    for g in sorted_groups:
        for msg in sorted(g, key=lambda m: m.created_at):
            flattened.append({
                "id": msg.id,
                "conversation_id": msg.conversation_id,
                "role": msg.role,
                "content": msg.content,
                "confidence": msg.confidence,
                "route": msg.route,
                "created_at": msg.created_at,
            })
    return flattened


@router.get("/feedback", response_model=list[FeedbackOut], dependencies=[Depends(super_admin)])
async def feedback_dashboard(session: AsyncSession = Depends(get_session)) -> list[FeedbackOut]:
    rows = (
        await session.execute(
            select(Feedback, ConversationMessage)
            .join(ConversationMessage, Feedback.message_id == ConversationMessage.id)
            .order_by(Feedback.created_at.desc())
            .limit(300)
        )
    ).all()
    return [
        FeedbackOut(
            id=item.id,
            message_id=item.message_id,
            rating=item.rating,
            comment=item.comment,
            message_content=message.content,
            conversation_id=message.conversation_id,
            created_at=item.created_at,
        )
        for item, message in rows
    ]


@router.get("/handoff-tickets", response_model=list[HandoffTicketOut], dependencies=[Depends(super_admin)])
async def handoff_tickets(session: AsyncSession = Depends(get_session)) -> list[HandoffTicket]:
    return list(
        (
            await session.scalars(
                select(HandoffTicket).order_by(HandoffTicket.created_at.desc()).limit(300)
            )
        ).all()
    )


@router.patch("/handoff-tickets/{ticket_id}", response_model=HandoffTicketOut)
async def update_handoff_ticket(
    ticket_id: str,
    payload: HandoffTicketUpdateIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(super_admin),
) -> HandoffTicket:
    ticket = await session.get(HandoffTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Handoff ticket not found")
    ticket.status = payload.status
    ticket.internal_note = payload.internal_note
    if payload.status in {"resolved", "closed"}:
        ticket.resolved_by_id = user.id
        ticket.resolved_at = now()
    else:
        ticket.resolved_by_id = None
        ticket.resolved_at = None
    await write_audit(
        session,
        action="update",
        entity_type="handoff_ticket",
        entity_id=ticket.id,
        user=user,
        request=request,
        metadata={"status": ticket.status},
    )
    await session.commit()
    await session.refresh(ticket)
    return ticket


@router.get("/audit-logs", response_model=list[AuditLogOut], dependencies=[Depends(super_admin)])
async def audit_logs(session: AsyncSession = Depends(get_session)) -> list[AuditLogOut]:
    logs = (await session.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))).all()
    return [
        AuditLogOut(
            id=log.id,
            actor_id=log.actor_id,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            ip_address=log.ip_address,
            metadata=log.metadata_,
            created_at=log.created_at,
        )
        for log in logs
    ]


@router.get("/domains", response_model=list[DomainOut], dependencies=[Depends(super_admin)])
async def list_domains(session: AsyncSession = Depends(get_session)) -> list[AllowedDomain]:
    return list((await session.scalars(select(AllowedDomain).order_by(AllowedDomain.domain))).all())


@router.post("/domains", response_model=DomainOut)
async def create_domain(
    payload: DomainIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    user: AdminUser = Depends(super_admin),
) -> AllowedDomain:
    domain = AllowedDomain(domain=payload.domain.lower().strip(), is_active=payload.is_active)
    session.add(domain)
    await session.flush()
    await write_audit(session, action="create", entity_type="allowed_domain", entity_id=domain.id, user=user, request=request)
    await session.commit()
    await session.refresh(domain)
    return domain
