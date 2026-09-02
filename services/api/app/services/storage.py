import asyncio
from pathlib import Path

import boto3

from app.core.config import Settings


class StorageService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None
        if settings.r2_endpoint_url and settings.r2_access_key_id and settings.r2_secret_access_key:
            self.client = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.r2_access_key_id,
                aws_secret_access_key=settings.r2_secret_access_key,
            )

    async def put(self, key: str, content: bytes, content_type: str) -> str:
        if not self.client:
            local_dir = Path(self.settings.local_storage_path)
            local_dir.mkdir(parents=True, exist_ok=True)
            local_path = local_dir / Path(key).name
            local_path.write_bytes(content)
            return f"local://{local_path.name}"
        await asyncio.to_thread(
            self.client.put_object,
            Bucket=self.settings.r2_bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return f"r2://{self.settings.r2_bucket}/{key}"

    async def get(self, path: str) -> bytes:
        if path.startswith("local://"):
            filename = path.removeprefix("local://")
            if not filename or filename != Path(filename).name:
                raise ValueError("Invalid local storage path")
            local_path = Path(self.settings.local_storage_path) / filename
            return local_path.read_bytes()
        if path.startswith("r2://"):
            parts = path.replace("r2://", "").split("/", 1)
            bucket = parts[0]
            key = parts[1]
            if not self.client:
                raise ValueError("R2 storage client is not configured but r2 path requested")
            response = await asyncio.to_thread(self.client.get_object, Bucket=bucket, Key=key)
            return await asyncio.to_thread(response["Body"].read)
        raise ValueError("Invalid storage path scheme")

    async def delete(self, path: str) -> None:
        if path.startswith("local://"):
            filename = Path(path.removeprefix("local://")).name
            (Path(self.settings.local_storage_path) / filename).unlink(missing_ok=True)
            return
        if path.startswith("r2://"):
            bucket, key = path.removeprefix("r2://").split("/", 1)
            if not self.client:
                raise ValueError("R2 storage client is not configured but r2 path requested")
            await asyncio.to_thread(self.client.delete_object, Bucket=bucket, Key=key)
            return
        raise ValueError("Invalid storage path scheme")
