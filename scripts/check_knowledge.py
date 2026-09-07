#!/usr/bin/env python3
"""Safely validate the configured knowledge corpus before starting Agent-Me."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings
from app.knowledge import KnowledgeBase, KnowledgeLoadError


@dataclass(frozen=True)
class KnowledgeCheckSuccess:
    status: str
    document_count: int
    paths: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeCheckFailure:
    status: str
    code: str


def check_knowledge(
    directory: Path, settings: Settings
) -> KnowledgeCheckSuccess | KnowledgeCheckFailure:
    knowledge = KnowledgeBase(
        str(directory),
        max_document_bytes=settings.max_document_bytes,
        max_documents=settings.max_knowledge_documents,
        max_corpus_bytes=settings.max_knowledge_bytes,
    )
    try:
        documents = knowledge.documents()
    except KnowledgeLoadError as error:
        return KnowledgeCheckFailure(status="error", code=error.code)
    if not documents:
        return KnowledgeCheckFailure(status="error", code="knowledge_corpus_empty")
    return KnowledgeCheckSuccess(
        status="ok",
        document_count=len(documents),
        paths=tuple(document.path for document in documents),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate knowledge files without printing their contents."
    )
    parser.add_argument("--knowledge-dir", type=Path)
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable output"
    )
    args = parser.parse_args(argv)
    settings = Settings()
    directory = args.knowledge_dir or Path(settings.knowledge_dir)
    result = check_knowledge(directory, settings)

    if args.json:
        print(json.dumps(asdict(result), sort_keys=True))
    elif isinstance(result, KnowledgeCheckSuccess):
        print(f"Knowledge corpus is valid ({result.document_count} documents).")
        for path in result.paths:
            print(f"- {path}")
    else:
        print(f"Knowledge corpus validation failed: {result.code}", file=sys.stderr)
    return 0 if isinstance(result, KnowledgeCheckSuccess) else 1


if __name__ == "__main__":
    raise SystemExit(main())
