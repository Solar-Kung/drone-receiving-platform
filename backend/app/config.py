from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change-me-in-production"

    # Database (TimescaleDB)
    database_url: str = "postgresql+asyncpg://drone_admin:drone_secret@timescaledb:5432/drone_station"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_root_user: str = "minio_admin"
    minio_root_password: str = "minio_secret"
    minio_bucket_images: str = "inspection-images"
    minio_bucket_logs: str = "flight-logs"
    minio_use_ssl: bool = False

    # ROS 2
    ros_domain_id: int = 0

    # CORS
    cors_origins: List[str] = ["http://localhost:3000"]

    model_config = {"env_file": "/app/../configs/.env", "extra": "ignore"}


settings = Settings()
