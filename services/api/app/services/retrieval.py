from difflib import SequenceMatcher
from time import perf_counter

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import FAQ, Metric
from app.schemas import Citation, RetrievalResult
from app.services.guardrails import SAFE_STAT_RESPONSES, is_sensitive_stat_question
from app.services.cache import cache_answer, get_cached_answer
from app.services.llm import LLMService, LLMUnavailableError
from app.services.pinecone_service import PineconeService, citations_from_hits, keyword_score, normalize_tokens
from app.services.website_search import OfficialWebsiteSearch


LOCALIZED_FALLBACKS = {
    "en": "I could not find sufficiently relevant, verified CIET information for this question. Please contact the appropriate CIET office for an official answer.",
    "te": "ఈ ప్రశ్నకు తగిన ధృవీకరించిన CIET సమాచారం నాకు దొరకలేదు. అధికారిక సమాధానం కోసం సంబంధిత CIET కార్యాలయాన్ని సంప్రదించండి.",
    "hi": "इस प्रश्न के लिए पर्याप्त प्रासंगिक और सत्यापित CIET जानकारी नहीं मिली। आधिकारिक उत्तर के लिए संबंधित CIET कार्यालय से संपर्क करें।",
}
AI_UNAVAILABLE = {
    "en": "I found relevant verified CIET material, but the answer service is temporarily unavailable. Please try again shortly.",
    "te": "సంబంధిత ధృవీకరించిన CIET సమాచారం దొరికింది, కానీ సమాధాన సేవ తాత్కాలికంగా అందుబాటులో లేదు. దయచేసి కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి.",
    "hi": "प्रासंगिक सत्यापित CIET जानकारी मिली, लेकिन उत्तर सेवा अस्थायी रूप से उपलब्ध नहीं है। कृपया थोड़ी देर बाद फिर प्रयास करें।",
}
UNSAFE_QUERY_TERMS = {"ignore instructions", "system prompt", "reveal secret", "api key", "password", "database credentials"}
FOLLOW_UP_PREFIXES = (
    "what about",
    "how about",
    "and what",
    "what else",
    "tell me more",
    "can you explain",
)


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


def conversation_context(memory: list[tuple[str, str]] | None) -> str:
    """Render bounded history as data, never as a source of institutional facts."""
    if not memory:
        return ""
    return "\n".join(f"{role.title()}: {content}" for role, content in memory)


def contextual_query(query: str, memory: list[tuple[str, str]] | None) -> str:
    """Use the prior user topic only for short, referential follow-up questions."""
    normalized = query.casefold().strip()
    if not memory or not normalized.startswith(FOLLOW_UP_PREFIXES):
        return query
    prior_user_questions = [content for role, content in memory if role == "user"]
    if not prior_user_questions:
        return query
    return prior_user_questions[-1]


class RetrievalService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = LLMService(settings)
        self.pinecone = PineconeService(settings)
        self.website = OfficialWebsiteSearch(settings)

    async def answer(
        self,
        session: AsyncSession,
        query: str,
        language: str,
        *,
        conversation_memory: list[tuple[str, str]] | None = None,
    ) -> tuple[RetrievalResult, int]:
        start = perf_counter()
        # Contextual follow-ups must never reuse another conversation's cached
        # answer. Only standalone queries are safe to share through this cache.
        if self.settings.response_cache_seconds and not conversation_memory:
            cached = await get_cached_answer(self.settings, query, language)
            if cached:
                return cached, int((perf_counter() - start) * 1000)
        # Official statistics must come from the structured metrics store. A
        # free-form FAQ or document must never bypass this verification gate.
        retrieval_query = contextual_query(query, conversation_memory)
        memory_context = conversation_context(conversation_memory)
        sensitive_metric = is_sensitive_stat_question(query)
        result = await self._metric(session, query, language) if sensitive_metric else None
        if not result:
            result = await self._faq(session, retrieval_query, language, memory_context)
        if not result and not sensitive_metric:
            result = await self._metric(session, retrieval_query, language)
        if not result:
            result = await self._rag(session, retrieval_query, language, memory_context, query)
        if not result:
            result = await self._website_search(retrieval_query, language, memory_context, query)
        if not result:
            result = RetrievalResult(
                answer=LOCALIZED_FALLBACKS.get(language, LOCALIZED_FALLBACKS["en"]),
                route="fallback",
                confidence="low",
                score=0,
                citations=[],
            )
        if result.route != "fallback" and self.settings.response_cache_seconds and not conversation_memory:
            await cache_answer(self.settings, query, language, result)
        return result, int((perf_counter() - start) * 1000)

    async def _faq(
        self, session: AsyncSession, query: str, language: str, memory_context: str = ""
    ) -> RetrievalResult | None:
        if is_sensitive_stat_question(query):
            return None
        query_tokens = list(dict.fromkeys(normalize_tokens(query)))[:6]
        token_filter = or_(*(FAQ.question.ilike(f"%{token}%") for token in query_tokens)) if query_tokens else None
        statement = select(FAQ).where(FAQ.is_active.is_(True), or_(FAQ.language == language, FAQ.language == "en"))
        if token_filter is not None:
            statement = statement.where(token_filter)
        faqs = (
            await session.scalars(statement.order_by(FAQ.updated_at.desc()).limit(100))
        ).all()
        if not faqs:
            return None
        def faq_score(faq: FAQ) -> float:
            return max(similarity(query, faq.question), keyword_score(query, faq.question))

        best = max(faqs, key=faq_score)
        score = faq_score(best)
        if score < 0.68:
            return None
        if best.language != language:
            try:
                answer = await self.llm.generate(
                    query=query,
                    context=f"Verified FAQ question: {best.question}\nVerified FAQ answer: {best.answer}",
                    citations=[Citation(title=best.source, section="FAQ Database")],
                    language=language,
                    conversation_context=memory_context,
                )
            except LLMUnavailableError:
                return RetrievalResult(answer=AI_UNAVAILABLE[language], route="fallback", confidence="low", score=0, citations=[])
        else:
            answer = best.answer
        return RetrievalResult(
            answer=answer,
            route="faq",
            confidence="verified" if best.language == language else "high",
            score=score,
            citations=[Citation(title=best.source, section="FAQ Database")],
        )

    async def _metric(self, session: AsyncSession, query: str, language: str) -> RetrievalResult | None:
        query_tokens = list(dict.fromkeys(normalize_tokens(query)))[:6]
        statement = select(Metric)
        if query_tokens:
            statement = statement.where(or_(*(Metric.name.ilike(f"%{token}%") for token in query_tokens)))
        metrics = (await session.scalars(statement.order_by(Metric.updated_at.desc()).limit(100))).all()
        if not metrics:
            if is_sensitive_stat_question(query):
                return RetrievalResult(
                    answer=SAFE_STAT_RESPONSES.get(language, SAFE_STAT_RESPONSES["en"]),
                    route="metric",
                    confidence="low",
                    score=0,
                    citations=[],
                )
            return None
        def metric_score(metric: Metric) -> float:
            return max(similarity(query, metric.name), keyword_score(query, metric.name))

        best = max(metrics, key=metric_score)
        score = metric_score(best)
        if score < 0.5:
            if is_sensitive_stat_question(query):
                return RetrievalResult(
                    answer=SAFE_STAT_RESPONSES.get(language, SAFE_STAT_RESPONSES["en"]),
                    route="metric",
                    confidence="low",
                    score=0,
                    citations=[],
                )
            return None
        value = f"{best.value}{f' {best.unit}' if best.unit else ''}"
        templates = {
            "en": f"According to verified CIET records, {best.name} is {value}.",
            "te": f"ధృవీకరించిన CIET రికార్డుల ప్రకారం, {best.name} {value}.",
            "hi": f"सत्यापित CIET रिकॉर्ड के अनुसार, {best.name} {value} है।",
        }
        return RetrievalResult(
            answer=templates.get(language, templates["en"]),
            route="metric",
            confidence="verified",
            score=score,
            citations=[Citation(title=best.source, section=f"Verified by {best.verified_by}")],
        )

    async def _rag(
        self,
        session: AsyncSession,
        query: str,
        language: str,
        memory_context: str = "",
        original_query: str | None = None,
    ) -> RetrievalResult | None:
        if any(term in query.casefold() for term in UNSAFE_QUERY_TERMS) or not normalize_tokens(query):
            return None
        hits = await self.pinecone.hybrid_search(session, query, top_k=self.settings.rag_top_k * 2)
        if not hits:
            return None
        hits = [hit for hit in hits if hit.score >= self.settings.rag_min_score]
        if not hits:
            return None
        top_score = hits[0].score
        hits = [hit for hit in hits if hit.score >= max(self.settings.rag_min_score, top_score - 0.18)][
            : self.settings.rag_top_k
        ]
        citations = citations_from_hits(hits)
        context = "\n\n".join(hit.chunk.content[:1500] for hit in hits if hit.chunk)
        try:
            answer = await self.llm.generate(
                query=original_query or query,
                context=context,
                citations=citations,
                language=language,
                conversation_context=memory_context,
            )
        except LLMUnavailableError:
            return RetrievalResult(
                answer=AI_UNAVAILABLE.get(language, AI_UNAVAILABLE["en"]),
                route="fallback",
                confidence="low",
                score=0,
                citations=[],
            )
        confidence = "high" if top_score >= self.settings.rag_high_confidence_score else "medium"
        return RetrievalResult(
            answer=answer,
            route="rag",
            confidence=confidence,
            score=top_score,
            citations=citations,
        )

    async def _website_search(
        self,
        query: str,
        language: str,
        memory_context: str = "",
        original_query: str | None = None,
    ) -> RetrievalResult | None:
        if is_sensitive_stat_question(query):
            return None
        hits = await self.website.search(query)
        if not hits:
            return None
        citations = [Citation(title=hit.title, url=hit.url, section="Official CIET website") for hit in hits]
        context = "\n\n".join(
            f"Official page: {hit.title}\nURL: {hit.url}\n{hit.text[:2500]}"
            for hit in hits
        )
        try:
            answer = await self.llm.generate(
                query=original_query or query,
                context=context,
                citations=citations,
                language=language,
                conversation_context=memory_context,
            )
        except LLMUnavailableError:
            return RetrievalResult(
                answer=AI_UNAVAILABLE.get(language, AI_UNAVAILABLE["en"]),
                route="fallback",
                confidence="low",
                score=0,
                citations=[],
            )
        return RetrievalResult(
            answer=answer,
            route="website",
            confidence="medium",
            score=0.6,
            citations=citations,
        )
