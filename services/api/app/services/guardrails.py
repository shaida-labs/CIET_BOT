import re

SENSITIVE_PATTERNS = [
    r"\bplacement\s*percentage\b",
    r"\bfee\s*(structure|amount|details)?\b",
    r"\bhighest\s*package\b",
    r"\baverage\s*package\b",
    r"\bstudent\s*(count|strength|number)\b",
    r"\bfaculty\s*(name|list|count)\b",
    r"\bnaac\s*grade\b",
]

SAFE_STAT_RESPONSE = (
    "I found related CIET records, but I do not have the complete verified data required "
    "to answer this official statistic accurately. Please contact the relevant CIET office "
    "for the latest verified figure."
)


def is_sensitive_stat_question(query: str) -> bool:
    text = query.lower()
    return any(re.search(pattern, text) for pattern in SENSITIVE_PATTERNS)


def contains_unsafe_numeric_claim(answer: str) -> bool:
    lowered = answer.lower()
    if not any(term in lowered for term in ["placement", "fee", "package", "student", "faculty"]):
        return False
    return bool(re.search(r"(\d+(\.\d+)?\s*%|\u20b9|rs\.?|lpa|lakhs?|crores?)", lowered))


def sanitize_answer(query: str, answer: str, verified: bool) -> str:
    if verified:
        return answer
    if is_sensitive_stat_question(query) or contains_unsafe_numeric_claim(answer):
        return SAFE_STAT_RESPONSE
    return answer
