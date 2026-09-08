import { useId } from "react";
import type { CollaborationResponse } from "./api";
import type { Messages } from "./i18n";
import { AnswerResult } from "./AnswerResult";

export type ComparisonSide =
  | { status: "loading" }
  | { status: "error" }
  | { status: "success"; result: CollaborationResponse };

export type ComparisonState = {
  question: string;
  baseline: ComparisonSide;
  verified: ComparisonSide;
};

export function WorkflowComparison({ comparison, comparing, text, onRetry }: {
  comparison: ComparisonState;
  comparing: boolean;
  text: Messages;
  onRetry: () => void;
}) {
  const id = useId();
  return (
    <section className="workflow-comparison" aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{text.compareWorkflows}</h2>
      <p className="comparison-question">{text.comparisonQuestion}: {comparison.question}</p>
      <p className="workflow-hint">{text.comparisonLimits}</p>
      <div className="comparison-grid">
        {(["baseline", "verified"] as const).map((policy) => {
          const side = comparison[policy];
          return (
            <article key={policy} aria-labelledby={`${id}-${policy}`} aria-busy={side.status === "loading"}>
              <h3 id={`${id}-${policy}`}>{policy === "baseline" ? text.baselineComparison : text.verifiedComparison}</h3>
              <p className="comparison-stages">
                planner → researcher → critic → writer{policy === "verified" ? " → verifier" : ""}
              </p>
              {policy === "verified" && <p className="verifier-note">{text.extraVerifier}</p>}
              <p aria-live="polite" aria-atomic="true" className="comparison-status">
                {side.status === "loading" ? text.searching : side.status === "success" ? text.completed : ""}
              </p>
              {side.status === "error" && <p role="alert" className="error">{text.comparisonFailed}</p>}
              {side.status === "success" && <AnswerResult result={side.result} text={text} headingLevel={4} />}
            </article>
          );
        })}
      </div>
      <button type="button" className="comparison-retry" disabled={comparing} onClick={onRetry}>
        {text.retryComparison}
      </button>
    </section>
  );
}
