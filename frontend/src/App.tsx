import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ApiError,
  ask,
  ChatResponse,
  collaborate,
  CollaborationPolicy,
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
import { AnswerResult } from "./AnswerResult";
import { LocalRunReplay } from "./LocalRunReplay";
import { WorkflowComparison, type ComparisonState } from "./WorkflowComparison";
import {
  initialWorkflowMode,
  readWorkflowMode,
  workflowUrl,
  WorkflowMode,
} from "./workflowLink";
import "./styles.css";
import { PersonalWorkspace } from "./PersonalWorkspace";

const DEFAULT_MAX_QUESTION_CHARS = 8000;

export function App() {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<ChatResponse | CollaborationResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState<ComparisonState | null>(null);
  const [comparing, setComparing] = useState(false);
  const comparisonController = useRef<AbortController | null>(null);
  const busy = loading || comparing;
  const [profile, setProfile] = useState<ProfileResponse | null>(null);
  const [workflowMode, setWorkflowMode] = useState<WorkflowMode>(initialWorkflowMode);
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
    function onPopState() {
      setWorkflowMode(readWorkflowMode(window.location.search));
    }
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => () => comparisonController.current?.abort(), []);

  function selectWorkflow(mode: WorkflowMode) {
    setWorkflowMode(mode);
    const url = workflowUrl(window.location, mode);
    window.history.pushState({ workflow: mode }, "", url);
  }

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
    if (!question.trim() || busy) return;

    setLoading(true);
    setError("");
    setResult(null);
    setComparison(null);
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

  async function compare(questionToCompare: string) {
    const submittedQuestion = questionToCompare.trim();
    if (!submittedQuestion || loading || comparisonController.current) return;
    const controller = new AbortController();
    comparisonController.current = controller;
    setComparing(true);
    setResult(null);
    setError("");
    setComparison({
      question: submittedQuestion,
      baseline: { status: "loading" },
      verified: { status: "loading" },
    });

    async function runSide(policy: CollaborationPolicy) {
      try {
        const response = await collaborate(submittedQuestion, policy, controller.signal);
        const expected = policy === "verified"
          ? "planner-researcher-critic-writer-verifier"
          : "planner-researcher-critic-writer";
        if (response.workflow !== expected) throw new Error("unexpected workflow");
        if (!controller.signal.aborted) {
          setComparison((current) => current && {
            ...current, [policy]: { status: "success", result: response },
          });
        }
      } catch {
        if (!controller.signal.aborted) {
          setComparison((current) => current && { ...current, [policy]: { status: "error" } });
        }
      }
    }

    // Settle each side independently: one failure must not discard the other result.
    await Promise.all([runSide("baseline"), runSide("verified")]);
    if (!controller.signal.aborted) setComparing(false);
    if (comparisonController.current === controller) comparisonController.current = null;
  }

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

      {profile?.personal_enabled && <PersonalWorkspace external={profile.external_provider_enabled} />}

      <form onSubmit={submit} aria-busy={busy}>
        <fieldset className="workflow-picker">
          <legend>{text.workflowMode}</legend>
          <div className="workflow-options">
            <label>
              <input
                type="radio"
                name="workflow"
                value="standard"
                checked={workflowMode === "standard"}
                onChange={() => selectWorkflow("standard")}
                disabled={busy}
              />
              {text.standardWorkflow}
            </label>
            <label>
              <input
                type="radio"
                name="workflow"
                value="collaboration"
                checked={workflowMode === "collaboration"}
                onChange={() => selectWorkflow("collaboration")}
                disabled={busy}
              />
              {text.collaborationWorkflow}
            </label>
            <label>
              <input
                type="radio"
                name="workflow"
                value="verified"
                checked={workflowMode === "verified"}
                onChange={() => selectWorkflow("verified")}
                disabled={busy}
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
          <button disabled={!question.trim() || busy} type="submit">
            {loading ? text.searching : text.ask}
          </button>
        </div>
        <div id="question-meta" className="question-meta">
          <span>{privacyMessage}</span>
          <span>
            {question.length} / {maxQuestionChars} {text.characters}
          </span>
        </div>
        <div className="comparison-action">
          <button type="button" disabled={!question.trim() || busy} onClick={() => compare(question)} aria-describedby="compare-help">
            {text.compareWorkflows}
          </button>
          <p id="compare-help" className="workflow-hint">{text.compareHelp}</p>
        </div>
      </form>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      <LocalRunReplay text={text} />

      {result && <AnswerResult result={result} text={text} />}
      {comparison && (
        <WorkflowComparison comparison={comparison} comparing={comparing} text={text} onRetry={() => compare(comparison.question)} />
      )}

      <footer>{text.footer}</footer>
    </main>
  );
}
