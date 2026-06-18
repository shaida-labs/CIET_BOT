from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import DocumentChunk
from app.schemas import Citation
from app.services.llm import LLMService


@dataclass(slots=True)
class SearchHit:
    chunk: DocumentChunk | None
    score: float
    source: str


class PineconeService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = LLMService(settings)
        self.index = None
        if settings.pinecone_api_key:
            from pinecone import Pinecone

            self.index = Pinecone(api_key=settings.pinecone_api_key).Index(settings.pinecone_index)

    async def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        if not self.index or not chunks:
            return 0
        vectors = await self.llm.embed([chunk.content for chunk in chunks])
        payload = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            embedding_id = f"chunk-{chunk.id}"
            chunk.embedding_id = embedding_id
            payload.append(
                {
                    "id": embedding_id,
                    "values": vector,
                    "metadata": {
                        "document_id": chunk.document_id,
                        "chunk_id": chunk.id,
                        "section": chunk.section or "",
                        "text": chunk.content[:4000],
                    },
                }
            )
        self.index.upsert(vectors=payload, namespace=self.settings.pinecone_namespace)
        return len(payload)

    def delete_document(self, document_id: str) -> None:
        if not self.index:
            return
        self.index.delete(
            filter={"document_id": {"$eq": document_id}},
            namespace=self.settings.pinecone_namespace,
        )

    async def hybrid_search(
        self,
        session: AsyncSession,
        query: str,
        *,
        top_k: int = 6,
        filters: dict | None = None,
    ) -> list[SearchHit]:
        postgres_hits = await self._postgres_full_text(session, query, top_k=top_k)
        vector_hits = await self._pinecone_search(session, query, top_k=top_k, filters=filters)
        return rerank_hits(query, postgres_hits + vector_hits)[:top_k]

    async def _postgres_full_text(self, session: AsyncSession, query: str, top_k: int) -> list[SearchHit]:
        tokens = [token for token in query.lower().split() if len(token) > 2][:8]
        if not tokens:
            return []
        conditions = [DocumentChunk.content.ilike(f"%{token}%") for token in tokens]
        chunks = (await session.scalars(select(DocumentChunk).where(or_(*conditions)).limit(top_k * 2))).all()
        return [SearchHit(chunk=chunk, score=keyword_score(query, chunk.content), source="postgres") for chunk in chunks]

    async def _pinecone_search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int,
        filters: dict | None,
    ) -> list[SearchHit]:
        if not self.index:
            return []
        embeddings = await self.llm.embed([query])
        if not embeddings:
            return []
        result = self.index.query(
            vector=embeddings[0],
            top_k=top_k,
            include_metadata=True,
            filter=filters,
            namespace=self.settings.pinecone_namespace,
        )
        ids = [match["metadata"].get("chunk_id") for match in result.get("matches", []) if match.get("metadata")]
        chunks = {}
        if ids:
            rows = (await session.scalars(select(DocumentChunk).where(DocumentChunk.id.in_(ids)))).all()
            chunks = {chunk.id: chunk for chunk in rows}
        return [
            SearchHit(
                chunk=chunks.get(match["metadata"].get("chunk_id")),
                score=float(match.get("score", 0)),
                source="pinecone",
            )
            for match in result.get("matches", [])
            if match.get("metadata")
        ]


def keyword_score(query: str, content: str) -> float:
    words = {word for word in query.lower().split() if len(word) > 2}
    if not words:
        return 0
    content_lower = content.lower()
    matches = sum(1 for word in words if word in content_lower)
    return matches / len(words)


def rerank_hits(query: str, hits: list[SearchHit]) -> list[SearchHit]:
    seen: set[str] = set()
    merged: list[SearchHit] = []
    for hit in sorted(hits, key=lambda item: item.score, reverse=True):
        if not hit.chunk or hit.chunk.id in seen:
            continue
        seen.add(hit.chunk.id)
        boost = 0.15 if hit.source == "pinecone" else 0.08
        merged.append(SearchHit(chunk=hit.chunk, score=hit.score + boost + keyword_score(query, hit.chunk.content), source=hit.source))
    return sorted(merged, key=lambda item: item.score, reverse=True)


def citations_from_hits(hits: list[SearchHit]) -> list[Citation]:
    return [
        Citation(document_id=hit.chunk.document_id, title="CIET Knowledge Base", section=hit.chunk.section)
        for hit in hits
        if hit.chunk
    ]
