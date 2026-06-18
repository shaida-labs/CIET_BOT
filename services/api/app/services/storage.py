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
            return f"local://{key}"
        self.client.put_object(
            Bucket=self.settings.r2_bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
        )
        return f"r2://{self.settings.r2_bucket}/{key}"
