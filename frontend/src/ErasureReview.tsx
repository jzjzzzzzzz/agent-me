import { useState } from "react";
import { ReviewDialog } from "./ReviewDialog";
import { eraseKinds, type EraseKind, type ErasureCatalogue, type ErasurePreview, type ErasureRef, type ErasureRequest, type ErasureResult } from "./erasureApi";
import type { createPersonalClient } from "./personalApi";
import type { PersonalWorkspaceMessages } from "./personalMessages";

type Action = (client: ReturnType<typeof createPersonalClient>, signal: AbortSignal) => Promise<void>;
export function ErasureReview({ catalogue, text, epoch, busy, perform }: {
  catalogue: ErasureCatalogue; text: PersonalWorkspaceMessages; epoch: number; busy: boolean;
  perform: (action: Action, mutation?: boolean) => Promise<void>;
}) {
  const t = text.erasure;
  const [kind, setKind] = useState<EraseKind>("task");
  const [id, setId] = useState("");
  const [purgeOutput, setPurgeOutput] = useState(false);
  const [forgetMemories, setForgetMemories] = useState(false);
  const [view, setView] = useState<{ epoch: number; preview: ErasurePreview; trigger: HTMLElement | null } | null>(null);
  const [consent, setConsent] = useState(false);
  const [result, setResult] = useState<ErasureResult | null>(null);
  const current = view?.epoch === epoch ? view : null;
  const choices = catalogue.items.filter(item => item.kind === kind);
  const target = choices.find(item => item.record.id === id)?.record;
  function invalidate() { setView(null); setConsent(false); setResult(null); }
  async function preview() {
    if (!target) return;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    invalidate();
    const request: ErasureRequest = { kind, id: target.id, expected_owner_id: catalogue.owner_id, expected_revision: target.revision,
      purge_output: kind === "action" && purgeOutput, expected_output_revision: null, forget_memories: kind === "source" && forgetMemories };
    await perform(async (client, signal) => {
      const preview = await client.previewErasure(request);
      if (!signal.aborted) setView({ preview, trigger, epoch });
    });
  }
  function rows(name: string, copies: ErasureRef[]) {
    const counts: Record<string, number> = {};
    for (const row of copies) counts[row.table] = (counts[row.table] ?? 0) + 1;
    return <section aria-label={name}><h6>{name}: {copies.length}</h6>
      <p>{Object.entries(counts).map(([table, n]) => `${table}: ${n}`).join(" · ") || "—"}</p>
      <details><summary>{name}</summary><ul>{copies.map(row => <li key={`${row.table}/${row.key}`}>{row.table} · {row.label} · {row.id}{row.revision !== null ? ` @ ${row.revision}` : ""}</li>)}</ul></details>
    </section>;
  }
  return <section aria-label={t.title} className="erasure-review">
    <h4>{t.title}</h4><p className="review-hint">{t.boundary}</p>
    <form className="review-form" onSubmit={event => { event.preventDefault(); void preview(); }}>
      <div className="review-form-grid">
        <label>{t.kind}<select disabled={busy} value={kind} onChange={event => { invalidate(); setKind(event.target.value as EraseKind); setId(""); setPurgeOutput(false); setForgetMemories(false); }}>
          {eraseKinds.map(kind => <option key={kind} value={kind}>{t[kind]}</option>)}
        </select></label>
        <label>{t.target}<select disabled={busy} value={id} onChange={event => { invalidate(); setId(event.target.value); }}><option value="">—</option>
          {choices.map(item => <option key={item.record.key} value={item.record.id}>{item.record.label} · {item.record.id}{item.record.revision !== null ? ` @ ${item.record.revision}` : ""}</option>)}
        </select></label>
      </div>
      {!choices.length && <p>{t.noTargets}</p>}
      {kind === "action" && <><label className="review-checkbox"><input type="checkbox" disabled={busy} checked={purgeOutput} onChange={event => { invalidate(); setPurgeOutput(event.target.checked); }} />{t.purgeOutput}</label><p className="review-hint">{t.actionHint}</p></>}
      {kind === "source" && <><label className="review-checkbox"><input type="checkbox" disabled={busy} checked={forgetMemories} onChange={event => { invalidate(); setForgetMemories(event.target.checked); }} />{t.forgetMemories}</label><p className="review-hint">{t.sourceHint}</p></>}
      {kind === "archive" && <p className="review-hint">{t.archiveHint}</p>}
      <button disabled={busy || !target}>{t.preview}</button>
    </form>
    {current && <ReviewDialog label={t.scope} returnFocus={current.trigger} onCancel={invalidate}>
      <h5>{t.scope}</h5><p>{t[current.preview.request.kind]} · {current.preview.target.label} · {current.preview.target.id} @ {current.preview.target.revision ?? "—"}</p>
      <p>{text.review.revision}: {current.preview.request.expected_revision ?? "—"} · purge_output={String(current.preview.request.purge_output)} · forget_memories={String(current.preview.request.forget_memories)}</p>
      {current.preview.request.expected_output_revision !== null && <p>{t.purgeOutput} @ {current.preview.request.expected_output_revision}</p>}
      <dl className="review-metadata"><div><dt>{t.digest}</dt><dd>{current.preview.digest}</dd></div></dl>
      {rows(t.removed, current.preview.removed)}{rows(t.updated, current.preview.updated)}{rows(t.added, current.preview.added)}{rows(t.retained, current.preview.retained)}
      <p>{t.retainedHint}</p><p>{t.boundary}</p>
      <label className="review-checkbox"><input disabled={busy} type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />{t.consent}</label>
      <div className="memory-actions"><button disabled={busy || !consent} onClick={() => void perform(async (client, signal) => {
        invalidate(); const result = await client.applyErasure(current.preview); if (!signal.aborted) setResult(result);
      }, true)}>{t.confirm}</button><button disabled={busy} onClick={invalidate}>{text.cancel}</button></div>
    </ReviewDialog>}
    {result && <p role="status">{t.done}: {result.request.kind}/{result.request.id}</p>}
  </section>;
}
