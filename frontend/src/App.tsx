import { FormEvent, useEffect, useState } from "react";
import {
  ApiError,
  ask,
  ChatResponse,
  collaborate,
  CollaborationResponse,
  loadProfile,
  ProfileResponse,
} from "./api";
import {
  initialLocale,
  Locale,
  messages,
  persistLocale,
  supportedLocales,
} from "./i18n";
import { downloadCollaborationRun } from "./exportRun";
import "./styles.css";

const DEFAULT_MAX_QUESTION_CHARS = 8000;
type WorkflowMode = "standard" | "collaboration" | "verified";

function formatSourcesForCopy(sources: readonly { title: string; path: string }[]): string {
  return sources.map((source) => `${source.title} — ${source.path}`).join("\n");
}

export function App() {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<ChatResponse | CollaborationResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [workflowMode, setWorkflowMode] = useState<WorkflowMode>("standard");
  const [copyStatus, setCopyStatus] = useState("");
  const text = messages[locale];
  const maxQuestionChars = profile?.max_question_chars ?? DEFAULT_MAX_QUESTION_CHARS;
  const privacyMessage = profile
    ? profile.external_provider_enabled && workflowMode === "standard"
      ? text.inputPrivacyProvider
      : text.inputPrivacyLocal
    : text.inputPrivacyUnconfirmed;

  useEffect(() => {
    persistLocale(locale);
  }, [locale]);

  useEffect(() => {
    const profileName = profile?.name.trim();
    const profileDescription = profile?.description.trim();

    document.documentElement.lang = locale;
    document.title = `${profileName || text.projectLabel} | ${text.title}`;

    const description = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (description) {
      description.content = profileDescription || text.intro;
    }
  }, [locale, profile, text]);

  useEffect(() => {
    const controller = new AbortController();
    loadProfile(controller.signal)
      .then(setProfile)
      .catch(() => {
        // The localized reference copy remains usable when profile metadata is unavailable.
      });
    return () => controller.abort();
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || loading) return;

    setLoading(true);
    setError("");
    setResult(null);
    setCopyStatus("");
    try {
      setResult(
        workflowMode === "standard"
          ? await ask(question.trim())
          : await collaborate(
              question.trim(),
              workflowMode === "verified" ? "verified" : "baseline",
            ),
      );
    } catch (reason) {
      const detail = reason instanceof ApiError ? reason.message : "";
      setError(detail ? `${text.requestFailed}: ${detail}` : text.requestFailed);
    } finally {
      setLoading(false);
    }
  }

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
    result?.mode === "multi-agent-local"
      ? result.workflow === "planner-researcher-critic-writer-verifier"
        ? text.verifiedModeLabel
        : text.collaborationModeLabel
      : result?.mode === "extractive"
      ? text.extractiveMode
      : result?.mode === "openai-compatible"
        ? text.providerMode
        : "";

  return (
    <main>
      <div className="toolbar">
        <label htmlFor="locale">{text.language}</label>
        <select
          id="locale"
          value={locale}
          onChange={(event) => setLocale(event.target.value as Locale)}
        >
          {supportedLocales.map(({ code, label }) => (
            <option key={code} value={code}>
              {label}
            </option>
          ))}
        </select>
      </div>

      <header>
        <div className="mark" aria-hidden="true">
          {profile?.name.trim().charAt(0).toUpperCase() || "A"}
        </div>
        <div>
          <p className="eyebrow">{profile?.name || text.projectLabel}</p>
          <h1>{text.title}</h1>
          <p className="intro">{profile?.description || text.intro}</p>
        </div>
      </header>

      <form onSubmit={submit} aria-busy={loading}>
        <fieldset className="workflow-picker">
          <legend>{text.workflowMode}</legend>
          <div className="workflow-options">
            <label>
              <input
                type="radio"
                name="workflow"
                value="standard"
                checked={workflowMode === "standard"}
                onChange={() => setWorkflowMode("standard")}
                disabled={loading}
              />
              {text.standardWorkflow}
            </label>
            <label>
              <input
                type="radio"
                name="workflow"
                value="collaboration"
                checked={workflowMode === "collaboration"}
                onChange={() => setWorkflowMode("collaboration")}
                disabled={loading}
              />
              {text.collaborationWorkflow}
            </label>
            <label>
              <input
                type="radio"
                name="workflow"
                value="verified"
                checked={workflowMode === "verified"}
                onChange={() => setWorkflowMode("verified")}
                disabled={loading}
              />
              {text.verifiedWorkflow}
            </label>
          </div>
          {workflowMode === "collaboration" && (
            <p className="workflow-hint">{text.collaborationHint}</p>
          )}
          {workflowMode === "verified" && (
            <p className="workflow-hint">{text.verifiedHint}</p>
          )}
        </fieldset>
        <label htmlFor="question">{text.formLabel}</label>
        <div className="ask-row">
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={text.placeholder}
            maxLength={maxQuestionChars}
            aria-describedby="question-meta"
            rows={4}
          />
          <button disabled={!question.trim() || loading} type="submit">
            {loading ? text.searching : text.ask}
          </button>
        </div>
        <div id="question-meta" className="question-meta">
          <span>{privacyMessage}</span>
          <span>
            {question.length} / {maxQuestionChars} {text.characters}
          </span>
        </div>
      </form>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      {result && (
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
      )}

      <footer>{text.footer}</footer>
    </main>
  );
}
