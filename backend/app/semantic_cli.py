"""Explicit-file configuration for the opt-in CLI adapter; never read ambient settings."""

import asyncio
import hashlib
import json
import os
import stat
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from .config import Settings
from .learning import MAX_DOCUMENT_BYTES
from .memory import MemoryInputError, MemoryPermissionDenied
from .memory_models import IngestionInput, valid_unicode
from .provider import ProviderError
from .semantic_learning import INSTRUCTIONS, _unique_pairs, ingest_semantic, review_semantic
from .semantic_models import SemanticIngestion

MAX_CONFIG_BYTES = 65_536


class ExplicitProvider(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    llm_base_url: str = Field(min_length=1, max_length=4096)
    llm_model: str = Field(min_length=1, max_length=200)
    llm_api_key: SecretStr
    max_context_chars: int = Field(default=12_000, ge=1, le=100_000)
    max_answer_chars: int = Field(default=50_000, ge=1, le=200_000)
    max_provider_response_bytes: int = Field(default=2_000_000, ge=1024, le=50_000_000)
    provider_timeout_seconds: float = Field(default=60, ge=1, le=300)

    @field_validator("llm_base_url")
    @classmethod
    def endpoint(cls, value):
        if any(ord(char) < 33 or ord(char) > 126 for char in value):
            raise ValueError("Endpoint must be an explicit ASCII HTTP(S) URL")
        url = urlsplit(value)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or url.port == 0
        ):
            raise ValueError("Endpoint must not contain credentials, a query or a fragment")
        try:
            httpx.URL(value)
        except httpx.InvalidURL:
            raise ValueError("Endpoint must be a valid HTTP(S) URL") from None
        return value

    @field_validator("llm_model")
    @classmethod
    def model_name(cls, value):
        valid_unicode(value)
        if value != value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("Model must have explicit nonblank trimmed boundaries")
        return value

    @field_validator("llm_api_key")
    @classmethod
    def credential(cls, value):
        key = value.get_secret_value()
        if not 1 <= len(key) <= 4096 or any(not 33 <= ord(char) <= 126 for char in key):
            raise ValueError("Credential must be a bounded printable ASCII token")
        return value

    def settings(self):
        # All supplied values above have been validated. Constructing Settings
        # directly with its validated defaults bypasses ALL BaseSettings sources,
        # not just dotenv (which would still permit ambient environment overrides).
        values = self.model_dump(exclude={"llm_api_key"})
        return Settings.model_construct(**values, llm_api_key=self.llm_api_key.get_secret_value())


def _read_regular(path: Path, limit: int, label: str):
    try:
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise MemoryInputError(f"{label} must be a regular file")
            data = handle.read(limit + 1)
    except OSError:
        raise MemoryInputError(f"Cannot read {label}") from None
    if len(data) > limit:
        raise MemoryInputError(f"{label} exceeds its byte limit")
    return data


def load_provider(path: Path):
    data = _read_regular(path, MAX_CONFIG_BYTES, "Explicit provider configuration")
    try:
        raw = json.loads(data, object_pairs_hook=_unique_pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise MemoryInputError(
            "Explicit provider configuration must be valid unique-field JSON"
        ) from None
    return ExplicitProvider.model_validate(raw).settings()


def source_content(path: Path):
    data = _read_regular(path, MAX_DOCUMENT_BYTES, "Semantic source")
    try:
        content = data.decode("utf-8")
    except UnicodeError:
        raise MemoryInputError("Semantic source must be valid UTF-8") from None
    return IngestionInput(content=content, mode="notes").content


def execute_semantic(store, args):
    if args.action == "ingest" and not args.allow_provider:
        raise MemoryPermissionDenied("Semantic ingestion requires explicit --allow-provider")
    config = load_provider(args.provider_config)
    content = source_content(args.file)
    if args.action == "review":
        return {
            **review_semantic(store, args.source_id, config),
            "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "source_chars": len(content),
            "source_bytes": len(content.encode("utf-8")),
            "source_fits_budget": len(content)
            <= max(0, config.max_context_chars - len(INSTRUCTIONS)),
        }
    payload = SemanticIngestion(
        content=content,
        expected_source_revision=args.expected_source_revision,
        expected_disclosure_revision=args.expected_disclosure_revision,
        reviewed_target_id=args.reviewed_target_id,
        reviewed_content_hash=args.reviewed_content_hash,
        allow_provider=args.allow_provider,
        allow_sensitive=args.allow_sensitive,
        **{field: getattr(args, field) for field in ("valid_from", "valid_until", "occurred_at")},
    )
    try:
        return asyncio.run(ingest_semantic(store, args.source_id, payload, config))
    except ProviderError as error:
        raise MemoryInputError(error.code) from None
