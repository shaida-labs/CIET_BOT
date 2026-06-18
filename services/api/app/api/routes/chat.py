import uuid

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import AnalyticsEvent, Channel, Conversation, ConversationMessage
from app.schemas import ChatMessageOut, ChatRequest, ChatResponse, FeedbackIn
from app.services.retrieval import RetrievalService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    conversation = None
    if payload.conversation_id:
        conversation = await session.get(Conversation, payload.conversation_id)
    if not conversation:
        conversation = Conversation(
            id=str(uuid.uuid4()),
            channel=Channel(payload.channel),
            user_ref=payload.user_ref or request.client.host if request.client else None,
            language=payload.language,
        )
        session.add(conversation)
        await session.flush()

    session.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role="user",
            content=payload.message,
        )
    )
    retrieval = RetrievalService(settings)
    result, latency_ms = await retrieval.answer(session, payload.message, payload.language)
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
            created_at=assistant.created_at,
            confidence=result.confidence,
            citations=result.citations,
        ),
    )


@router.post("/feedback", status_code=204)
async def feedback(payload: FeedbackIn, session: AsyncSession = Depends(get_session)) -> None:
    from app.models import Feedback

    session.add(Feedback(message_id=payload.message_id, rating=payload.rating, comment=payload.comment))
    session.add(
        AnalyticsEvent(
            event_type="feedback",
            query=None,
            metadata_={"message_id": payload.message_id, "rating": payload.rating},
        )
    )
    await session.commit()


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    response = await chat(payload, request, session, settings)

    async def events():
        yield f"event: metadata\ndata: {json.dumps({'conversation_id': response.conversation_id, 'route': response.route})}\n\n"
        for token in response.message.content.split():
            if await request.is_disconnected():
                break
            yield f"event: token\ndata: {json.dumps({'token': token + ' '})}\n\n"
            await asyncio.sleep(0.015)
        yield f"event: done\ndata: {response.message.model_dump_json()}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
