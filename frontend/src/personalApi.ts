/** Authenticated review contracts. Credentials and private content stay in page memory. */
export type Sensitivity = "public" | "private" | "sensitive";
export type MemoryKind = "fact" | "preference" | "event" | "decision";
export type MemoryStatus = "pending" | "confirmed" | "superseded";
export type MemoryRecord = {
  id: string; kind: MemoryKind; key: string; content: string; status: MemoryStatus;
  source: string; revision: number; sensitivity: Sensitivity; entity_id: string | null;
  belief: "known" | "inferred" | "disputed" | "outdated" | "unknown";
  confidence: number | null; valid_from: string | null; valid_until: string | null;
  occurred_at: string | null; created_at: string; updated_at: string; owner_id: string;
  category: "episodic" | "semantic" | "preference"; superseded_by: string | null;
};
export type MemoryRevision = MemoryRecord & {
  change: "baseline" | "created" | "edited" | "confirmed" | "superseded" | "corroborated";
};
export type LearningSource = {
  id: string; kind: "document" | "project" | "conversation" | "event"; name: string;
  sensitivity: Sensitivity; entity_id: string | null; approved: boolean; revision: number;
  owner_id: string; created_at: string; updated_at: string;
};
export type Entity = {
  id: string; kind: "person" | "project" | "organization" | "event" | "idea" | "preference" | "decision";
  name: string; status: "pending" | "confirmed"; sensitivity: Sensitivity;
  aliases: string[]; revision: number; owner_id: string; source: "manual";
  created_at: string; updated_at: string;
};
export type EntityInput = Pick<Entity, "kind" | "name" | "aliases" | "sensitivity">;
export type EntityRevision = Entity & { change: "created" | "edited" | "confirmed" };
export type Relationship = {
  id: string; owner_id: string; from_entity_id: string; to_entity_id: string; predicate: string;
  evidence_id: string; evidence_revision: number; sensitivity: Sensitivity;
  status: "pending" | "confirmed"; revision: number; created_at: string; updated_at: string;
};
export type RelationshipRevision = Relationship & { change: "created" | "confirmed" };
export type OwnerIdentity = { owner_id: string; entity_id: string | null };
export type IdentityData = { owner: OwnerIdentity; relationships: Relationship[] };
export type EntityResolution = { status: "resolved" | "ambiguous" | "unknown"; matches: Entity[] };
export type IdentityContext = { entities: Entity[]; relationships: Relationship[] };
export type IdentityDeletePreview = {
  kind: "entity" | "relationship"; record: Entity | Relationship; digest: string;
  memories: MemoryRecord[]; sources: LearningSource[]; runs: IngestionRun[]; relationships: Relationship[];
  owner_binding: boolean; origin_count: number; history_count: number;
};
export type IngestionRun = {
  id: string; source_id: string; source_revision: number; document_hash: string;
  extractor: string; mode: "fields" | "notes"; status: "completed" | "failed";
  attempts: number; created_at: string; updated_at: string; replayed: boolean;
  error_code: "extraction_invalid" | "storage_failed" | null;
  items: { index: number; outcome: "created" | "duplicate" | "known" | "forgotten";
    memory_id: string | null; conflict_ids: string[] }[];
  trace: { stage: "source" | "extraction" | "deduplication" | "conflicts" | "storage";
    outcome: "completed" | "failed"; count: number }[];
};
export type Origin = {
  id: string; memory_id: string; memory_revision: number; source_id: string; source_revision: number;
  document_hash: string; start: number; end: number; excerpt: string; run_id: string; created_at: string;
};
export type Evidence = {
  id: string; kind: "memory_value" | "episode_time" | "document_excerpt" | "entity_label" | "relationship";
  path: string; field: string; value: string; source: string; belief: MemoryRecord["belief"];
  sensitivity: Sensitivity; revision: number | null; entity_id: string | null; confidence: number | null;
  observed_at: string | null; occurred_at: string | null; valid_from: string | null; valid_until: string | null;
  score: number; reasons: string[]; purpose: "answer" | "presentation" | "context";
};
export type PersonalAnswer = {
  run_id: string; mode: "personal-grounded-local";
  status: "known" | "partial" | "unknown" | "disputed" | "inferred" | "outdated" | "ambiguous";
  answer: string; evidence: Evidence[];
};
export type SemanticReview = {
  source_id: string; source_revision: number; selector: string; target_id: string | null;
  disclosure_revision: number; permitted: boolean; configured: boolean;
  sensitivity: "private" | "sensitive"; max_source_chars: number;
};
export type WorkbenchData = {
  sources: LearningSource[]; memories: MemoryRecord[]; runs: IngestionRun[]; entities: Entity[];
};

export class PersonalApiError extends Error {
  constructor(
    readonly status: number,
    readonly kind: "request" | "stale" | "invalid",
    readonly detail: string | null = null,
    readonly conflictRevisions: Record<string, number> | null = null,
  ) { super(kind); }
}

type ObjectValue = Record<string, unknown>;
type Guard<T> = (value: unknown) => value is T;
const object = (value: unknown): value is ObjectValue => !!value && typeof value === "object" && !Array.isArray(value);
const string = (value: unknown): value is string => typeof value === "string";
const text = (value: unknown): value is string => string(value) && value.length > 0;
const integer = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0;
const revision = (value: unknown): value is number => integer(value) && value >= 1;
const date = (value: unknown): value is string => text(value) && Number.isFinite(Date.parse(value));
const nullable = <T>(guard: Guard<T>) => (value: unknown): value is T | null => value === null || guard(value);
const array = <T>(guard: Guard<T>) => (value: unknown): value is T[] => Array.isArray(value) && value.every(guard);
const oneOf = <T extends string>(...options: T[]) => (value: unknown): value is T => string(value) && options.includes(value as T);
const sensitivity = oneOf("public", "private", "sensitive");
const belief = oneOf("known", "inferred", "disputed", "outdated", "unknown");
const confidence = (value: unknown): value is number | null => value === null || (
  typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1
);
const isMemory: Guard<MemoryRecord> = (value): value is MemoryRecord => object(value) &&
  ["id", "key", "content", "source", "owner_id"].every(key => text(value[key])) &&
  oneOf("fact", "preference", "event", "decision")(value.kind) &&
  oneOf("pending", "confirmed", "superseded")(value.status) && revision(value.revision) &&
  sensitivity(value.sensitivity) && nullable(text)(value.entity_id) && belief(value.belief) && confidence(value.confidence) &&
  ["valid_from", "valid_until", "occurred_at"].every(key => nullable(date)(value[key])) &&
  date(value.created_at) && date(value.updated_at) && oneOf("episodic", "semantic", "preference")(value.category) &&
  nullable(text)(value.superseded_by);
const isRevision: Guard<MemoryRevision> = (value): value is MemoryRevision => isMemory(value) &&
  oneOf("baseline", "created", "edited", "confirmed", "superseded", "corroborated")((value as MemoryRevision).change);
const isSource: Guard<LearningSource> = (value): value is LearningSource => object(value) &&
  ["id", "name", "owner_id"].every(key => text(value[key])) &&
  oneOf("document", "project", "conversation", "event")(value.kind) && sensitivity(value.sensitivity) &&
  nullable(text)(value.entity_id) && typeof value.approved === "boolean" && revision(value.revision) &&
  date(value.created_at) && date(value.updated_at);
const isEntity: Guard<Entity> = (value): value is Entity => object(value) && text(value.id) && text(value.name) &&
  oneOf("person", "project", "organization", "event", "idea", "preference", "decision")(value.kind) &&
  oneOf("pending", "confirmed")(value.status) && sensitivity(value.sensitivity) && array(text)(value.aliases) &&
  revision(value.revision) && text(value.owner_id) && value.source === "manual" && date(value.created_at) && date(value.updated_at);
const isEntityRevision: Guard<EntityRevision> = (value): value is EntityRevision => isEntity(value) &&
  oneOf("created", "edited", "confirmed")((value as EntityRevision).change);
const isRelationship: Guard<Relationship> = (value): value is Relationship => object(value) &&
  ["id", "owner_id", "from_entity_id", "to_entity_id", "evidence_id"].every(key => text(value[key])) &&
  text(value.predicate) && /^[a-z][a-z0-9_]{0,99}$/.test(value.predicate) && value.from_entity_id !== value.to_entity_id &&
  revision(value.evidence_revision) && revision(value.revision) && sensitivity(value.sensitivity) &&
  oneOf("pending", "confirmed")(value.status) && date(value.created_at) && date(value.updated_at);
const isRelationshipRevision: Guard<RelationshipRevision> = (value): value is RelationshipRevision => isRelationship(value) &&
  oneOf("created", "confirmed")((value as RelationshipRevision).change);
const isOwner: Guard<OwnerIdentity> = (value): value is OwnerIdentity => object(value) && text(value.owner_id) && nullable(text)(value.entity_id);
const isResolution: Guard<EntityResolution> = (value): value is EntityResolution => object(value) &&
  array(isEntity)(value.matches) && value.matches.every(item => item.status === "confirmed") &&
  (value.status === "unknown" && value.matches.length === 0 || value.status === "resolved" && value.matches.length === 1 ||
    value.status === "ambiguous" && value.matches.length > 1);
const isContext: Guard<IdentityContext> = (value): value is IdentityContext => object(value) &&
  array(isEntity)(value.entities) && array(isRelationship)(value.relationships) &&
  value.entities.every(item => item.status === "confirmed") && value.relationships.every(item => item.status === "confirmed" &&
    (value.entities as Entity[]).some(entity => entity.id === item.from_entity_id) &&
    (value.entities as Entity[]).some(entity => entity.id === item.to_entity_id));
const isRun: Guard<IngestionRun> = (value): value is IngestionRun => object(value) &&
  ["id", "source_id", "extractor"].every(key => text(value[key])) && revision(value.source_revision) &&
  string(value.document_hash) && /^[0-9a-f]{64}$/.test(value.document_hash) &&
  oneOf("fields", "notes")(value.mode) && oneOf("completed", "failed")(value.status) && revision(value.attempts) &&
  date(value.created_at) && date(value.updated_at) && typeof value.replayed === "boolean" &&
  nullable(oneOf("extraction_invalid", "storage_failed"))(value.error_code) &&
  Array.isArray(value.items) && value.items.every(item => object(item) && integer(item.index) &&
    oneOf("created", "duplicate", "known", "forgotten")(item.outcome) && nullable(text)(item.memory_id) && array(text)(item.conflict_ids)) &&
  Array.isArray(value.trace) && value.trace.every(item => object(item) &&
    oneOf("source", "extraction", "deduplication", "conflicts", "storage")(item.stage) &&
    oneOf("completed", "failed")(item.outcome) && integer(item.count));
const isOrigin: Guard<Origin> = (value): value is Origin => object(value) &&
  ["id", "memory_id", "source_id", "document_hash", "excerpt", "run_id"].every(key => text(value[key])) &&
  revision(value.memory_revision) && revision(value.source_revision) && integer(value.start) && integer(value.end) &&
  value.end > value.start && date(value.created_at);
const isEvidence: Guard<Evidence> = (value): value is Evidence => object(value) &&
  ["id", "path", "field", "value", "source"].every(key => text(value[key])) &&
  oneOf("memory_value", "episode_time", "document_excerpt", "entity_label", "relationship")(value.kind) &&
  belief(value.belief) && sensitivity(value.sensitivity) && nullable(revision)(value.revision) &&
  nullable(text)(value.entity_id) && confidence(value.confidence) &&
  ["observed_at", "occurred_at", "valid_from", "valid_until"].every(key => nullable(date)(value[key])) &&
  typeof value.score === "number" && Number.isFinite(value.score) && value.score >= 0 && value.score <= 1 &&
  array(oneOf("lexical", "field", "alias", "relationship", "intent", "preference"))(value.reasons) &&
  oneOf("answer", "presentation", "context")(value.purpose);
const isAnswer: Guard<PersonalAnswer> = (value): value is PersonalAnswer => object(value) && text(value.run_id) &&
  value.mode === "personal-grounded-local" && string(value.answer) &&
  oneOf("known", "partial", "unknown", "disputed", "inferred", "outdated", "ambiguous")(value.status) && array(isEvidence)(value.evidence);
const isDeletePreview: Guard<IdentityDeletePreview> = (value): value is IdentityDeletePreview => object(value) &&
  (value.kind === "entity" && isEntity(value.record) || value.kind === "relationship" && isRelationship(value.record)) &&
  text(value.digest) && /^[0-9a-f]{64}$/.test(value.digest) && array(isMemory)(value.memories) && array(isSource)(value.sources) &&
  array(isRun)(value.runs) && array(isRelationship)(value.relationships) && typeof value.owner_binding === "boolean" &&
  integer(value.origin_count) && integer(value.history_count) && (value.kind !== "relationship" ||
    !value.memories.length && !value.sources.length && !value.runs.length && !value.relationships.length && !value.owner_binding);
const isSemanticReview: Guard<SemanticReview> = (value): value is SemanticReview => object(value) && text(value.source_id) &&
  revision(value.source_revision) && text(value.selector) && /^learning-source\/[0-9a-f]{64}$/.test(value.selector) &&
  revision(value.disclosure_revision) && typeof value.permitted === "boolean" && typeof value.configured === "boolean" &&
  oneOf("private", "sensitive")(value.sensitivity) && integer(value.max_source_chars) &&
  (value.configured ? text(value.target_id) && /^[0-9a-f]{64}$/.test(value.target_id) : value.target_id === null && !value.permitted);
const isMutation = (value: unknown): value is { status: "pending" | "confirmed"; revision: number } =>
  object(value) && oneOf("pending", "confirmed")(value.status) && revision(value.revision);
const apiBase = (import.meta.env.VITE_API_BASE_URL ?? "").trim().replace(/\/+$/, "");
const idPath = (id: string) => encodeURIComponent(id);

export function createPersonalClient(token: string, signal: AbortSignal) {
  async function request<T>(path: string, guard: Guard<T>, body?: unknown): Promise<T> {
    const response = await fetch(`${apiBase}/api/v1/personal${path}`, {
      method: body === undefined ? "GET" : "POST", signal, cache: "no-store",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    let value: unknown;
    try { value = await response.json(); }
    catch (error) {
      if (signal.aborted) throw error;
      throw new PersonalApiError(response.status, response.ok ? "invalid" : "request");
    }
    if (!response.ok) {
      const detail = object(value) ? value.detail : null;
      const conflicts = object(detail) && object(detail.conflict_revisions) &&
        Object.values(detail.conflict_revisions).every(revision) && array(text)(detail.conflict_ids) &&
        Object.keys(detail.conflict_revisions).length === detail.conflict_ids.length &&
        detail.conflict_ids.every(id => Object.hasOwn(detail.conflict_revisions as object, id))
        ? detail.conflict_revisions as Record<string, number> : null;
      throw new PersonalApiError(response.status, response.status === 409 ? "stale" : "request", string(detail) ? detail : null, conflicts);
    }
    if (!guard(value)) throw new PersonalApiError(502, "invalid");
    return value;
  }
  return {
    async load(): Promise<WorkbenchData> {
      const [sources, memories, runs, entities] = await Promise.all([
        request("/learning/sources", array(isSource)), request("/entries?include_superseded=true", array(isMemory)),
        request("/learning/runs", array(isRun)), request("/identity/entities", array(isEntity)),
      ]);
      return { sources, memories, runs, entities };
    },
    async loadIdentity(): Promise<IdentityData> {
      const [owner, relationships] = await Promise.all([
        request("/identity/owner", isOwner), request("/identity/relationships", array(isRelationship)),
      ]);
      if (relationships.some(item => item.owner_id !== owner.owner_id)) throw new PersonalApiError(502, "invalid");
      return { owner, relationships };
    },
    createEntity: (input: EntityInput, distinct: boolean) => request("/identity/entities", isEntity, { ...input, distinct }),
    editEntity: (entity: Entity, input: EntityInput) => request(`/identity/entities/${idPath(entity.id)}/edit`, isEntity,
      { ...input, expected_revision: entity.revision }),
    confirmEntity: (entity: Entity) => request(`/identity/entities/${idPath(entity.id)}/confirm`, isEntity, { expected_revision: entity.revision }),
    async entityHistory(entity: Entity) {
      const rows = await request(`/identity/entities/${idPath(entity.id)}/history`, array(isEntityRevision));
      if (rows.some(item => item.id !== entity.id)) throw new PersonalApiError(502, "invalid");
      if (rows.at(-1)?.revision !== entity.revision) throw new PersonalApiError(409, "stale");
      return rows;
    },
    async relationshipHistory(relationship: Relationship) {
      const rows = await request(`/identity/relationships/${idPath(relationship.id)}/history`, array(isRelationshipRevision));
      if (rows.some(item => item.id !== relationship.id)) throw new PersonalApiError(502, "invalid");
      if (rows.at(-1)?.revision !== relationship.revision) throw new PersonalApiError(409, "stale");
      return rows;
    },
    async bindOwner(owner: OwnerIdentity, target: Entity | null) {
      const result = await request("/identity/owner", isOwner, {
        entity_id: target?.id ?? null, expected_owner_entity_id: owner.entity_id,
        ...(target ? { expected_entity_revision: target.revision } : {}),
      });
      if (result.owner_id !== owner.owner_id || result.entity_id !== (target?.id ?? null)) throw new PersonalApiError(502, "invalid");
      return result;
    },
    async resolve(name: string, kind: Entity["kind"] | null, allowSensitive: boolean) {
      const result = await request("/identity/resolve", isResolution, { name, kind, allow_sensitive: allowSensitive });
      if (!allowSensitive && result.matches.some(item => item.sensitivity === "sensitive")) throw new PersonalApiError(502, "invalid");
      return result;
    },
    async neighbours(entity: Entity, allowSensitive: boolean) {
      const result = await request(`/identity/entities/${idPath(entity.id)}/neighbours?allow_sensitive=${allowSensitive}`, isContext);
      if (result.entities.length && !result.entities.some(item => item.id === entity.id) ||
        [...result.entities, ...result.relationships].some(item => item.owner_id !== entity.owner_id) ||
        result.relationships.some(item => item.from_entity_id !== entity.id && item.to_entity_id !== entity.id)) {
        throw new PersonalApiError(502, "invalid");
      }
      if (!allowSensitive && [...result.entities, ...result.relationships].some(item => item.sensitivity === "sensitive")) {
        throw new PersonalApiError(502, "invalid");
      }
      return result;
    },
    createRelationship: (left: Entity, right: Entity, evidence: MemoryRecord, predicate: string, sensitivity: Sensitivity) =>
      request("/identity/relationships", isRelationship, {
        from_entity_id: left.id, to_entity_id: right.id, evidence_id: evidence.id, predicate, sensitivity,
        expected_evidence_revision: evidence.revision, expected_entity_revisions: { [left.id]: left.revision, [right.id]: right.revision },
      }),
    confirmRelationship: (relationship: Relationship, left: Entity, right: Entity) => request(
      `/identity/relationships/${idPath(relationship.id)}/confirm`, isRelationship,
      { expected_revision: relationship.revision, expected_entity_revisions: { [left.id]: left.revision, [right.id]: right.revision } },
    ),
    async previewIdentityDelete(record: Entity | Relationship, kind: "entity" | "relationship") {
      const plural = kind === "entity" ? "entities" : "relationships";
      const preview = await request(`/identity/${plural}/${idPath(record.id)}/delete-preview`, isDeletePreview);
      if (preview.kind !== kind || preview.record.id !== record.id) throw new PersonalApiError(502, "invalid");
      if (preview.record.revision !== record.revision) throw new PersonalApiError(409, "stale");
      return preview;
    },
    deleteIdentity: (preview: IdentityDeletePreview) => request(
      `/identity/${preview.kind === "entity" ? "entities" : "relationships"}/${idPath(preview.record.id)}/delete`,
      (value): value is { deleted: boolean } => object(value) && value.deleted === true,
      { expected_revision: preview.record.revision, digest: preview.digest },
    ),
    register: (body: Pick<LearningSource, "kind" | "name" | "sensitivity" | "entity_id">) => request("/learning/sources", isSource, body),
    reviewSource: (source: LearningSource) => request(`/learning/sources/${idPath(source.id)}/review`, isSource,
      { approved: !source.approved, expected_revision: source.revision }),
    ingest: (source: LearningSource, content: string, mode: "fields" | "notes") => request(`/learning/sources/${idPath(source.id)}/ingest`, isRun,
      { content, mode, expected_source_revision: source.revision }),
    async semanticReview(source: LearningSource) {
      const value = await request(`/learning/sources/${idPath(source.id)}/semantic-review`, isSemanticReview);
      if (value.source_id !== source.id) throw new PersonalApiError(502, "invalid");
      if (value.source_revision !== source.revision) throw new PersonalApiError(409, "stale");
      return value;
    },
    async ingestSemantic(source: LearningSource, content: string, review: SemanticReview, allowSensitive: boolean) {
      if (!review.configured || !review.permitted || review.source_id !== source.id || review.source_revision !== source.revision) {
        throw new PersonalApiError(409, "stale");
      }
      const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(content));
      const hash = Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, "0")).join("");
      return request(`/learning/sources/${idPath(source.id)}/ingest-semantic`, isRun, {
        content, mode: "notes", expected_source_revision: source.revision,
        expected_disclosure_revision: review.disclosure_revision, reviewed_target_id: review.target_id,
        reviewed_content_hash: hash, allow_provider: true, allow_sensitive: allowSensitive,
      });
    },
    confirm: (memory: MemoryRecord, replacements: Record<string, number> = {}) => request(`/entries/${idPath(memory.id)}/confirm`, isMutation,
      { expected_revision: memory.revision, replace_ids: Object.keys(replacements), replace_revisions: replacements }),
    edit: (memory: MemoryRecord, content: string) => request(`/entries/${idPath(memory.id)}/edit`, isMutation,
      { kind: memory.kind, key: memory.key, content, expected_revision: memory.revision }),
    remove: (memory: MemoryRecord) => request(`/entries/${idPath(memory.id)}/delete`,
      (value): value is { deleted: boolean } => object(value) && value.deleted === true, { expected_revision: memory.revision }),
    async inspect(memory: MemoryRecord) {
      const [history, origins] = await Promise.all([
        request(`/entries/${idPath(memory.id)}/history`, array(isRevision)),
        request(`/entries/${idPath(memory.id)}/origins`, array(isOrigin)),
      ]);
      if (history.some(item => item.id !== memory.id) || origins.some(item => item.memory_id !== memory.id)) {
        throw new PersonalApiError(502, "invalid");
      }
      if (!history.length || history.at(-1)?.revision !== memory.revision) {
        throw new PersonalApiError(409, "stale");
      }
      return { memory, history, origins };
    },
    ask: (question: string, allowSensitive: boolean, entityId?: string) => request("/ask", isAnswer, { question, allow_sensitive: allowSensitive, ...(entityId ? { entity_id: entityId } : {}) }),
  };
}

export function ingestionWithinLimits(content: string): boolean {
  return [...content].length <= 80_000 && new TextEncoder().encode(content).length <= 200_000;
}
