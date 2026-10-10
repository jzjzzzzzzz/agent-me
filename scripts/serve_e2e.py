#!/usr/bin/env python3
"""Serve only an owned disposable E2E workspace; never load owner environment or provider keys."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import config

FIXTURE_TOKEN = "e2e-fixture-only-token-00000000000000000000"
MARKER = ".agent-me-e2e-fixture"


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

    uvicorn.run(app, host="127.0.0.1", port=0, log_level="info")


if __name__ == "__main__":
    main()
