export type DestinationState = { owner_id: string; empty: boolean; max_snapshot_bytes: number; max_request_body_bytes: number };
export type ImportReview = {
  digest: string; source_version: 6 | 7 | 8; owner_id: string; destination_owner_id: string;
  counts: Record<string, number>; tool_permissions_restored: false; executable_plans_restored: false;
  learning_sources_require_review: true; provider_permissions_restored: false;
};
export type ImportReceipt = ImportReview & { imported: true; archive_id: string };
export type AuditEvent = { id: string; owner_id: string; actor: "core" | "api" | "cli"; operation: string; outcome: "succeeded" | "denied" | "failed"; counts: Record<string, number>; created_at: string };
export type RawSnapshot = { raw: string; ownerId: string; version: 6 | 7 | 8; bytes: number };
export class SnapshotFileError extends Error { constructor(readonly kind: "invalid" | "tooLarge" | "readFailed") { super(kind); } }
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === "string" && v.length > 0;
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const hash = (v: unknown): v is string => typeof v === "string" && /^[0-9a-f]{64}$/.test(v);
const counts = (v: unknown): v is Record<string, number> => object(v) && Object.entries(v).every(([key, n]) => /^[a-z_]{1,40}$/.test(key) && count(n));
export const isDestination = (v: unknown): v is DestinationState => object(v) && text(v.owner_id) && typeof v.empty === "boolean" &&
  count(v.max_snapshot_bytes) && v.max_snapshot_bytes >= 1 && v.max_snapshot_bytes <= 16 * 1024 * 1024 &&
  count(v.max_request_body_bytes) && v.max_request_body_bytes >= 1024 && v.max_request_body_bytes <= 10_000_000;
export const isImportReview = (v: unknown): v is ImportReview => object(v) && hash(v.digest) && [6, 7, 8].includes(v.source_version as number) &&
  text(v.owner_id) && text(v.destination_owner_id) && counts(v.counts) && v.tool_permissions_restored === false && v.executable_plans_restored === false && v.learning_sources_require_review === true && v.provider_permissions_restored === false;
export const isImportReceipt = (v: unknown): v is ImportReceipt => object(v) && v.imported === true && text(v.archive_id) && isImportReview(v);
export const isAuditRows = (v: unknown): v is AuditEvent[] => Array.isArray(v) && v.length <= 1000 && v.every(row => object(row) &&
  text(row.id) && text(row.owner_id) && ["core", "api", "cli"].includes(row.actor as string) && ["succeeded", "denied", "failed"].includes(row.outcome as string) &&
  typeof row.operation === "string" && /^[a-z][a-z0-9_.]{0,79}$/.test(row.operation) && counts(row.counts) && Object.keys(row.counts).length <= 10 && text(row.created_at) && Number.isFinite(Date.parse(row.created_at)) && /(?:Z|[+-]\d\d:\d\d)$/.test(row.created_at)) && new Set(v.map(row => row.id)).size === v.length;

/** Detect duplicate decoded keys before JSON.parse can discard them; never reflect token errors. */
export function strictSnapshotJson(raw: string): Record<string, unknown> {
  const frames: ({ keys: Set<string>; key: boolean } | null)[] = [];
  try {
    for (let i = 0; i < raw.length; i++) {
      const char = raw[i];
      if (char === "{" || char === "[") frames.push(char === "{" ? { keys: new Set(), key: true } : null);
      else if (char === "}" || char === "]") frames.pop();
      else if (char === ",") { const frame = frames.at(-1); if (frame) frame.key = true; }
      else if (char === '"') {
        const start = i++;
        while (i < raw.length && raw[i] !== '"') { if (raw[i] === "\\") i++; i++; }
        const value = JSON.parse(raw.slice(start, i + 1)) as string;
        // UTF-8 input can still contain invalid surrogate escapes in a JSON string.
        for (let j = 0; j < value.length; j++) {
          const code = value.charCodeAt(j);
          if (code >= 0xd800 && code <= 0xdbff) { const next = value.charCodeAt(++j); if (!(next >= 0xdc00 && next <= 0xdfff)) throw new Error(); }
          else if (code >= 0xdc00 && code <= 0xdfff) throw new Error();
        }
        const frame = frames.at(-1);
        if (frame?.key) { if (frame.keys.has(value)) throw new Error(); frame.keys.add(value); frame.key = false; }
      }
    }
    const parsed: unknown = JSON.parse(raw);
    if (!object(parsed)) throw new Error();
    const pending: unknown[] = [parsed];
    while (pending.length) {
      const value = pending.pop();
      if (typeof value === "number" && !Number.isFinite(value)) throw new Error();
      if (Array.isArray(value)) for (const child of value) pending.push(child);
      else if (object(value)) for (const child of Object.values(value)) pending.push(child);
    }
    return parsed;
  } catch { throw new SnapshotFileError("invalid"); }
}

export function snapshotBody(snapshot: RawSnapshot, destination: string, digest?: string): string {
  return `{"snapshot":${snapshot.raw},"expected_destination_owner_id":${JSON.stringify(destination)}${digest ? `,"digest":${JSON.stringify(digest)}` : ""}}`;
}
export function snapshotFits(snapshot: RawSnapshot, state: DestinationState): boolean {
  return snapshot.bytes <= state.max_snapshot_bytes && new TextEncoder().encode(snapshotBody(snapshot, state.owner_id, "0".repeat(64))).length <= state.max_request_body_bytes;
}
export async function readSnapshot(file: File, state: DestinationState, signal: AbortSignal): Promise<RawSnapshot> {
  if (file.size > state.max_snapshot_bytes || file.size > 16 * 1024 * 1024) throw new SnapshotFileError("tooLarge");
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  let data: ArrayBuffer;
  try { data = await file.arrayBuffer(); } catch { throw new SnapshotFileError("readFailed"); }
  if (signal.aborted) throw new DOMException("Aborted", "AbortError");
  if (data.byteLength > state.max_snapshot_bytes) throw new SnapshotFileError("tooLarge");
  let raw: string;
  try {
    const decoded = new TextDecoder("utf-8", { fatal: true }).decode(data);
    let start = 0; let end = decoded.length;
    while (start < end && " \t\r\n".includes(decoded[start])) start++;
    while (end > start && " \t\r\n".includes(decoded[end - 1])) end--;
    raw = decoded.slice(start, end);
  } catch { throw new SnapshotFileError("invalid"); }
  const header = strictSnapshotJson(raw);
  if (![6, 7, 8].includes(header.version as number) || !text(header.owner_id)) throw new SnapshotFileError("invalid");
  // Keep original numeric tokens: re-serializing JSON.parse would round large revision integers.
  const snapshot: RawSnapshot = { raw, ownerId: header.owner_id, version: header.version as 6 | 7 | 8, bytes: data.byteLength };
  if (!snapshotFits(snapshot, state)) throw new SnapshotFileError("tooLarge");
  return snapshot;
}
