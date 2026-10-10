import type { Sensitivity } from "./personalApi";

export const toolNames = ["tasks.create", "tasks.complete", "notes.create"] as const;
/** Operation IDs are not credentials; use CSPRNG bytes without a secure-context-only UUID helper. */
export function newOperationKey(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return "web-" + Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
}
export type ToolName = (typeof toolNames)[number];
export type Invocation = {
  tool: ToolName; arguments: TaskArgs | CompleteArgs | NoteArgs; idempotency_key: string;
  sensitivity: Sensitivity; source_ids: string[]; intent: "recommend" | "act";
};
export type TaskArgs = { title: string; description: string; due_at: string | null; project_id: string | null };
export type CompleteArgs = { task_id: string; expected_revision: number };
export type NoteArgs = { title: string; content: string; project_id: string | null };
export type PermissionInput = { enabled: boolean; labels: Sensitivity[]; entity_ids: string[] | null };
export type ToolPermission = PermissionInput & {
  tool: ToolName; owner_id: string; scope: "workspace_tasks" | "workspace_notes"; revision: number;
};
export type ActionPlan = {
  id: string; owner_id: string; invocation: Invocation; permission_revision: number;
  source_revisions: Record<string, number>; entity_revisions: Record<string, number>;
  digest: string; request_digest: string; revision: number;
  status: "recommended" | "planned" | "approved" | "completed" | "failed" | "rolled_back" | "cancelled";
  attempts: number; result: { table: "tasks" | "notes"; id: string; revision: number; changed: boolean } | null;
  undo: { before_status?: "open" | "completed" } | null;
  approved_digest: string | null; created_at: string; updated_at: string;
};
export type TaskRecord = TaskArgs & {
  id: string; owner_id: string; created_by: string; sensitivity: Sensitivity; source_ids: string[];
  status: "open" | "completed"; revision: number; created_at: string; updated_at: string;
};
export type NoteRecord = NoteArgs & Omit<TaskRecord, keyof TaskArgs | "status">;
export type ActionEvent = {
  id: string; plan_id: string; stage: "intent" | "plan" | "approval" | "execution" | "rollback" | "cancellation";
  outcome: "recommended" | "planned" | "approved" | "completed" | "blocked" | "failed" | "rolled_back" | "cancelled";
  code: string; created_at: string;
};
export type AgencyData = { owner_id: string; permissions: ToolPermission[]; plans: ActionPlan[]; tasks: TaskRecord[]; notes: NoteRecord[] };

type ObjectValue = Record<string, unknown>;
const object = (v: unknown): v is ObjectValue => !!v && typeof v === "object" && !Array.isArray(v);
const string = (v: unknown): v is string => typeof v === "string";
const nonempty = (v: unknown): v is string => string(v) && v.length > 0;
const bounded = (v: unknown, max: number, blank = false): v is string => string(v) &&
  [...v].length <= max && v === v.trim() && (blank || v.trim().length > 0);
const rev = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) > 0;
const date = (v: unknown): v is string => nonempty(v) && Number.isFinite(Date.parse(v)) && /(?:Z|[+-]\d\d:\d\d)$/.test(v);
const optional = (v: unknown, guard: (v: unknown) => boolean) => v === null || guard(v);
const enumValue = (v: unknown, options: readonly string[]) => string(v) && options.includes(v);
const label = (v: unknown): v is Sensitivity => enumValue(v, ["public", "private", "sensitive"]);
const ids = (v: unknown, max = Infinity): v is string[] => Array.isArray(v) && v.length <= max && v.every(nonempty) && new Set(v).size === v.length;
const versions = (v: unknown): v is Record<string, number> => object(v) && Object.entries(v).every(([id, version]) => id.length > 0 && rev(version));
const hash = (v: unknown): v is string => string(v) && /^[a-f0-9]{64}$/.test(v);
const keys = (v: ObjectValue, names: string[]) => Object.keys(v).length === names.length && names.every(name => Object.hasOwn(v, name));
const taskArgs = (v: unknown): v is TaskArgs => object(v) && bounded(v.title, 160) && bounded(v.description, 2000, true) && optional(v.due_at, date) && optional(v.project_id, nonempty);
const noteArgs = (v: unknown): v is NoteArgs => object(v) && bounded(v.title, 160) && bounded(v.content, 8000) && optional(v.project_id, nonempty);
const completeArgs = (v: unknown): v is CompleteArgs => object(v) && nonempty(v.task_id) && rev(v.expected_revision);
export const isInvocation = (v: unknown): v is Invocation => object(v) &&
  enumValue(v.tool, toolNames) && nonempty(v.idempotency_key) && [...v.idempotency_key].length <= 100 && label(v.sensitivity) && ids(v.source_ids, 20) &&
  enumValue(v.intent, ["recommend", "act"]) && object(v.arguments) && (
    v.tool === "tasks.create" && taskArgs(v.arguments) && keys(v.arguments, ["title", "description", "due_at", "project_id"]) ||
    v.tool === "tasks.complete" && completeArgs(v.arguments) && keys(v.arguments, ["task_id", "expected_revision"]) ||
    v.tool === "notes.create" && noteArgs(v.arguments) && keys(v.arguments, ["title", "content", "project_id"])
  );
export const isPermission = (v: unknown): v is ToolPermission => object(v) && enumValue(v.tool, toolNames) && nonempty(v.owner_id) &&
  v.scope === (v.tool === "notes.create" ? "workspace_notes" : "workspace_tasks") && typeof v.enabled === "boolean" &&
  Array.isArray(v.labels) && v.labels.length <= 3 && v.labels.every(label) &&
  optional(v.entity_ids, value => Array.isArray(value) && value.length <= 100 && value.every(nonempty)) && rev(v.revision);
export const isPlan = (v: unknown): v is ActionPlan => {
  if (!object(v) || !nonempty(v.id) || !nonempty(v.owner_id) || !isInvocation(v.invocation) ||
    !rev(v.permission_revision) || !versions(v.source_revisions) || !versions(v.entity_revisions) || !hash(v.digest) || !hash(v.request_digest) ||
    !rev(v.revision) || !date(v.created_at) || !date(v.updated_at) || !Number.isSafeInteger(v.attempts) || (v.attempts as number) < 0 || (v.attempts as number) > 3 ||
    !enumValue(v.status, ["recommended", "planned", "approved", "completed", "failed", "rolled_back", "cancelled"]) ||
    Object.keys(v.source_revisions).length !== v.invocation.source_ids.length || !v.invocation.source_ids.every(id => Object.hasOwn(v.source_revisions as object, id)) ||
    !optional(v.approved_digest, hash) || v.approved_digest !== null && v.approved_digest !== v.digest) return false;
  if (v.invocation.intent === "recommend" && !["recommended", "cancelled"].includes(v.status as string) ||
    v.invocation.intent === "act" && v.status === "recommended") return false;
  if (["completed", "rolled_back"].includes(v.status as string)) {
    return object(v.result) && nonempty(v.result.id) && rev(v.result.revision) && typeof v.result.changed === "boolean" &&
      v.result.table === (v.invocation.tool === "notes.create" ? "notes" : "tasks") && object(v.undo) &&
      (v.invocation.tool === "tasks.complete" ? keys(v.undo, ["before_status"]) && enumValue(v.undo.before_status, ["open", "completed"]) : keys(v.undo, [])) &&
      (v.attempts as number) >= 1 && v.approved_digest === v.digest;
  }
  if (v.result !== null || v.undo !== null) return false;
  if (["approved", "failed"].includes(v.status as string) && v.approved_digest !== v.digest) return false;
  if (["planned", "recommended"].includes(v.status as string) && (v.approved_digest !== null || v.attempts !== 0)) return false;
  return v.status !== "failed" || (v.attempts as number) >= 1;
};
const output = (v: ObjectValue) => nonempty(v.id) && nonempty(v.owner_id) && nonempty(v.created_by) && label(v.sensitivity) && ids(v.source_ids) && rev(v.revision) && date(v.created_at) && date(v.updated_at);
export const isTask = (v: unknown): v is TaskRecord => object(v) && enumValue(v.status, ["open", "completed"]) && output(v) && taskArgs(v);
export const isNote = (v: unknown): v is NoteRecord => object(v) && noteArgs(v) && output(v);
export const isEvent = (v: unknown): v is ActionEvent => object(v) && nonempty(v.id) && nonempty(v.plan_id) &&
  enumValue(v.stage, ["intent", "plan", "approval", "execution", "rollback", "cancellation"]) &&
  enumValue(v.outcome, ["recommended", "planned", "approved", "completed", "blocked", "failed", "rolled_back", "cancelled"]) && nonempty(v.code) && date(v.created_at);
export const rows = <T>(guard: (value: unknown) => value is T) => (value: unknown): value is T[] => Array.isArray(value) && value.every(guard) &&
  new Set(value.map(item => (item as { id?: string; tool?: string }).id ?? (item as { tool?: string }).tool)).size === value.length;
