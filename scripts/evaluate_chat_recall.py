"""Compare literal v1 local retrieval with current scoped chat recall on fictional cases."""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.identity import IdentityStore
from app.memory import Store
from app.memory_models import EntityInput, Entry, TemporalQuery
from app.text import normalized_tokens

FIXTURE = ROOT / "course" / "fixtures" / "chat_recall_cases.json"
STAGES = ("initial", "pending", "revised", "forgotten", "conflict")


def literal_baseline(store, question, project_id, allow_sensitive, use_memory):
    """v1 local evidence: same scope/current-state gate, positive raw overlap, stable order."""
    if not use_memory:
        return []
    selected = [
        row["record"]
        for row in store.select(
            TemporalQuery(entity_id=project_id, allow_sensitive=allow_sensitive),
            chat_scope=True,
        )
    ]
    overrides = {
        unicodedata.normalize("NFC", item["key"])
        for item in selected
        if project_id is not None
        and item["entity_id"] == project_id
        and item["kind"] == "preference"
    }
    tokens = normalized_tokens(question)
    facts, preferences = [], []
    for item in selected:
        if (
            item["kind"] == "preference"
            and item["entity_id"] != project_id
            and unicodedata.normalize("NFC", item["key"]) in overrides
        ):
            continue
        hits = len(tokens & normalized_tokens(f"{item['key']}: {item['content']}"))
        if hits:
            (preferences if item["kind"] == "preference" else facts).append(
                (hits, item["id"])
            )
    preferences.sort(key=lambda item: item[0], reverse=True)
    facts.sort(key=lambda item: item[0], reverse=True)
    facts = facts[: 20 - min(5, len(preferences))]
    return [
        item[1]
        for item in sorted(
            preferences[: 20 - len(facts)] + facts,
            key=lambda item: item[0],
            reverse=True,
        )
    ]


def agrees(values, expected, excluded, disputed, expect_dispute):
    return (
        (values[0] if values else None) == expected
        and not set(values) & excluded
        and disputed == expect_dispute
    )


def evaluate(fixture=FIXTURE):
    cases = json.loads(fixture.read_text(encoding="utf-8"))["cases"]
    if len(cases) != len({case["id"] for case in cases}) or any(
        case["stage"] not in STAGES for case in cases
    ):
        raise ValueError("Duplicate case ID or unknown stage")
    results = []
    with TemporaryDirectory(prefix="agent-me-chat-recall-") as directory:
        db = Store(directory)
        identity = IdentityStore(db)
        projects, ids = {}, {}
        for short, name in [("orchid", "Demo Orchid"), ("bamboo", "Demo Bamboo")]:
            project = identity.add(EntityInput(kind="project", name=name))
            identity.confirm(project["id"], project["revision"])
            projects[short] = project["id"]

        def add(label, key, value, *, scope=None, approve=True, **metadata):
            new = db.add(
                Entry(key=key, content=value, entity_id=projects.get(scope), **metadata)
            )
            ids[label] = new["id"]
            if approve:
                db.confirm(new["id"], [], 1)

        add("name", "identity.name", "Rowan Example")
        add("role", "identity.role", "Optical systems engineer")
        add("skills", "identity.skills", "Prototype fabrication and SolidWorks")
        add("style", "response.style", "Lead with the conclusion", kind="preference")
        add("focus", "projects.current", "Mechanical design study")
        add("orchid-deadline", "project.deadline", "2028-02-04", scope="orchid")
        add("bamboo-deadline", "project.deadline", "2028-07-15", scope="bamboo")
        add(
            "orchid-style",
            "response.style",
            "Use three short bullets",
            scope="orchid",
            kind="preference",
        )
        add(
            "orchid-note",
            "project.calibration",
            "Lumos calibration uses fixture B.",
            scope="orchid",
        )
        add("han-note", "project.name", "项目代号：翠野", scope="orchid")
        add(
            "sensitive",
            "identity.note",
            "FictionalHiddenTopaz",
            sensitivity="sensitive",
        )
        add(
            "expired",
            "project.archive",
            "FictionalExpiredQuill",
            scope="orchid",
            valid_until="2000-01-01T00:00:00Z",
        )

        for stage in STAGES:
            if stage == "pending":
                add(
                    "revised-deadline",
                    "project.deadline",
                    "2028-03-01",
                    scope="orchid",
                    approve=False,
                )
            elif stage == "revised":
                db.confirm(
                    ids["revised-deadline"],
                    [ids["orchid-deadline"]],
                    expected_revision=1,
                    replace_revisions={ids["orchid-deadline"]: 2},
                )
            elif stage == "forgotten":
                db.delete(ids["revised-deadline"], expected_revision=2)
            elif stage == "conflict":
                add("conflicting-role", "job.title", "Geology instructor")
            for case in (case for case in cases if case["stage"] == stage):
                scope = projects[case["scope"]] if "scope" in case else None
                sensitive = case.get("allow_sensitive", False)
                enabled = case.get("use_memory", True)
                current = db.chat_recall(
                    case["question"],
                    project_id=scope,
                    allow_sensitive=sensitive,
                    use_memory=enabled,
                )
                predicted = [
                    match.document.path.removeprefix("memory/")
                    for match in current.matches
                    if match.score > 0
                ]
                baseline = literal_baseline(
                    db, case["question"], scope, sensitive, enabled
                )
                expected = ids[case["top"]] if case["top"] is not None else None
                excluded = {ids[label] for label in case.get("exclude", [])}

                expect_dispute = case.get("disputed", False)
                labels = {value: name for name, value in ids.items()}
                results.append(
                    {
                        "case": case["id"],
                        "expected_top": case["top"],
                        "literal_top": labels[baseline[0]] if baseline else None,
                        "current_top": labels[predicted[0]] if predicted else None,
                        "literal_pass": agrees(
                            baseline, expected, excluded, False, expect_dispute
                        ),
                        "current_pass": agrees(
                            predicted,
                            expected,
                            excluded,
                            current.conflict,
                            expect_dispute,
                        ),
                    }
                )
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    results = evaluate()
    old = sum(item["literal_pass"] for item in results)
    current = sum(item["current_pass"] for item in results)
    if args.json:
        print(
            json.dumps(
                {
                    "literal": old,
                    "current": current,
                    "total": len(results),
                    "cases": results,
                }
            )
        )
    else:
        for item in results:
            print(f"{item['case']}\t{'PASS' if item['current_pass'] else 'FAIL'}")
        print(
            f"CHAT_RECALL_EVAL {current}/{len(results)} passed; literal baseline {old}/{len(results)}"
        )
    return 0 if results and current == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
