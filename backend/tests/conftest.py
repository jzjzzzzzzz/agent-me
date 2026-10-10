import httpx
import pytest

from app.config import Settings, get_settings
from app.disclosure import DisclosureManager, target_id
from app.main import app
from app.memory import Store
from app.owner_models import DisclosurePolicy


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


@pytest.fixture
def configured_private_provider(personal):
    _, config = personal
    config.llm_base_url = "https://provider.fixture.invalid/v1"
    config.llm_api_key = "fixture-" + "key"
    config.llm_model = "fictional-model"
    DisclosureManager(Store(config.personal_data_dir)).configure(
        DisclosurePolicy(
            enabled=True,
            target_id=target_id(config.llm_base_url, config.llm_model),
            labels=["public", "private", "sensitive"],
        ),
        1,
    )
    return config
