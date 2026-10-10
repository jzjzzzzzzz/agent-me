import { afterEach, expect, it, vi } from "vitest";
import fixture from "./__fixtures__/governance.json";
import { isConsolidationPlan, isGovernanceData, isLearningPolicy, isRetentionPlan, isRetentionReview, type GovernanceData, type RetentionReview } from "./governanceApi";
import { createPersonalClient } from "./personalApi";
afterEach(() => vi.unstubAllGlobals());
const response = (v: unknown) => new Response(JSON.stringify(v), { status: 200 });
const client = () => createPersonalClient("fictional-token", new AbortController().signal);
it("parses actual native governance, retention and consolidation snapshots", () => {
  expect(isGovernanceData(fixture.state)).toBe(true); expect(isRetentionPlan(fixture.retention)).toBe(true);
  expect(isRetentionReview(fixture.retentionReview)).toBe(true); expect(isConsolidationPlan(fixture.consolidation)).toBe(true); expect(isConsolidationPlan(fixture.consolidationApplied)).toBe(true);
});
it.each([
  { max_candidates: true }, { max_candidates: 101 }, { labels: ["secret"] }, { source_kinds: ["shell"] },
  { blocked_key_prefixes: [" "] }, { approved: true },
])("rejects invalid policy metadata %j", update => expect(isLearningPolicy({ ...fixture.state.learning.policy, ...update })).toBe(false));
it("rejects duplicate members, missing keeper, wrong merged count and malformed retention fingerprints", () => {
  const plan = fixture.consolidation;
  expect(isConsolidationPlan({ ...plan, groups: [{ ...plan.groups[0], keeper_id: "foreign" }] })).toBe(false);
  expect(isConsolidationPlan({ ...plan, groups: [plan.groups[0], plan.groups[0]] })).toBe(false);
  expect(isConsolidationPlan({ ...fixture.consolidationApplied, merged_count: 0 })).toBe(false);
  expect(isRetentionPlan({ ...fixture.retention, targets: [{ table: "turns", id: "fixture", revision: null, fingerprint: null }] })).toBe(false);
  expect(isGovernanceData({ ...fixture.state, retention_plans: [{ ...fixture.retention, owner_id: "foreign" }] })).toBe(false);
});
it("sends exact policy revision/owner and both independently reviewed retention digests", async () => {
  const state = fixture.state as GovernanceData; const review = fixture.retentionReview as RetentionReview;
  const fetcher = vi.fn(async (url: string, options: RequestInit) => {
    expect(options.cache).toBe("no-store");
    return response(url.endsWith("/learning/policy") ? { ...state.learning, revision: state.learning.revision + 1 } : fixture.retentionApplied);
  }); vi.stubGlobal("fetch", fetcher);
  await client().configureLearning(state, state.learning.policy); await client().applyRetention(review);
  expect(JSON.parse(fetcher.mock.calls[0][1].body as string)).toEqual({ policy: state.learning.policy, expected_revision: state.learning.revision, expected_owner_id: state.owner_id });
  expect(JSON.parse(fetcher.mock.calls[1][1].body as string)).toEqual({ digest: review.digest, scope_digest: review.scope_digest });
});
it("refuses wrong owner previews and altered application receipts", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...fixture.retention, owner_id: "foreign" })));
  await expect(client().previewRetention({ ...fixture.state, retention: { revision: fixture.retention.policy_revision, policy: fixture.state.retention.policy } } as GovernanceData, null)).rejects.toMatchObject({ kind: "invalid" });
  vi.stubGlobal("fetch", vi.fn(async () => response({ ...fixture.retentionApplied, id: "foreign" })));
  await expect(client().applyRetention(fixture.retentionReview as RetentionReview)).rejects.toMatchObject({ kind: "invalid" });
});
