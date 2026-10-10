import type { IngestionRun, LearningSource, MemoryRecord, MemoryRevision, Origin, PersonalAnswer } from "../personalApi";

export const timestamp = "2026-01-01T00:00:00Z";
export const sourceFixture: LearningSource = {
  id: "source-one", name: "Fictional profile", kind: "document", sensitivity: "private",
  approved: false, revision: 1, entity_id: null, owner_id: "synthetic-owner", created_at: timestamp, updated_at: timestamp,
};
export const memoryFixture: MemoryRecord = {
  id: "memory-one", kind: "fact", key: "identity.name", content: "Alex Example", source: "learning:source-one",
  status: "pending", revision: 1, sensitivity: "private", entity_id: null, belief: "known", confidence: 0.8,
  valid_from: null, valid_until: null, occurred_at: null, created_at: timestamp, updated_at: timestamp,
  owner_id: "synthetic-owner", category: "semantic", superseded_by: null,
};
export const historyFixture: MemoryRevision[] = [{ ...memoryFixture, change: "created" }];
export const originFixture: Origin = {
  id: "origin-one", memory_id: "memory-one", memory_revision: 1, source_id: "source-one", source_revision: 2,
  document_hash: "a".repeat(64), start: 20, end: 32, excerpt: "Alex Example", run_id: "run-one", created_at: timestamp,
};
export const runFixture: IngestionRun = {
  id: "run-one", source_id: "source-one", source_revision: 2, document_hash: "a".repeat(64), extractor: "exact-excerpts-v1",
  mode: "fields", status: "completed", attempts: 1, created_at: timestamp, updated_at: timestamp, replayed: false, error_code: null,
  items: [{ index: 0, outcome: "created", memory_id: "memory-one", conflict_ids: [] }],
  trace: [{ stage: "storage", outcome: "completed", count: 1 }],
};
export const answerFixture: PersonalAnswer = {
  run_id: "personal_synthetic", mode: "personal-grounded-local", status: "known", answer: "identity.name: Alex Example",
  evidence: [{
    id: "memory-one@2", kind: "memory_value", path: "memory/memory-one@2", revision: 2,
    entity_id: null, field: "identity.name", value: "Alex Example", source: "learning:source-one",
    belief: "known", sensitivity: "private", confidence: 0.8, observed_at: timestamp, occurred_at: null,
    valid_from: null, valid_until: null, score: 1, reasons: ["field"], purpose: "answer",
  }],
};

export const entityFixture = {
  id: "entity-one", kind: "person" as const, name: "Alex Example", aliases: ["Alex"],
  status: "confirmed" as const, sensitivity: "private" as const, revision: 2,
  owner_id: "synthetic-owner", source: "manual" as const, created_at: timestamp, updated_at: timestamp,
};
export const projectFixture = { ...entityFixture, id: "project-one", kind: "project" as const, name: "Orchid Demo", aliases: ["Orchid"] };
export const relationshipFixture = {
  id: "relationship-one", from_entity_id: "entity-one", to_entity_id: "project-one", predicate: "works_on",
  evidence_id: "memory-one", evidence_revision: 2, sensitivity: "private" as const, status: "pending" as const,
  revision: 1, owner_id: "synthetic-owner", created_at: timestamp, updated_at: timestamp,
};
export const identityDeleteFixture = {
  kind: "entity" as const, record: entityFixture, digest: "b".repeat(64),
  memories: [{ ...memoryFixture, revision: 2, status: "confirmed" as const, entity_id: "entity-one" }],
  sources: [sourceFixture], runs: [runFixture], relationships: [relationshipFixture],
  owner_binding: true, origin_count: 1, history_count: 5,
};
