import json

import pytest

from app.agency import Agency
from app.agency_models import PermissionInput
from app.memory import MemoryConflict, Store
from app.memory_models import Entry
from app.owner_control import OwnerControl
from app.owner_models import WorkspacePurge
from app.portability import PortableMemory


def snapshot(root):
    db = Store(root)
    row = db.add(Entry(key="project", content="Fictional migration body"))
    db.confirm(row["id"], [], 1)
    return db.export()


def test_destination_inspection_distinguishes_empty_configured_and_occupied_without_writes(
    tmp_path,
):
    db = Store(tmp_path)
    manager = PortableMemory(db)
    before = db.export()
    assert manager.destination() == {"owner_id": db.owner_id, "empty": True}
    assert db.export() == before
    Agency(db).configure("notes.create", PermissionInput(enabled=False), 1)
    assert not manager.destination()["empty"]


def test_reviewed_destination_prevents_import_after_purge_even_when_destination_is_empty_again(
    tmp_path,
):
    payload = snapshot(tmp_path / "source")
    db = Store(tmp_path / "destination")
    manager = PortableMemory(db)
    old = db.owner_id
    preview = manager.preview(payload, expected_destination_owner_id=old)
    assert preview["destination_owner_id"] == old and preview["owner_id"] == payload["owner_id"]
    OwnerControl(db).purge(
        WorkspacePurge(expected_owner_id=old, confirmation="erase-personal-workspace")
    )
    before = db.export()
    with pytest.raises(MemoryConflict, match="destination owner changed"):
        manager.apply(payload, preview["digest"], expected_destination_owner_id=old)
    assert db.export() == before and manager.destination()["empty"]
    with pytest.raises(MemoryConflict):
        manager.preview(payload, expected_destination_owner_id=old)
    fresh = manager.preview(payload, expected_destination_owner_id=db.owner_id)
    current = db.owner_id
    result = manager.apply(payload, fresh["digest"], expected_destination_owner_id=current)
    assert result["destination_owner_id"] == current and db.owner_id == payload["owner_id"]


def test_legacy_import_omission_stays_compatible_and_nonempty_destination_stays_protected(tmp_path):
    payload = snapshot(tmp_path / "source")
    db = Store(tmp_path / "destination")
    manager = PortableMemory(db)
    preview = manager.preview(payload)
    manager.apply(payload, preview["digest"])
    before = db.export()
    with pytest.raises(MemoryConflict, match="empty destination"):
        manager.apply(payload, preview["digest"], expected_destination_owner_id=db.owner_id)
    assert db.export() == before


def test_destination_bound_import_failure_rolls_back_owner_and_every_row(tmp_path, monkeypatch):
    payload = snapshot(tmp_path / "source")
    db = Store(tmp_path / "destination")
    manager = PortableMemory(db)
    owner = db.owner_id
    preview = manager.preview(payload, expected_destination_owner_id=owner)
    before = db.export()
    real = manager._write

    def fail(*args):
        real(*args)
        raise RuntimeError("Fictional atomic failure")

    monkeypatch.setattr(manager, "_write", fail)
    with pytest.raises(RuntimeError):
        manager.apply(payload, preview["digest"], expected_destination_owner_id=owner)
    assert db.export() == before


async def test_api_destination_metadata_has_actual_limits_auth_and_no_snapshot_contents(
    personal, tmp_path
):
    client, settings = personal
    headers = {"Authorization": f"Bearer {settings.personal_token}"}
    assert (await client.get("/api/v1/personal/portability/state")).status_code == 401
    settings.max_request_body_bytes = 12345
    response = await client.get("/api/v1/personal/portability/state", headers=headers)
    state = response.json()
    assert response.headers["cache-control"] == "no-store"
    assert state["empty"] and state["max_request_body_bytes"] == 12345
    assert state["max_snapshot_bytes"] == 16 * 1024 * 1024
    payload = snapshot(tmp_path / "source")
    request = {"snapshot": payload, "expected_destination_owner_id": state["owner_id"]}
    preview = await client.post(
        "/api/v1/personal/portability/preview", headers=headers, json=request
    )
    assert preview.status_code == 200 and "Fictional migration body" not in preview.text
    await client.post(
        "/api/v1/personal/workspace/purge",
        headers=headers,
        json={"expected_owner_id": state["owner_id"], "confirmation": "erase-personal-workspace"},
    )
    result = await client.post(
        "/api/v1/personal/portability/import",
        headers=headers,
        json={**request, "digest": preview.json()["digest"]},
    )
    assert result.status_code == 409 and not Store(settings.personal_data_dir).entries()


def test_cli_destination_precondition_and_current_dispositions(tmp_path, capsys):
    from app.agent_cli import main

    payload = snapshot(tmp_path / "source")
    file = tmp_path / "snapshot.json"
    file.write_text(json.dumps(payload), encoding="utf-8")
    db = Store(tmp_path / "destination")
    prefix = ["--data-dir", str(db.root), "portability"]
    assert main([*prefix, "preview", str(file), "--expected-destination-owner-id", "wrong"]) == 2
    capsys.readouterr()
    assert (
        main([*prefix, "preview", str(file), "--expected-destination-owner-id", db.owner_id]) == 0
    )
    preview = json.loads(capsys.readouterr().out)
    assert (
        preview["destination_owner_id"] == db.owner_id and not preview["executable_plans_restored"]
    )
    assert (
        main(
            [
                *prefix,
                "import",
                str(file),
                "--expected-destination-owner-id",
                db.owner_id,
                "--digest",
                preview["digest"],
                "--yes",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["imported"] and Store(db.root).owner_id == payload["owner_id"]
