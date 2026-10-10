"""Owner-operated local CLI. It never starts an HTTP server or calls a model provider."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from .agency import Agency
from .agency_models import PermissionInput, ToolInvocation
from .agent_runtime import AgentIntent, AgentRuntime
from .audit import AuditLog
from .consolidation import ConsolidationManager
from .disclosure import DisclosureManager
from .identity import IdentityStore
from .knowledge import KnowledgeBase
from .learning import MAX_DOCUMENT_BYTES, LearningPipeline
from .learning_policy import LearningPolicyManager
from .memory import MemoryError, MemoryInputError, MemoryNotFound, Store
from .memory_models import (
    ConsolidationFilter,
    EntityInput,
    Entry,
    IngestionInput,
    LearningPolicy,
    RelationshipInput,
    RetentionPolicy,
    SourceInput,
    TemporalQuery,
)
from .owner_control import OwnerControl
from .owner_models import DisclosurePolicy, WorkspacePurge
from .personal_agent import ClaimVerifier, PersonalAgent
from .portability import MAX_IMPORT_BYTES, PortableMemory
from .retention import RetentionManager
from .retrieval import PersonalRetriever
from .retrieval_models import AskRequest, VerifyRequest


def _metadata_flags(parser):
    parser.add_argument("--entity-id")
    parser.add_argument("--confidence", type=float)
    parser.add_argument(
        "--belief", choices=("known", "inferred", "disputed", "outdated", "unknown")
    )
    for name in ("valid-from", "valid-until", "occurred-at"):
        parser.add_argument(f"--{name}")
    parser.add_argument(
        "--unset",
        action="append",
        default=[],
        choices=("entity_id", "confidence", "valid_from", "valid_until", "occurred_at"),
    )


def _metadata(args):
    fields = ("entity_id", "confidence", "belief", "valid_from", "valid_until", "occurred_at")
    values = {
        field: getattr(args, field) for field in fields if getattr(args, field, None) is not None
    }
    values.update({field: None for field in getattr(args, "unset", [])})
    return values


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="agent-me", description=__doc__)
    root.add_argument("--data-dir", default="private", help="Owner's local workspace directory")
    commands = root.add_subparsers(dest="command", required=True)
    memory = commands.add_parser("memory").add_subparsers(dest="action", required=True)
    listing = memory.add_parser("list")
    listing.add_argument("--include-superseded", action="store_true")
    for action in ("show", "history", "origins", "delete", "restore", "confirm", "edit"):
        child = memory.add_parser(action)
        child.add_argument("id")
        if action in ("restore", "confirm", "edit"):
            child.add_argument("--expected-revision", type=int, required=action == "confirm")
        if action == "delete":
            child.add_argument(
                "--yes", action="store_true", help="Purge this record and its versions"
            )
        if action == "restore":
            child.add_argument("--revision", type=int, required=True)
        if action == "confirm":
            child.add_argument("--replace", action="append", default=[])
            child.add_argument("--replace-revision", action="append", default=[], metavar="ID:REV")
        if action == "edit":
            _metadata_flags(child)
            child.add_argument("--kind", choices=("fact", "preference", "event", "decision"))
            child.add_argument("--key")
            child.add_argument("--content", required=True)
            child.add_argument("--sensitivity", choices=("public", "private", "sensitive"))
    add = memory.add_parser("add")
    add.add_argument("--kind", default="fact", choices=("fact", "preference", "event", "decision"))
    add.add_argument("--key", required=True)
    add.add_argument("--content", required=True)
    add.add_argument("--sensitivity", default="private", choices=("public", "private", "sensitive"))
    _metadata_flags(add)

    sources = commands.add_parser("source").add_subparsers(dest="action", required=True)
    sources.add_parser("list")
    register = sources.add_parser("register")
    register.add_argument("--name", required=True)
    register.add_argument("--entity-id")
    register.add_argument("--entity-alias")
    register.add_argument(
        "--kind", default="document", choices=("document", "project", "conversation", "event")
    )
    register.add_argument(
        "--sensitivity", default="private", choices=("public", "private", "sensitive")
    )
    for action in ("approve", "revoke"):
        child = sources.add_parser(action)
        child.add_argument("id")
        child.add_argument("--expected-revision", type=int, required=True)
    ingest = commands.add_parser("ingest")
    ingest.add_argument("source_id")
    ingest.add_argument("file", type=Path)
    ingest.add_argument("--mode", default="fields", choices=("fields", "notes"))
    ingest.add_argument("--expected-source-revision", type=int)
    for name in ("valid-from", "valid-until", "occurred-at"):
        ingest.add_argument(f"--{name}")
    commands.add_parser("runs")
    recall = commands.add_parser("recall")
    recall.add_argument("question")
    recall.add_argument("--allow-sensitive", action="store_true")
    recall.add_argument("--entity-id")
    recall.add_argument("--as-of")
    recall.add_argument("--known-at")
    inspect = commands.add_parser("select")
    for name in ("entity-id", "as-of", "known-at"):
        inspect.add_argument(f"--{name}")
    inspect.add_argument("--allow-sensitive", action="store_true")
    inspect.add_argument("--include-uncertain", action="store_true")
    kinds = ("person", "project", "organization", "event", "idea", "preference", "decision")
    entity = commands.add_parser("entity").add_subparsers(dest="action", required=True)
    entity.add_parser("list")
    owner = entity.add_parser("owner")
    owner.add_argument("id", nargs="?")
    owner.add_argument("--clear", action="store_true")
    resolve = entity.add_parser("resolve")
    resolve.add_argument("name")
    resolve.add_argument("--allow-sensitive", action="store_true")
    for action in ("add", "edit"):
        child = entity.add_parser(action)
        child.add_argument("--kind", choices=kinds, required=action == "add")
        child.add_argument("--name", required=True)
        child.add_argument("--alias", action="append")
        child.add_argument("--sensitivity", choices=("public", "private", "sensitive"))
        if action == "add":
            child.add_argument("--distinct", action="store_true")
        else:
            child.add_argument("id")
            child.add_argument("--expected-revision", type=int, required=True)
    for action in ("confirm", "history", "delete", "neighbours"):
        child = entity.add_parser(action)
        child.add_argument("id")
        if action == "confirm":
            child.add_argument("--expected-revision", type=int, required=True)
        if action == "delete":
            child.add_argument("--yes", action="store_true")
        if action == "neighbours":
            child.add_argument("--allow-sensitive", action="store_true")
    relation = commands.add_parser("relationship").add_subparsers(dest="action", required=True)
    relation.add_parser("list")
    create = relation.add_parser("add")
    for name in ("from-entity-id", "to-entity-id", "predicate", "evidence-id"):
        create.add_argument(f"--{name}", required=True)
    for action in ("confirm", "history", "delete"):
        child = relation.add_parser(action)
        child.add_argument("id")
        if action == "confirm":
            child.add_argument("--expected-revision", type=int, required=True)
        if action == "delete":
            child.add_argument("--yes", action="store_true")
    retention = commands.add_parser("retention").add_subparsers(dest="action", required=True)
    retention.add_parser("policy")
    retention.add_parser("plans")
    configure = retention.add_parser("configure")
    configure.add_argument("--policy-json", required=True)
    configure.add_argument("--expected-revision", type=int, required=True)
    retention.add_parser("preview").add_argument("--as-of")
    apply = retention.add_parser("apply")
    apply.add_argument("id")
    apply.add_argument("--yes", action="store_true")
    learning = commands.add_parser("learning").add_subparsers(dest="action", required=True)
    learning.add_parser("policy")
    configure = learning.add_parser("configure")
    configure.add_argument("--policy-json", required=True)
    configure.add_argument("--expected-revision", type=int, required=True)
    consolidate = commands.add_parser("consolidate").add_subparsers(dest="action", required=True)
    preview = consolidate.add_parser("preview")
    preview.add_argument("--entity-id")
    preview.add_argument("--key-prefix")
    preview.add_argument(
        "--kind", action="append", choices=("fact", "preference", "event", "decision")
    )
    consolidate.add_parser("plans")
    apply = consolidate.add_parser("apply")
    apply.add_argument("id")
    apply.add_argument("--digest", required=True)
    apply.add_argument("--yes", action="store_true")
    for command in ("ask", "retrieve"):
        child = commands.add_parser(command)
        child.add_argument("question")
        child.add_argument(
            "--intent",
            default="auto",
            choices=(
                "auto",
                "recall",
                "profile",
                "preferences",
                "projects",
                "timeline",
                "relationships",
            ),
        )
        child.add_argument("--entity-id")
        child.add_argument("--entity-alias")
        for name in ("as-of", "known-at", "since", "until"):
            child.add_argument(f"--{name}")
        child.add_argument("--allow-sensitive", action="store_true")
        child.add_argument("--no-documents", action="store_true")
        child.add_argument("--public-knowledge", type=Path)
        child.add_argument("--minimum-confidence", type=float)
        child.add_argument("--limit", type=int, default=12)
        child.add_argument("--max-context-chars", type=int, default=12000)
        child.add_argument("--locale", default="auto", choices=("auto", "en", "zh"))
    verify = commands.add_parser("verify")
    verify.add_argument(
        "file", type=Path, help="JSON VerifyRequest containing original request and claims"
    )
    verify.add_argument("--public-knowledge", type=Path)
    commands.add_parser("tasks")
    commands.add_parser("notes")
    agent = commands.add_parser("agent")
    agent.add_argument("file", type=Path)
    tools = commands.add_parser("tools").add_subparsers(dest="action", required=True)
    tools.add_parser("permissions")
    configure = tools.add_parser("configure")
    configure.add_argument("name", choices=("tasks.create", "tasks.complete", "notes.create"))
    configure.add_argument("--policy-json", required=True)
    configure.add_argument("--expected-revision", type=int, required=True)
    action = commands.add_parser("action").add_subparsers(dest="action", required=True)
    action.add_parser("list")
    create = action.add_parser("plan")
    create.add_argument("file", type=Path, help="JSON ToolInvocation; no effects occur")
    approve = action.add_parser("approve")
    approve.add_argument("id")
    approve.add_argument("--expected-revision", type=int, required=True)
    approve.add_argument("--digest", required=True)
    for name in ("execute", "rollback", "cancel", "events"):
        child = action.add_parser(name)
        child.add_argument("id")
        if name in {"execute", "rollback"}:
            child.add_argument("--yes", action="store_true")
    export = commands.add_parser("export")
    export.add_argument("file", help="Private JSON destination, or '-' for stdout")
    export.add_argument("--force", action="store_true", help="Overwrite an existing regular file")
    audit = commands.add_parser("audit").add_subparsers(dest="action", required=True)
    audit.add_parser("events").add_argument("--limit", type=int, default=100)
    audit.add_parser("clear").add_argument("--yes", action="store_true")
    disclosure = commands.add_parser("disclosure").add_subparsers(dest="action", required=True)
    disclosure.add_parser("policy")
    configure = disclosure.add_parser("configure")
    configure.add_argument("--policy-json", required=True)
    configure.add_argument("--expected-revision", type=int, required=True)
    portability = commands.add_parser("portability").add_subparsers(dest="action", required=True)
    for name in ("preview", "import"):
        child = portability.add_parser(name)
        child.add_argument("file", type=Path)
        if name == "import":
            child.add_argument("--digest", required=True)
            child.add_argument("--yes", action="store_true")
    portability.add_parser("archives")
    child = portability.add_parser("delete-archive")
    child.add_argument("id")
    child.add_argument("--yes", action="store_true")
    owner = commands.add_parser("owner").add_subparsers(dest="action", required=True)
    child = owner.add_parser("purge")
    child.add_argument("--expected-owner-id", required=True)
    child.add_argument("--yes", action="store_true")
    for name in ("delete-output", "delete-action", "delete-source"):
        child = owner.add_parser(name)
        if name == "delete-output":
            child.add_argument("table", choices=("tasks", "notes"))
        child.add_argument("id")
        child.add_argument("--expected-revision", type=int, required=True)
        child.add_argument("--yes", action="store_true")
        if name == "delete-action":
            child.add_argument("--purge-output", action="store_true")
            child.add_argument("--expected-output-revision", type=int)
        if name == "delete-source":
            child.add_argument("--forget-memories", action="store_true")
    return root


def _record(store, entry_id):
    for item in store.entries(include_superseded=True):
        if item["id"] == entry_id:
            return item
    raise MemoryNotFound("Memory not found")


def _replacement_versions(values, ids):
    versions = {}
    for value in values:
        entry_id, number = value.rsplit(":", 1)
        if entry_id in versions:
            raise MemoryInputError("Replacement versions must be unique")
        versions[entry_id] = int(number)
    if set(versions) != set(ids):
        raise MemoryInputError("Every replacement requires its reviewed ID:REV")
    return versions


def _execute(args):
    store = Store(args.data_dir)
    learning = LearningPipeline(store)
    identity = IdentityStore(store)
    if args.command == "disclosure":
        manager = DisclosureManager(store)
        if args.action == "policy":
            return manager.settings()
        return manager.configure(
            DisclosurePolicy.model_validate_json(args.policy_json), args.expected_revision
        )
    if args.command == "audit":
        if args.action == "events":
            return AuditLog(store).events(args.limit)
        if not args.yes:
            raise MemoryInputError("Audit erasure requires --yes")
        return AuditLog(store).clear()
    if args.command == "portability":
        if args.action == "archives":
            return OwnerControl(store).archives()
        if args.action == "delete-archive":
            if not args.yes:
                raise MemoryInputError("Archive erasure requires --yes")
            return OwnerControl(store).delete_archive(args.id)
        with args.file.open("rb") as handle:
            content = handle.read(MAX_IMPORT_BYTES + 1)
        if len(content) > MAX_IMPORT_BYTES:
            raise MemoryInputError("Snapshot exceeds the 16 MiB import limit")
        try:
            payload = json.loads(content)
        except (ValueError, UnicodeError, RecursionError):
            raise MemoryInputError("Snapshot must be valid JSON") from None
        if args.action == "preview":
            return PortableMemory(store).preview(payload)
        if not args.yes:
            raise MemoryInputError("Import requires --yes and the reviewed snapshot digest")
        return PortableMemory(store).apply(payload, args.digest)
    if args.command == "owner":
        if not args.yes:
            raise MemoryInputError("Owner erasure requires --yes")
        owner = OwnerControl(store)
        if args.action == "purge":
            return owner.purge(
                WorkspacePurge(
                    expected_owner_id=args.expected_owner_id,
                    confirmation="erase-personal-workspace",
                )
            )
        if args.action == "delete-output":
            return owner.delete_output(args.table, args.id, args.expected_revision)
        if args.action == "delete-source":
            return owner.delete_source(
                args.id, args.expected_revision, forget_memories=args.forget_memories
            )
        return owner.delete_action(
            args.id,
            args.expected_revision,
            purge_output=args.purge_output,
            expected_output_revision=args.expected_output_revision,
        )
    if args.command == "learning":
        policy = LearningPolicyManager(store)
        if args.action == "policy":
            return policy.settings()
        return policy.configure(
            LearningPolicy.model_validate_json(args.policy_json), args.expected_revision
        )
    if args.command == "consolidate":
        manager = ConsolidationManager(store)
        if args.action == "preview":
            return manager.preview(
                ConsolidationFilter(
                    entity_id=args.entity_id, key_prefix=args.key_prefix, kinds=args.kind
                )
            )
        if args.action == "plans":
            return manager.plans()
        if not args.yes:
            raise MemoryInputError("Consolidation requires --yes and the reviewed preview digest")
        return manager.apply(args.id, args.digest)
    if args.command in {"tools", "action", "tasks", "notes", "agent"}:
        agency = Agency(store)
        if args.command == "tools":
            if args.action == "permissions":
                return agency.permissions()
            return agency.configure(
                args.name,
                PermissionInput.model_validate_json(args.policy_json),
                args.expected_revision,
            )
        if args.command in {"tasks", "notes"}:
            return agency.tasks() if args.command == "tasks" else agency.notes()
        if args.command == "agent" or args.action == "plan":
            with args.file.open("rb") as handle:
                data = handle.read(65537)
            if len(data) > 65536:
                raise MemoryInputError("Agent/action request exceeds the byte limit")
            if args.command == "agent":
                retriever = PersonalRetriever(
                    store, documents={"private": KnowledgeBase(str(store.root / "knowledge"))}
                )
                return (
                    AgentRuntime(retriever)
                    .route(AgentIntent.model_validate_json(data))
                    .model_dump(mode="json")
                )
            return agency.plan(ToolInvocation.model_validate_json(data))
        if args.action == "list":
            return agency.plans()
        if args.action == "approve":
            return agency.approve(args.id, args.expected_revision, args.digest)
        if args.action == "events":
            return agency.events(args.id)
        if args.action == "cancel":
            return agency.cancel(args.id)
        if not args.yes:
            raise MemoryInputError(
                "Action execution/rollback requires --yes after reviewing its plan"
            )
        return agency.execute(args.id) if args.action == "execute" else agency.rollback(args.id)
    if args.command in {"entity", "relationship"}:
        relationship = args.command == "relationship"
        if args.action == "list":
            return identity.relationships() if relationship else identity.entities()
        if args.action == "owner":
            if args.clear or args.id is not None:
                return identity.bind_owner(None if args.clear else args.id)
            return identity.owner()
        if args.action == "confirm":
            return identity.confirm(args.id, args.expected_revision, relationship=relationship)
        if args.action == "history":
            return identity.history(args.id, relationship=relationship)
        if args.action == "delete":
            if not args.yes:
                raise MemoryInputError("Identity deletion requires --yes")
            return identity.delete(args.id, relationship=relationship)
        if relationship:
            return identity.relate(
                RelationshipInput(
                    **{
                        field: getattr(args, field)
                        for field in ("from_entity_id", "to_entity_id", "predicate", "evidence_id")
                    }
                )
            )
        if args.action == "resolve":
            return identity.resolve(args.name, allow_sensitive=args.allow_sensitive)
        if args.action == "neighbours":
            return identity.neighbours(args.id, allow_sensitive=args.allow_sensitive)
        data = {"name": args.name}
        for field, argument in (
            ("kind", args.kind),
            ("aliases", args.alias),
            ("sensitivity", args.sensitivity),
        ):
            if argument is not None:
                data[field] = argument
        if args.action == "edit":
            current = next((item for item in identity.entities() if item["id"] == args.id), None)
            if not current:
                raise MemoryNotFound("Entity not found")
            data.setdefault("kind", current["kind"])
            return identity.edit(args.id, EntityInput(**data), args.expected_revision)
        return identity.add(EntityInput(**data), distinct=args.distinct)
    if args.command == "retention":
        manager = RetentionManager(store)
        if args.action == "policy":
            return manager.settings()
        if args.action == "configure":
            return manager.configure(
                RetentionPolicy.model_validate_json(args.policy_json), args.expected_revision
            )
        if args.action == "preview":
            return manager.preview(as_of=args.as_of)
        if args.action == "plans":
            return manager.plans()
        if not args.yes:
            raise MemoryInputError("Applying retention requires --yes after reviewing the plan")
        return manager.apply(args.id)
    if args.command == "select":
        return store.select(
            TemporalQuery(
                as_of=args.as_of,
                known_at=args.known_at,
                entity_id=args.entity_id,
                allow_sensitive=args.allow_sensitive,
                include_uncertain=args.include_uncertain,
            )
        )
    if args.command in {"ask", "retrieve", "verify"}:
        documents = {"private": KnowledgeBase(str(store.root / "knowledge"))}
        if args.public_knowledge is not None:
            documents["public"] = KnowledgeBase(str(args.public_knowledge))
        retriever = PersonalRetriever(store, documents=documents)
        if args.command == "verify":
            with args.file.open("rb") as handle:
                data = handle.read(262145)
            if len(data) > 262144:
                raise MemoryInputError("Verification request exceeds the byte limit")
            payload = VerifyRequest.model_validate_json(data)
            return [
                item.model_dump(mode="json")
                for item in ClaimVerifier(retriever).verify(payload.request, payload.claims)
            ]
        fields = (
            "question",
            "intent",
            "entity_id",
            "entity_alias",
            "as_of",
            "known_at",
            "since",
            "until",
            "allow_sensitive",
            "minimum_confidence",
            "limit",
            "max_context_chars",
            "locale",
        )
        request = AskRequest(
            **{field: getattr(args, field) for field in fields},
            include_documents=not args.no_documents,
        )
        return (
            PersonalAgent(retriever).ask(request)
            if args.command == "ask"
            else retriever.retrieve(request)
        ).model_dump(mode="json")
    if args.command == "memory":
        if args.action == "list":
            return store.entries(include_superseded=args.include_superseded)
        if args.action == "add":
            return store.add(
                Entry(
                    kind=args.kind,
                    key=args.key,
                    content=args.content,
                    sensitivity=args.sensitivity,
                    **_metadata(args),
                )
            )
        if args.action == "show":
            return _record(store, args.id)
        if args.action == "history":
            return store.revisions(args.id)
        if args.action == "origins":
            return learning.origins(args.id)
        if args.action == "delete":
            if not args.yes:
                raise MemoryInputError("Deletion requires --yes; it purges all record versions")
            return store.delete(args.id)
        if args.action == "restore":
            return store.restore(args.id, args.revision, args.expected_revision)
        if args.action == "confirm":
            return store.confirm(
                args.id,
                args.replace,
                args.expected_revision,
                _replacement_versions(args.replace_revision, args.replace),
            )
        item = _record(store, args.id)
        entry = Entry(
            kind=args.kind or item["kind"],
            key=args.key or item["key"],
            content=args.content,
            **({"sensitivity": args.sensitivity} if args.sensitivity is not None else {}),
            **_metadata(args),
        )
        return store.edit(
            args.id,
            entry,
            args.expected_revision if args.expected_revision is not None else item["revision"],
        )
    if args.command == "source":
        if args.action == "list":
            return learning.sources()
        if args.action == "register":
            return learning.register(
                SourceInput(
                    kind=args.kind,
                    name=args.name,
                    sensitivity=args.sensitivity,
                    entity_id=args.entity_id,
                    entity_alias=args.entity_alias,
                )
            )
        return learning.approve(
            args.id, approved=args.action == "approve", expected_revision=args.expected_revision
        )
    if args.command == "ingest":
        with args.file.open("rb") as handle:
            content = handle.read(MAX_DOCUMENT_BYTES + 1)
        if len(content) > MAX_DOCUMENT_BYTES:
            raise MemoryInputError("Document exceeds the ingestion byte limit")
        return learning.ingest(
            args.source_id,
            IngestionInput(
                content=content.decode("utf-8"),
                mode=args.mode,
                expected_source_revision=args.expected_source_revision,
                **{
                    field: getattr(args, field)
                    for field in ("valid_from", "valid_until", "occurred_at")
                },
            ),
        )
    if args.command == "runs":
        return learning.runs()
    if args.command == "recall":
        return [
            dict(path=match.document.path, excerpt=match.excerpt, score=match.score)
            for match in store.context(
                args.question,
                allow_sensitive=args.allow_sensitive,
                as_of=args.as_of,
                known_at=args.known_at,
                entity_id=args.entity_id,
            )
        ]
    data = store.export()
    if args.file == "-":
        return data
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if args.force else os.O_EXCL)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(args.file, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        if hasattr(os, "fchmod"):
            os.fchmod(handle.fileno(), 0o600)
        else:
            os.chmod(args.file, 0o600)
        json.dump(data, handle, ensure_ascii=False, indent=2)
    return {"exported": True, "version": data["version"]}


def execute(args):
    audit = AuditLog(Store(args.data_dir))
    operation = "cli." + args.command.replace("-", "_")
    if getattr(args, "action", None):
        operation += "." + args.action.replace("-", "_")
    try:
        result = _execute(args)
    except Exception:
        audit.record(operation, "failed", actor="cli")
        raise
    audit.record(
        operation,
        "failed" if isinstance(result, dict) and result.get("status") == "failed" else "succeeded",
        actor="cli",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        data = execute(args)
    except (MemoryError, ValidationError, OSError, ValueError) as error:
        message = "Invalid command data" if isinstance(error, ValidationError) else str(error)
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 1 if isinstance(data, dict) and data.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
