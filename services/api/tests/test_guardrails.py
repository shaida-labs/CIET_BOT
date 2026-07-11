from app.services.guardrails import contains_unsafe_numeric_claim, is_sensitive_stat_question, sanitize_answer


def test_detects_sensitive_stat_questions():
    assert is_sensitive_stat_question("What is the placement percentage?")
    assert is_sensitive_stat_question("Tell me hostel fee structure")
    assert is_sensitive_stat_question("ఫీజు ఎంత?")  # Telugu "How much is the fee?"
    assert is_sensitive_stat_question("प्लेसमेंट प्रतिशत क्या है?")  # Hindi "What is placement percentage?"


def test_blocks_unverified_numeric_claims():
    assert contains_unsafe_numeric_claim("Placement is 95% this year")
    assert contains_unsafe_numeric_claim("ప్లేస్‌మెంట్ ప్యాకేజీ 12 LPA")  # Telugu "Placement package 12 LPA"
    assert contains_unsafe_numeric_claim("फीस ₹50,000 प्रति वर्ष है")  # Hindi "Fee is ₹50,000 per year"
    assert "complete verified data" in sanitize_answer("placement percentage", "95%", verified=False, language="en")
    assert "ధృవీకరించబడిన సమాచారం" in sanitize_answer("ప్లేస్‌మెంట్ శాతం ఎంత?", "95%", verified=False, language="te")
    assert "सत्यापित डेटा" in sanitize_answer("प्लेसमेंट प्रतिशत क्या है?", "95%", verified=False, language="hi")
