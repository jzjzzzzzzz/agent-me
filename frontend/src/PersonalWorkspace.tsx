import { FormEvent, useState } from "react";
import type { PersonalWorkspaceMessages } from "./personalMessages";

type Entry = { id: string; kind: string; key: string; content: string; status: string; source: string; updated_at: string };
type Turn = { id: string; role: string; content: string };
type WorkspaceError = { kind: "conflict" } | { kind: "request"; detail: string | null };
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
  const [token, setToken] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [history, setHistory] = useState<Turn[]>([]);
  const [kind, setKind] = useState("fact");
  const [key, setKey] = useState("identity.name");
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState<WorkspaceError | null>(null);
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState<{ id: string; ids: string[] } | null>(null);

  async function request(path: string, body?: unknown) {
    const response = await fetch(`${base}/api/v1/personal${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json();
    if (response.status === 409 && Array.isArray(data.detail?.conflict_ids)) {
      setConflict({ id: path.split("/")[2], ids: data.detail.conflict_ids });
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
    setToken(""); setUnlocked(false); setEntries([]); setHistory([]);
    setContent(""); setQuestion(""); setConflict(null); setError(null); setEditing(null);
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await request(editing ? `/entries/${editing}/edit` : "/entries", { kind, key, content });
      setContent(""); setEditing(null); await refresh();
    });
  }
  const renderedError = error?.kind === "conflict"
    ? text.conflictError
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
      <h3>{text.profileTitle}</h3>
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
        <p>{entry.content}</p><small>{entry.source} · {entry.updated_at}</small>
        <div className="memory-actions">
          {entry.status === "pending" && <button aria-label={memoryActionName(text.confirm, entry.key, index + 1, text.memoryItem)} disabled={busy} onClick={() => void run(async () => { setConflict(null); await request(`/entries/${entry.id}/confirm`, { replace_ids: [] }); await refresh(); })}>{text.confirm}</button>}
          <button aria-label={memoryActionName(text.edit, entry.key, index + 1, text.memoryItem)} disabled={busy} onClick={() => { setEditing(entry.id); setKind(entry.kind); setKey(entry.key); setContent(entry.content); }}>{text.edit}</button>
          <button aria-label={memoryActionName(text.delete, entry.key, index + 1, text.memoryItem)} disabled={busy} onClick={() => void run(async () => { await request(`/entries/${entry.id}/delete`, {}); setConflict(null); await refresh(); })}>{text.delete}</button>
        </div>
      </li>)}</ul>
      {conflict && <aside role="alert"><p>{text.replacePrompt}</p>
        {entries.filter(entry => conflict.ids.includes(entry.id)).map(entry => <p key={entry.id}>{entry.key}: {entry.content}</p>)}
        <button disabled={busy} onClick={() => void run(async () => { await request(`/entries/${conflict.id}/confirm`, { replace_ids: conflict.ids }); setConflict(null); await refresh(); })}>{text.replace}</button>
        <button onClick={() => setConflict(null)}>{text.cancel}</button>
      </aside>}
      <h3>{text.privateChatTitle}</h3>
      <p>{text.chatGuidance}</p>
      <div className="private-history">{history.map(turn => <article key={turn.id}><strong>{displayRole(turn.role, text)}</strong><p>{turn.content}</p></article>)}</div>
      <form onSubmit={event => { event.preventDefault(); if (busy || question.length > questionLimit) return; void run(async () => { await request("/chat", { question }); setQuestion(""); await refresh(); }); }}>
        <label>{text.privateQuestion}<textarea required maxLength={questionLimit} value={question} onChange={event => setQuestion(event.target.value)} /></label>
        <button disabled={busy || question.length > questionLimit}>{text.send}</button>
      </form>
      <button disabled={busy} onClick={() => void run(async () => { await request("/history/clear", {}); await refresh(); })}>{text.clearHistory}</button>
      <button disabled={busy} onClick={() => void run(async () => {
        const data = await request("/export");
        const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
        const link = document.createElement("a"); link.href = url; link.download = "private-twin-export.json"; link.click(); URL.revokeObjectURL(url);
      })}>{text.exportData}</button>
    </>}
    {busy && <p role="status">{text.working}</p>}
    {error && <p role="alert">{renderedError}</p>}
  </section>;
}
