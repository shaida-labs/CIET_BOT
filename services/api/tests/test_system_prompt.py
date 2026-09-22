"""Regression guards for the answer-style rules inside SYSTEM_PROMPT.

The live UI suite verifies this behaviour end-to-end (a real question must
produce a one-fact answer); these tests pin the prompt contract itself so the
directive cannot be dropped silently.
"""

from app.services.llm import SYSTEM_PROMPT


def test_system_prompt_requires_question_only_answers():
    assert "Answer only what the question asks" in SYSTEM_PROMPT
    assert "facts needed to answer it" in SYSTEM_PROMPT
    assert "Never volunteer unasked details" in SYSTEM_PROMPT
    assert "driver or staff names" in SYSTEM_PROMPT
    assert "no preamble, no closing remarks" in SYSTEM_PROMPT
    assert "one short" in SYSTEM_PROMPT and "nothing else" in SYSTEM_PROMPT


def test_system_prompt_keeps_grounding_and_language_guards():
    for marker in (
        "VERIFIED_CONTEXT",
        "CONVERSATION_CONTEXT",
        "REQUESTED_LANGUAGE",
        "Do not add a sources section",
        "Keep the answer direct, helpful, and concise",
    ):
        assert marker in SYSTEM_PROMPT, marker
