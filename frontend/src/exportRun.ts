import type { CollaborationResponse } from "./api";

export function downloadCollaborationRun(result: CollaborationResponse): void {
  const exported: CollaborationResponse = {
    run_id: result.run_id,
    workflow: result.workflow,
    mode: result.mode,
    answer: result.answer,
    grounded: result.grounded,
    sources: result.sources,
    trace: result.trace,
  };
  const blob = new Blob([`${JSON.stringify(exported, null, 2)}\n`], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = `${result.run_id}.json`;
    link.click();
  } finally {
    URL.revokeObjectURL(url);
  }
}
