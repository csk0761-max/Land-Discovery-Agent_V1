import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    cors_allowed_origins: List[str]
    api_token: str
    admin_token: str


def get_settings() -> Settings:
    cors_origins = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
    )
    return Settings(
        cors_allowed_origins=_split_csv(cors_origins),
        api_token=os.getenv("AUXILIUM_API_TOKEN", ""),
        admin_token=os.getenv("AUXILIUM_ADMIN_TOKEN", ""),
    )
