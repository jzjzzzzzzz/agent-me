import { useState, type ChangeEvent } from "react";
import { ReviewDialog } from "./ReviewDialog";
import { readSnapshot, snapshotFits, SnapshotFileError, type AuditEvent, type DestinationState, type ImportReview, type ImportReceipt, type RawSnapshot } from "./migrationApi";
import type { createPersonalClient } from "./personalApi";
import type { PersonalWorkspaceMessages } from "./personalMessages";

type Action = (client: ReturnType<typeof createPersonalClient>, signal: AbortSignal) => Promise<void>;
export type MigrationData = { destination: DestinationState; audit: AuditEvent[] };
export function MigrationReview({ data, text, busy, epoch, perform }: {
  data: MigrationData; text: PersonalWorkspaceMessages; busy: boolean; epoch: number;
  perform: (action: Action, mutation?: boolean) => Promise<void>;
}) {
  const t = text.migration;
  const [snapshot, setSnapshot] = useState<RawSnapshot | null>(null);
  const [view, setView] = useState<{ epoch: number; snapshot: RawSnapshot; review: ImportReview; trigger: HTMLElement | null } | null>(null);
  const [consent, setConsent] = useState(false);
  const [fileError, setFileError] = useState<SnapshotFileError["kind"] | null>(null);
  const [imported, setImported] = useState<ImportReceipt | null>(null);
  const [exported, setExported] = useState(false);
  const [limit, setLimit] = useState(100);
  const [audit, setAudit] = useState<{ epoch: number; rows: AuditEvent[] } | null>(null);
  const current = view?.epoch === epoch && view.snapshot === snapshot ? view : null;
  const auditRows = audit?.epoch === epoch ? audit.rows : data.audit;
  const fits = !snapshot || snapshotFits(snapshot, data.destination);
  function invalidate() { setView(null); setConsent(false); setFileError(null); setImported(null); }
  function discard() { invalidate(); setSnapshot(null); }
  async function file(event: ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0]; event.target.value = ""; if (!selected) return;
    discard();
    await perform(async (_client, signal) => {
      try { const parsed = await readSnapshot(selected, data.destination, signal); if (!signal.aborted) setSnapshot(parsed); }
      catch (error) { if (signal.aborted) return; if (error instanceof SnapshotFileError) setFileError(error.kind); else throw error; }
    });
  }
  async function preview() {
    if (!snapshot || !data.destination.empty) return;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    invalidate();
    await perform(async (client, signal) => {
      const review = await client.previewImport(snapshot, data.destination); if (!signal.aborted) setView({ epoch, snapshot, review, trigger });
    });
  }
  async function download() {
    setExported(false);
    await perform(async (client, signal) => {
      const raw = await client.exportSnapshot(data.destination); if (signal.aborted) return;
      const url = URL.createObjectURL(new Blob([raw], { type: "application/json" }));
      try { const link = document.createElement("a"); link.href = url; link.download = "private-twin-export.json"; link.click(); setExported(true); }
      finally { URL.revokeObjectURL(url); }
    });
  }
  return <section className="migration-review" aria-label={t.title}>
    <h4>{t.title}</h4><p className="review-hint">{t.boundary}</p>
    <dl className="review-metadata"><div><dt>{t.destination}</dt><dd>{data.destination.owner_id}</dd></div><div><dt>{t.requestLimit}</dt><dd>{data.destination.max_request_body_bytes}</dd></div></dl>
    <p>{data.destination.empty ? t.empty : t.occupied}</p>
    <label>{t.readFile}<input type="file" accept="application/json,.json" disabled={busy || !data.destination.empty} onChange={event => void file(event)} /></label>
    {fileError && <p role="alert">{t[fileError]}</p>}
    {!fits && <p role="alert">{t.tooLarge}</p>}
    {snapshot && <p>{t.fileSize}: {snapshot.bytes} · v{snapshot.version} · {t.sourceOwner}: {snapshot.ownerId}</p>}
    <div className="memory-actions"><button disabled={busy || !snapshot} onClick={discard}>{t.clearFile}</button><button disabled={busy || !snapshot || !fits || !data.destination.empty} onClick={() => void preview()}>{t.preview}</button>
      <button disabled={busy} onClick={() => void download()}>{t.export}</button></div>
    {exported && <p role="status">{t.exported}</p>}
    {current && <ReviewDialog label={t.review} returnFocus={current.trigger} onCancel={invalidate}>
      <h5>{t.review}</h5><dl className="review-metadata"><div><dt>{t.sourceOwner}</dt><dd>{current.review.owner_id}</dd></div><div><dt>{t.destinationOwner}</dt><dd>{current.review.destination_owner_id}</dd></div><div><dt>{t.digest}</dt><dd>{current.review.digest}</dd></div></dl>
      <h6>{t.counts}</h6><ul>{Object.entries(current.review.counts).map(([key, n]) => <li key={key}>{key}: {n}</li>)}</ul>
      <ul>{[t.sourcesRevoked, t.toolsArchived, t.providerOff, t.ownerAdopt, t.policyPreserved].map(value => <li key={value}>{value}</li>)}</ul><p>{t.trustHint}</p>
      <label className="review-checkbox"><input disabled={busy} type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />{t.consent}</label>
      <div className="memory-actions"><button disabled={busy || !consent} onClick={() => void perform(async (client, signal) => {
        invalidate(); const result = await client.importSnapshot(current.snapshot, current.review, data.destination);
        if (!signal.aborted) { setSnapshot(null); setImported(result); }
      }, true)}>{t.import}</button><button disabled={busy} onClick={invalidate}>{text.cancel}</button></div>
    </ReviewDialog>}
    {imported && <p role="status">{t.done}: {imported.owner_id} · {imported.archive_id}</p>}
    <section aria-label={t.audit}><h5>{t.audit}</h5><p className="review-hint">{t.auditHint}</p>
      <label>{t.limit}<select disabled={busy} value={limit} onChange={event => setLimit(Number(event.target.value))}>{[100, 500, 1000].map(n => <option key={n}>{n}</option>)}</select></label>
      <button disabled={busy} onClick={() => void perform(async (client, signal) => { const rows = await client.inspectAudit(data.destination, limit); if (!signal.aborted) setAudit({ epoch, rows }); })}>{t.reloadAudit}</button>
      {!auditRows.length && <p>{t.noEvents}</p>}<ul className="review-list">{auditRows.map(row => <li key={row.id}><strong>{row.operation}</strong><p>{row.actor} · {row.outcome} · {row.created_at}</p><p>{Object.entries(row.counts).map(([key, n]) => `${key}: ${n}`).join(" · ") || "—"}</p></li>)}</ul>
    </section>
  </section>;
}
