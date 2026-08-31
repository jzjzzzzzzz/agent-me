from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

_TOKEN = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]", re.IGNORECASE)
_ATX_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)(?:\s+#+)?$")
_MIN_QUERY_COVERAGE = 0.75
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "you",
        "your",
    }
)


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


@dataclass(frozen=True)
class _KnowledgeFile:
    resolved: Path
    relative_path: str
    size: int
    modified_ns: int
    changed_ns: int


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in _TOKEN.findall(value)}


def _query_tokens(value: str) -> set[str]:
    return _tokens(value) - _STOP_WORDS


def _title(path: Path, text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def _content_chunks(text: str) -> list[str]:
    chunks: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        lines: list[str] = []
        has_body = False
        for raw_line in block.splitlines():
            heading = _ATX_HEADING.fullmatch(raw_line)
            if heading:
                lines.append(heading.group(1).strip())
            else:
                lines.append(raw_line.strip())
                has_body = has_body or bool(raw_line.strip())
        normalized = "\n".join(line for line in lines if line).strip()
        if has_body and normalized:
            chunks.append(normalized)
    return chunks


class KnowledgeBase:
    def __init__(self, directory: str, *, max_document_bytes: int = 1_000_000) -> None:
        self.directory = Path(directory)
        self.max_document_bytes = max_document_bytes
        self._cache_lock = RLock()
        self._cached_root: Path | None = None
        self._cached_signature: tuple[tuple[str, int, int, int], ...] | None = None
        self._cached_documents: tuple[Document, ...] = ()

    def _files(self, root: Path) -> list[_KnowledgeFile]:
        try:
            paths = sorted(self.directory.rglob("*.md"))
        except OSError as error:
            raise KnowledgeLoadError("knowledge_directory_unavailable") from error

        result: list[_KnowledgeFile] = []
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
                stat = resolved.stat()
                if stat.st_size > self.max_document_bytes:
                    raise KnowledgeLoadError("knowledge_document_too_large")
            except KnowledgeLoadError:
                raise
            except OSError as error:
                raise KnowledgeLoadError("knowledge_document_unreadable") from error

            result.append(
                _KnowledgeFile(
                    resolved=resolved,
                    relative_path=path.relative_to(self.directory).as_posix(),
                    size=stat.st_size,
                    modified_ns=stat.st_mtime_ns,
                    changed_ns=stat.st_ctime_ns,
                )
            )
        return result

    @staticmethod
    def _signature(
        files: list[_KnowledgeFile],
    ) -> tuple[tuple[str, int, int, int], ...]:
        return tuple(
            (item.relative_path, item.size, item.modified_ns, item.changed_ns) for item in files
        )

    def _read(self, files: list[_KnowledgeFile]) -> list[Document]:
        result: list[Document] = []
        for item in files:
            try:
                with item.resolved.open("rb") as source:
                    raw = source.read(self.max_document_bytes + 1)
                if len(raw) > self.max_document_bytes:
                    raise KnowledgeLoadError("knowledge_document_too_large")
                text = raw.decode("utf-8")
            except KnowledgeLoadError:
                raise
            except (OSError, UnicodeError) as error:
                raise KnowledgeLoadError("knowledge_document_unreadable") from error

            result.append(
                Document(
                    title=_title(Path(item.relative_path), text),
                    path=item.relative_path,
                    text=text,
                )
            )
        return result

    def documents(self) -> list[Document]:
        if not self.directory.exists():
            with self._cache_lock:
                self._cached_root = None
                self._cached_signature = None
                self._cached_documents = ()
            return []

        try:
            root = self.directory.resolve(strict=True)
        except OSError as error:
            raise KnowledgeLoadError("knowledge_directory_unavailable") from error
        if not root.is_dir():
            raise KnowledgeLoadError("knowledge_directory_invalid")

        files = self._files(root)
        signature = self._signature(files)
        with self._cache_lock:
            for _ in range(2):
                if root == self._cached_root and signature == self._cached_signature:
                    return list(self._cached_documents)

                documents = self._read(files)
                refreshed_files = self._files(root)
                refreshed_signature = self._signature(refreshed_files)
                if signature == refreshed_signature:
                    self._cached_root = root
                    self._cached_signature = signature
                    self._cached_documents = tuple(documents)
                    return list(self._cached_documents)
                files = refreshed_files
                signature = refreshed_signature

        raise KnowledgeLoadError("knowledge_corpus_changed")

    def search(
        self,
        question: str,
        *,
        limit: int = 4,
        min_score: float = _MIN_QUERY_COVERAGE,
    ) -> list[Match]:
        if not 0 <= min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")
        query = _query_tokens(question)
        if not query:
            return []
        matches: list[Match] = []
        for document in self.documents():
            for paragraph in _content_chunks(document.text):
                paragraph_tokens = _tokens(paragraph)
                overlap = query & paragraph_tokens
                score = len(overlap) / len(query)
                if score < min_score:
                    continue
                matches.append(
                    Match(
                        document=document,
                        excerpt=paragraph[:1_000],
                        score=round(score, 4),
                    )
                )
        matches.sort(key=lambda item: (-item.score, item.document.path, item.excerpt))
        return matches[:limit]
