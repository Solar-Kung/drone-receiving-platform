from miniopy_async import Minio

from app.config import settings

minio_client = Minio(
    endpoint=settings.minio_endpoint,
    access_key=settings.minio_root_user,
    secret_key=settings.minio_root_password,
    secure=settings.minio_use_ssl,
)


async def ensure_buckets():
    for bucket in [settings.minio_bucket_images, settings.minio_bucket_logs]:
        exists = await minio_client.bucket_exists(bucket)
        if not exists:
            await minio_client.make_bucket(bucket)


async def upload_file(file_data: bytes, object_key: str, content_type: str = "application/octet-stream"):
    from io import BytesIO

    data = BytesIO(file_data)
    await minio_client.put_object(
        bucket_name=settings.minio_bucket_images,
        object_name=object_key,
        data=data,
        length=len(file_data),
        content_type=content_type,
    )


async def get_presigned_url(object_key: str, expires_hours: int = 1) -> str:
    from datetime import timedelta

    return await minio_client.presigned_get_object(
        bucket_name=settings.minio_bucket_images,
        object_name=object_key,
        expires=timedelta(hours=expires_hours),
    )
