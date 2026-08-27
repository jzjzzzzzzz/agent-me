import re
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]", re.IGNORECASE)


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
    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)

    def documents(self) -> list[Document]:
        if not self.directory.exists():
            return []
        result: list[Document] = []
        for path in sorted(self.directory.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            result.append(
                Document(
                    title=_title(path, text),
                    path=str(path.relative_to(self.directory)),
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
