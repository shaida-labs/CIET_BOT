from dataclasses import dataclass
import asyncio
import unicodedata

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import Settings
from app.models import Document, DocumentChunk
from app.schemas import Citation
from app.services.llm import LLMService


logger = structlog.get_logger()


class PineconeUnavailableError(RuntimeError):
    pass


EMBEDDING_DIMENSIONS = {
    # The application does not send OpenAI's optional `dimensions` parameter,
    # therefore these are the documented default vector lengths for supported
    # embedding models.
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


@dataclass(slots=True)
class SearchHit:
    chunk: DocumentChunk | None
    score: float
    source: str


STOPWORDS = {
    "a", "an", "and", "are", "about", "can", "could", "do", "does", "for", "from",
    "how", "i", "in", "is", "it", "me", "of", "on", "please", "tell", "the", "to",
    "what", "when", "where", "which", "with", "you", "your", "hai", "hain", "kya",
    "kaise", "mein", "mujhe", "batao", "enti", "ela", "unda", "unnayi", "cheppandi",
    "gurinchi", "నాకు", "గురించి", "ఏమిటి", "ఎలా", "ఉందా", "చెప్పండి", "क्या", "कैसे",
    "के", "की", "में", "मुझे", "बताएं",
}

ALIASES = {
    "admission": {"admission", "admissions", "admit", "ప్రవేశం", "అడ్మిషన్", "అడ్మిషన్లు", "pravesam"},
    "course": {"course", "courses", "program", "programs", "కోర్సు", "కోర్సులు", "courseulu", "पाठ्यक्रम", "कोर्स"},
    "placement": {"placement", "placements", "job", "jobs", "ప్లేస్మెంట్", "ప్లేస్‌మెంట్", "ఉద్యోగాలు", "udyogalu", "प्लेसमेंट", "नौकरी"},
    "hostel": {"hostel", "accommodation", "హాస్టల్", "vasathi", "छात्रावास"},
    "transport": {"transport", "bus", "buses", "రవాణా", "బస్సు", "buslu", "परिवहन", "बस"},
    "scholarship": {"scholarship", "scholarships", "స్కాలర్‌షిప్", "ఉపకారవేతనం", "छात्रवृत्ति"},
    "department": {"department", "departments", "branch", "branches", "విభాగం", "శాఖ", "विभाग"},
    "fee": {"fee", "fees", "ఫీజు", "ఫీజులు", "feeslu", "फीस", "शुल्क"},
    "contact": {"contact", "phone", "email", "address", "సంప్రదింపు", "చిరునామా", "संपर्क", "पता"},
    "percentage": {"percentage", "percent", "శాతం", "प्रतिशत"},
}
ALIAS_LOOKUP = {alias: canonical for canonical, aliases in ALIASES.items() for alias in aliases}


def normalize_tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    # Python's regular-expression ``\w`` class splits Indic combining marks
    # away from their base characters. Build words from Unicode categories so
    # Telugu and Hindi tokens remain intact for lexical retrieval.
    raw: list[str] = []
    current: list[str] = []
    for character in normalized:
        category = unicodedata.category(character)
        if category[0] in {"L", "M", "N"} or character in {"\u200c", "\u200d"}:
            current.append(character)
        elif current:
            raw.append("".join(current))
            current = []
    if current:
        raw.append("".join(current))
    return [ALIAS_LOOKUP.get(token, token) for token in raw if len(token) > 1 and token not in STOPWORDS]


class PineconeService:
    _indexes: dict[tuple[str, str], object] = {}

    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = LLMService(settings)
        self.index = self._indexes.get((settings.pinecone_api_key, settings.pinecone_index)) if settings.pinecone_api_key else None
        self.initialization_error: Exception | None = None

    def _initialize_index(self) -> object:
        """Resolve the synchronous SDK client outside the async request loop."""
        if not self.settings.pinecone_api_key:
            raise PineconeUnavailableError("Pinecone is not configured")
        if self.index:
            return self.index
        try:
            from pinecone import Pinecone

            key = (self.settings.pinecone_api_key, self.settings.pinecone_index)
            index = self._indexes.get(key)
            if index is None:
                index = Pinecone(api_key=self.settings.pinecone_api_key).Index(self.settings.pinecone_index)
                self._indexes[key] = index
            self.index = index
            return index
        except Exception as exc:
            self.initialization_error = exc
            logger.warning(
                "pinecone_unavailable",
                index=self.settings.pinecone_index,
                error_type=type(exc).__name__,
            )
            raise PineconeUnavailableError("Configured Pinecone index is unavailable") from exc

    @property
    def expected_dimension(self) -> int:
        dimension = EMBEDDING_DIMENSIONS.get(self.settings.embedding_model)
        if dimension is None:
            raise PineconeUnavailableError(
                f"No default dimension is defined for embedding model {self.settings.embedding_model!r}"
            )
        return dimension

    async def ensure_index_compatible(self) -> None:
        """Fail ingestion before writes when the configured index is absent or mismatched."""
        if not self.settings.pinecone_api_key:
            raise PineconeUnavailableError("Pinecone is not configured")
        if not self.index:
            await asyncio.to_thread(self._initialize_index)

        def describe_dimension() -> int | None:
            description = self.index.describe_index_stats()
            if isinstance(description, dict):
                value = description.get("dimension")
            else:
                value = getattr(description, "dimension", None)
            return int(value) if value is not None else None

        try:
            actual_dimension = await asyncio.to_thread(describe_dimension)
        except Exception as exc:
            logger.warning(
                "pinecone_index_verification_failed",
                index=self.settings.pinecone_index,
                error_type=type(exc).__name__,
            )
            raise PineconeUnavailableError("Configured Pinecone index could not be verified") from exc
        if actual_dimension is not None and actual_dimension != self.expected_dimension:
            raise PineconeUnavailableError(
                "Configured Pinecone index dimension does not match the embedding model"
            )

    async def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        if not chunks:
            return 0
        await self.ensure_index_compatible()
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
        await asyncio.to_thread(
            self.index.upsert,
            vectors=payload,
            namespace=self.settings.pinecone_namespace,
        )
        return len(payload)

    def delete_document(self, document_id: str) -> None:
        if not self.index:
            if self.settings.pinecone_api_key:
                raise PineconeUnavailableError("Configured Pinecone index is unavailable") from self.initialization_error
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
        try:
            vector_hits = await self._pinecone_search(session, query, top_k=top_k, filters=filters)
        except Exception as exc:
            logger.warning(
                "pinecone_search_failed",
                index=self.settings.pinecone_index,
                error_type=type(exc).__name__,
            )
            vector_hits = []
        return rerank_hits(query, postgres_hits + vector_hits)[:top_k]

    async def _postgres_full_text(self, session: AsyncSession, query: str, top_k: int) -> list[SearchHit]:
        tokens = list(dict.fromkeys(normalize_tokens(query)))[:8]
        if not tokens:
            return []
        conditions = [DocumentChunk.content.ilike(f"%{token}%") for token in tokens]
        chunks = (
            await session.scalars(
                select(DocumentChunk)
                .join(Document)
                .where(Document.status == "indexed", or_(*conditions))
                .options(joinedload(DocumentChunk.document))
                .limit(top_k * 3)
            )
        ).unique().all()
        return [SearchHit(chunk=chunk, score=keyword_score(query, chunk.content), source="postgres") for chunk in chunks]

    async def _pinecone_search(
        self,
        session: AsyncSession,
        query: str,
        top_k: int,
        filters: dict | None,
    ) -> list[SearchHit]:
        await self.ensure_index_compatible()
        embeddings = await self.llm.embed([query])
        if not embeddings:
            return []
        result = await asyncio.to_thread(
            self.index.query,
            vector=embeddings[0],
            top_k=top_k,
            include_metadata=True,
            filter=filters,
            namespace=self.settings.pinecone_namespace,
        )
        ids = [match["metadata"].get("chunk_id") for match in result.get("matches", []) if match.get("metadata")]
        chunks = {}
        if ids:
            rows = (
                await session.scalars(
                    select(DocumentChunk)
                    .join(Document)
                    .where(DocumentChunk.id.in_(ids), Document.status == "indexed")
                    .options(joinedload(DocumentChunk.document))
                )
            ).unique().all()
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
    words = set(normalize_tokens(query))
    content_words = set(normalize_tokens(content))
    if not words or not content_words:
        return 0
    return len(words & content_words) / len(words)


def rerank_hits(query: str, hits: list[SearchHit]) -> list[SearchHit]:
    candidates: dict[str, dict[str, object]] = {}
    for hit in hits:
        if not hit.chunk:
            continue
        record = candidates.setdefault(hit.chunk.id, {"chunk": hit.chunk, "vector": 0.0, "sources": set()})
        record["sources"].add(hit.source)
        if hit.source == "pinecone":
            record["vector"] = max(float(record["vector"]), max(0.0, min(1.0, hit.score)))

    merged: list[SearchHit] = []
    for record in candidates.values():
        chunk = record["chunk"]
        lexical = keyword_score(query, chunk.content)
        vector = float(record["vector"])
        sources = record["sources"]
        score = lexical if not vector else (0.65 * vector) + (0.35 * lexical)
        source = "hybrid" if len(sources) > 1 else next(iter(sources))
        merged.append(SearchHit(chunk=chunk, score=round(max(0.0, min(1.0, score)), 4), source=source))
    return sorted(merged, key=lambda item: item.score, reverse=True)


def citations_from_hits(hits: list[SearchHit]) -> list[Citation]:
    return [
        Citation(
            document_id=hit.chunk.document_id,
            title=hit.chunk.document.title if hit.chunk.document else "CIET Knowledge Base",
            section=hit.chunk.section,
        )
        for hit in hits
        if hit.chunk
    ]
