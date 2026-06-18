def detect_language(text: str) -> str:
    for char in text:
        code = ord(char)
        if 0x0C00 <= code <= 0x0C7F:
            return "te"
        if 0x0900 <= code <= 0x097F:
            return "hi"
    return "en"
