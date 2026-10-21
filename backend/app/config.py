"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache
from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Axio system configuration settings."""

    app_name: str = Field("Axio", validation_alias=AliasChoices("axio_app_name", "app_name"))
    environment: str = Field("development", validation_alias=AliasChoices("axio_env", "environment", "env"))
    host: str = Field("127.0.0.1", validation_alias=AliasChoices("axio_host", "host"))
    port: int = Field(8000, validation_alias=AliasChoices("axio_port", "port"))
    log_level: str = Field("INFO", validation_alias=AliasChoices("log_level", "axio_log_level"))

    # Persistence
    database_url: str = Field("sqlite:///./axio.db", validation_alias=AliasChoices("database_url", "axio_database_url"))

    # MCP Server
    mcp_server_name: str = Field("axio", validation_alias=AliasChoices("mcp_server_name", "axio_mcp_server_name"))
    mcp_server_version: str = Field("0.1.0", validation_alias=AliasChoices("mcp_server_version", "axio_mcp_server_version"))
    mcp_mount_path: str = Field("/mcp", validation_alias=AliasChoices("mcp_mount_path", "axio_mcp_mount_path"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
