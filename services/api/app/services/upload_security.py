import hashlib
import io
import mimetypes
import socket
import zipfile
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Document

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md"}
ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    ".xlsx": {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    },
    ".csv": {"text/csv", "text/plain", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
}
EICAR_FRAGMENT = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR"
MAX_ARCHIVE_MEMBERS = 2_000
MAX_ARCHIVE_EXPANSION_RATIO = 100


def sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_filename(filename: str | None) -> str:
    if not filename:
        raise HTTPException(status_code=422, detail="A filename is required")
    if len(filename) > 255 or filename != Path(filename).name or any(ord(char) < 32 for char in filename):
        raise HTTPException(status_code=422, detail="Invalid filename")
    return filename


async def read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read no more than the configured limit plus one sentinel byte."""
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size")
    return content


def validate_file_signature(suffix: str, content: bytes, max_upload_bytes: int) -> None:
    if suffix == ".pdf":
        if not content[:1024].lstrip().startswith(b"%PDF-"):
            raise HTTPException(status_code=415, detail="File content does not match its extension")
        return
    if suffix in {".docx", ".xlsx"}:
        _validate_office_archive(suffix, content, max_upload_bytes)
        return
    if b"\x00" in content:
        raise HTTPException(status_code=415, detail="Text uploads cannot contain binary data")
    try:
        content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=415, detail="Text uploads must use UTF-8 encoding") from exc


def _validate_office_archive(suffix: str, content: bytes, max_upload_bytes: int) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise HTTPException(status_code=422, detail="Office archive contains too many files")
            total_size = sum(member.file_size for member in members)
            compressed_size = max(1, sum(member.compress_size for member in members))
            if (
                total_size > max_upload_bytes * 4
                or total_size / compressed_size > MAX_ARCHIVE_EXPANSION_RATIO
                or any(member.flag_bits & 0x1 for member in members)
            ):
                raise HTTPException(status_code=422, detail="Unsafe Office archive")
            names = {member.filename for member in members}
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=415, detail="Invalid Office document") from exc
    required = "word/document.xml" if suffix == ".docx" else "xl/workbook.xml"
    if "[Content_Types].xml" not in names or required not in names:
        raise HTTPException(status_code=415, detail="File content does not match its extension")


async def validate_upload(
    file: UploadFile,
    content: bytes,
    session: AsyncSession,
    settings: Settings,
) -> str:
    filename = validate_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file extension")
    if not content:
        raise HTTPException(status_code=422, detail="File is empty")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size")
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    if content_type not in ALLOWED_MIME_TYPES[suffix]:
        raise HTTPException(status_code=415, detail="Unsupported MIME type")
    validate_file_signature(suffix, content, settings.max_upload_bytes)
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
