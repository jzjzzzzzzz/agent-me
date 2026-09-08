import { useEffect, useId, useRef, useState, type ChangeEvent } from "react";
import type { CollaborationResponse } from "./api";
import type { Messages } from "./i18n";
import { AnswerResult } from "./AnswerResult";
import { readCollaborationRun, RunImportError, type RunImportFailure } from "./importRun";

export function LocalRunReplay({ text }: { text: Messages }) {
  const id = useId();
  const [record, setRecord] = useState<CollaborationResponse | null>(null);
  const [error, setError] = useState<RunImportFailure | null>(null);
  const [reading, setReading] = useState(false);
  const generation = useRef(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const errorMessage = useRef<HTMLParagraphElement>(null);

  useEffect(() => () => { generation.current += 1; }, []);
  useEffect(() => {
    if (error) errorMessage.current?.focus();
    else if (record) heading.current?.focus();
  }, [error, record]);

  async function openRecord(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    if (!file) return; // Cancelling the picker preserves the previous view.
    event.currentTarget.value = ""; // Allow retrying the same file, including after an error.
    const current = ++generation.current;
    setRecord(null);
    setError(null);
    setReading(true);
    try {
      const imported = await readCollaborationRun(file);
      if (current === generation.current) setRecord(imported);
    } catch (reason) {
      if (current === generation.current) {
        setError(reason instanceof RunImportError ? reason.code : "replayReadFailed");
      }
    } finally {
      if (current === generation.current) setReading(false);
    }
  }

  return (
    <section className="local-replay" aria-labelledby={`${id}-label`}>
      <label id={`${id}-label`} htmlFor={`${id}-file`}>{text.openRun}</label>
      <p id={`${id}-help`} className="workflow-hint">{text.replayHelp}</p>
      <input
        id={`${id}-file`}
        type="file"
        accept=".json,application/json"
        aria-describedby={`${id}-help`}
        disabled={reading}
        onChange={openRecord}
      />
      <p aria-live="polite" aria-atomic="true" className="replay-status">
        {reading ? text.replayReading : record ? text.replayLoaded : ""}
      </p>
      {error && <p ref={errorMessage} tabIndex={-1} role="alert" className="error">{text[error]}</p>}
      {record && (
        <>
          <h2 ref={heading} tabIndex={-1} className="replay-label">{text.replayLabel}</h2>
          <p className="workflow-hint">{text.replayBoundary}</p>
          <AnswerResult result={record} text={text} />
        </>
      )}
    </section>
  );
}
