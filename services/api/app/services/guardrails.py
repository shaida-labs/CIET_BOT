import re

SENSITIVE_PATTERNS = [
    # English
    r"\bplacement\s*percentage\b",
    r"\bfee\s*(structure|amount|details)?\b",
    r"\bhighest\s*package\b",
    r"\baverage\s*package\b",
    r"\bstudent\s*(count|strength|number)\b",
    r"\bfaculty\s*(name|list|count)\b",
    r"\bnaac\s*grade\b",
    # Telugu
    r"ప్లేస్‌మెంట్|ప్లేస్మెంట్|ఉద్యోగ",
    r"ఫీజు|ఫీజులు|రుసుము|రుసుములు",
    r"ప్యాకేజీ|ప్యాకేజ్|జీతం",
    r"విద్యార్థి|విద్యార్థులు|స్టూడెంట్",
    r"అధ్యాపకులు|ఫ్యాకల్టీ|టీచర్స్",
    r"నాక్|naac",
    # Hindi
    r"प्लेसमेंट|नौकरी",
    r"फीस|शुल्क",
    r"पैकेज|वेतन",
    r"छात्र|स्टूडेंट्स",
    r"संकाय|शिक्षक|फैकल्टी",
    r"नैक|naac"
]

SAFE_STAT_RESPONSE = (
    "I found related CIET records, but I do not have the complete verified data required "
    "to answer this official statistic accurately. Please contact the relevant CIET office "
    "for the latest verified figure."
)

SAFE_STAT_RESPONSES = {
    "en": SAFE_STAT_RESPONSE,
    "te": (
        "నేను సంబంధిత CIET రికార్డులను కనుగొన్నాను, కానీ ఈ అధికారిక గణాంకాన్ని ఖచ్చితంగా సమాధానం ఇవ్వడానికి "
        "అవసరమైన పూర్తి ధృవీకరించబడిన సమాచారం నా దగ్గర లేదు. దయచేసి తాజా ధృవీకరించబడిన వివరాల కోసం "
        "సంబంధిత CIET కార్యాలయాన్ని సంప్రదించండి."
    ),
    "hi": (
        "मुझे प्रासंगिक सीआईईटी (CIET) रिकॉर्ड मिले हैं, लेकिन इस आधिकारिक आंकड़े का सटीक उत्तर देने के लिए "
        "मेरे पास पूरा सत्यापित डेटा नहीं है। कृपया नवीनतम सत्यापित आंकड़े के लिए संबंधित सीआईईटी कार्यालय से संपर्क करें।"
    )
}


def is_sensitive_stat_question(query: str) -> bool:
    text = query.lower()
    return any(re.search(pattern, text) for pattern in SENSITIVE_PATTERNS)


def contains_unsafe_numeric_claim(answer: str) -> bool:
    lowered = answer.lower()
    keywords = [
        "placement", "fee", "package", "student", "faculty",
        "ప్లేస్‌మెంట్", "ప్లేస్మెంట్", "ఉద్యోగ", "ఫీజు", "ప్యాకేజీ", "ప్యాకేజ్", "జీతం", "విద్యార్థి", "విద్యార్థులు", "అధ్యాపకులు", "ఫ్యాకల్టీ",
        "प्लेसमेंट", "नौकरी", "फीस", "शुल्क", "पैकेज", "वेतन", "छात्र", "संकाय", "शिक्षक", "फैकल्टी"
    ]
    if not any(term in lowered for term in keywords):
        return False
    return bool(re.search(r"(\d+(\.\d+)?\s*%|\u20b9|rs\.?|lpa|lakhs?|crores?|percent|प्रतिशत|శాతం|రూ|రూపాయలు|रू|रुपये)", lowered))


def sanitize_answer(query: str, answer: str, verified: bool, language: str = "en") -> str:
    if verified:
        return answer
    if is_sensitive_stat_question(query) or contains_unsafe_numeric_claim(answer):
        return SAFE_STAT_RESPONSES.get(language, SAFE_STAT_RESPONSES["en"])
    return answer
