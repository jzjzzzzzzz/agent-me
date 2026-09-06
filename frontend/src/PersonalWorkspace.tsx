import { FormEvent, useState } from "react";

type Entry = { id: string; kind: string; key: string; content: string; status: string; source: string; updated_at: string };
type Turn = { id: string; role: string; content: string };
const base = (import.meta.env.VITE_API_BASE_URL ?? "").trim().replace(/\/+$/, "");

export function PersonalWorkspace({ external }: { external: boolean }) {
  const [token, setToken] = useState("");
  const [unlocked, setUnlocked] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [history, setHistory] = useState<Turn[]>([]);
  const [kind, setKind] = useState("fact");
  const [key, setKey] = useState("identity.name");
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");
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
      throw new Error("存在同类记忆，请核对下方替换确认。 / Conflicting memory: review replacement below.");
    }
    if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed");
    return data;
  }
  async function refresh() {
    const [items, turns] = await Promise.all([request("/entries"), request("/history")]);
    setEntries(items); setHistory(turns);
  }
  async function run(action: () => Promise<void>) {
    setBusy(true); setError("");
    try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "Request failed"); }
    finally { setBusy(false); }
  }
  function lock() {
    setToken(""); setUnlocked(false); setEntries([]); setHistory([]);
    setContent(""); setQuestion(""); setConflict(null); setError(""); setEditing(null);
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    await run(async () => {
      await request(editing ? `/entries/${editing}/edit` : "/entries", { kind, key, content });
      setContent(""); setEditing(null); await refresh();
    });
  }
  return <section className="personal-workspace" aria-label="Private workspace">
    <h2>我的 AI 分身 / Private twin</h2>
    <p>本地保存档案、对话与记忆。只有确认的记忆用于回答。 / Only confirmed memories ground answers.</p>
    <p>{external
      ? "模型已连接：私有聊天的问题、相关记忆和知识片段会发送给配置的模型服务。"
      : "本地摘录模式：不调用外部模型；接入模型后才能生成个性化表达。"}</p>
    {!unlocked ? <form onSubmit={e => { e.preventDefault(); void run(async () => { await refresh(); setUnlocked(true); }); }}>
      <label>工作区密钥 / Workspace token<input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} required /></label>
      <button disabled={busy}>解锁 / Unlock</button>
    </form> : <>
      <button disabled={busy} onClick={lock}>锁定 / Lock</button>
      <h3>我的档案与记忆 / Profile & memories</h3>
      <form onSubmit={save}>
        <label>类型 / Type<select value={kind} onChange={e => setKind(e.target.value)}>
          <option value="fact">事实 / Fact</option><option value="preference">偏好 / Preference</option>
          <option value="event">事件 / Event</option><option value="decision">决策 / Decision</option>
        </select></label>
        <label>字段 / Key<input maxLength={100} required value={key} onChange={e => setKey(e.target.value)} placeholder="identity.name / goals.current / response.style" /></label>
        <label>内容 / Content<textarea maxLength={2000} required value={content} onChange={e => setContent(e.target.value)} /></label>
        <button disabled={busy}>{editing ? "保存修改为候选 / Save edit as pending" : "添加候选 / Add candidate"}</button>
        {editing && <button type="button" onClick={() => { setEditing(null); setContent(""); }}>取消 / Cancel</button>}
      </form>
      <ul className="memory-list">{entries.map(entry => <li key={entry.id}>
        <strong>{entry.key}</strong> · {entry.kind} · {entry.status === "confirmed" ? "已确认 / Confirmed" : "待确认 / Pending"}
        <p>{entry.content}</p><small>{entry.source} · {entry.updated_at}</small>
        <div className="memory-actions">
          {entry.status === "pending" && <button disabled={busy} onClick={() => void run(async () => { setConflict(null); await request(`/entries/${entry.id}/confirm`, { replace_ids: [] }); await refresh(); })}>确认 / Confirm</button>}
          <button disabled={busy} onClick={() => { setEditing(entry.id); setKind(entry.kind); setKey(entry.key); setContent(entry.content); }}>编辑 / Edit</button>
          <button disabled={busy} onClick={() => void run(async () => { await request(`/entries/${entry.id}/delete`, {}); setConflict(null); await refresh(); })}>删除 / Delete</button>
        </div>
      </li>)}</ul>
      {conflict && <aside role="alert"><p>确认用新内容替换以下旧记忆？ / Replace these confirmed memories?</p>
        {entries.filter(e => conflict.ids.includes(e.id)).map(e => <p key={e.id}>{e.key}: {e.content}</p>)}
        <button disabled={busy} onClick={() => void run(async () => { await request(`/entries/${conflict.id}/confirm`, { replace_ids: conflict.ids }); setConflict(null); await refresh(); })}>确认替换 / Replace</button>
        <button onClick={() => setConflict(null)}>取消 / Cancel</button>
      </aside>}
      <h3>私有聊天 / Private chat</h3>
      <p>使用“记住：…”或“Remember: …”生成候选偏好，再到上方确认。其他信息可手动添加。</p>
      <div className="private-history">{history.map(turn => <article key={turn.id}><strong>{turn.role}</strong><p>{turn.content}</p></article>)}</div>
      <form onSubmit={e => { e.preventDefault(); void run(async () => { await request("/chat", { question }); setQuestion(""); await refresh(); }); }}>
        <label>私有问题 / Private question<textarea required maxLength={8000} value={question} onChange={e => setQuestion(e.target.value)} /></label>
        <button disabled={busy}>发送 / Send</button>
      </form>
      <button disabled={busy} onClick={() => void run(async () => { await request("/history/clear", {}); await refresh(); })}>清空全部聊天（保留记忆） / Clear history</button>
      <button disabled={busy} onClick={() => void run(async () => {
        const data = await request("/export");
        const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
        const link = document.createElement("a"); link.href = url; link.download = "private-twin-export.json"; link.click(); URL.revokeObjectURL(url);
      })}>导出私有数据 / Export private data</button>
    </>}
    {busy && <p role="status">处理中 / Working…</p>}
    {error && <p role="alert">{error}</p>}
  </section>;
}
