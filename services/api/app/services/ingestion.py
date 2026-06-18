import csv
import io
from pathlib import Path

import docx
import openpyxl
from pypdf import PdfReader


def extract_text(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if suffix == ".docx":
        document = docx.Document(io.BytesIO(content))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    if suffix in {".xlsx", ".xlsm"}:
        workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        rows: list[str] = []
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(values_only=True):
                rows.append(" | ".join("" if cell is None else str(cell) for cell in row))
        return "\n".join(rows)
    if suffix == ".csv":
        decoded = content.decode("utf-8", errors="ignore")
        return "\n".join(" | ".join(row) for row in csv.reader(io.StringIO(decoded)))
    if suffix in {".txt", ".md"}:
        return content.decode("utf-8", errors="ignore")
    raise ValueError("Unsupported file type")


def chunk_text(text: str, size: int = 1200, overlap: int = 180) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        chunks.append(normalized[start : start + size])
        start += max(1, size - overlap)
    return chunks
