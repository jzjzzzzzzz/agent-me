import raw from "./agency.json";
import type { ActionEvent, ActionPlan, NoteRecord, TaskRecord, ToolPermission } from "../agencyApi";
import type { MemoryRecord } from "../personalApi";

/** Snapshots generated from a disposable fictional Agency; never owner workspace data. */
export const agencyFixture = raw as unknown as Record<
  "planned" | "approved" | "completed" | "completionPlan" | "completion" | "rolledBack" | "recommended" | "cancelled" | "notePlan" | "noteCompleted" | "failed", ActionPlan
> & {
  owner_id: string; permissions: ToolPermission[]; disabled: ToolPermission[];
  tasks: TaskRecord[]; notes: NoteRecord[]; events: ActionEvent[]; memories: MemoryRecord[];
};
