export type WorkflowMode = "standard" | "collaboration" | "verified";

const PARAM = "workflow";

export function readWorkflowMode(search: string): WorkflowMode {
  const value = new URLSearchParams(search).get(PARAM);
  if (value === "standard" || value === "collaboration" || value === "verified") {
    return value;
  }
  return "standard";
}

export function initialWorkflowMode(): WorkflowMode {
  return readWorkflowMode(window.location.search);
}

export function workflowUrl(
  location: Pick<Location, "pathname" | "search" | "hash">,
  mode: WorkflowMode,
): string {
  const params = new URLSearchParams(location.search);
  params.set(PARAM, mode);
  return `${location.pathname}?${params.toString()}${location.hash}`;
}
