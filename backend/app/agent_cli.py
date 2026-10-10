"""Owner-operated local CLI. It never starts an HTTP server or calls a model provider."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from .learning import MAX_DOCUMENT_BYTES, LearningPipeline
from .memory import MemoryError, MemoryInputError, MemoryNotFound, Store
from .memory_models import Entry, IngestionInput, SourceInput


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="agent-me", description=__doc__)
    root.add_argument("--data-dir", default="private", help="Owner's local workspace directory")
    commands = root.add_subparsers(dest="command", required=True)
    memory = commands.add_parser("memory").add_subparsers(dest="action", required=True)
    listing = memory.add_parser("list")
    listing.add_argument("--include-superseded", action="store_true")
    for action in ("show", "history", "origins", "delete", "restore", "confirm", "edit"):
        child = memory.add_parser(action)
        child.add_argument("id")
        if action in ("restore", "confirm", "edit"):
            child.add_argument("--expected-revision", type=int, required=action == "confirm")
        if action == "delete":
            child.add_argument(
                "--yes", action="store_true", help="Purge this record and its versions"
            )
        if action == "restore":
            child.add_argument("--revision", type=int, required=True)
        if action == "confirm":
            child.add_argument("--replace", action="append", default=[])
            child.add_argument("--replace-revision", action="append", default=[], metavar="ID:REV")
        if action == "edit":
            child.add_argument("--kind", choices=("fact", "preference", "event", "decision"))
            child.add_argument("--key")
            child.add_argument("--content", required=True)
            child.add_argument("--sensitivity", choices=("public", "private", "sensitive"))
    add = memory.add_parser("add")
    add.add_argument("--kind", default="fact", choices=("fact", "preference", "event", "decision"))
    add.add_argument("--key", required=True)
    add.add_argument("--content", required=True)
    add.add_argument("--sensitivity", default="private", choices=("public", "private", "sensitive"))

    sources = commands.add_parser("source").add_subparsers(dest="action", required=True)
    sources.add_parser("list")
    register = sources.add_parser("register")
    register.add_argument("--name", required=True)
    register.add_argument(
        "--kind", default="document", choices=("document", "project", "conversation", "event")
    )
    register.add_argument(
        "--sensitivity", default="private", choices=("public", "private", "sensitive")
    )
    for action in ("approve", "revoke"):
        child = sources.add_parser(action)
        child.add_argument("id")
        child.add_argument("--expected-revision", type=int, required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("source_id")
    ingest.add_argument("file", type=Path)
    ingest.add_argument("--mode", default="fields", choices=("fields", "notes"))
    ingest.add_argument("--expected-source-revision", type=int)
    commands.add_parser("runs")
    recall = commands.add_parser("recall")
    recall.add_argument("question")
    recall.add_argument("--allow-sensitive", action="store_true")
    export = commands.add_parser("export")
    export.add_argument("file", help="Private JSON destination, or '-' for stdout")
    export.add_argument("--force", action="store_true", help="Overwrite an existing regular file")
    return root


def _record(store, entry_id):
    for item in store.entries(include_superseded=True):
        if item["id"] == entry_id:
            return item
    raise MemoryNotFound("Memory not found")


def _replacement_versions(values, ids):
    versions = {}
    for value in values:
        entry_id, number = value.rsplit(":", 1)
        if entry_id in versions:
            raise MemoryInputError("Replacement versions must be unique")
        versions[entry_id] = int(number)
    if set(versions) != set(ids):
        raise MemoryInputError("Every replacement requires its reviewed ID:REV")
    return versions


def execute(args):
    store = Store(args.data_dir)
    learning = LearningPipeline(store)
    if args.command == "memory":
        if args.action == "list":
            return store.entries(include_superseded=args.include_superseded)
        if args.action == "add":
            return store.add(
                Entry(
                    kind=args.kind, key=args.key, content=args.content, sensitivity=args.sensitivity
                )
            )
        if args.action == "show":
            return _record(store, args.id)
        if args.action == "history":
            return store.revisions(args.id)
        if args.action == "origins":
            return learning.origins(args.id)
        if args.action == "delete":
            if not args.yes:
                raise MemoryInputError("Deletion requires --yes; it purges all record versions")
            return store.delete(args.id)
        if args.action == "restore":
            return store.restore(args.id, args.revision, args.expected_revision)
        if args.action == "confirm":
            return store.confirm(
                args.id,
                args.replace,
                args.expected_revision,
                _replacement_versions(args.replace_revision, args.replace),
            )
        item = _record(store, args.id)
        entry = Entry(
            kind=args.kind or item["kind"],
            key=args.key or item["key"],
            content=args.content,
            **({"sensitivity": args.sensitivity} if args.sensitivity is not None else {}),
        )
        return store.edit(
            args.id,
            entry,
            args.expected_revision if args.expected_revision is not None else item["revision"],
        )
    if args.command == "source":
        if args.action == "list":
            return learning.sources()
        if args.action == "register":
            return learning.register(
                SourceInput(kind=args.kind, name=args.name, sensitivity=args.sensitivity)
            )
        return learning.approve(
            args.id, approved=args.action == "approve", expected_revision=args.expected_revision
        )
    if args.command == "ingest":
        with args.file.open("rb") as handle:
            content = handle.read(MAX_DOCUMENT_BYTES + 1)
        if len(content) > MAX_DOCUMENT_BYTES:
            raise MemoryInputError("Document exceeds the ingestion byte limit")
        return learning.ingest(
            args.source_id,
            IngestionInput(
                content=content.decode("utf-8"),
                mode=args.mode,
                expected_source_revision=args.expected_source_revision,
            ),
        )
    if args.command == "runs":
        return learning.runs()
    if args.command == "recall":
        return [
            dict(path=match.document.path, excerpt=match.excerpt, score=match.score)
            for match in store.context(args.question, allow_sensitive=args.allow_sensitive)
        ]
    data = store.export()
    if args.file == "-":
        return data
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if args.force else os.O_EXCL)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(args.file, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        if hasattr(os, "fchmod"):
            os.fchmod(handle.fileno(), 0o600)
        else:
            os.chmod(args.file, 0o600)
        json.dump(data, handle, ensure_ascii=False, indent=2)
    return {"exported": True, "version": data["version"]}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        data = execute(args)
    except (MemoryError, ValidationError, OSError, ValueError) as error:
        message = "Invalid command data" if isinstance(error, ValidationError) else str(error)
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 1 if isinstance(data, dict) and data.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
