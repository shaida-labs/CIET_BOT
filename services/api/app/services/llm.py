from openai import AsyncOpenAI

from app.core.config import Settings
from app.schemas import Citation
from app.services.guardrails import sanitize_answer


SYSTEM_PROMPT = """You are CIET AI Assistant.
Answer only from provided context. Never invent fees, placement percentages, packages,
student counts, faculty names, statistics, or official information.
If context is insufficient, clearly say verified information was not found.
Keep answers helpful, warm, concise, and cite the supplied sources."""


class LLMService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    async def generate(self, query: str, context: str, citations: list[Citation], language: str) -> str:
        if not self.client:
            return sanitize_answer(
                query,
                "I found relevant CIET source material, but AI generation is not configured. "
                "Please configure OPENAI_API_KEY to enable generated answers.",
                verified=False,
            )

        response = await self.client.responses.create(
            model=self.settings.openai_model,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Language: {language}\n"
                        f"Question: {query}\n"
                        f"Context:\n{context}\n"
                        f"Sources: {[c.model_dump() for c in citations]}"
                    ),
                },
            ],
        )
        return sanitize_answer(query, response.output_text, verified=False)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not self.client:
            return []
        response = await self.client.embeddings.create(
            model=self.settings.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]
