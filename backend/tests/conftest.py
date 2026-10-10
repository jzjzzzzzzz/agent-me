import httpx
import pytest

from app.config import Settings, get_settings
from app.main import app


@pytest.fixture
async def personal(tmp_path):
    knowledge = tmp_path / "public"
    knowledge.mkdir()
    config = Settings(
        _env_file=None,
        personal_enabled=True,
        personal_token="t" * 40,
        personal_data_dir=str(tmp_path / "private"),
        knowledge_dir=str(knowledge),
    )
    app.dependency_overrides[get_settings] = lambda: config
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, config
    app.dependency_overrides.clear()
