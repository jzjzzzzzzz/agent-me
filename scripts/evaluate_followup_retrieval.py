"""Compare current-question retrieval and source revisiting on synthetic follow-ups, offline."""

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings
from app.followup_retrieval import retrieve_chat_context
from app.knowledge import KnowledgeBase
from app.provider import context_matches
from app.schemas import ChatRequest


def evaluate() -> list[dict]:
    cases = json.loads(
        (ROOT / "course/examples/followup-retrieval/cases.json").read_text("utf-8")
    )
    # Complete synthetic settings enable the API retrieval path. No provider is called.
    settings = Settings(
        _env_file=None,
        llm_base_url="https://provider.example/v1",
        llm_api_key="synthetic-key",
        llm_model="synthetic-model",
    )
    results = []
    for case in cases:
        with TemporaryDirectory(prefix="agent-me-followup-") as directory:
            for name, text in case["documents"].items():
                (Path(directory) / name).write_text(text, "utf-8")
            knowledge = KnowledgeBase(directory)
            previous = context_matches(
                knowledge.search(case["history"][0]["content"]),
                settings.max_context_chars,
            )
            request = ChatRequest(
                question=case["question"],
                history=case["history"],
                previous_sources=[
                    {"path": m.document.path, "excerpt": m.excerpt} for m in previous
                ],
            )
            baseline = knowledge.search(request.question)
            revisited = retrieve_chat_context(knowledge, request, settings)
            expected = (
                {"tea.md"}
                if case["condition"] == "topic_switch"
                else set(case["documents"])
            )
            actual = {m.document.path for m in revisited}
            assert actual == expected, f"{case['id']}: {actual} != {expected}"
            results.append(
                {
                    "case": case["id"],
                    "baseline_sources": [m.document.path for m in baseline],
                    "revisited_sources": sorted(actual),
                    "source_recall_passed": True,
                }
            )
    return results


if __name__ == "__main__":
    print(json.dumps({"network_called": False, "cases": evaluate()}, indent=2))
