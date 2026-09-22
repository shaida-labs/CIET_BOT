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


SCRIPT_RANGES = {"te": (0x0C00, 0x0C7F), "hi": (0x0900, 0x097F)}


def _in_script(text: str, language: str) -> bool:
    bounds = SCRIPT_RANGES.get(language)
    if not bounds:
        return False
    low, high = bounds
    return any(low <= ord(char) <= high for char in text)


def needs_translation(text: str, target: str) -> bool:
    """Whether a stored chat line should be translated into ``target``.

    Script-neutral content (numbers, punctuation) and text already rendered
    in the target script are kept as-is so a language switch never spends a
    model call on text that is already correct.
    """
    if not any(char.isalpha() for char in text):
        return False
    if target == "en":
        return detect_language(text) != "en"
    return not _in_script(text, target)


_TRANSLATION_DELIMITERS = ("<text>", "</text>", "<text/>")
_TEXT_LABEL_LINE = "TEXT:"


def strip_translation_delimiters(text: str) -> str:
    """Remove wrapper markup a translation model occasionally echoes back.

    The provider prompt brackets the input in ``<text>`` tags; a model that
    copies them into the reply would put raw markup on screen, so the
    delimiters and their label lines are dropped before verification.
    """
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in _TRANSLATION_DELIMITERS or stripped == _TEXT_LABEL_LINE:
            continue
        if stripped.startswith("TARGET_LANGUAGE:"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    for token in _TRANSLATION_DELIMITERS:
        cleaned = cleaned.replace(token, "")
    return cleaned.strip()


def translation_accepted(original: str, translated: str, target: str) -> bool:
    """Verify a candidate translation actually landed in the target language.

    Fail-closed: a candidate that comes back in the wrong script, still
    carrying prompt delimiters, or empty is rejected so the caller keeps the
    original text instead of claiming a translation that never happened.
    """
    if not translated.strip():
        return False
    if any(token in translated for token in _TRANSLATION_DELIMITERS):
        return False
    if not any(char.isalpha() for char in original):
        return True
    if target == "en":
        return not _in_script(translated, "te") and not _in_script(translated, "hi")
    return _in_script(translated, target)
