import hashlib
import mimetypes
import socket
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Document

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md"}
ALLOWED_MIME_PREFIXES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "text/plain",
    "text/markdown",
    "application/octet-stream",
}
EICAR_FRAGMENT = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR"


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def validate_upload(
    file: UploadFile,
    content: bytes,
    session: AsyncSession,
    settings: Settings,
) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file extension")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size")
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    if content_type not in ALLOWED_MIME_PREFIXES:
        raise HTTPException(status_code=415, detail="Unsupported MIME type")
    checksum = sha256(content)
    existing = await session.scalar(select(Document).where(Document.checksum == checksum))
    if existing:
        raise HTTPException(status_code=409, detail="Duplicate document already exists")
    scan_content(content, settings)
    return checksum


def scan_content(content: bytes, settings: Settings) -> None:
    if EICAR_FRAGMENT in content:
        raise HTTPException(status_code=422, detail="Virus scan failed")
    if not settings.clamav_host:
        return
    with socket.create_connection((settings.clamav_host, settings.clamav_port), timeout=8) as sock:
        sock.sendall(b"zINSTREAM\0")
        for offset in range(0, len(content), 1024 * 512):
            chunk = content[offset : offset + 1024 * 512]
            sock.sendall(len(chunk).to_bytes(4, "big") + chunk)
        sock.sendall((0).to_bytes(4, "big"))
        result = sock.recv(4096)
    if b"OK" not in result:
        raise HTTPException(status_code=422, detail="Virus scan failed")
