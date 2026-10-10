export const eraseKinds = ["task", "note", "action", "source", "archive"] as const;
export type EraseKind = (typeof eraseKinds)[number];
export type ErasureRequest = {
  kind: EraseKind; id: string; expected_owner_id: string; expected_revision: number | null;
  purge_output: boolean; expected_output_revision: number | null; forget_memories: boolean;
};
const tables = ["tasks", "notes", "action_plans", "action_events", "entries", "revisions", "sources", "ingestion_runs", "origins", "relationships", "relationships_revisions", "memory_digests", "forgotten", "import_archives"] as const;
export type ErasureRef = { table: (typeof tables)[number]; key: string; id: string; revision: number | null; label: string };
export type ErasureChoice = { kind: EraseKind; record: ErasureRef };
export type ErasureCatalogue = { owner_id: string; items: ErasureChoice[] };
export type ErasurePreview = { request: ErasureRequest; target: ErasureRef; digest: string; removed: ErasureRef[]; updated: ErasureRef[]; added: ErasureRef[]; retained: ErasureRef[] };
export type ErasureResult = { deleted: true; request: ErasureRequest; digest: string; removed_counts: Record<string, number>; retained_counts: Record<string, number>; forgotten_memories: number };
export const targetTables: Record<EraseKind, ErasureRef["table"]> = { task: "tasks", note: "notes", action: "action_plans", source: "sources", archive: "import_archives" };
export function sameErasureRequest(a: ErasureRequest, b: ErasureRequest, resolveOutput = false): boolean {
  return (["kind", "id", "expected_owner_id", "expected_revision", "purge_output", "expected_output_revision", "forget_memories"] as const).every(field =>
    field === "expected_output_revision" && resolveOutput && a.expected_output_revision === null || a[field] === b[field]);
}
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const string = (v: unknown): v is string => typeof v === "string";
const text = (v: unknown): v is string => string(v) && v.length > 0;
const rev = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) > 0;
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const hash = (v: unknown): v is string => string(v) && /^[0-9a-f]{64}$/.test(v);
const kind = (v: unknown): v is EraseKind => string(v) && eraseKinds.includes(v as EraseKind);
export const isErasureRef = (v: unknown): v is ErasureRef => object(v) && string(v.table) && tables.includes(v.table as ErasureRef["table"]) && hash(v.key) && text(v.id) && (v.revision === null || rev(v.revision)) && text(v.label);
const refs = (v: unknown): v is ErasureRef[] => Array.isArray(v) && v.every(isErasureRef) && new Set(v.map(row => row.table + "/" + row.key)).size === v.length;
export const isErasureRequest = (v: unknown): v is ErasureRequest => object(v) && kind(v.kind) && text(v.id) && text(v.expected_owner_id) &&
  (v.kind === "archive" ? v.expected_revision === null : rev(v.expected_revision)) && typeof v.purge_output === "boolean" && typeof v.forget_memories === "boolean" &&
  (v.kind === "action" || !v.purge_output) && (v.kind === "source" || !v.forget_memories) &&
  (v.purge_output ? v.expected_output_revision === null || rev(v.expected_output_revision) : v.expected_output_revision === null);
export const isErasureCatalogue = (v: unknown): v is ErasureCatalogue => object(v) && text(v.owner_id) && Array.isArray(v.items) &&
  v.items.every(row => object(row) && kind(row.kind) && isErasureRef(row.record) && row.record.table === targetTables[row.kind] && (row.kind === "archive" ? row.record.revision === null : rev(row.record.revision))) &&
  new Set(v.items.map(row => row.kind + "/" + row.record.id)).size === v.items.length;
export const isErasurePreview = (v: unknown): v is ErasurePreview => {
  if (!object(v) || !isErasureRequest(v.request) || !isErasureRef(v.target) || !hash(v.digest) || !refs(v.removed) || !refs(v.updated) || !refs(v.added) || !refs(v.retained)) return false;
  const target = v.target;
  if (target.table !== targetTables[v.request.kind] || target.id !== v.request.id || target.revision !== v.request.expected_revision ||
    v.request.purge_output && !rev(v.request.expected_output_revision) || !v.removed.some(row => row.table === target.table && row.key === target.key)) return false;
  const removed = new Set(v.removed.map(row => row.table + "/" + row.key));
  const updated = new Set(v.updated.map(row => row.table + "/" + row.key));
  const added = new Set(v.added.map(row => row.table + "/" + row.key));
  if (v.updated.some(row => removed.has(row.table + "/" + row.key)) || v.added.some(row => removed.has(row.table + "/" + row.key) || updated.has(row.table + "/" + row.key)) ||
    v.retained.some(row => [removed, updated, added].some(set => set.has(row.table + "/" + row.key)))) return false;
  return v.added.every(row => row.table === "forgotten") && v.updated.every(row => row.table === "forgotten");
};
const counts = (v: unknown): v is Record<string, number> => object(v) && Object.entries(v).every(([table, n]) => tables.includes(table as ErasureRef["table"]) && count(n));
export const isErasureResult = (v: unknown): v is ErasureResult => object(v) && v.deleted === true && isErasureRequest(v.request) && hash(v.digest) && counts(v.removed_counts) && counts(v.retained_counts) && count(v.forgotten_memories);
