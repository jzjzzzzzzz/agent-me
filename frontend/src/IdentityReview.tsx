import { ReviewDialog } from "./ReviewDialog";
import { FormEvent, useState } from "react";
import {
  type createPersonalClient, type Entity, type EntityInput, type EntityRevision,
  type EntityResolution, type IdentityContext, type IdentityData, type IdentityDeletePreview,
  type Relationship, type RelationshipRevision, type WorkbenchData,
} from "./personalApi";
import type { PersonalWorkspaceMessages } from "./personalMessages";

type Client = ReturnType<typeof createPersonalClient>;
export type IdentityAction = (client: Client, signal: AbortSignal) => Promise<void>;
type View = { epoch: number } & (
  | { kind: "entityHistory"; rows: EntityRevision[] }
  | { kind: "relationshipHistory"; rows: RelationshipRevision[] }
  | { kind: "resolution"; result: EntityResolution }
  | { kind: "graph"; result: IdentityContext }
  | { kind: "delete"; preview: IdentityDeletePreview }
  | { kind: "owner"; target: Entity | null; owner: IdentityData["owner"] }
);
const kinds: Entity["kind"][] = ["person", "project", "organization", "event", "idea", "preference", "decision"];

export function IdentityReview({ data, identity, text, busy, epoch, perform }: {
  data: WorkbenchData; identity: IdentityData; text: PersonalWorkspaceMessages; busy: boolean; epoch: number;
  perform: (action: IdentityAction, mutation?: boolean) => Promise<void>;
}) {
  const t = text.identity;
  const r = text.review;
  const [name, setName] = useState("");
  const [kind, setKind] = useState<Entity["kind"]>("person");
  const [aliases, setAliases] = useState("");
  const [sensitivity, setSensitivity] = useState<Entity["sensitivity"]>("private");
  const [distinct, setDistinct] = useState(false);
  const [editing, setEditing] = useState<Entity | null>(null);
  const [ownerTarget, setOwnerTarget] = useState("");
  const [alias, setAlias] = useState("");
  const [aliasKind, setAliasKind] = useState<Entity["kind"] | "">("");
  const [allowResolveSensitive, setAllowResolveSensitive] = useState(false);
  const [allowGraphSensitive, setAllowGraphSensitive] = useState(false);
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");
  const [evidenceId, setEvidenceId] = useState("");
  const [predicate, setPredicate] = useState("works_on");
  const [relationSensitivity, setRelationSensitivity] = useState<Entity["sensitivity"]>("private");
  const [view, setView] = useState<View | null>(null);
  const [deleteTrigger, setDeleteTrigger] = useState<HTMLElement | null>(null);
  const currentView = view?.epoch === epoch ? view : null;
  const confirmed = data.entities.filter(item => item.status === "confirmed");
  const nameOf = (id: string | null) => id ? data.entities.find(item => item.id === id)?.name ?? id : t.notBound;
  const label = (action: string, item: Entity) => `${action}: ${item.name}, ${item.id}`;
  const relationLabel = (action: string, item: Relationship) => `${action}: ${item.predicate}, ${item.id}`;
  const aliasRows = aliases.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
  const validAliases = aliasRows.length <= 20 && aliasRows.every(value => [...value].length <= 160);
  const left = confirmed.find(item => item.id === leftId);
  const right = confirmed.find(item => item.id === rightId);
  const evidence = data.memories.find(item => item.id === evidenceId && item.status === "confirmed");
  const predicateValid = /^[a-z][a-z0-9_]{0,99}$/.test(predicate);
  const target = confirmed.find(item => item.id === ownerTarget && item.kind === "person");
  function resetForm() { setEditing(null); setName(""); setAliases(""); setKind("person"); setSensitivity("private"); setDistinct(false); }
  function metadata(item: Entity | Relationship) {
    return <dl className="review-metadata">
      <div><dt>{r.revision}</dt><dd>{item.revision}</dd></div>
      <div><dt>{r.sensitivity}</dt><dd>{item.sensitivity}</dd></div>
      <div><dt>ID</dt><dd>{item.id}</dd></div>
      <div><dt>{t.status}</dt><dd>{r[item.status]}</dd></div>
      {"aliases" in item && <div><dt>{t.aliases}</dt><dd>{item.aliases.join(" · ") || "—"}</dd></div>}
    </dl>;
  }
  async function save(event: FormEvent) {
    event.preventDefault(); if (!name.trim() || !validAliases) return;
    const input: EntityInput = { name: name.trim(), kind, aliases: aliasRows, sensitivity };
    await perform(async (client, signal) => {
      if (editing) await client.editEntity(editing, input);
      else await client.createEntity(input, distinct);
      if (!signal.aborted) resetForm();
    }, true);
  }
  async function previewDelete(record: Entity | Relationship, recordKind: "entity" | "relationship") {
    // Disabling the clicked control during the request can blur it before the
    // scope arrives. Capture it before the shared request mutex changes the DOM.
    setDeleteTrigger(document.activeElement instanceof HTMLElement ? document.activeElement : null);
    await perform(async (client, signal) => {
      setView(null); const preview = await client.previewIdentityDelete(record, recordKind);
      if (!signal.aborted) setView({ epoch, kind: "delete", preview });
    });
  }
  function selectEntity(value: string, update: (id: string) => void, inputLabel: string) {
    return <label>{inputLabel}<select value={value} disabled={busy} required onChange={event => update(event.target.value)}>
      <option value="">—</option>
      {value && !confirmed.some(item => item.id === value) && <option value={value}>{value} · {r.pending}</option>}
      {confirmed.map(item => <option key={item.id} value={item.id}>{item.name} · {item.kind} · {item.id}</option>)}
    </select></label>;
  }

  return <section className="identity-review" aria-label={t.title}>
    <h4>{t.title}</h4>
    <section aria-label={t.entities}>
      <h5>{t.entities}</h5>
      <form className="review-form" onSubmit={save}>
        {editing && <p>{editing.name} · {r.revision}: {editing.revision}</p>}
        <div className="review-form-grid">
          <label>{t.entityName}<input value={name} maxLength={160} disabled={busy} required onChange={event => setName(event.target.value)} /></label>
          <label>{t.entityKind}<select value={kind} disabled={busy || !!editing && editing.id === identity.owner.entity_id && editing.kind === "person"} onChange={event => setKind(event.target.value as Entity["kind"])}>
            {kinds.map(value => <option key={value}>{value}</option>)}
          </select></label>
          <label>{r.sensitivity}<select value={sensitivity} disabled={busy} onChange={event => setSensitivity(event.target.value as Entity["sensitivity"])}>
            {["public", "private", "sensitive"].map(value => <option key={value}>{value}</option>)}
          </select></label>
        </div>
        <label>{t.aliases}<textarea value={aliases} disabled={busy} rows={3} onChange={event => setAliases(event.target.value)} aria-describedby="identity-alias-hint" /></label>
        <p className="review-hint" id="identity-alias-hint">{t.aliasHint}</p>
        {!editing && <><label className="review-checkbox"><input type="checkbox" checked={distinct} disabled={busy} onChange={event => setDistinct(event.target.checked)} />{t.distinct}</label><p className="review-hint">{t.distinctHint}</p></>}
        <button disabled={busy || !name.trim() || !validAliases}>{editing ? text.saveEdit : t.create}</button>
        {editing && <button type="button" disabled={busy} onClick={resetForm}>{text.cancel}</button>}
      </form>
      {!data.entities.length && <p>{t.noEntities}</p>}
      <label className="review-checkbox"><input type="checkbox" checked={allowGraphSensitive} disabled={busy} onChange={event => setAllowGraphSensitive(event.target.checked)} />{t.allowSensitive}</label>
      <ul className="review-list">{data.entities.map(item => <li key={item.id}>
        <strong>{item.name}</strong> · <code>{item.kind}</code><span className={`review-badge ${item.status}`}>{r[item.status]}</span>
        {metadata(item)}
        <div className="memory-actions">
          {item.status === "pending" && <button disabled={busy} aria-label={label(text.confirm, item)} onClick={() => void perform(async client => { await client.confirmEntity(item); }, true)}>{text.confirm}</button>}
          <button disabled={busy} aria-label={label(text.edit, item)} onClick={() => {
            setEditing(item); setName(item.name); setKind(item.kind); setAliases(item.aliases.join("\n")); setSensitivity(item.sensitivity); setView(null);
          }}>{text.edit}</button>
          <button disabled={busy} aria-label={label(t.history, item)} onClick={() => void perform(async (client, signal) => {
            setView(null); const rows = await client.entityHistory(item); if (!signal.aborted) setView({ epoch, kind: "entityHistory", rows });
          })}>{t.history}</button>
          <button disabled={busy || item.status !== "confirmed"} aria-label={label(t.graph, item)} onClick={() => void perform(async (client, signal) => {
            setView(null); const result = await client.neighbours(item, allowGraphSensitive);
            if (!signal.aborted) { setView({ epoch, kind: "graph", result }); setAllowGraphSensitive(false); }
          })}>{t.graph}</button>
          <button disabled={busy} aria-label={label(t.previewDelete, item)} onClick={() => void previewDelete(item, "entity")}>{t.previewDelete}</button>
        </div>
      </li>)}</ul>
    </section>
    <section aria-label={t.owner}>
      <h5>{t.owner}</h5><p>{nameOf(identity.owner.entity_id)}</p><p className="review-hint">{t.ownerHint}</p>
      <label>{t.owner}<select value={ownerTarget} disabled={busy} onChange={event => setOwnerTarget(event.target.value)}>
        <option value="">—</option>
        {ownerTarget && !confirmed.some(item => item.id === ownerTarget && item.kind === "person") && <option value={ownerTarget}>{ownerTarget} · {r.pending}</option>}
        {confirmed.filter(item => item.kind === "person").map(item => <option key={item.id} value={item.id}>{item.name} · {item.id}</option>)}
      </select></label>
      <button disabled={busy || !target} onClick={() => setView({ epoch, kind: "owner", target: target!, owner: identity.owner })}>{t.bindOwner}</button>
      <button disabled={busy || !identity.owner.entity_id} onClick={() => setView({ epoch, kind: "owner", target: null, owner: identity.owner })}>{t.unbindOwner}</button>
    </section>
    <section aria-label={t.resolve}>
      <h5>{t.resolve}</h5>
      <form className="review-form" onSubmit={event => {
        event.preventDefault(); if (!alias.trim()) return;
        void perform(async (client, signal) => {
          setView(null); const result = await client.resolve(alias.trim(), aliasKind || null, allowResolveSensitive);
          if (!signal.aborted) { setView({ epoch, kind: "resolution", result }); setAllowResolveSensitive(false); }
        });
      }}>
        <label>{t.aliasQuery}<input value={alias} maxLength={160} required disabled={busy} onChange={event => setAlias(event.target.value)} /></label>
        <label>{t.entityKind}<select value={aliasKind} disabled={busy} onChange={event => setAliasKind(event.target.value as Entity["kind"] | "")}>
          <option value="">{r.all}</option>{kinds.map(value => <option key={value}>{value}</option>)}
        </select></label>
        <label className="review-checkbox"><input type="checkbox" checked={allowResolveSensitive} disabled={busy} onChange={event => setAllowResolveSensitive(event.target.checked)} />{t.allowSensitive}</label>
        <button disabled={busy || !alias.trim()}>{t.resolve}</button>
      </form>
    </section>
    <section aria-label={t.relationships}>
      <h5>{t.relationships}</h5>
      <form className="review-form" onSubmit={event => {
        event.preventDefault(); if (!left || !right || left.id === right.id || !evidence || !predicateValid) return;
        void perform(async (client, signal) => {
          await client.createRelationship(left, right, evidence, predicate, relationSensitivity);
          if (!signal.aborted) { setEvidenceId(""); setView(null); }
        }, true);
      }}>
        <div className="review-form-grid">{selectEntity(leftId, setLeftId, t.from)}{selectEntity(rightId, setRightId, t.to)}</div>
        <label>{t.predicate}<input value={predicate} disabled={busy} required maxLength={100} pattern="[a-z][a-z0-9_]*" onChange={event => setPredicate(event.target.value)} /></label>
        <p className="review-hint">{t.predicateHint}</p>
        <label>{t.evidence}<select value={evidenceId} disabled={busy} required onChange={event => setEvidenceId(event.target.value)}>
          <option value="">—</option>
          {evidenceId && !evidence && <option value={evidenceId}>{evidenceId} · {r.pending}</option>}
          {data.memories.filter(item => item.status === "confirmed").map(item => <option key={item.id} value={item.id}>{item.key} · {item.id}@{item.revision}</option>)}
        </select></label>
        {evidence && <blockquote>{evidence.content}<p><code>{evidence.id}@{evidence.revision} · {evidence.belief} · {evidence.sensitivity} · {evidence.source}</code></p></blockquote>}
        <p className="review-hint">{t.evidenceHint}</p>
        <label>{r.sensitivity}<select value={relationSensitivity} disabled={busy} onChange={event => setRelationSensitivity(event.target.value as Entity["sensitivity"])}>
          {["public", "private", "sensitive"].map(value => <option key={value}>{value}</option>)}
        </select></label>
        <button disabled={busy || !left || !right || left.id === right.id || !evidence || !predicateValid}>{t.propose}</button>
      </form>
      {!identity.relationships.length && <p>{t.noRelationships}</p>}
      <ul className="review-list">{identity.relationships.map(item => {
        const a = confirmed.find(entity => entity.id === item.from_entity_id);
        const b = confirmed.find(entity => entity.id === item.to_entity_id);
        const memory = data.memories.find(memory => memory.id === item.evidence_id);
        const current = !!a && !!b && memory?.status === "confirmed" && memory.revision === item.evidence_revision;
        return <li key={item.id}>
          <strong>{nameOf(item.from_entity_id)} → {item.predicate} → {nameOf(item.to_entity_id)}</strong>{metadata(item)}
          <p>{t.evidence}: <code>{item.evidence_id}@{item.evidence_revision}</code></p>
          {current ? <blockquote>{memory?.content}</blockquote> : <p>{t.staleEvidence}</p>}
          <div className="memory-actions">
            {item.status === "pending" && <button disabled={busy || !current} aria-label={relationLabel(text.confirm, item)}
              onClick={() => void perform(async client => { await client.confirmRelationship(item, a!, b!); }, true)}>{text.confirm}</button>}
            <button disabled={busy} aria-label={relationLabel(t.history, item)} onClick={() => void perform(async (client, signal) => {
              setView(null); const rows = await client.relationshipHistory(item); if (!signal.aborted) setView({ epoch, kind: "relationshipHistory", rows });
            })}>{t.history}</button>
            <button disabled={busy} aria-label={relationLabel(t.previewDelete, item)} onClick={() => void previewDelete(item, "relationship")}>{t.previewDelete}</button>
          </div>
        </li>;
      })}</ul>
    </section>
    {currentView?.kind === "owner" && <ReviewDialog label={t.bindOwner} onCancel={() => setView(null)}>
      <h5>{t.bindOwner}</h5><p>{nameOf(currentView.owner.entity_id)} → {currentView.target?.name ?? t.notBound}</p>
      {currentView.target && metadata(currentView.target)}
      <button disabled={busy} onClick={() => void perform(async (client, signal) => {
        await client.bindOwner(currentView.owner, currentView.target); if (!signal.aborted) { setView(null); setOwnerTarget(""); }
      }, true)}>{text.confirm}</button><button disabled={busy} onClick={() => setView(null)}>{text.cancel}</button>
    </ReviewDialog>}
    {currentView?.kind === "delete" && <ReviewDialog label={t.deletionTargets} returnFocus={deleteTrigger} onCancel={() => setView(null)}>
      <h5>{t.deletionTargets}</h5><p>{t.deleteHint}</p>
      <p><strong>{"name" in currentView.preview.record ? currentView.preview.record.name
        : `${nameOf(currentView.preview.record.from_entity_id)} → ${currentView.preview.record.predicate} → ${nameOf(currentView.preview.record.to_entity_id)}`}</strong></p>
      {metadata(currentView.preview.record)}
      <p><code>{currentView.preview.digest}</code></p><p>{t.owner}: {currentView.preview.owner_binding ? nameOf(currentView.preview.record.id) : "—"}</p>
      <p>{t.historyCount}: {currentView.preview.history_count} · {t.originsCount}: {currentView.preview.origin_count}</p>
      <h6>{r.review} ({currentView.preview.memories.length})</h6><p>{t.memoryScopeHint}</p>
      <ul>{currentView.preview.memories.map(item => <li key={item.id}>{item.key}@{item.revision}<p>{item.content}</p></li>)}</ul>
      <h6>{r.sources} ({currentView.preview.sources.length})</h6>
      <ul>{currentView.preview.sources.map(item => <li key={item.id}>{item.name} · <code>{item.id}@{item.revision}</code></li>)}</ul>
      <h6>{r.runs} ({currentView.preview.runs.length})</h6><ul>{currentView.preview.runs.map(item => <li key={item.id}><code>{item.id} · {item.status}</code></li>)}</ul>
      <h6>{t.relationships} ({currentView.preview.relationships.length})</h6><ul>{currentView.preview.relationships.map(item => <li key={item.id}><code>{item.id}@{item.revision} · {item.predicate}</code></li>)}</ul>
      <button disabled={busy} onClick={() => void perform(async (client, signal) => {
        const preview = currentView.preview; setView(null); await client.deleteIdentity(preview); if (!signal.aborted) resetForm();
      }, true)}>{t.confirmDelete}</button><button disabled={busy} onClick={() => setView(null)}>{text.cancel}</button>
    </ReviewDialog>}
    {currentView && (currentView.kind === "entityHistory" || currentView.kind === "relationshipHistory") && <section className="review-inspection" aria-label={t.history}>
      <h5>{t.history}</h5><ol className="review-list">{currentView.rows.map(item => <li key={item.revision}>
        <strong>{"name" in item ? item.name : item.predicate}</strong> · <code>{item.change}</code>{metadata(item)}
      </li>)}</ol><button onClick={() => setView(null)}>{text.cancel}</button>
    </section>}
    {currentView?.kind === "resolution" && <section className="review-inspection" aria-label={t.resolve}>
      <h5>{t[currentView.result.status]}</h5><ul className="review-list">{currentView.result.matches.map(item => <li key={item.id}><strong>{item.name}</strong>{metadata(item)}</li>)}</ul>
    </section>}
    {currentView?.kind === "graph" && <section className="review-inspection" aria-label={t.graph}>
      <h5>{t.graph}</h5>{!currentView.result.relationships.length && <p>{t.noRelationships}</p>}
      <ul>{currentView.result.entities.map(item => <li key={item.id}>{item.name} · <code>{item.id}@{item.revision}</code></li>)}</ul>
      <ul>{currentView.result.relationships.map(item => <li key={item.id}>{nameOf(item.from_entity_id)} → {item.predicate} → {nameOf(item.to_entity_id)} · <code>{item.evidence_id}@{item.evidence_revision}</code></li>)}</ul>
    </section>}
  </section>;
}
