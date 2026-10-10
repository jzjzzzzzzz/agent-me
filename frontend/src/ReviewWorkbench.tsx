import { ReviewDialog } from "./ReviewDialog";
import { IdentityReview, type IdentityAction } from "./IdentityReview";
import { AgencyReview } from "./AgencyReview";
import type { AgencyData } from "./agencyApi";
import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import {
  createPersonalClient, ingestionWithinLimits, PersonalApiError,
  type SemanticReview, type IdentityData, type IngestionRun, type LearningSource, type MemoryRecord, type PersonalAnswer, type WorkbenchData,
} from "./personalApi";
import type { PersonalWorkspaceMessages } from "./personalMessages";

type Client = ReturnType<typeof createPersonalClient>;
type Inspection = Awaited<ReturnType<Client["inspect"]>>;
type Conflict = { candidate: MemoryRecord; records: MemoryRecord[] };
type WorkbenchError = { kind: "request" | "stale" | "invalid" | "tooLarge"; detail?: string | null };

export function ReviewWorkbench({ token, text, maxQuestionChars, onLock }: {
  token: string; text: PersonalWorkspaceMessages; maxQuestionChars: number; onLock: () => void;
}) {
  return <WorkbenchSession key={token} token={token} text={text} maxQuestionChars={maxQuestionChars} onLock={onLock} />;
}

function WorkbenchSession({ token, text, maxQuestionChars, onLock }: {
  token: string; text: PersonalWorkspaceMessages; maxQuestionChars: number; onLock: () => void;
}) {
  const t = text.review;
  const [identityOpen, setIdentityOpen] = useState(false);
  const [identity, setIdentity] = useState<IdentityData | null>(null);
  const [agencyOpen, setAgencyOpen] = useState(false);
  const [agency, setAgency] = useState<AgencyData | null>(null);
  const [epoch, setEpoch] = useState(0);
  const [askEntityId, setAskEntityId] = useState("");
  const [data, setData] = useState<WorkbenchData | null>(null);
  const [busy, setBusy] = useState(true);
  const busyRef = useRef(true);
  const session = useRef<{ controller: AbortController; client: Client } | null>(null);
  const lockRef = useRef(onLock);
  useEffect(() => { lockRef.current = onLock; }, [onLock]);
  const [error, setError] = useState<WorkbenchError | null>(null);
  const [name, setName] = useState("");
  const [sourceKind, setSourceKind] = useState<LearningSource["kind"]>("document");
  const [sensitivity, setSensitivity] = useState<LearningSource["sensitivity"]>("private");
  const [entityId, setEntityId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [content, setContent] = useState("");
  const [mode, setMode] = useState<"fields" | "notes" | "semantic">("fields");
  const [semantic, setSemantic] = useState<SemanticReview | null>(null);
  const [allowProvider, setAllowProvider] = useState(false);
  const [allowSourceSensitive, setAllowSourceSensitive] = useState(false);
  const [filter, setFilter] = useState<"all" | MemoryRecord["status"]>("pending");
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [conflict, setConflict] = useState<Conflict | null>(null);
  const [editing, setEditing] = useState<MemoryRecord | null>(null);
  const [deleting, setDeleting] = useState<MemoryRecord | null>(null);
  const [editContent, setEditContent] = useState("");
  const [latestRun, setLatestRun] = useState<IngestionRun | null>(null);
  const [question, setQuestion] = useState("");
  const [allowSensitive, setAllowSensitive] = useState(false);
  const [answer, setAnswer] = useState<PersonalAnswer | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const client = createPersonalClient(token, controller.signal);
    session.current = { controller, client };
    busyRef.current = true;
    void client.load().then(loaded => {
      if (!controller.signal.aborted) setData(loaded);
    }).catch(reason => {
      if (controller.signal.aborted) return;
      if (reason instanceof PersonalApiError && reason.status === 401) lockRef.current();
      else setError(reason instanceof PersonalApiError ? { kind: reason.kind, detail: reason.detail } : { kind: "request" });
    }).finally(() => {
      if (!controller.signal.aborted) { busyRef.current = false; setBusy(false); }
    });
    return () => { controller.abort(); if (session.current?.controller === controller) session.current = null; };
  }, [token]);

  async function run(action: (client: Client, signal: AbortSignal) => Promise<void>) {
    const current = session.current;
    if (!current || current.controller.signal.aborted || busyRef.current) return;
    busyRef.current = true; setBusy(true); setError(null);
    try { await action(current.client, current.controller.signal); }
    catch (reason) {
      if (current.controller.signal.aborted) return;
      if (reason instanceof PersonalApiError && reason.status === 401) lockRef.current();
      else setError(reason instanceof PersonalApiError ? { kind: reason.kind, detail: reason.detail }
        : reason === "tooLarge" || reason === "invalid" ? { kind: reason } : { kind: "request" });
    } finally {
      if (!current.controller.signal.aborted) { busyRef.current = false; setBusy(false); }
    }
  }
  async function refresh(client: Client, signal: AbortSignal) {
    if (signal.aborted) return;
    const loaded = await client.load();
    const identities = identityOpen ? await client.loadIdentity() : null;
    const actions = agencyOpen ? await client.loadAgency() : null;
    if (identities && loaded.entities.some(item => item.owner_id !== identities.owner.owner_id)) throw new PersonalApiError(502, "invalid");
    if (actions && [...loaded.entities, ...loaded.memories, ...loaded.sources].some(item => item.owner_id !== actions.owner_id) ||
      actions && identities && actions.owner_id !== identities.owner.owner_id) throw new PersonalApiError(502, "invalid");
    const source = loaded.sources.find(item => item.id === sourceId && item.approved);
    const review = mode === "semantic" && source ? await client.semanticReview(source) : null;
    if (!signal.aborted) { setData(loaded); setIdentity(identities); setAgency(actions); setSemantic(review); setEpoch(value => value + 1); }
  }
  function invalidate() { setEpoch(value => value + 1); setAllowProvider(false); setAnswer(null); setInspection(null); setConflict(null); }
  async function mutation(action: (client: Client) => Promise<unknown>) {
    await run(async (client, signal) => { invalidate(); await action(client); await refresh(client, signal); });
  }
  async function performIdentity(action: IdentityAction, changes = false) {
    await run(async (client, signal) => {
      if (changes) invalidate();
      await action(client, signal);
      if (changes) await refresh(client, signal);
    });
  }
  async function confirm(memory: MemoryRecord) {
    await run(async (client, signal) => {
      invalidate();
      try { await client.confirm(memory); await refresh(client, signal); }
      catch (reason) {
        if (signal.aborted) return;
        if (!(reason instanceof PersonalApiError) || !reason.conflictRevisions || !data) throw reason;
        const pairs = Object.entries(reason.conflictRevisions);
        const records = pairs.map(([id, revision]) => data.memories.find(item => item.id === id && item.revision === revision));
        if (!pairs.length || records.some(item => !item)) throw reason;
        setConflict({ candidate: memory, records: records as MemoryRecord[] });
      }
    });
  }
  async function register(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    await run(async (client, signal) => {
      if (entityId && !data?.entities.some(item => item.id === entityId && item.status === "confirmed")) throw new PersonalApiError(409, "stale");
      invalidate();
      const source = await client.register({ name: name.trim(), kind: sourceKind, sensitivity, entity_id: entityId || null });
      if (signal.aborted) return;
      setName(""); setSourceId(source.id); setContent("");
      await refresh(client, signal);
    });
  }
  async function readFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file) return;
    await run(async (_client, signal) => {
      if (file.size > 200_000) throw "tooLarge";
      let value: string;
      try { value = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer()); }
      catch { throw "invalid"; }
      if (!ingestionWithinLimits(value)) throw "tooLarge";
      if (!signal.aborted) { setContent(value); setAllowProvider(false); }
    });
  }
  async function reviewSemantic(source: LearningSource | undefined) {
    setSemantic(null); setAllowProvider(false); setAllowSourceSensitive(false);
    if (!source?.approved) return;
    await run(async (client, signal) => {
      const value = await client.semanticReview(source); if (!signal.aborted) setSemantic(value);
    });
  }
  const selectedSource = data?.sources.find(item => item.id === sourceId);
  const visible = data?.memories.filter(item => filter === "all" || item.status === filter) ?? [];
  const actionName = (label: string, item: MemoryRecord) => `${label}: ${item.key}, ${item.id}`;
  const sourceName = (id: string) => data?.sources.find(item => item.id === id)?.name ?? id;
  const subjectName = (id: string | null) => id ? data?.entities.find(item => item.id === id)?.name ?? id : t.unscoped;
  const status = (value: MemoryRecord["status"]) => t[value];
  const runStatus = (item: IngestionRun) => t[item.status];
  const evidenceMemory = (path: string, revision: number | null) => {
    const match = /^memory\/(.+)@(\d+)$/.exec(path);
    return match && data?.memories.find(memory => memory.id === match[1] && memory.revision === revision && memory.revision === Number(match[2]));
  };
  const renderedError = error?.kind === "request" ? `${text.requestFailed}${error.detail ? `: ${error.detail}` : ""}`
    : error ? t[error.kind] : "";

  function metadata(item: MemoryRecord) {
    return <dl className="review-metadata">
      <div><dt>{t.revision}</dt><dd>{item.revision}</dd></div>
      <div><dt>{t.source}</dt><dd>{item.source}</dd></div>
      <div><dt>{t.entity}</dt><dd>{subjectName(item.entity_id)}</dd></div>
      <div><dt>{t.sensitivity}</dt><dd>{item.sensitivity}</dd></div>
      <div><dt>{t.belief}</dt><dd>{item.belief}</dd></div>
      {item.confidence !== null && <div><dt>{t.confidence}</dt><dd>{item.confidence}</dd></div>}
      {(["valid_from", "valid_until", "occurred_at"] as const).map((key, index) => item[key] &&
        <div key={key}><dt>{[t.validFrom, t.validUntil, t.occurredAt][index]}</dt><dd>{item[key]}</dd></div>)}
    </dl>;
  }

  return <section className="review-workbench" aria-label={t.title}>
    <div className="review-heading"><h3>{t.title}</h3><button disabled={busy} onClick={() => void run(async (client, signal) => {
      invalidate(); setEditing(null); setDeleting(null); setEditContent(""); await refresh(client, signal);
    })}>{t.refresh}</button></div>
    {busy && <p role="status">{text.working}</p>}
    {error && <p role="alert" className="error">{renderedError}</p>}
    {data && <>
      <button disabled={busy} aria-expanded={identityOpen} onClick={() => {
        if (identityOpen) { setIdentityOpen(false); setIdentity(null); }
        else {
          setIdentityOpen(true);
          void run(async (client, signal) => {
            const value = await client.loadIdentity();
            if (data.entities.some(item => item.owner_id !== value.owner.owner_id)) throw new PersonalApiError(502, "invalid");
            if (!signal.aborted) setIdentity(value);
          });
        }
      }}>{identityOpen ? text.identity.close : text.identity.open}</button>
      {identityOpen && identity && <IdentityReview data={data} identity={identity} text={text} busy={busy} epoch={epoch} perform={performIdentity} />}
      <button disabled={busy} aria-expanded={agencyOpen} onClick={() => {
        if (agencyOpen) { setAgencyOpen(false); setAgency(null); }
        else {
          setAgencyOpen(true);
          void run(async (client, signal) => {
            const value = await client.loadAgency();
            if ([...data.entities, ...data.memories, ...data.sources].some(item => item.owner_id !== value.owner_id)) throw new PersonalApiError(502, "invalid");
            if (!signal.aborted) setAgency(value);
          });
        }
      }}>{agencyOpen ? text.agency.close : text.agency.open}</button>
      {agencyOpen && agency && <AgencyReview data={data} agency={agency} text={text} busy={busy} epoch={epoch} perform={performIdentity} />}
      <section aria-label={t.sources}>
        <h4>{t.sources}</h4>
        <form onSubmit={register} className="review-form">
          <div className="review-form-grid">
            <label>{t.name}<input value={name} maxLength={160} required disabled={busy} onChange={event => setName(event.target.value)} /></label>
            <label>{t.sourceKind}<select value={sourceKind} disabled={busy} onChange={event => setSourceKind(event.target.value as LearningSource["kind"])}>
              {["document", "project", "conversation", "event"].map(kind => <option key={kind}>{kind}</option>)}
            </select></label>
            <label>{t.sensitivity}<select value={sensitivity} disabled={busy} onChange={event => setSensitivity(event.target.value as LearningSource["sensitivity"])}>
              {["public", "private", "sensitive"].map(label => <option key={label}>{label}</option>)}
            </select></label>
            <label>{t.entity}<select value={entityId} disabled={busy} onChange={event => setEntityId(event.target.value)}>
              <option value="">{t.unscoped}</option>
              {entityId && !data.entities.some(item => item.id === entityId && item.status === "confirmed") && <option value={entityId}>{entityId} · {t.pending}</option>}
              {data.entities.filter(item => item.status === "confirmed").map(item => <option key={item.id} value={item.id}>{item.name} · {item.kind}</option>)}
            </select></label>
          </div>
          <button disabled={busy || !name.trim()}>{t.register}</button>
        </form>
        {!data.sources.length && <p>{t.noSources}</p>}
        <ul className="review-list">{data.sources.map(source => <li key={source.id}>
          <strong>{source.name}</strong> <span className={`review-badge ${source.approved ? "confirmed" : "pending"}`}>{source.approved ? t.approved : t.unapproved}</span>
          <p><code>{source.kind} · {source.sensitivity} · {source.id}</code></p>
          <p>{t.entity}: {subjectName(source.entity_id)} · {t.revision}: {source.revision}</p>
          <button disabled={busy} aria-label={`${source.approved ? t.revoke : t.approve}: ${source.name}, ${source.id}`}
            onClick={() => void mutation(client => client.reviewSource(source))}>{source.approved ? t.revoke : t.approve}</button>
        </li>)}</ul>
        <form className="review-form" onSubmit={event => {
          event.preventDefault();
          if (!selectedSource?.approved || !content.trim()) return;
          void run(async (client, signal) => {
            if (!ingestionWithinLimits(content)) throw "tooLarge";
            invalidate();
            let result: IngestionRun;
            if (mode === "semantic") {
              if (!semantic || !allowProvider || !semantic.permitted || !semantic.configured ||
                semantic.sensitivity === "sensitive" && !allowSourceSensitive || [...content].length > semantic.max_source_chars) {
                throw new PersonalApiError(403, "request");
              }
              try { result = await client.ingestSemantic(selectedSource, content, semantic, allowSourceSensitive); }
              finally { if (!signal.aborted) { setAllowProvider(false); setAllowSourceSensitive(false); } }
            } else result = await client.ingest(selectedSource, content, mode);
            if (signal.aborted) return;
            setLatestRun(result); setFilter("pending");
            // Model-selected quotations can omit negation/context. Keep the
            // owner's original draft available during human review, not in SQL.
            if (result.status === "completed" && mode !== "semantic") setContent("");
            await refresh(client, signal);
          });
        }}>
          <label>{t.source}<select value={sourceId} disabled={busy} required onChange={event => {
            const id = event.target.value;
            setSourceId(id); setContent(""); setLatestRun(null); setAllowProvider(false);
            if (mode === "semantic") void reviewSemantic(data.sources.find(item => item.id === id));
          }}><option value="">—</option>{data.sources.map(source => <option key={source.id} value={source.id}>
            {source.name} · {source.approved ? t.approved : t.unapproved}
          </option>)}</select></label>
          <label>{t.mode}<select value={mode} disabled={busy} onChange={event => {
            const next = event.target.value as "fields" | "notes" | "semantic";
            setMode(next); setAllowProvider(false); setSemantic(null); setAllowSourceSensitive(false);
            if (next === "semantic") void reviewSemantic(selectedSource);
          }}>
            <option value="fields">{t.fields}</option><option value="notes">{t.notes}</option><option value="semantic">{text.semantic.mode}</option>
          </select></label>
          <p className="review-hint" id="review-input-hint">{mode === "semantic" ? text.semantic.hint : t.inputHint}</p>
          {mode === "semantic" && semantic && <aside>
            <p>{text.semantic.selector}: <code>{semantic.selector}</code></p>
            <p>{text.semantic.target}: <code>{semantic.target_id ?? "—"}</code></p>
            <p>{text.semantic.sourceLimit}: {semantic.max_source_chars}</p>
            {!semantic.configured && <p>{text.semantic.notConfigured}</p>}
            {semantic.configured && !semantic.permitted && <p>{text.semantic.notPermitted}</p>}
            <label className="review-checkbox"><input type="checkbox" disabled={busy || !semantic.configured || !semantic.permitted}
              checked={allowProvider} onChange={event => setAllowProvider(event.target.checked)} />{text.semantic.consent}</label>
            {semantic.sensitivity === "sensitive" && <label className="review-checkbox"><input type="checkbox" disabled={busy}
              checked={allowSourceSensitive} onChange={event => { setAllowSourceSensitive(event.target.checked); setAllowProvider(false); }} />{text.semantic.sensitive}</label>}
          </aside>}
          <label>{t.importFile}<input type="file" accept=".txt,.md,.markdown,text/plain,text/markdown" disabled={busy || !selectedSource?.approved} onChange={event => void readFile(event)} /></label>
          <label>{t.input}<textarea value={content} required disabled={busy || !selectedSource?.approved} rows={6}
            aria-describedby="review-input-hint" onChange={event => { setContent(event.target.value); setAllowProvider(false); }} /></label>
          <button disabled={busy || !selectedSource?.approved || !content.trim() || mode === "semantic" && (
            !semantic?.configured || !semantic?.permitted || !allowProvider || semantic.sensitivity === "sensitive" && !allowSourceSensitive ||
            [...content].length > semantic.max_source_chars
          )}>{t.ingest}</button>
        </form>
        {latestRun && <p role="status">{runStatus(latestRun)} · {latestRun.id}{latestRun.replayed ? ` · ${t.replayed}` : ""}{latestRun.error_code ? ` · ${latestRun.error_code}` : ""}</p>}
        <details><summary>{t.runs} ({data.runs.length})</summary>
          <p className="review-hint">{t.retryHint}</p>
          {!data.runs.length && <p>{t.noRuns}</p>}
          <ul className="review-list">{data.runs.map(item => <li key={item.id}>
            <strong>{sourceName(item.source_id)}</strong> · {runStatus(item)}
            <p><code>{item.id} · {item.mode} · {item.extractor} · {item.attempts} · {item.document_hash}</code></p>
            <p>{t.revision}: {item.source_revision} · {item.updated_at}{item.error_code && ` · ${item.error_code}`}</p>
            <ul>{item.items.map(entry => <li key={entry.index}><code>{entry.outcome} · {entry.memory_id ?? "—"}</code>
              {entry.conflict_ids.length > 0 && <p>{text.conflictError} <code>{entry.conflict_ids.join(", ")}</code></p>}
            </li>)}</ul>
            <ol>{item.trace.map(stage => <li key={stage.stage}><code>{stage.stage} · {stage.outcome} · {stage.count}</code></li>)}</ol>
          </li>)}</ul>
        </details>
      </section>
      <section aria-label={t.review}>
        <h4>{t.review}</h4>
        <div className="review-filters" role="group" aria-label={t.review}>
          {(["all", "pending", "confirmed", "superseded"] as const).map(value => <button key={value} disabled={busy}
            aria-pressed={filter === value} onClick={() => setFilter(value)}>{t[value]} ({value === "all" ? data.memories.length : data.memories.filter(item => item.status === value).length})</button>)}
        </div>
        {!visible.length && <p>{t.noMemories}</p>}
        <ul className="review-list">{visible.map(item => <li key={item.id}>
          <strong>{item.key}</strong> <span className={`review-badge ${item.status}`}>{status(item.status)}</span>
          <p>{item.content}</p>{metadata(item)}
          <div className="memory-actions">
            {item.status === "pending" && <button disabled={busy} aria-label={actionName(text.confirm, item)} onClick={() => void confirm(item)}>{text.confirm}</button>}
            {item.status !== "superseded" && <button disabled={busy} aria-label={actionName(text.edit, item)} onClick={() => {
              setEditing(item); setEditContent(item.content); setConflict(null);
            }}>{text.edit}</button>}
            <button disabled={busy} aria-label={actionName(t.details, item)} onClick={() => void run(async (client, signal) => {
              setInspection(null); const value = await client.inspect(item); if (!signal.aborted) setInspection(value);
            })}>{t.details}</button>
            <button disabled={busy} aria-label={actionName(text.delete, item)} onClick={() => setDeleting(item)}>{text.delete}</button>
          </div>
        </li>)}</ul>
        {deleting && <ReviewDialog label={actionName(text.delete, deleting)} onCancel={() => setDeleting(null)}>
          <h5>{text.delete}: {deleting.key}</h5><p>{deleting.content}</p>{metadata(deleting)}
          <button disabled={busy} onClick={() => {
            const memory = deleting; setDeleting(null); void mutation(client => client.remove(memory));
          }}>{text.delete}</button>
          <button disabled={busy} onClick={() => setDeleting(null)}>{text.cancel}</button>
        </ReviewDialog>}
        {editing && <form className="review-form" onSubmit={event => {
          event.preventDefault(); if (!editContent.trim()) return;
          void run(async (client, signal) => {
            invalidate(); await client.edit(editing, editContent);
            if (signal.aborted) return;
            setEditing(null); setEditContent(""); await refresh(client, signal);
          });
        }}>
          <p><strong>{editing.key}</strong> · {t.revision}: {editing.revision}</p>
          <label>{text.contentLabel}<textarea required maxLength={2000} value={editContent} disabled={busy} onChange={event => setEditContent(event.target.value)} /></label>
          <button disabled={busy || !editContent.trim()}>{text.saveEdit}</button>
          <button type="button" disabled={busy} onClick={() => { setEditing(null); setEditContent(""); }}>{text.cancel}</button>
        </form>}
        {conflict && <aside role="alert">
          <p>{text.replacePrompt}</p>
          <h5>{t.replacement}</h5><p>{conflict.candidate.key}: {conflict.candidate.content}</p>{metadata(conflict.candidate)}
          <ul>{conflict.records.map(item => <li key={item.id}><p>{item.key}: {item.content}</p>{metadata(item)}</li>)}</ul>
          <button disabled={busy} onClick={() => void mutation(client => client.confirm(conflict.candidate,
            Object.fromEntries(conflict.records.map(item => [item.id, item.revision]))))}>{text.replace}</button>
          <button disabled={busy} onClick={() => setConflict(null)}>{text.cancel}</button>
        </aside>}
        {inspection && <section className="review-inspection" aria-label={`${t.details}: ${inspection.memory.key}`}>
          <h5>{t.details}: {inspection.memory.key}</h5>
          <h6>{t.origins}</h6>{!inspection.origins.length && <p>{t.noOrigins}</p>}
          <ul className="review-list">{inspection.origins.map(origin => <li key={origin.id}>
            <strong>{sourceName(origin.source_id)}</strong>
            <blockquote>{origin.excerpt}</blockquote>
            <p>{t.source}: <code>{origin.source_id}@{origin.source_revision}</code> · {t.revision}: {origin.memory_revision}</p>
            <p><code>{origin.run_id} · {origin.start}–{origin.end} · {origin.document_hash}</code></p>
          </li>)}</ul>
          <h6>{t.history}</h6>{!inspection.history.length && <p>{t.emptyHistory}</p>}
          <ol className="review-list">{inspection.history.map(item => <li key={item.revision}>
            <strong>{t.revision} {item.revision}</strong> · <code>{item.change}</code> · {status(item.status)}
            <p>{item.content}</p>{metadata(item)}
          </li>)}</ol>
          <button onClick={() => setInspection(null)}>{text.cancel}</button>
        </section>}
      </section>
      <section aria-label={t.ask}>
        <h4>{t.ask}</h4><p className="review-hint">{t.askHint}</p>
        <form className="review-form" onSubmit={event => {
          event.preventDefault(); if (!question.trim() || question.length > maxQuestionChars) return;
          void run(async (client, signal) => {
            if (askEntityId && !data.entities.some(item => item.id === askEntityId && item.status === "confirmed")) throw new PersonalApiError(409, "stale");
            setAnswer(null); const value = await client.ask(question.trim(), allowSensitive, askEntityId || undefined);
            if (!signal.aborted) { setAnswer(value); setAllowSensitive(false); }
          });
        }}>
          <label>{t.entity}<select value={askEntityId} disabled={busy} onChange={event => setAskEntityId(event.target.value)}>
            <option value="">{t.unscoped}</option>
            {askEntityId && !data.entities.some(item => item.id === askEntityId && item.status === "confirmed") && <option value={askEntityId}>{askEntityId} · {t.pending}</option>}
            {data.entities.filter(item => item.status === "confirmed").map(item => <option key={item.id} value={item.id}>{item.name} · {item.kind} · {item.id}</option>)}
          </select></label>
          <label>{text.privateQuestion}<textarea required maxLength={maxQuestionChars} value={question} disabled={busy} onChange={event => setQuestion(event.target.value)} /></label>
          <label className="review-checkbox"><input type="checkbox" checked={allowSensitive} disabled={busy} onChange={event => setAllowSensitive(event.target.checked)} />{t.allowSensitive}</label>
          <button disabled={busy || !question.trim() || question.length > maxQuestionChars}>{text.send}</button>
        </form>
        {answer && <article className="review-answer" aria-label={t.answer}>
          <h5>{t.answer} · <code>{answer.status}</code></h5><p>{answer.answer}</p><code>{answer.run_id}</code>
          {!answer.evidence.length && <p>{t.noEvidence}</p>}
          <ul className="review-list">{answer.evidence.map(item => <li key={item.id}>
            <strong>{item.field}</strong> · <code>{item.belief} · {item.sensitivity} · {item.purpose}</code>
            <p>{item.value}</p><p><code>{item.path}</code> · {t.source}: {item.source}</p>
            {item.kind === "memory_value" && evidenceMemory(item.path, item.revision) &&
              <button disabled={busy} onClick={() => void run(async (client, signal) => {
                const memory = evidenceMemory(item.path, item.revision)!;
                setInspection(null); const value = await client.inspect(memory); if (!signal.aborted) setInspection(value);
              })}>{t.details}: {item.field}</button>}
          </li>)}</ul>
        </article>}
      </section>
    </>}
  </section>;
}
