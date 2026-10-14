import pytest

from app.text import normalized_tokens, token_spans


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", []),
        ("\u0301 _ !", []),
        ("E\u0301valuation", [(0, 11)]),
        ("a\u0301\u0327_b", [(0, 3), (4, 5)]),
        ("填E\u0301valuation检索", [(0, 1), (1, 12), (12, 13), (13, 14)]),
        ("नमस्ते Python42", [(0, 6), (7, 15)]),
    ],
)
def test_token_spans_preserve_original_offsets(value: str, expected: list[tuple[int, int]]) -> None:
    assert list(token_spans(value)) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", set()),
        ("\u0301 _ !", set()),
        ("Évaluation E\u0301valuation", {"évaluation"}),
        ("İstanbul", {"i\u0307stanbul"}),
        ("Straße ＰＹＴＨＯＮ ﬃ ½", {"strasse", "python", "ffi", "1", "2"}),
        ("填E\u0301valuation检索", {"填", "évaluation", "检", "索"}),
        ("नमस्ते Python42", {"नमस्ते", "python42"}),
    ],
)
def test_normalized_tokens_keep_existing_unicode_semantics(value: str, expected: set[str]) -> None:
    assert normalized_tokens(value) == expected
