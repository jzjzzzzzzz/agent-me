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
  oneOf("pending", "confirmed")(value.status) && sensitivity(value.sensitivity);
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
    register: (body: Pick<LearningSource, "kind" | "name" | "sensitivity" | "entity_id">) => request("/learning/sources", isSource, body),
    reviewSource: (source: LearningSource) => request(`/learning/sources/${idPath(source.id)}/review`, isSource,
      { approved: !source.approved, expected_revision: source.revision }),
    ingest: (source: LearningSource, content: string, mode: "fields" | "notes") => request(`/learning/sources/${idPath(source.id)}/ingest`, isRun,
      { content, mode, expected_source_revision: source.revision }),
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
    ask: (question: string, allowSensitive: boolean) => request("/ask", isAnswer, { question, allow_sensitive: allowSensitive }),
  };
}

export function ingestionWithinLimits(content: string): boolean {
  return [...content].length <= 80_000 && new TextEncoder().encode(content).length <= 200_000;
}
