import { useState, type FormEvent } from "react";
import { ReviewDialog } from "./ReviewDialog";
import { newOperationKey, toolNames, type ActionEvent, type ActionPlan, type AgencyData, type Invocation, type PermissionInput, type ToolName, type ToolPermission } from "./agencyApi";
import type { createPersonalClient, Sensitivity, WorkbenchData } from "./personalApi";
import type { PersonalWorkspaceMessages } from "./personalMessages";

type Action = (client: ReturnType<typeof createPersonalClient>, signal: AbortSignal) => Promise<void>;
type View = { epoch: number; trigger: HTMLElement | null } & (
  | { kind: "permission"; permission: ToolPermission; input: PermissionInput }
  | { kind: "approve" | "execute" | "rollback" | "cancel"; plan: ActionPlan }
  | { kind: "events"; plan: ActionPlan; events: ActionEvent[] }
);
const labels: Sensitivity[] = ["public", "private", "sensitive"];
const selected = <T,>(items: T[], item: T, checked: boolean) => checked ? [...new Set([...items, item])] : items.filter(value => value !== item);

function PermissionForm({ permission, data, text, busy, dismiss, review }: {
  permission: ToolPermission; data: WorkbenchData; text: PersonalWorkspaceMessages; busy: boolean;
  dismiss: () => void; review: (input: PermissionInput) => void;
}) {
  const t = text.agency;
  const [input, setInput] = useState<PermissionInput>({ enabled: permission.enabled, labels: permission.labels, entity_ids: permission.entity_ids });
  function update(changes: Partial<PermissionInput>) { dismiss(); setInput(value => ({ ...value, ...changes })); }
  const entities = data.entities.filter(item => item.status === "confirmed");
  const missing = input.entity_ids?.filter(id => !entities.some(item => item.id === id)) ?? [];
  return <form className="review-form" onSubmit={event => { event.preventDefault(); review({ ...input, labels: [...input.labels], entity_ids: input.entity_ids === null ? null : [...input.entity_ids] }); }}>
    <h5>{permission.tool}</h5>
    <p>{text.review.revision}: {permission.revision} · {permission.scope}</p>
    <label className="review-checkbox"><input type="checkbox" disabled={busy} checked={input.enabled} onChange={event => update({ enabled: event.target.checked })} />{t.enabled}: {permission.tool}</label>
    <fieldset disabled={busy} className="agency-checkboxes"><legend>{text.review.sensitivity}: {permission.tool}</legend>
      {labels.map(label => <label className="review-checkbox" key={label}><input type="checkbox" checked={input.labels.includes(label)} onChange={event => update({ labels: selected(input.labels, label, event.target.checked) })} />{label}</label>)}
    </fieldset>
    <label>{t.entityScope}: {permission.tool}<select disabled={busy} value={input.entity_ids === null ? "all" : "selected"} onChange={event => update({ entity_ids: event.target.value === "all" ? null : [] })}>
      <option value="all">{t.allEntities}</option><option value="selected">{t.selectedEntities}</option>
    </select></label>
    {input.entity_ids !== null && <fieldset disabled={busy} className="agency-checkboxes"><legend>{t.selectedEntities}: {permission.tool}</legend>
      {[...entities.map(item => ({ id: item.id, name: item.name })), ...missing.map(id => ({ id, name: id }))].map(item => <label className="review-checkbox" key={item.id}>
        <input type="checkbox" checked={input.entity_ids!.includes(item.id)} onChange={event => update({ entity_ids: selected(input.entity_ids!, item.id, event.target.checked) })} />{item.name} · {item.id}
      </label>)}
    </fieldset>}
    <p className="review-hint">{t.entityHint}</p>
    <button disabled={busy}>{t.reviewPermission}: {permission.tool}</button>
  </form>;
}

export function AgencyReview({ data, agency, text, busy, epoch, perform }: {
  data: WorkbenchData; agency: AgencyData; text: PersonalWorkspaceMessages; busy: boolean; epoch: number;
  perform: (action: Action, mutation?: boolean) => Promise<void>;
}) {
  const t = text.agency;
  const [tool, setTool] = useState<ToolName>("tasks.create");
  const [intent, setIntent] = useState<"recommend" | "act">("recommend");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [content, setContent] = useState("");
  const [due, setDue] = useState("");
  const [project, setProject] = useState("");
  const [taskId, setTaskId] = useState("");
  const [sensitivity, setSensitivity] = useState<Sensitivity>("private");
  const [sources, setSources] = useState<string[]>([]);
  const [key, setKey] = useState<string>(newOperationKey);
  const [view, setView] = useState<View | null>(null);
  const current = view?.epoch === epoch ? view : null;
  const projects = data.entities.filter(item => item.kind === "project" && item.status === "confirmed");
  const memories = data.memories.filter(item => item.status === "confirmed" && item.belief === "known");
  const task = agency.tasks.find(item => item.id === taskId);
  const sourceCount = new Set([...sources, ...(tool === "tasks.complete" ? task?.source_ids ?? [] : [])]).size;
  const permission = agency.permissions.find(item => item.tool === tool)!;
  const validForm = key.trim().length > 0 && [...key].length <= 100 && sourceCount <= 20 && sources.every(id => memories.some(item => item.id === id)) &&
    (tool === "tasks.complete" ? !!task : title.trim().length > 0 && [...title.trim()].length <= 160 &&
      (!project || projects.some(item => item.id === project)) && (tool === "notes.create" ? content.trim().length > 0 && [...content.trim()].length <= 8000 :
        [...description.trim()].length <= 2000 && (!due || Number.isFinite(new Date(due).getTime())))) &&
    (intent === "recommend" || permission.enabled);
  const actionLabel = (name: string, plan: ActionPlan) => `${name}: ${plan.invocation.tool}, ${plan.id}`;
  function trigger() { return document.activeElement instanceof HTMLElement ? document.activeElement : null; }
  function live(plan: ActionPlan) {
    const p = agency.permissions.find(item => item.tool === plan.invocation.tool);
    return !!p && p.enabled && p.revision === plan.permission_revision && p.labels.includes(plan.invocation.sensitivity) &&
      Object.entries(plan.source_revisions).every(([id, version]) => memories.some(item => item.id === id && item.revision === version)) &&
      Object.entries(plan.entity_revisions).every(([id, version]) => data.entities.some(item => item.id === id && item.status === "confirmed" && item.revision === version)) &&
      (p.entity_ids === null || Object.keys(plan.entity_revisions).every(id => p.entity_ids!.includes(id))) &&
      (plan.invocation.tool !== "tasks.complete" || agency.tasks.some(item => {
        const args = plan.invocation.arguments as { task_id: string; expected_revision: number };
        return item.id === args.task_id && item.revision === args.expected_revision;
      }));
  }
  async function propose(event: FormEvent) {
    event.preventDefault(); if (!validForm) return;
    const argumentsValue: Invocation["arguments"] = tool === "tasks.complete" ? { task_id: task!.id, expected_revision: task!.revision }
      : tool === "notes.create" ? { title: title.trim(), content: content.trim(), project_id: project || null }
        : { title: title.trim(), description: description.trim(), project_id: project || null, due_at: due ? new Date(due).toISOString() : null };
    const invocation: Invocation = { tool, arguments: argumentsValue, source_ids: [...sources], sensitivity, intent, idempotency_key: key };
    await perform(async client => { await client.createAction(invocation, agency.owner_id); }, true);
    // Keep the exact draft/key on success and failure, including uncertain receipts.
    // A new key is always a separate explicit owner gesture.
  }
  async function inspect(plan: ActionPlan, kind: "approve" | "execute" | "rollback" | "cancel" | "events") {
    const initiating = trigger(); setView(null);
    await perform(async (client, signal) => {
      const reviewed = await client.reviewAction(plan);
      const events = kind === "events" ? await client.actionEvents(reviewed) : [];
      if (!signal.aborted) setView(kind === "events" ? { kind, plan: reviewed, events, epoch, trigger: initiating } : { kind, plan: reviewed, epoch, trigger: initiating });
    });
  }
  function metadata(plan: ActionPlan) {
    return <>
      <dl className="review-metadata">
        <div><dt>ID</dt><dd>{plan.id}</dd></div><div><dt>{text.identity.status}</dt><dd>{t[plan.status]}</dd></div>
        <div><dt>{text.review.revision}</dt><dd>{plan.revision}</dd></div><div><dt>{t.permissionVersion}</dt><dd>{plan.permission_revision}</dd></div>
        <div><dt>{text.review.sensitivity}</dt><dd>{plan.invocation.sensitivity}</dd></div><div><dt>{t.attempts}</dt><dd>{plan.attempts} / 3</dd></div>
        <div><dt>{t.idempotency}</dt><dd>{plan.invocation.idempotency_key}</dd></div><div><dt>{t.digest}</dt><dd>{plan.digest}</dd></div>
      </dl>
      <h6>{t.arguments}</h6><pre>{JSON.stringify(plan.invocation.arguments, null, 2)}</pre>
      <h6>{t.sourceVersions}</h6><ul>{Object.entries(plan.source_revisions).map(([id, revision]) => <li key={id}>{id} @ {revision}
        <blockquote>{data.memories.find(item => item.id === id && item.revision === revision)?.content ?? "—"}</blockquote>
      </li>)}</ul>
      <h6>{t.entityVersions}</h6><ul>{Object.entries(plan.entity_revisions).map(([id, revision]) => <li key={id}>{id} @ {revision} · {data.entities.find(item => item.id === id && item.revision === revision)?.name ?? "—"}</li>)}</ul>
      {plan.result && <p>{plan.result.table}/{plan.result.id} @ {plan.result.revision} · changed={String(plan.result.changed)}</p>}
    </>;
  }
  const dialogLabel = current?.kind === "permission" ? t.reviewPermission : current?.kind === "events" ? t.events
    : current?.kind === "approve" ? t.reviewPlan : current?.kind === "execute" ? t.reviewExecute : current?.kind === "rollback" ? t.reviewRollback : t.reviewCancel;
  return <section className="agency-review" aria-label={t.title}>
    <h4>{t.title}</h4><p className="review-hint">{t.boundary}</p>
    <section aria-label={t.permissions}><h5>{t.permissions}</h5>
      {agency.permissions.map(item => <PermissionForm key={`${epoch}-${item.tool}-${item.revision}`} permission={item} data={data} text={text} busy={busy}
        dismiss={() => setView(null)} review={input => setView({ kind: "permission", permission: item, input, epoch, trigger: trigger() })} />)}
    </section>
    <section aria-label={t.builder}><h5>{t.builder}</h5><form className="review-form" onSubmit={event => void propose(event)}>
      <div className="review-form-grid">
        <label>{t.tool}<select disabled={busy} value={tool} onChange={event => { setView(null); setTool(event.target.value as ToolName); }}>{toolNames.map(name => <option key={name}>{name}</option>)}</select></label>
        <label>{t.intent}<select disabled={busy} value={intent} onChange={event => { setView(null); setIntent(event.target.value as typeof intent); }}><option value="recommend">{t.recommend}</option><option value="act">{t.act}</option></select></label>
        <label>{text.review.sensitivity}<select disabled={busy} value={sensitivity} onChange={event => setSensitivity(event.target.value as Sensitivity)}>{labels.map(label => <option key={label}>{label}</option>)}</select></label>
        {tool === "tasks.complete" ? <label>{t.outputs}<select disabled={busy} value={taskId} onChange={event => setTaskId(event.target.value)}><option value="">—</option>{agency.tasks.map(item => <option key={item.id} value={item.id}>{item.title} · {item.id} @ {item.revision} · {item.status}</option>)}</select></label>
          : <><label>{t.taskTitle}<input disabled={busy} value={title} maxLength={160} required onChange={event => setTitle(event.target.value)} /></label>
            <label>{t.project}<select disabled={busy} value={project} onChange={event => setProject(event.target.value)}><option value="">{text.review.unscoped}</option>{projects.map(item => <option key={item.id} value={item.id}>{item.name} · {item.id}</option>)}</select></label>
            {tool === "tasks.create" && <label>{t.dueTime}<input type="datetime-local" disabled={busy} value={due} onChange={event => setDue(event.target.value)} /></label>}
          </>}
      </div>
      {tool !== "tasks.complete" && <label>{tool === "tasks.create" ? t.description : t.noteContent}<textarea disabled={busy} value={tool === "tasks.create" ? description : content} maxLength={tool === "tasks.create" ? 2000 : 8000} required={tool === "notes.create"}
        onChange={event => tool === "tasks.create" ? setDescription(event.target.value) : setContent(event.target.value)} /></label>}
      <label>{t.sources}<select multiple disabled={busy} value={sources} onChange={event => setSources(Array.from(event.target.selectedOptions, item => item.value))}>
        {memories.map(item => <option key={item.id} value={item.id}>{item.key} · {item.id} @ {item.revision}</option>)}
      </select></label>
      <p className="review-hint">{t.sources}: {sourceCount} / 20</p>
      {sources.map(id => <blockquote key={id}>{data.memories.find(item => item.id === id)?.content ?? id}</blockquote>)}
      <label>{t.idempotency}<input disabled={busy} value={key} maxLength={100} onChange={event => setKey(event.target.value)} /></label>
      <p className="review-hint">{t.keyHint}</p><div className="memory-actions"><button type="button" disabled={busy} onClick={() => { setView(null); setKey(newOperationKey()); }}>{t.newKey}</button><button disabled={busy || !validForm}>{t.propose}</button></div>
    </form></section>
    {current && <ReviewDialog label={dialogLabel} returnFocus={current.trigger} onCancel={() => setView(null)}>
      <h5>{dialogLabel}</h5>
      {current.kind === "permission" ? <><p>{current.permission.tool} · {text.review.revision}: {current.permission.revision}</p>
        <pre>{JSON.stringify({ before: { enabled: current.permission.enabled, labels: current.permission.labels, entity_ids: current.permission.entity_ids }, after: current.input }, null, 2)}</pre>
        <p>{t.entityHint}</p><button disabled={busy} onClick={() => void perform(async client => { setView(null); await client.configureTool(current.permission, current.input); }, true)}>{t.applyPermission}</button></>
        : <>{metadata(current.plan)}
          {current.kind === "events" ? <ul>{current.events.map(event => <li key={event.id}>{event.stage} · {t[event.outcome]} · {event.code} · {event.created_at}</li>)}</ul>
            : <><p>{current.kind === "rollback" ? t.rollbackHint : t.reviewHint}</p>{current.kind === "rollback" && <p>{t.copiesHint}</p>}
              {(current.kind === "approve" || current.kind === "execute") && !live(current.plan) && <p role="alert">{t.stalePlan}</p>}
              <button disabled={busy || (current.kind === "approve" || current.kind === "execute") && !live(current.plan)} onClick={() => void perform(async client => {
                setView(null); if (current.kind === "approve") await client.approveAction(current.plan);
                else await client.act(current.plan, current.kind as "execute" | "rollback" | "cancel");
              }, true)}>{current.kind === "approve" ? t.approve : current.kind === "execute" ? current.plan.status === "failed" ? t.retry : t.execute : current.kind === "rollback" ? t.rollback : t.cancelPlan}</button>
            </>}
        </>}
      <button disabled={busy} onClick={() => setView(null)}>{text.cancel}</button>
    </ReviewDialog>}
    <section aria-label={t.plans}><h5>{t.plans}</h5>{!agency.plans.length && <p>{t.noPlans}</p>}<ul className="review-list">
      {[...agency.plans].reverse().map(plan => <li key={plan.id}><h6>{plan.invocation.tool} · {plan.id}</h6><p>{t[plan.status]}</p>
        <p>{t.attempts}: {plan.attempts} / 3 · {text.review.revision}: {plan.revision}</p><div className="memory-actions">
          {plan.status === "planned" && <button disabled={busy} onClick={() => void inspect(plan, "approve")}>{actionLabel(t.reviewPlan, plan)}</button>}
          {(plan.status === "approved" || plan.status === "failed" && plan.attempts < 3) && <button disabled={busy} onClick={() => void inspect(plan, "execute")}>{actionLabel(t.reviewExecute, plan)}</button>}
          {plan.status === "completed" && <button disabled={busy} onClick={() => void inspect(plan, "rollback")}>{actionLabel(t.reviewRollback, plan)}</button>}
          {["recommended", "planned", "approved", "failed"].includes(plan.status) && <button disabled={busy} onClick={() => void inspect(plan, "cancel")}>{actionLabel(t.reviewCancel, plan)}</button>}
          <button disabled={busy} onClick={() => void inspect(plan, "events")}>{actionLabel(t.events, plan)}</button>
        </div>
      </li>)}
    </ul></section>
    <section aria-label={t.outputs}><h5>{t.outputs}</h5>{!agency.tasks.length && !agency.notes.length && <p>{t.noOutputs}</p>}<ul className="review-list">
      {[...agency.tasks, ...agency.notes].map(item => <li key={item.id}><h6>{item.title}</h6><p>{item.id} @ {item.revision} · {item.sensitivity}{"status" in item ? ` · ${item.status}` : ""}</p>
        <blockquote>{"description" in item ? item.description : item.content}</blockquote><p>{item.created_by} · {item.source_ids.join(" · ")}</p>
        {item.project_id && <p>{t.project}: {data.entities.find(entity => entity.id === item.project_id)?.name ?? item.project_id}</p>}
        {"due_at" in item && item.due_at && <p>{t.dueTime}: {item.due_at}</p>}
      </li>)}
    </ul><p className="review-hint">{t.copiesHint}</p></section>
  </section>;
}
