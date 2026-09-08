import { useState } from "react";
import type { ChatResponse, CollaborationResponse } from "./api";
import type { Messages } from "./i18n";
import { downloadCollaborationRun } from "./exportRun";

function formatSourcesForCopy(sources: readonly { title: string; path: string }[]): string {
  return sources.map((source) => `${source.title} — ${source.path}`).join("\n");
}

export function AnswerResult({ result, text }: {
  result: ChatResponse | CollaborationResponse;
  text: Messages;
}) {
  const [copyStatus, setCopyStatus] = useState("");

  async function copyToClipboard(value: string, successMessage: string) {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(value);
      setCopyStatus(successMessage);
    } catch {
      setCopyStatus(text.copyFailure);
    }
  }

  const modeLabel =
    result.mode === "multi-agent-local"
      ? result.workflow === "planner-researcher-critic-writer-verifier"
        ? text.verifiedModeLabel
        : text.collaborationModeLabel
      : result.mode === "extractive"
      ? text.extractiveMode
      : result.mode === "openai-compatible"
        ? text.providerMode
        : "";

  return (
    <section className="answer" aria-live="polite">
      <div className="answer-heading">
        <h2>{text.answer}</h2>
        <span>{modeLabel}</span>
      </div>
      <p>{result.answer}</p>
      <div className="copy-actions">
        {result.answer.trim() && (
          <button
            type="button"
            onClick={() => copyToClipboard(result.answer, text.copyAnswerSuccess)}
          >
            {text.copyAnswer}
          </button>
        )}
        {result.sources.length > 0 && (
          <button
            type="button"
            onClick={() =>
              copyToClipboard(formatSourcesForCopy(result.sources), text.copySourcesSuccess)
            }
          >
            {text.copySources}
          </button>
        )}
      </div>
      {copyStatus && (
        <p role="status" className="copy-status">
          {copyStatus}
        </p>
      )}
      <h3>{text.groundingSources}</h3>
      {result.sources.length > 0 ? (
        <ul>
          {result.sources.map((source) => (
            <li key={source.path + "-" + source.excerpt}>
              <strong>{source.title}</strong> <code>{source.path}</code>
              <p>{source.excerpt}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="no-sources">{text.noSources}</p>
      )}
      {result.mode === "multi-agent-local" && (
        <div className="workflow-trace">
          <div className="trace-heading">
            <h3>{text.workflowTrace}</h3>
            <span className={result.grounded ? "grounded" : "not-grounded"}>
              {result.grounded ? text.grounded : text.notGrounded}
            </span>
          </div>
          <p className="run-id">
            {text.runId}: <code>{result.run_id}</code>
          </p>
          <div className="run-export">
            <button type="button" onClick={() => downloadCollaborationRun(result)}>
              {text.exportRun}
            </button>
            <p>{text.exportPrivacy}</p>
          </div>
          <ol>
            {result.trace.map((stage) => (
              <li key={stage.sequence}>
                <div className="stage-heading">
                  <code>{stage.agent}</code>
                  <span>{stage.outcome === "blocked" ? text.blocked : text.completed}</span>
                </div>
                <p>{stage.summary}</p>
                <dl>
                  {Object.entries(stage.metrics).map(([name, value]) => (
                    <div key={name}>
                      <dt>{name}</dt>
                      <dd>{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
