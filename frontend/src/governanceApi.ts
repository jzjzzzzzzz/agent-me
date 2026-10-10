import type { MemoryKind, Sensitivity } from "./personalApi";
export type LearningPolicy = { source_kinds: ("document" | "project" | "conversation" | "event")[]; labels: Sensitivity[]; max_candidates: number; blocked_key_prefixes: string[]; require_revision_labels: Sensitivity[]; require_revision_key_prefixes: string[] };
export const retentionFields = ["pending_days", "superseded_days", "expired_days", "history_days", "run_days"] as const;
export type RetentionPolicy = Record<(typeof retentionFields)[number], number | null>;
export type Settings<T> = { revision: number; policy: T };
export type RetentionTarget = { table: "entries" | "turns" | "ingestion_runs"; id: string; revision: number | null; fingerprint: string | null };
export type RetentionPlan = { id: string; owner_id: string; status: "planned" | "applied"; policy_revision: number; as_of: string; created_at: string; targets: RetentionTarget[]; deleted_counts: Record<RetentionTarget["table"], number> };
export type RetentionReview = { plan: RetentionPlan; digest: string; scope_digest: string; removed_counts: Record<string, number>; forgetting_counts: Record<string, number>; retained_counts: Record<string, number> };
export type ConsolidationPlan = { id: string; owner_id: string; status: "planned" | "applied"; digest: string; created_at: string; merged_count: number; groups: { keeper_id: string; members: { id: string; revision: number; fingerprint: string }[] }[] };
export type ConsolidationFilter = { entity_id: string | null; key_prefix: string | null; kinds: MemoryKind[] | null };
export type GovernanceData = { owner_id: string; observed_at: string; learning: Settings<LearningPolicy>; retention: Settings<RetentionPolicy>; retention_plans: RetentionPlan[]; consolidation_plans: ConsolidationPlan[] };
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === "string" && v.length > 0;
const count = (v: unknown): v is number => Number.isSafeInteger(v) && (v as number) >= 0;
const rev = (v: unknown): v is number => count(v) && v > 0;
const hash = (v: unknown): v is string => typeof v === "string" && /^[0-9a-f]{64}$/.test(v);
const date = (v: unknown): v is string => text(v) && Number.isFinite(Date.parse(v)) && /(?:Z|[+-]\d\d:\d\d)$/.test(v);
const choices = (v: unknown, options: string[], max: number): v is string[] => Array.isArray(v) && v.length <= max && v.every(value => typeof value === "string" && options.includes(value));
const prefixes = (v: unknown): v is string[] => Array.isArray(v) && v.length <= 20 && v.every(value => text(value) && value.trim().length > 0 && [...value].length <= 100);
const counts = (v: unknown): v is Record<string, number> => object(v) && Object.entries(v).every(([key, n]) => /^[a-z_]{1,40}$/.test(key) && count(n));
export const isLearningPolicy = (v: unknown): v is LearningPolicy => object(v) && Object.keys(v).length === 6 && choices(v.source_kinds, ["document", "project", "conversation", "event"], 4) && choices(v.labels, ["public", "private", "sensitive"], 3) &&
  rev(v.max_candidates) && v.max_candidates <= 100 && prefixes(v.blocked_key_prefixes) && prefixes(v.require_revision_key_prefixes) && choices(v.require_revision_labels, ["public", "private", "sensitive"], 3);
export const isRetentionPolicy = (v: unknown): v is RetentionPolicy => object(v) && Object.keys(v).length === retentionFields.length && retentionFields.every(field => v[field] === null || rev(v[field]) && (v[field] as number) <= 365000);
export const isLearningSettings = (v: unknown): v is Settings<LearningPolicy> => object(v) && rev(v.revision) && isLearningPolicy(v.policy);
export const isRetentionSettings = (v: unknown): v is Settings<RetentionPolicy> => object(v) && rev(v.revision) && isRetentionPolicy(v.policy);
export const isRetentionPlan = (v: unknown): v is RetentionPlan => object(v) && text(v.id) && text(v.owner_id) && ["planned", "applied"].includes(v.status as string) && rev(v.policy_revision) && date(v.as_of) && date(v.created_at) &&
  Array.isArray(v.targets) && v.targets.length <= 1000 && v.targets.every(row => object(row) && text(row.id) && (row.table === "entries" ? rev(row.revision) && row.fingerprint === null : ["turns", "ingestion_runs"].includes(row.table as string) && row.revision === null && hash(row.fingerprint))) &&
  new Set(v.targets.map(row => row.table + "/" + row.id)).size === v.targets.length && object(v.deleted_counts) && ["entries", "turns", "ingestion_runs"].every(table => count((v.deleted_counts as Record<string, unknown>)[table])) &&
  (v.status !== "planned" || Object.values(v.deleted_counts).every(n => n === 0));
export const isConsolidationPlan = (v: unknown): v is ConsolidationPlan => {
  if (!object(v) || !text(v.id) || !text(v.owner_id) || !["planned", "applied"].includes(v.status as string) || !hash(v.digest) || !date(v.created_at) || !count(v.merged_count) || !Array.isArray(v.groups) || v.groups.length > 100) return false;
  const ids = new Set<string>(); let total = 0; let merged = 0;
  for (const group of v.groups) {
    if (!object(group) || !text(group.keeper_id) || !Array.isArray(group.members) || group.members.length < 2 || !group.members.some(row => object(row) && row.id === group.keeper_id)) return false;
    for (const member of group.members) {
      if (!object(member) || !text(member.id) || !rev(member.revision) || !hash(member.fingerprint) || ids.has(member.id)) return false;
      ids.add(member.id); total++;
    }
    merged += group.members.length - 1;
  }
  return total <= 1000 && v.merged_count === (v.status === "planned" ? 0 : merged);
};
export const isRetentionReview = (v: unknown): v is RetentionReview => object(v) && isRetentionPlan(v.plan) && hash(v.digest) && hash(v.scope_digest) && counts(v.removed_counts) && counts(v.forgetting_counts) && counts(v.retained_counts);
export const isGovernanceData = (v: unknown): v is GovernanceData => object(v) && text(v.owner_id) && date(v.observed_at) && isLearningSettings(v.learning) && isRetentionSettings(v.retention) &&
  Array.isArray(v.retention_plans) && v.retention_plans.length <= 100 && v.retention_plans.every(row => isRetentionPlan(row) && row.owner_id === v.owner_id) && new Set(v.retention_plans.map(row => row.id)).size === v.retention_plans.length &&
  Array.isArray(v.consolidation_plans) && v.consolidation_plans.length <= 100 && v.consolidation_plans.every(row => isConsolidationPlan(row) && row.owner_id === v.owner_id) && new Set(v.consolidation_plans.map(row => row.id)).size === v.consolidation_plans.length;
