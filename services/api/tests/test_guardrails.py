from app.services.guardrails import contains_unsafe_numeric_claim, is_sensitive_stat_question, sanitize_answer


def test_detects_sensitive_stat_questions():
    assert is_sensitive_stat_question("What is the placement percentage?")
    assert is_sensitive_stat_question("Tell me hostel fee structure")


def test_blocks_unverified_numeric_claims():
    assert contains_unsafe_numeric_claim("Placement is 95% this year")
    assert "complete verified data" in sanitize_answer("placement percentage", "95%", verified=False)
