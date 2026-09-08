#!/usr/bin/env python3
"""Create an ignored local workspace without altering public configuration."""

import json
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    private = ROOT / "private"
    private.mkdir(mode=0o700, exist_ok=True)
    created = []

    knowledge = private / "knowledge"
    if not knowledge.exists():
        knowledge.mkdir(mode=0o700)
        created.append("private/knowledge/")
    env = private / "personal.env"
    if not env.exists():
        token = secrets.token_urlsafe(32)
        env.write_text(
            "PERSONAL_ENABLED=true\n"
            f"PERSONAL_DATA_DIR={json.dumps(str(private))}\n"
            f"PERSONAL_TOKEN={token}\n",
            encoding="utf-8",
        )
        env.chmod(0o600)
        created.append("private/personal.env")

    profile = private / "profile-template.json"
    if not profile.exists():
        profile.write_text(
            json.dumps(
                {
                    "kind": "fact",
                    "key": "identity.name",
                    "content": "Replace with your name",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        created.append("private/profile-template.json")

    if created:
        print("Created:")
        for path in created:
            print(f"- {path}")
        print(
            "Read PERSONAL_TOKEN in private/personal.env to unlock the browser workspace."
        )
        print(
            "Run: .venv/bin/uvicorn app.main:app --app-dir backend --env-file private/personal.env "
            "--host 127.0.0.1 --port 8000"
        )
    else:
        print("Workspace already exists; no files changed.")


if __name__ == "__main__":
    main()
