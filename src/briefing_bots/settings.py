from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    openai_model: str
    digest_discord_token: str
    qa_discord_token: str
    discord_guild_id: int
    database_path: Path
    config_path: Path
    timezone: str


@dataclass(frozen=True)
class DigestSettings:
    openai_api_key: str
    openai_model: str
    digest_discord_token: str
    database_path: Path
    config_path: Path
    timezone: str


@dataclass(frozen=True)
class QaSettings:
    openai_api_key: str
    openai_model: str
    qa_discord_token: str
    discord_guild_id: int
    database_path: Path
    config_path: Path
    timezone: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        openai_api_key=_required("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        digest_discord_token=_required("DIGEST_DISCORD_TOKEN"),
        qa_discord_token=_required("QA_DISCORD_TOKEN"),
        discord_guild_id=int(_required("DISCORD_GUILD_ID")),
        database_path=Path(os.getenv("DATABASE_PATH", "data/knowledge.sqlite3")),
        config_path=Path(os.getenv("CONFIG_PATH", "config/sources.yml")),
        timezone=os.getenv("TIMEZONE", "Asia/Tokyo"),
    )


def load_digest_settings() -> DigestSettings:
    load_dotenv()
    return DigestSettings(
        openai_api_key=_required("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        digest_discord_token=_required("DIGEST_DISCORD_TOKEN"),
        database_path=Path(os.getenv("DATABASE_PATH", "data/knowledge.sqlite3")),
        config_path=Path(os.getenv("CONFIG_PATH", "config/sources.yml")),
        timezone=os.getenv("TIMEZONE", "Asia/Tokyo"),
    )


def load_qa_settings() -> QaSettings:
    load_dotenv()
    return QaSettings(
        openai_api_key=_required("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        qa_discord_token=_required("QA_DISCORD_TOKEN"),
        discord_guild_id=int(_required("DISCORD_GUILD_ID")),
        database_path=Path(os.getenv("DATABASE_PATH", "data/knowledge.sqlite3")),
        config_path=Path(os.getenv("CONFIG_PATH", "config/sources.yml")),
        timezone=os.getenv("TIMEZONE", "Asia/Tokyo"),
    )


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
