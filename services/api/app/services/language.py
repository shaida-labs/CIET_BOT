import re


ROMAN_TELUGU = {
    "enti", "entha", "ela", "yela", "emiti", "unda", "undaa", "undi", "unnaya", "unnayi", "unnai", "cheppu",
    "cheppandi", "chepandi", "gurinchi", "ekkada", "eppudu", "kavali", "avutundi", "avutayi", "chadavali",
}
ROMAN_HINDI = {
    "kya", "kaise", "kab", "kahan", "kitna", "kitni", "hain", "hai", "batao",
    "bataye", "bataiye", "mujhe", "chahiye", "kaunse", "kaunsi", "mein", "honge", "hoga",
}


def detect_language(text: str, preferred: str = "en") -> str:
    for char in text:
        code = ord(char)
        if 0x0C00 <= code <= 0x0C7F:
            return "te"
        if 0x0900 <= code <= 0x097F:
            return "hi"
    words = set(re.findall(r"[a-z]+", text.lower()))
    te_score = len(words & ROMAN_TELUGU)
    hi_score = len(words & ROMAN_HINDI)
    if te_score >= 2 and te_score > hi_score:
        return "te"
    if hi_score >= 2 and hi_score > te_score:
        return "hi"
    return preferred if preferred in {"en", "te", "hi"} else "en"
