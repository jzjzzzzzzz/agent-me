import { FormEvent, useEffect, useState } from "react";
import { ask, ChatResponse } from "./api";
import {
  initialLocale,
  Locale,
  messages,
  persistLocale,
  supportedLocales,
} from "./i18n";
import "./styles.css";

export function App() {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const text = messages[locale];

  useEffect(() => {
    persistLocale(locale);
  }, [locale]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!question.trim() || loading) return;

    setLoading(true);
    setError("");
    try {
      setResult(await ask(question.trim()));
    } catch (reason) {
      setError(
        reason instanceof Error ? text.requestFailed + ": " + reason.message : text.requestFailed,
      );
    } finally {
      setLoading(false);
    }
  }

  const modeLabel =
    result?.mode === "extractive"
      ? text.extractiveMode
      : result?.mode === "provider"
        ? text.providerMode
        : result?.mode;

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
          A
        </div>
        <div>
          <p className="eyebrow">{text.projectLabel}</p>
          <h1>{text.title}</h1>
          <p className="intro">{text.intro}</p>
        </div>
      </header>

      <form onSubmit={submit}>
        <label htmlFor="question">{text.formLabel}</label>
        <div className="ask-row">
          <textarea
            id="question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={text.placeholder}
            maxLength={8000}
            rows={4}
          />
          <button disabled={!question.trim() || loading} type="submit">
            {loading ? text.searching : text.ask}
          </button>
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
          <h3>{text.groundingSources}</h3>
          <ul>
            {result.sources.map((source) => (
              <li key={source.path + "-" + source.excerpt}>
                <strong>{source.title}</strong> <code>{source.path}</code>
                <p>{source.excerpt}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer>{text.footer}</footer>
    </main>
  );
}
