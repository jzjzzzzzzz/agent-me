import { useState } from "react";
import { ReviewDialog } from "./ReviewDialog";
import { strictSnapshotJson } from "./migrationApi";
import { isLearningPolicy, isRetentionPolicy, type ConsolidationPlan, type GovernanceData, type LearningPolicy, type RetentionPolicy, type RetentionPlan, type RetentionReview } from "./governanceApi";
import type { createPersonalClient, MemoryKind, WorkbenchData } from "./personalApi";
import type { PersonalWorkspaceMessages } from "./personalMessages";
type Action = (client: ReturnType<typeof createPersonalClient>, signal: AbortSignal) => Promise<void>;
type View = { epoch: number; trigger: HTMLElement | null } & (
  | { kind: "learning"; policy: LearningPolicy; state: GovernanceData }
  | { kind: "retentionPolicy"; policy: RetentionPolicy; state: GovernanceData }
  | { kind: "retention"; review: RetentionReview }
  | { kind: "consolidation"; plan: ConsolidationPlan }
);
const kinds: MemoryKind[] = ["fact", "preference", "event", "decision"];
function PolicyEditor({ title, value, valid, text, busy, changed, review }: {
  title: string; value: object; valid: (value: unknown) => boolean; text: PersonalWorkspaceMessages; busy: boolean;
  changed: () => void; review: (value: unknown) => void;
}) {
  const [raw, setRaw] = useState(JSON.stringify(value, null, 2));
  let parsed: unknown = null; try { parsed = strictSnapshotJson(raw); } catch { /* Local typed error only. */ }
  const good = valid(parsed);
  return <form className="review-form" onSubmit={event => { event.preventDefault(); if (good) review(parsed); }}>
    <h5>{title}</h5><label>{text.governance.policyJson}: {title}<textarea maxLength={16384} disabled={busy} value={raw} rows={10} onChange={event => { changed(); setRaw(event.target.value); }} /></label>
    <p className="review-hint">{text.governance.policyHint}</p>{!good && <p role="alert">{text.governance.invalid}</p>}
    <button disabled={busy || !good}>{text.governance.reviewPolicy}: {title}</button>
  </form>;
}
export function LearningGovernance({ data, state, text, epoch, busy, perform }: {
  data: WorkbenchData; state: GovernanceData; text: PersonalWorkspaceMessages; epoch: number; busy: boolean;
  perform: (action: Action, mutation?: boolean) => Promise<void>;
}) {
  const t = text.governance;
  const [view, setView] = useState<View | null>(null); const [consent, setConsent] = useState(false);
  const [asOf, setAsOf] = useState(""); const [prefix, setPrefix] = useState(""); const [entity, setEntity] = useState(""); const [selectedKinds, setSelectedKinds] = useState<MemoryKind[]>(kinds);
  const [result, setResult] = useState("");
  const current = view?.epoch === epoch ? view : null;
  function dismiss() { setView(null); setConsent(false); setResult(""); }
  const trigger = () => document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const memory = (id: string, revision: number) => data.memories.find(item => item.id === id && item.revision === revision);
  function showCounts(label: string, counts: Record<string, number>) { return <p>{label}: {Object.entries(counts).map(([key, n]) => `${key}: ${n}`).join(" · ") || "—"}</p>; }
  async function retentionReview(plan: RetentionPlan) {
    const initiating = trigger(); dismiss();
    await perform(async (client, signal) => { const review = await client.reviewRetention(plan); if (!signal.aborted) setView({ kind: "retention", review, epoch, trigger: initiating }); });
  }
  const label = current?.kind === "retention" ? t.retentionScope : current?.kind === "consolidation" ? t.reviewConsolidation : t.reviewPolicy;
  return <section aria-label={t.title} className="governance-review"><h4>{t.title}</h4><p className="review-hint">{t.boundary}</p>
    <PolicyEditor key={`learning-${epoch}-${state.learning.revision}`} title={t.learning} value={state.learning.policy} valid={isLearningPolicy} text={text} busy={busy} changed={dismiss}
      review={policy => { dismiss(); setView({ kind: "learning", policy: policy as LearningPolicy, state, epoch, trigger: trigger() }); }} />
    <PolicyEditor key={`retention-${epoch}-${state.retention.revision}`} title={t.retention} value={state.retention.policy} valid={isRetentionPolicy} text={text} busy={busy} changed={dismiss}
      review={policy => { dismiss(); setView({ kind: "retentionPolicy", policy: policy as RetentionPolicy, state, epoch, trigger: trigger() }); }} />
    <section aria-label={t.retentionPlans}><h5>{t.retentionPlans}</h5><p>{t.retentionHint}</p><label>{t.asOf}<input type="datetime-local" disabled={busy} value={asOf} onChange={event => setAsOf(event.target.value)} /></label>
      <button disabled={busy || !!asOf && !Number.isFinite(new Date(asOf).getTime())} onClick={() => void perform(async client => { dismiss(); await client.previewRetention(state, asOf ? new Date(asOf).toISOString() : null); }, true)}>{t.createRetention}</button>
      {!state.retention_plans.length && <p>{t.noPlans}</p>}<ul className="review-list">{state.retention_plans.map(plan => <li key={plan.id}><p>{plan.id} · {plan.status} · {plan.as_of} · {plan.targets.length}</p>
        {Date.parse(plan.as_of) > Date.parse(state.observed_at) && <p>{t.future}</p>}
        {plan.status === "planned" && <button disabled={busy || Date.parse(plan.as_of) > Date.parse(state.observed_at)} onClick={() => void retentionReview(plan)}>{t.reviewRetention}: {plan.id}</button>}
      </li>)}</ul>
    </section>
    <section aria-label={t.consolidation}><h5>{t.consolidation}</h5><p>{t.consolidationHint}</p><div className="review-form-grid">
      <label>{t.keyPrefix}<input disabled={busy} value={prefix} maxLength={200} onChange={event => setPrefix(event.target.value)} /></label>
      <label>{text.review.entity}<select disabled={busy} value={entity} onChange={event => setEntity(event.target.value)}><option value="">{text.review.unscoped}</option>{data.entities.filter(row => row.status === "confirmed").map(row => <option key={row.id} value={row.id}>{row.name} · {row.id}</option>)}</select></label>
    </div><fieldset disabled={busy} className="agency-checkboxes"><legend>{t.kinds}</legend>{kinds.map(kind => <label className="review-checkbox" key={kind}><input type="checkbox" checked={selectedKinds.includes(kind)} onChange={event => setSelectedKinds(event.target.checked ? [...selectedKinds, kind] : selectedKinds.filter(value => value !== kind))} />{kind}</label>)}</fieldset>
      <button disabled={busy || [...prefix.trim()].length > 100 || !!entity && !data.entities.some(row => row.id === entity && row.status === "confirmed")} onClick={() => void perform(async client => { dismiss(); await client.previewConsolidation(state, { key_prefix: prefix.trim() || null, entity_id: entity || null, kinds: selectedKinds }); }, true)}>{t.createConsolidation}</button>
      <h6>{t.consolidationPlans}</h6>{!state.consolidation_plans.length && <p>{t.noPlans}</p>}<ul className="review-list">{[...state.consolidation_plans].reverse().map(plan => <li key={plan.id}><p>{plan.id} · {plan.status} · {plan.groups.length}</p>
        {plan.status === "planned" && <button disabled={busy} onClick={() => { dismiss(); setView({ kind: "consolidation", plan, epoch, trigger: trigger() }); }}>{t.reviewConsolidation}: {plan.id}</button>}
      </li>)}</ul>
    </section>
    {current && <ReviewDialog label={label} returnFocus={current.trigger} onCancel={dismiss}><h5>{label}</h5>
      {current.kind === "learning" || current.kind === "retentionPolicy" ? <><p>{state.owner_id} · {text.review.revision}: {current.kind === "learning" ? current.state.learning.revision : current.state.retention.revision}</p>
        <pre>{JSON.stringify({ before: current.kind === "learning" ? current.state.learning.policy : current.state.retention.policy, after: current.policy }, null, 2)}</pre>
        <button disabled={busy} onClick={() => void perform(async client => { dismiss(); if (current.kind === "learning") await client.configureLearning(current.state, current.policy); else await client.configureRetention(current.state, current.policy); }, true)}>{t.applyPolicy}</button>
      </> : <>
        {current.kind === "retention" ? <><p>{current.review.plan.id} · {current.review.plan.as_of}</p><dl className="review-metadata"><div><dt>{t.digest}</dt><dd>{current.review.digest}</dd></div><div><dt>{t.scopeDigest}</dt><dd>{current.review.scope_digest}</dd></div></dl>
          {showCounts(t.removed, current.review.removed_counts)}{showCounts(t.forgetting, current.review.forgetting_counts)}{showCounts(t.retained, current.review.retained_counts)}<p>{t.independentHint}</p>
          <ul>{current.review.plan.targets.map(target => <li key={`${target.table}/${target.id}`}>{target.table} · {target.id} @ {target.revision ?? "—"}{target.table === "entries" && target.revision !== null && <blockquote>{memory(target.id, target.revision)?.content ?? "—"}</blockquote>}</li>)}</ul>
        </> : <><dl className="review-metadata"><div><dt>{t.digest}</dt><dd>{current.plan.digest}</dd></div></dl><p>{t.consolidationHint}</p><ul>{current.plan.groups.map(group => <li key={group.keeper_id}><h6>{t.keeper}: {group.keeper_id}</h6><ul>{group.members.map(member => <li key={member.id}>{member.id} @ {member.revision} · {memory(member.id, member.revision)?.status ?? "—"}<blockquote>{memory(member.id, member.revision)?.content ?? "—"}</blockquote></li>)}</ul></li>)}</ul></>}
        <label className="review-checkbox"><input type="checkbox" disabled={busy} checked={consent} onChange={event => setConsent(event.target.checked)} />{t.consent}</label>
        <button disabled={busy || !consent || current.kind === "consolidation" && current.plan.groups.some(group => group.members.some(member => !memory(member.id, member.revision)))} onClick={() => void perform(async (client, signal) => {
          dismiss(); const value = current.kind === "retention" ? await client.applyRetention(current.review) : await client.applyConsolidation(current.plan); if (!signal.aborted) setResult(value.id);
        }, true)}>{current.kind === "retention" ? t.applyRetention : t.applyConsolidation}</button>
      </>}
      <button disabled={busy} onClick={dismiss}>{text.cancel}</button>
    </ReviewDialog>}
    {result && <p role="status">{t.applied}: {result}</p>}
  </section>;
}
