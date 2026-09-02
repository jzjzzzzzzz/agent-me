from __future__ import annotations

import unicodedata


def _is_han(character: str) -> bool:
    codepoint = ord(character)
    return 0x3400 <= codepoint <= 0x9FFF


def normalized_tokens(value: str) -> set[str]:
    """Return deterministic search terms after NFKC normalization and case folding.

    Letters and numbers stay grouped into words. Combining marks stay attached to
    the word they modify, while Han characters remain individual terms so the
    reference implementation's existing CJK matching behavior does not change.
    """

    normalized = unicodedata.normalize("NFKC", value).casefold()
    tokens: set[str] = set()
    word: list[str] = []

    def flush_word() -> None:
        if word:
            tokens.add("".join(word))
            word.clear()

    for character in normalized:
        if _is_han(character):
            flush_word()
            tokens.add(character)
        elif character.isalnum():
            word.append(character)
        elif unicodedata.category(character).startswith("M") and word:
            word.append(character)
        else:
            flush_word()

    flush_word()
    return tokens
