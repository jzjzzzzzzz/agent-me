#!/usr/bin/env python3
"""Serve only an owned disposable E2E workspace; never load owner environment or provider keys."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config

FIXTURE_TOKEN = "e2e-fixture-only-token-00000000000000000000"
MARKER = ".agent-me-e2e-fixture"


class FixtureModelControl(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = Field(strict=True)


def fixture_settings(workspace: Path, nonce: str) -> config.Settings:
    """Reject existing/private paths even if someone runs the helper directly."""
    if str(UUID(nonce)) != nonce:
        raise ValueError("Invalid fixture nonce")
    if workspace.is_symlink():
        raise ValueError("Fixture workspace cannot be a symlink")
    root = workspace.resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith(
        "agent-me-e2e-"
    ):
        raise ValueError(
            "Fixture workspace must be a freshly owned temporary directory"
        )
    marker = root / MARKER
    if marker.is_symlink() or marker.read_text(encoding="utf-8") != nonce:
        raise ValueError("Fixture workspace marker does not match")
    private = root / "private"
    if private.exists() or private.is_symlink() or private.resolve() != private:
        raise ValueError("Fixture private data directory must not already exist")
    public = root / "public"
    if public.is_symlink() or public.resolve() != public:
        raise ValueError("Fixture knowledge directory cannot be a symlink")
    return config.Settings(
        _env_file=None,
        app_name="Agent-Me E2E fixture",
        app_description="Disposable fictional owner-review acceptance workspace",
        personal_enabled=True,
        personal_token=FIXTURE_TOKEN,
        personal_data_dir=str(root / "private"),
        knowledge_dir=str(root / "public"),
        llm_base_url="",
        llm_api_key="",
        llm_model="",
        cors_origins="",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--model-url", type=fixture_model_url, required=True)
    args = parser.parse_args()
    # Strip every current Settings field, case-insensitively. Do not read .env.
    fields = set(config.Settings.model_fields)
    for name in list(os.environ):
        if name.casefold() in fields:
            del os.environ[name]
    settings = fixture_settings(args.workspace, args.nonce)
    config.get_settings.cache_clear()
    config.get_settings = lambda: settings
    # Import after installing fixture configuration so middleware and Depends
    # use the same isolated settings, rather than merely overriding HTTP routes.
    import uvicorn
    from app.main import app
    from fastapi import Header, HTTPException

    @app.post("/__e2e/model")
    def fixture_model(
        payload: FixtureModelControl, authorization: str = Header(default="")
    ):
        if authorization != f"Bearer {FIXTURE_TOKEN}":
            raise HTTPException(401, "Fixture token required")
        # This route exists only in this guarded disposable interpreter. No
        # caller can provide a URL, credentials or another workspace.
        settings.llm_base_url = args.model_url if payload.enabled else ""
        settings.llm_model = "literal-fixture-model" if payload.enabled else ""
        settings.llm_api_key = "fixture-model-key" if payload.enabled else ""
        return {"configured": payload.enabled}

    uvicorn.run(app, host="127.0.0.1", port=0, log_level="info")


def fixture_model_url(value: str):
    url = urlsplit(value)
    if (
        url.scheme != "http"
        or url.hostname != "127.0.0.1"
        or url.port is None
        or not 1024 <= url.port <= 65535
        or url.path != "/__mock_semantic"
        or url.query
        or url.fragment
        or url.username
        or url.password
    ):
        raise ValueError("Fixture model must be the owned loopback mock endpoint")
    return value


if __name__ == "__main__":
    main()
