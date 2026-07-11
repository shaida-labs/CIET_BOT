from difflib import SequenceMatcher
from time import perf_counter

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import FAQ, Metric
from app.schemas import Citation, RetrievalResult
from app.services.guardrails import SAFE_STAT_RESPONSES, is_sensitive_stat_question
from app.services.llm import LLMService
from app.services.pinecone_service import PineconeService, citations_from_hits


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


class RetrievalService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = LLMService(settings)
        self.pinecone = PineconeService(settings)

    async def answer(self, session: AsyncSession, query: str, language: str) -> tuple[RetrievalResult, int]:
        start = perf_counter()
        result = await self._faq(session, query, language)
        if not result:
            result = await self._metric(session, query, language)
        if not result:
            result = await self._rag(session, query, language)
        if not result:
            result = await self._website_search(query)
        if not result:
            result = RetrievalResult(
                answer=self.settings.safe_fallback,
                route="fallback",
                confidence="low",
                score=0,
                citations=[],
            )
        return result, int((perf_counter() - start) * 1000)

    async def _faq(self, session: AsyncSession, query: str, language: str) -> RetrievalResult | None:
        faqs = (
            await session.scalars(
                select(FAQ).where(FAQ.is_active.is_(True), or_(FAQ.language == language, FAQ.language == "en"))
            )
        ).all()
        if not faqs:
            return None
        best = max(faqs, key=lambda faq: similarity(query, faq.question))
        score = similarity(query, best.question)
        if score < 0.63:
            return None
        return RetrievalResult(
            answer=best.answer,
            route="faq",
            confidence="verified",
            score=score,
            citations=[Citation(title=best.source, section="FAQ Database")],
        )

    async def _metric(self, session: AsyncSession, query: str, language: str) -> RetrievalResult | None:
        metrics = (await session.scalars(select(Metric))).all()
        if not metrics:
            if is_sensitive_stat_question(query):
                return RetrievalResult(
                    answer=SAFE_STAT_RESPONSES.get(language, SAFE_STAT_RESPONSES["en"]),
                    route="metric",
                    confidence="medium",
                    score=0.6,
                    citations=[Citation(title="Verified Metrics Database", section="Metric unavailable")],
                )
            return None
        best = max(metrics, key=lambda metric: similarity(query, metric.name))
        score = similarity(query, best.name)
        if score < 0.5:
            if is_sensitive_stat_question(query):
                return RetrievalResult(
                    answer=SAFE_STAT_RESPONSES.get(language, SAFE_STAT_RESPONSES["en"]),
                    route="metric",
                    confidence="medium",
                    score=0.6,
                    citations=[Citation(title="Verified Metrics Database", section="Metric unavailable")],
                )
            return None
        return RetrievalResult(
            answer=f"{best.name}: {best.value}{f' {best.unit}' if best.unit else ''}.",
            route="metric",
            confidence="verified",
            score=score,
            citations=[Citation(title=best.source, section=f"Verified by {best.verified_by}")],
        )

    async def _rag(self, session: AsyncSession, query: str, language: str) -> RetrievalResult | None:
        hits = await self.pinecone.hybrid_search(session, query, top_k=6)
        if not hits:
            return None
        citations = citations_from_hits(hits)
        context = "\n\n".join(hit.chunk.content[:1500] for hit in hits if hit.chunk)
        answer = await self.llm.generate(query=query, context=context, citations=citations, language=language)
        return RetrievalResult(
            answer=answer,
            route="rag",
            confidence="high",
            score=max(hit.score for hit in hits),
            citations=citations,
        )

    async def _website_search(self, query: str) -> RetrievalResult | None:
        if is_sensitive_stat_question(query):
            return None
        return None
