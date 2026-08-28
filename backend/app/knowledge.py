from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]", re.IGNORECASE)


class KnowledgeLoadError(RuntimeError):
    """Raised when the configured knowledge corpus cannot be loaded safely."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Document:
    title: str
    path: str
    text: str


@dataclass(frozen=True)
class Match:
    document: Document
    excerpt: str
    score: float


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in _TOKEN.findall(value)}


def _title(path: Path, text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


class KnowledgeBase:
    def __init__(self, directory: str, *, max_document_bytes: int = 1_000_000) -> None:
        self.directory = Path(directory)
        self.max_document_bytes = max_document_bytes

    def documents(self) -> list[Document]:
        if not self.directory.exists():
            return []

        try:
            root = self.directory.resolve(strict=True)
        except OSError as error:
            raise KnowledgeLoadError("knowledge_directory_unavailable") from error
        if not root.is_dir():
            raise KnowledgeLoadError("knowledge_directory_invalid")

        result: list[Document] = []
        try:
            paths = sorted(self.directory.rglob("*.md"))
        except OSError as error:
            raise KnowledgeLoadError("knowledge_directory_unavailable") from error

        for path in paths:
            if path.is_symlink():
                raise KnowledgeLoadError("knowledge_symlink_rejected")
            try:
                resolved = path.resolve(strict=True)
                resolved.relative_to(root)
            except (OSError, ValueError) as error:
                raise KnowledgeLoadError("knowledge_path_rejected") from error
            if not resolved.is_file():
                continue
            try:
                if resolved.stat().st_size > self.max_document_bytes:
                    raise KnowledgeLoadError("knowledge_document_too_large")
                text = resolved.read_text(encoding="utf-8")
            except KnowledgeLoadError:
                raise
            except (OSError, UnicodeError) as error:
                raise KnowledgeLoadError("knowledge_document_unreadable") from error

            result.append(
                Document(
                    title=_title(path, text),
                    path=path.relative_to(self.directory).as_posix(),
                    text=text,
                )
            )
        return result

    def search(self, question: str, *, limit: int = 4) -> list[Match]:
        query = _tokens(question)
        if not query:
            return []
        matches: list[Match] = []
        for document in self.documents():
            paragraphs = [part.strip() for part in re.split(r"\n\s*\n", document.text)]
            for paragraph in paragraphs:
                if not paragraph or paragraph.startswith("#"):
                    continue
                paragraph_tokens = _tokens(paragraph)
                overlap = query & paragraph_tokens
                if not overlap:
                    continue
                score = len(overlap) / max(len(query), 1)
                matches.append(
                    Match(
                        document=document,
                        excerpt=paragraph[:1_000],
                        score=round(score, 4),
                    )
                )
        matches.sort(key=lambda item: (-item.score, item.document.path, item.excerpt))
        return matches[:limit]
