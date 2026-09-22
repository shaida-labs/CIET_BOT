import asyncio
import json
import secrets
import uuid
from asyncio import sleep
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.db.session import get_session
from app.models import (
    AnalyticsEvent,
    Channel,
    Conversation,
    ConversationMessage,
    Feedback,
    HandoffTicket,
)
from app.schemas import (
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    FeedbackIn,
    HandoffTicketIn,
    HandoffTicketOut,
    TranslateMessageIn,
    TranslateMessageOut,
    TranslateRequest,
    TranslateResponse,
)
from app.services.language import (
    detect_language,
    needs_translation,
    strip_translation_delimiters,
    translation_accepted,
)
from app.services.llm import LLMService, LLMUnavailableError
from app.services.retrieval import RetrievalService

router = APIRouter(tags=["chat"])
logger = structlog.get_logger()
WIDGET_VISITOR_COOKIE = "ciet_widget_visitor"


def resolve_widget_visitor(request: Request) -> tuple[str, bool]:
    """Return the browser-bound anonymous owner for website conversations.

    IP addresses and client-supplied identifiers are not ownership credentials:
    they are shared or spoofable.  The opaque cookie is HttpOnly and is only
    accepted from an allowed widget origin by DomainSecurityMiddleware.
    """
    cookies = getattr(request, "cookies", {})
    visitor = cookies.get(WIDGET_VISITOR_COOKIE) if cookies else None
    if visitor and len(visitor) >= 32:
        return visitor, False
    return secrets.token_urlsafe(32), True


def set_widget_visitor_cookie(response: Response, visitor: str, settings: Settings) -> None:
    response.set_cookie(
        WIDGET_VISITOR_COOKIE,
        visitor,
        httponly=True,
        secure=settings.secure_cookies,
        # CIET widgets are commonly embedded on a distinct CIET web origin.
        # SameSite=None is required for that supported production deployment;
        # local development retains Lax without HTTPS.
        samesite="none" if settings.secure_cookies else "lax",
        max_age=60 * 60 * 24 * 30,
        path="/",
    )


async def recent_conversation_memory(
    session: AsyncSession, conversation_id: str, settings: Settings
) -> list[tuple[str, str]]:
    """Load a bounded, server-authoritative history for one owned conversation."""
    if not settings.conversation_memory_messages or not settings.conversation_memory_characters:
        return []
    messages = list(
        (
            await session.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.conversation_id == conversation_id)
                .order_by(ConversationMessage.created_at.desc())
                .limit(settings.conversation_memory_messages)
            )
        ).all()
    )
    remaining = settings.conversation_memory_characters
    memory: list[tuple[str, str]] = []
    for message in messages:
        if remaining <= 0:
            break
        content = message.content[:remaining]
        if content:
            memory.append((message.role, content))
            remaining -= len(content)
    return list(reversed(memory))


async def process_chat(
    payload: ChatRequest,
    request: Request,
    session: AsyncSession,
    settings: Settings,
    owner: str,
) -> ChatResponse:
    """Execute a chat request after the trusted channel owner is established."""
    language = detect_language(payload.message, payload.language)
    conversation = None
    if payload.conversation_id:
        conversation = await session.get(Conversation, payload.conversation_id)
        if conversation and (conversation.channel != Channel(payload.channel) or conversation.user_ref != owner):
            raise HTTPException(status_code=403, detail="Conversation does not belong to this client")
    if not conversation:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            channel=Channel(payload.channel),
            user_ref=owner,
            language=language,
        )
        session.add(conversation)
        await session.flush()

    memory = await recent_conversation_memory(session, conversation.id, settings)

    session.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role="user",
            content=payload.message,
        )
    )
    retrieval = RetrievalService(settings)
    result, latency_ms = await retrieval.answer(
        session,
        payload.message,
        language,
        conversation_memory=memory,
    )
    assistant = ConversationMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result.answer,
        confidence=result.confidence,
        route=result.route,
        citations=[citation.model_dump() for citation in result.citations],
        latency_ms=latency_ms,
    )
    session.add(assistant)
    session.add(
        AnalyticsEvent(
            event_type="query_answered",
            channel=Channel(payload.channel),
            query=payload.message,
            latency_ms=latency_ms,
            route=result.route,
            confidence_score=result.score,
            metadata_={"conversation_id": conversation.id},
        )
    )
    await session.commit()
    await session.refresh(assistant)

    return ChatResponse(
        conversation_id=conversation.id,
        route=result.route,
        message=ChatMessageOut(
            id=assistant.id,
            role="assistant",
            content=assistant.content,
            language=language,
            created_at=assistant.created_at,
            confidence=result.confidence,
            citations=result.citations,
        ),
    )


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def chat(
    payload: ChatRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    if payload.channel != "website":
        raise HTTPException(status_code=403, detail="This endpoint only accepts website chat")
    visitor, created = resolve_widget_visitor(request)
    result = await process_chat(payload, request, session, settings, visitor)
    if created:
        set_widget_visitor_cookie(response, visitor, settings)
    return result


async def translate_contents(
    settings: Settings, language: str, messages: list[TranslateMessageIn]
) -> list[TranslateMessageOut]:
    """Translate widget-held history line by line.

    Every line fails closed on its own: text already in the target language
    or without a working translation is returned unchanged with
    ``translated=False``, so the client never displays invented text.  Once a
    provider chain reports total failure the remaining lines skip their own
    retries instead of repeating the same dead chain.  When that chain died on
    provider rate limits, one bounded recovery pass runs just inside the next
    wall-clock minute: free-tier quotas reset there, while the widget itself
    never re-asks for a switch that came back untranslated.
    """
    service = LLMService(settings)
    semaphore = asyncio.Semaphore(4)
    exhausted = asyncio.Event()
    rate_limited = False

    async def translate_one(item: TranslateMessageIn) -> TranslateMessageOut:
        nonlocal rate_limited
        if exhausted.is_set() or not needs_translation(item.content, language):
            return TranslateMessageOut(id=item.id, content=item.content, translated=False)
        async with semaphore:
            for attempt in range(2):
                try:
                    raw = await service.translate(item.content, language)
                except LLMUnavailableError as exc:
                    if exc.category == "rate_limit":
                        rate_limited = True
                    exhausted.set()
                    break
                candidate = strip_translation_delimiters(raw)
                if translation_accepted(item.content, candidate, language):
                    return TranslateMessageOut(id=item.id, content=candidate, translated=True)
                if attempt == 0:
                    logger.warning(
                        "llm_translation_rejected",
                        language=language,
                        error_type="wrong_script",
                    )
        return TranslateMessageOut(id=item.id, content=item.content, translated=False)

    results = list(await asyncio.gather(*(translate_one(item) for item in messages)))
    if not rate_limited:
        return results
    pending = [
        index
        for index, (item, result) in enumerate(zip(messages, results, strict=True))
        if not result.translated and needs_translation(item.content, language)
    ]
    if not pending:
        return results

    wait_seconds = 60 - datetime.now().second + 1
    logger.warning(
        "llm_translation_recovery",
        pending=len(pending),
        wait_seconds=wait_seconds,
    )
    await sleep(wait_seconds)
    exhausted.clear()
    retried = await asyncio.gather(*(translate_one(messages[index]) for index in pending))
    for index, result in zip(pending, retried, strict=True):
        results[index] = result
    return results


@router.post("/chat/translate", response_model=TranslateResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def chat_translate(
    payload: TranslateRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> TranslateResponse:
    """Re-render an already-delivered conversation in another UI language.

    This endpoint only rewords text the client already received; it never
    creates new answers, so a provider outage degrades to the original
    messages instead of blocking the chat.
    """
    messages = await translate_contents(settings, payload.language, payload.messages)
    return TranslateResponse(
        language=payload.language,
        translated=any(item.translated for item in messages),
        messages=messages,
    )


@router.post("/feedback", status_code=204)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def feedback(
    payload: FeedbackIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> None:
    message = await session.get(ConversationMessage, payload.message_id)
    if not message or message.role != "assistant":
        raise HTTPException(status_code=404, detail="Assistant message not found")
    conversation = await session.get(Conversation, message.conversation_id)
    visitor, _ = resolve_widget_visitor(request)
    if not conversation or conversation.channel != Channel.website or conversation.user_ref != visitor:
        raise HTTPException(status_code=403, detail="Message does not belong to this client")
    item = await session.scalar(select(Feedback).where(Feedback.message_id == payload.message_id))
    if item:
        item.rating = payload.rating
        item.comment = payload.comment
    else:
        session.add(Feedback(message_id=payload.message_id, rating=payload.rating, comment=payload.comment))
    session.add(
        AnalyticsEvent(
            event_type="feedback",
            query=None,
            metadata_={"message_id": payload.message_id, "rating": payload.rating},
        )
    )
    await session.commit()


@router.post("/support/tickets", response_model=HandoffTicketOut, status_code=201)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def create_handoff_ticket(
    payload: HandoffTicketIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> HandoffTicket:
    """Create a consented support request for the caller's own conversation only."""
    visitor, _ = resolve_widget_visitor(request)
    conversation = await session.get(Conversation, payload.conversation_id)
    if (
        not conversation
        or conversation.channel != Channel.website
        or conversation.user_ref != visitor
    ):
        raise HTTPException(status_code=403, detail="Conversation does not belong to this client")
    ticket = HandoffTicket(
        conversation_id=conversation.id,
        contact=payload.contact.strip(),
        contact_consent=True,
    )
    session.add(ticket)
    await session.flush()
    session.add(
        AnalyticsEvent(
            event_type="handoff_requested",
            channel=Channel.website,
            metadata_={"conversation_id": conversation.id, "ticket_id": ticket.id},
        )
    )
    await session.commit()
    await session.refresh(ticket)
    return ticket


@router.post("/chat/stream")
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    if payload.channel != "website":
        raise HTTPException(status_code=403, detail="This endpoint only accepts website chat")
    visitor, created = resolve_widget_visitor(request)
    response = await process_chat(payload, request, session, settings, visitor)

    async def events():
        yield f"event: metadata\ndata: {json.dumps({'conversation_id': response.conversation_id, 'route': response.route})}\n\n"
        # This is intentionally a buffered SSE response.  The retrieval path
        # currently persists an answer before responding; emitting split words
        # would falsely imply that they came from a provider token stream.
        yield f"event: message\ndata: {response.message.model_dump_json()}\n\n"
        yield "event: done\ndata: {}\n\n"

    stream = StreamingResponse(
        events(),
        media_type="text/event-stream; charset=utf-8",
        headers={"X-CIET-Streaming-Mode": "buffered"},
    )
    if created:
        set_widget_visitor_cookie(stream, visitor, settings)
    return stream
