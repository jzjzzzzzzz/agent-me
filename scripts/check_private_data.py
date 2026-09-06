#!/usr/bin/env python3
"""Reject known private paths and credential patterns in Git's index, not working files."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import PurePosixPath

SECRET = re.compile(
    rb"(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


def private_path(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        "private" in path.parts
        or path.name == "private-twin-export.json"
        or (path.name.startswith(".env") and path.name != ".env.example")
        or re.search(r"\.(?:db|sqlite\d*)(?:[-.].*)?$", path.name) is not None
    )


def main() -> int:
    names = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    failures = []
    for name in filter(None, names):
        if private_path(name):
            failures.append(name)
            continue
        body = subprocess.check_output(["git", "show", f":{name}"])
        if SECRET.search(body):
            failures.append(name)
    if failures:
        print("Private data check failed (paths only; values redacted):")
        print("\n".join(failures))
        return 1
    print(
        "Private data check passed. Manually review content for personal information too."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
