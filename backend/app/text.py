from __future__ import annotations

import unicodedata
from collections.abc import Iterator


def _is_han(character: str) -> bool:
    codepoint = ord(character)
    return 0x3400 <= codepoint <= 0x9FFF


def token_spans(value: str) -> Iterator[tuple[int, int]]:
    """Yield word/Han boundaries as offsets into the supplied, unchanged text.

    Combining marks belong to the preceding word. Each Han character is a
    separate term, including when adjacent to a non-Han word.
    """
    start: int | None = None
    for index, character in enumerate(value):
        if _is_han(character):
            if start is not None:
                yield start, index
                start = None
            yield index, index + 1
        elif character.isalnum():
            if start is None:
                start = index
        elif unicodedata.category(character).startswith("M") and start is not None:
            continue
        elif start is not None:
            yield start, index
            start = None

    if start is not None:
        yield start, len(value)


def normalized_tokens(value: str) -> set[str]:
    """Return deterministic search terms after NFKC normalization and case folding.

    Letters and numbers stay grouped into words. Combining marks stay attached to
    the word they modify, while Han characters remain individual terms so the
    reference implementation's existing CJK matching behavior does not change.
    """

    normalized = unicodedata.normalize("NFKC", value).casefold()
    return {normalized[start:end] for start, end in token_spans(normalized)}
