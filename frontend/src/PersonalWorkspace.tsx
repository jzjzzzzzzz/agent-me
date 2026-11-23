import { FormEvent, useId, useState } from "react";
import { ReviewWorkbench } from "./ReviewWorkbench";
import type { PersonalWorkspaceMessages } from "./personalMessages";

type Entry = { revision?: number; id: string; kind: string; key: string; content: string; status: string; source: string; updated_at: string; entity_id?: string | null };
type CaptureOutcome = "created" | "existing" | "superseded" | "forgotten" | "ignored";
type ChatSource = { path: string; excerpt: string };
type Project = { id: string; kind: string; name: string; status: string; sensitivity: string };
type CaptureDraft = { turnId: string; kind: string; key: string; content: string; projectId: string; sensitivity: string };
type Turn = { id: string; role: string; content: string };
type WorkspaceError = { kind: "conflict" } | { kind: "stale" } | { kind: "request"; detail: string | null };
const base = (import.meta.env.VITE_API_BASE_URL ?? "").trim().replace(/\/+$/, "");

class WorkspaceRequestError extends Error {
  constructor(readonly workspaceError: WorkspaceError) {
    super(workspaceError.kind);
  }
}

function memoryActionName(
  label: string,
  entryKey: string,
  position: number,
  memoryItem: string,
) {
  return `${label}: ${entryKey}, ${memoryItem} ${position}`;
}

function displayKind(kind: string, text: PersonalWorkspaceMessages) {
  const labels: Record<string, string> = {
    fact: text.kindFact,
    preference: text.kindPreference,
    event: text.kindEvent,
    decision: text.kindDecision,
  };
  return labels[kind] ?? kind;
}

function displayRole(role: string, text: PersonalWorkspaceMessages) {
  if (role === "user") return text.roleUser;
  if (role === "assistant") return text.roleAssistant;
  return role;
}

export function PersonalWorkspace({
  external,
  text,
  maxQuestionChars = 8000,
}: {
  external: boolean;
  text: PersonalWorkspaceMessages;
  maxQuestionChars?: number;
}) {
  const questionLimit = Math.min(maxQuestionChars, 8000);
  const memoryPanel = useId();
  const chatText = text.chatMemory;
  const [workbenchOpen, setWorkbenchOpen] = useState(false);
  const [token, setToken] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [history, setHistory] = useState<Turn[]>([]);
  const [kind, setKind] = useState("fact");
  const [key, setKey] = useState("identity.name");
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editingRevision, setEditingRevision] = useState<number | undefined>();
  const [question, setQuestion] = useState("");
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectId, setProjectId] = useState("");
  const [suggest, setSuggest] = useState(false);
  const [useMemory, setUseMemory] = useState(true);
  const [allowSensitive, setAllowSensitive] = useState(false);
  const [allowProvider, setAllowProvider] = useState(false);
  const [captureDraft, setCaptureDraft] = useState<CaptureDraft | null>(null);
  const [captureOutcome, setCaptureOutcome] = useState<CaptureOutcome | null>(null);
  const [sources, setSources] = useState<ChatSource[]>([]);
  const [error, setError] = useState<WorkspaceError | null>(null);
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState<{ id: string; ids: string[]; revision?: number; revisions?: Record<string, number> } | null>(null);

  async function request(path: string, body?: unknown) {
    const response = await fetch(`${base}/api/v1/personal${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json();
    if (response.status === 409 && Array.isArray(data.detail?.conflict_ids)) {
      const id = path.split("/")[2];
      const reported = data.detail.conflict_revisions;
      if (reported && data.detail.conflict_ids.some((conflictId: string) =>
        entries.find(entry => entry.id === conflictId)?.revision !== reported[conflictId])) {
        setConflict(null);
        throw new WorkspaceRequestError({ kind: "stale" });
      }
      setConflict({ id, ids: data.detail.conflict_ids, revision: entries.find(entry => entry.id === id)?.revision,
        revisions: reported });
      throw new WorkspaceRequestError({ kind: "conflict" });
    }
    if (!response.ok) {
      throw new WorkspaceRequestError({
        kind: "request",
        detail: typeof data.detail === "string" ? data.detail : null,
      });
    }
    return data;
  }
  async function refresh() {
    const [items, turns] = await Promise.all([request("/entries"), request("/history")]);
    setEntries(items); setHistory(turns);
  }
  async function run(action: () => Promise<void>) {
    setBusy(true); setError(null);
    try {
      await action();
    } catch (reason) {
      setError(reason instanceof WorkspaceRequestError
        ? reason.workspaceError
        : { kind: "request", detail: null });
    } finally {
      setBusy(false);
    }
  }
  function lock() {
    setWorkbenchOpen(false); setToken(""); setUnlocked(false); setEntries([]); setHistory([]);
    setContent(""); setQuestion(""); setConflict(null); setError(null); setEditing(null); setEditingRevision(undefined);
    setProjects(null); setProjectId(""); setSuggest(false); setUseMemory(true); setAllowSensitive(false);
    setAllowProvider(false); setCaptureDraft(null); setCaptureOutcome(null); setSources([]);
  }
  async function loadProjects() {
    const items = await request("/identity/entities") as Project[];
    const confirmed = items.filter(project => project.kind === "project" && project.status === "confirmed");
    setProjects(confirmed);
    if (!confirmed.some(project => project.id === projectId)) setProjectId("");
    setCaptureDraft(draft => draft && draft.projectId && !confirmed.some(project => project.id === draft.projectId)
      ? { ...draft, projectId: "" } : draft);
  }
  async function sendChat(event: FormEvent) {
    event.preventDefault();
    if (busy || question.length > questionLimit) return;
    setCaptureOutcome(null);
    setSources([]);
    const oneTimeProvider = external && allowProvider;
    setAllowProvider(false);
    setAllowSensitive(false);
    await run(async () => {
      const result = await request("/chat", {
        question,
        ...(projectId ? { project_id: projectId } : {}),
        ...(suggest ? { suggest_memory: true } : {}),
        ...(!useMemory ? { use_memory: false } : {}),
        ...(allowSensitive ? { allow_sensitive: true } : {}),
        ...(oneTimeProvider ? { allow_provider: true } : {}),
      }) as { sources?: ChatSource[]; capture?: { outcome: CaptureOutcome } };
      setQuestion("");
      setSources(result.sources ?? []);
      setCaptureOutcome(result.capture?.outcome ?? null);
      await refresh();
    });
  }
  async function captureTurn(event: FormEvent) {
    event.preventDefault();
    if (!captureDraft || busy) return;
    const draft = captureDraft;
    setCaptureOutcome(null);
    await run(async () => {
      const result = await request(`/history/${encodeURIComponent(draft.turnId)}/capture`, {
        kind: draft.kind, key: draft.key, content: draft.content,
        entity_id: draft.projectId || null,
        sensitivity: draft.sensitivity,
      }) as { outcome: CaptureOutcome };
      setCaptureOutcome(result.outcome);
      setCaptureDraft(null);
      await refresh();
    });
  }
  function projectOptions() {
    return <><option value="">{chatText.global}</option>
      {projects?.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
    </>;
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await request(editing ? `/entries/${editing}/edit` : "/entries", { kind, key, content, ...(editing ? { expected_revision: editingRevision } : {}) });
      setContent(""); setEditing(null); await refresh();
    });
  }
  const renderedError = error?.kind === "conflict"
    ? text.conflictError
    : error?.kind === "stale"
      ? text.review.stale
    : error?.detail
      ? `${text.requestFailed}: ${error.detail}`
      : text.requestFailed;

  return <section className="personal-workspace" aria-label={text.workspaceLabel}>
    <h2>{text.title}</h2>
    <p>{text.intro}</p>
    <p>{external ? text.externalDisclosure : text.localDisclosure}</p>
    {!unlocked ? <form onSubmit={event => { event.preventDefault(); void run(async () => { await refresh(); setUnlocked(true); }); }}>
      <label>{text.tokenLabel}<input type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} required /></label>
      <button disabled={busy}>{text.unlock}</button>
    </form> : <>
      <button disabled={busy} onClick={lock}>{text.lock}</button>
      <button disabled={busy} aria-expanded={workbenchOpen} onClick={() => { setWorkbenchOpen(!workbenchOpen); if (workbenchOpen) void run(async () => { await refresh(); if (projects) await loadProjects(); }); }}>{workbenchOpen ? text.review.close : text.review.open}</button>
      {workbenchOpen && <ReviewWorkbench token={token} text={text} maxQuestionChars={questionLimit} onLock={lock} />}
      <div hidden={workbenchOpen}>
      <h3 id={memoryPanel}>{text.profileTitle}</h3>
      <form onSubmit={save}>
        <label>{text.typeLabel}<select value={kind} onChange={event => setKind(event.target.value)}>
          <option value="fact">{text.kindFact}</option>
          <option value="preference">{text.kindPreference}</option>
          <option value="event">{text.kindEvent}</option>
          <option value="decision">{text.kindDecision}</option>
        </select></label>
        <label>{text.keyLabel}<input maxLength={100} required value={key} onChange={event => setKey(event.target.value)} placeholder={text.keyPlaceholder} /></label>
        <label>{text.contentLabel}<textarea maxLength={2000} required value={content} onChange={event => setContent(event.target.value)} /></label>
        <button disabled={busy}>{editing ? text.saveEdit : text.addCandidate}</button>
        {editing && <button type="button" onClick={() => { setEditing(null); setContent(""); }}>{text.cancel}</button>}
      </form>
      <ul className="memory-list">{entries.map((entry, index) => <li key={entry.id}>
        <strong>{entry.key}</strong> · {displayKind(entry.kind, text)} · {entry.status === "confirmed" ? text.statusConfirmed : text.statusPending}
        <p>{entry.content}</p><small>{entry.source} · {entry.updated_at}
          {entry.entity_id && ` · ${projects?.find(project => project.id === entry.entity_id)?.name ?? entry.entity_id}`}
        </small>
        <div className="memory-actions">
          {entry.status === "pending" && <button aria-label={memoryActionName(text.confirm, entry.key, index + 1, text.memoryItem)} disabled={busy} onClick={() => void run(async () => { setConflict(null); await request(`/entries/${entry.id}/confirm`, { replace_ids: [], expected_revision: entry.revision }); await refresh(); })}>{text.confirm}</button>}
          <button aria-label={memoryActionName(text.edit, entry.key, index + 1, text.memoryItem)} disabled={busy} onClick={() => { setEditing(entry.id); setEditingRevision(entry.revision); setKind(entry.kind); setKey(entry.key); setContent(entry.content); }}>{text.edit}</button>
          <button aria-label={memoryActionName(text.delete, entry.key, index + 1, text.memoryItem)} disabled={busy} onClick={() => void run(async () => { await request(`/entries/${entry.id}/delete`, { expected_revision: entry.revision }); setConflict(null); await refresh(); })}>{text.delete}</button>
        </div>
      </li>)}</ul>
      {conflict && <aside role="alert"><p>{text.replacePrompt}</p>
        {entries.filter(entry => conflict.ids.includes(entry.id)).map(entry => <p key={entry.id}>{entry.key}: {entry.content}</p>)}
        <button disabled={busy} onClick={() => void run(async () => { await request(`/entries/${conflict.id}/confirm`, { replace_ids: conflict.ids, expected_revision: conflict.revision, replace_revisions: conflict.revisions }); setConflict(null); await refresh(); })}>{text.replace}</button>
        <button onClick={() => setConflict(null)}>{text.cancel}</button>
      </aside>}
      <h3>{text.privateChatTitle}</h3>
      <p>{chatText.guidance}</p>
      {projects === null && <button disabled={busy} type="button" onClick={() => void run(loadProjects)}>{chatText.loadProjects}</button>}
      <div className="private-history">{history.map(turn => <article key={turn.id}><strong>{displayRole(turn.role, text)}</strong><p>{turn.content}</p>
        {turn.role === "user" && <button type="button" disabled={busy} onClick={() => {
          setCaptureOutcome(null);
          setCaptureDraft({ turnId: turn.id, kind: "preference", key: "", content: Array.from(turn.content).slice(0, 2000).join(""), projectId: "", sensitivity: "private" });
        }}>{chatText.capture}</button>}
      </article>)}</div>
      {captureDraft && <form className="memory-capture-form" aria-label={chatText.captureTitle} onSubmit={captureTurn}>
        <h4>{chatText.captureTitle}</h4>
        <label>{text.typeLabel}<select value={captureDraft.kind} onChange={event => setCaptureDraft({ ...captureDraft, kind: event.target.value })}>
          <option value="fact">{text.kindFact}</option>
          <option value="preference">{text.kindPreference}</option>
          <option value="event">{text.kindEvent}</option>
          <option value="decision">{text.kindDecision}</option>
        </select></label>
        <label>{text.keyLabel}<input required maxLength={100} value={captureDraft.key} onChange={event => setCaptureDraft({ ...captureDraft, key: event.target.value })} /></label>
        <label>{chatText.quote}<textarea required maxLength={2000} value={captureDraft.content} onChange={event => setCaptureDraft({ ...captureDraft, content: event.target.value })} /></label>
        <label>{chatText.scope}<select value={captureDraft.projectId} onChange={event => {
          const projectId = event.target.value;
          setCaptureDraft({
            ...captureDraft, projectId,
            sensitivity: projects?.find(project => project.id === projectId)?.sensitivity === "sensitive" ? "sensitive" : captureDraft.sensitivity,
          });
        }}>{projectOptions()}</select></label>
        <label>{chatText.sensitivity}<select value={captureDraft.sensitivity} onChange={event => setCaptureDraft({ ...captureDraft, sensitivity: event.target.value })}>
          <option value="private">{chatText.private}</option>
          <option value="sensitive">{chatText.sensitiveLabel}</option>
        </select></label>
        <button disabled={busy}>{text.addCandidate}</button>
        <button disabled={busy} type="button" onClick={() => setCaptureDraft(null)}>{text.cancel}</button>
      </form>}
      {captureOutcome && <p role="status">{chatText[captureOutcome]} {captureOutcome === "created" && <a href={`#${memoryPanel}`}>{text.profileTitle}</a>}</p>}
      {sources.length > 0 && <details className="chat-memory-sources">
        <summary>{chatText.sources}</summary>
        <ul>{sources.map((source, index) => <li key={`${source.path}-${index}`}>
          <code>{source.path}</code><p>{source.excerpt}</p>
        </li>)}</ul>
      </details>}
      <form onSubmit={sendChat}>
        <label>{chatText.scope}<select value={projectId} onChange={event => { setProjectId(event.target.value); setAllowSensitive(false); }}>{projectOptions()}</select></label>
        <label className="review-checkbox">{chatText.useMemory}<input type="checkbox" checked={useMemory} onChange={event => setUseMemory(event.target.checked)} /></label>
        <label className="review-checkbox">{chatText.suggest}<input type="checkbox" checked={suggest} onChange={event => setSuggest(event.target.checked)} /></label>
        <label className="review-checkbox">{chatText.sensitive}<input type="checkbox" checked={allowSensitive} onChange={event => setAllowSensitive(event.target.checked)} /></label>
        {external && <label className="review-checkbox">{chatText.provider}<input type="checkbox" checked={allowProvider} onChange={event => setAllowProvider(event.target.checked)} /></label>}
        <label>{text.privateQuestion}<textarea required maxLength={questionLimit} value={question} onChange={event => setQuestion(event.target.value)} /></label>
        <button disabled={busy || question.length > questionLimit}>{text.send}</button>
      </form>
      <button disabled={busy} onClick={() => void run(async () => {
        await request("/history/clear", {}); setCaptureDraft(null); setCaptureOutcome(null); setSources([]); await refresh();
      })}>{text.clearHistory}</button>
      <button disabled={busy} onClick={() => void run(async () => {
        const data = await request("/export");
        const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
        const link = document.createElement("a"); link.href = url; link.download = "private-twin-export.json"; link.click(); URL.revokeObjectURL(url);
      })}>{text.exportData}</button>
      </div>
    </>}
    {busy && <p role="status">{text.working}</p>}
    {error && <p role="alert">{renderedError}</p>}
  </section>;
}
