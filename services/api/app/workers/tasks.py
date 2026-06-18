import asyncio
import base64

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Document, DocumentChunk, IngestionJob
from app.services.ingestion import chunk_text, extract_text
from app.services.pinecone_service import PineconeService
from app.workers.celery_app import celery_app


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def process_document(self, document_id: str, content_b64: str, filename: str) -> None:
    asyncio.run(_process_document(document_id, base64.b64decode(content_b64), filename))


async def _process_document(document_id: str, content: bytes, filename: str) -> None:
    settings = get_settings()
    async with SessionLocal() as session:
        document = await session.get(Document, document_id)
        job = await session.scalar(select(IngestionJob).where(IngestionJob.document_id == document_id))
        if not document or not job:
            return
        try:
            job.status = "extracting"
            job.progress = 20
            await session.commit()
            text = extract_text(filename, content)
            job.status = "chunking"
            job.progress = 45
            await session.execute(DocumentChunk.__table__.delete().where(DocumentChunk.document_id == document_id))
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
            session.add_all(chunks)
            await session.flush()
            job.status = "embedding"
            job.progress = 70
            await session.commit()
            await PineconeService(settings).upsert_chunks(chunks)
            document.status = "indexed"
            document.error_message = None
            job.status = "complete"
            job.progress = 100
            await session.commit()
        except Exception as exc:
            document.status = "failed"
            document.error_message = str(exc)
            job.status = "failed"
            job.error_message = str(exc)
            job.attempts += 1
            await session.commit()
            raise
