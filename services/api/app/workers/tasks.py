import asyncio
from pathlib import Path
from types import SimpleNamespace

from redis.asyncio import Redis
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.models import Document, DocumentChunk, IngestionJob, WhatsAppDelivery
from app.services.ingestion import chunk_text, extract_text
from app.services.llm import close_openai_clients
from app.services.pinecone_service import PineconeService, PineconeUnavailableError
from app.services.storage import StorageService
from app.services.upload_security import validate_file_signature
from app.services.whatsapp import send_whatsapp_message
from app.workers.celery_app import celery_app


@celery_app.task(bind=True)
def process_document(self, document_id: str) -> None:
    try:
        asyncio.run(_run_document_task(document_id))
    except PineconeUnavailableError:
        # A missing or incompatible index is a configuration failure, not a
        # transient task failure. The job is already marked failed and the
        # administrator can explicitly reprocess it after provider recovery.
        raise
    except Exception as exc:
        raise self.retry(exc=exc, countdown=20, max_retries=3) from exc


@celery_app.task(bind=True, autoretry_for=(RuntimeError,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def process_whatsapp_message(self, inbound_id: str, sender: str, text: str, language: str) -> None:
    asyncio.run(_run_whatsapp_task(inbound_id, sender, text, language))


async def _run_document_task(document_id: str) -> None:
    """Keep async database connections scoped to this Celery event loop."""
    try:
        await _process_document(document_id)
    finally:
        await engine.dispose()


async def _run_whatsapp_task(inbound_id: str, sender: str, text: str, language: str) -> None:
    try:
        async with SessionLocal() as session:
            delivery = await session.get(WhatsAppDelivery, inbound_id, with_for_update=True)
            if not delivery or delivery.status == "processed":
                return
            delivery.status = "processing"
            await session.commit()
            # Import here to keep task/module registration acyclic.
            from app.api.routes.chat import process_chat
            from app.schemas import ChatRequest

            settings = get_settings()
            response = await process_chat(
                ChatRequest(message=text, channel="whatsapp", language=language),
                SimpleNamespace(),
                session,
                settings,
                sender,
            )
            outbound = await send_whatsapp_message(settings, sender, response.message.content)
            session.add(outbound)
            if outbound.status == "failed":
                delivery.status = "failed"
                delivery.error_message = outbound.error_message
                await session.commit()
                raise RuntimeError("WhatsApp delivery failed")
            delivery.status = "processed" if outbound.status == "sent" else "not_configured"
            delivery.error_message = outbound.error_message
            await session.commit()
    finally:
        await close_openai_clients()
        await engine.dispose()


async def _process_document(document_id: str) -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
    lock = redis.lock(f"ciet:ingestion:{document_id}", timeout=360)
    try:
        acquired = await lock.acquire(blocking=False)
    except Exception:
        await redis.aclose()
        raise
    if not acquired:
        await redis.aclose()
        return
    try:
        async with SessionLocal() as session:
            document = await session.get(Document, document_id)
            job = await session.scalar(select(IngestionJob).where(IngestionJob.document_id == document_id))
            if not document or not job:
                return
            try:
                # Index state must never claim success unless both embeddings and
                # the configured Pinecone index have accepted the chunks.
                document.status = "processing"
                job.status = "extracting"
                job.progress = 20
                await session.commit()
                content = await StorageService(settings).get(document.file_path)
                validate_file_signature(
                    Path(document.title).suffix.lower(),
                    content,
                    settings.max_upload_bytes,
                )
                text = extract_text(document.title, content)
                job.status = "chunking"
                job.progress = 45
                pinecone = PineconeService(settings)
                await pinecone.ensure_index_compatible()
                await asyncio.to_thread(pinecone.delete_document, document_id)
                await session.execute(
                    DocumentChunk.__table__.delete().where(
                        DocumentChunk.document_id == document_id
                    )
                )
                chunks = [
                    DocumentChunk(
                        document_id=document_id,
                        chunk_index=index,
                        content=chunk,
                        section=f"Chunk {index + 1}",
                        token_count=max(1, len(chunk.split())),
                    )
                    for index, chunk in enumerate(chunk_text(text))
                ]
                if not chunks:
                    raise ValueError("Document contains no extractable text")
                session.add_all(chunks)
                await session.flush()
                job.status = "embedding"
                job.progress = 70
                await session.commit()
                await pinecone.upsert_chunks(chunks)
                document.status = "indexed"
                document.error_message = None
                job.status = "complete"
                job.progress = 100
                await session.commit()
            except Exception as exc:
                safe_error = f"{type(exc).__name__}: document processing failed"
                document.status = "failed"
                document.error_message = safe_error
                job.status = "failed"
                job.error_message = safe_error
                job.attempts += 1
                await session.commit()
                raise
            finally:
                await close_openai_clients()
    finally:
        try:
            if await lock.owned():
                await lock.release()
        finally:
            await redis.aclose()
