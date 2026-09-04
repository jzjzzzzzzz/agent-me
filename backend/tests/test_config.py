import pytest
from pydantic import ValidationError

from app.config import Settings


def test_knowledge_aggregate_limit_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.max_knowledge_documents == 256
    assert settings.max_knowledge_bytes == 16_000_000


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_knowledge_documents", 0),
        ("max_knowledge_documents", 10_001),
        ("max_knowledge_bytes", 0),
        ("max_knowledge_bytes", 1_000_000_001),
    ],
)
def test_knowledge_aggregate_limits_are_bounded(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
