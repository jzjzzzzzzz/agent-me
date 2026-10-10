import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { messages } from "./i18n";
import { PersonalWorkspace } from "./PersonalWorkspace";

const english = messages.en.personalWorkspace;

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it.each([[42, 42], [undefined, 8000], [12000, 8000]])("enforces configured limit %s with an effective boundary of %s", async (configured, limit) => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify([]), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  render(<PersonalWorkspace external={false} text={english} maxQuestionChars={configured} />);
  fireEvent.change(screen.getByLabelText(/Workspace token/), { target: { value: "synthetic-token" } });
  fireEvent.click(screen.getByRole("button", { name: /Unlock/ }));
  const question = await screen.findByLabelText(/Private question/);
  expect(question).toHaveAttribute("maxlength", String(limit));
  const form = question.closest("form")!;
  fireEvent.change(question, { target: { value: "x".repeat(limit + 1) } });
  fireEvent.submit(form);
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(question).toHaveValue("x".repeat(limit + 1));
  fireEvent.change(question, { target: { value: "x".repeat(limit) } });
  fireEvent.submit(form);
  await waitFor(() => expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("/chat"), expect.objectContaining({ body: JSON.stringify({ question: "x".repeat(limit) }) })));
  await waitFor(() => expect(question).toHaveValue(""));
});

it("preserves a draft when the limit shrinks and allows sending after shortening", async () => {
  const fetcher = vi.fn(async () => new Response(JSON.stringify([]), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  const { rerender } = render(<PersonalWorkspace external={false} text={english} maxQuestionChars={100} />);
  fireEvent.change(screen.getByLabelText(/Workspace token/), { target: { value: "synthetic-token" } });
  fireEvent.click(screen.getByRole("button", { name: /Unlock/ }));
  const question = await screen.findByLabelText(/Private question/);
  fireEvent.change(question, { target: { value: "x".repeat(43) } });
  rerender(<PersonalWorkspace external={false} text={english} maxQuestionChars={42} />);
  expect(question).toHaveValue("x".repeat(43));
  expect(screen.getByRole("button", { name: /Send/ })).toBeDisabled();
  fireEvent.submit(question.closest("form")!);
  expect(fetcher).toHaveBeenCalledTimes(2);
  fireEvent.change(question, { target: { value: "shortened question" } });
  expect(screen.getByRole("button", { name: /Send/ })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: /Send/ }));
  await waitFor(() => expect(question).toHaveValue(""));
});

it("requires a token, loads persisted memory, and clears private state on lock", async () => {
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify(
    url.endsWith("/entries") ? [{ id: "one", key: "identity.name", kind: "fact", content: "Alex Example", status: "confirmed", source: "manual", updated_at: "2026-01-01" }] : [{ id: "turn", role: "user", content: "Saved question" }],
  ), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  render(<PersonalWorkspace external={false} text={english} />);
  expect(fetcher).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText(/Workspace token/), { target: { value: "local-token" } });
  fireEvent.click(screen.getByRole("button", { name: /Unlock/ }));
  expect(await screen.findByText("Alex Example")).toBeInTheDocument();
  expect(screen.getByText("Saved question")).toBeInTheDocument();
  const options = (fetcher.mock.calls[0] as unknown as [string, RequestInit])[1];
  expect(options.headers).toMatchObject({ Authorization: "Bearer local-token" });
  fireEvent.click(screen.getByRole("button", { name: /Lock/ }));
  expect(screen.queryByText("Alex Example")).not.toBeInTheDocument();
  expect(screen.getByLabelText(/Workspace token/)).toHaveValue("");
});

it("does not expose the workspace after authentication failure", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Private workspace token required" }), { status: 401 })));
  render(<PersonalWorkspace external text={english} />);
  fireEvent.change(screen.getByLabelText(/Workspace token/), { target: { value: "bad" } });
  fireEvent.click(screen.getByRole("button", { name: /Unlock/ }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Private workspace token required"));
  expect(screen.queryByRole("button", { name: /Send/ })).not.toBeInTheDocument();
});

it("renders both private data destinations in the selected locale", () => {
  const { rerender } = render(
    <PersonalWorkspace external text={messages["zh-CN"].personalWorkspace} />,
  );

  expect(screen.getByRole("region", { name: "私有工作区" })).toHaveTextContent(
    "审核工作台不调用模型服务",
  );

  rerender(<PersonalWorkspace external={false} text={messages.ja.personalWorkspace} />);

  expect(screen.getByRole("region", { name: "プライベートワークスペース" })).toHaveTextContent(
    "外部モデルプロバイダーへ送信されません",
  );
});

it("relocalizes a safe server error without another request or HTML rendering", async () => {
  const fetcher = vi.fn(async () => new Response(
    JSON.stringify({ detail: "Synthetic <strong>token detail</strong>" }),
    { status: 401 },
  ));
  vi.stubGlobal("fetch", fetcher);
  const { rerender } = render(<PersonalWorkspace external={false} text={english} />);
  fireEvent.change(screen.getByLabelText("Workspace token"), { target: { value: "bad" } });
  fireEvent.click(screen.getByRole("button", { name: "Unlock" }));

  const alert = await screen.findByRole("alert");
  expect(alert).toHaveTextContent("Request failed: Synthetic <strong>token detail</strong>");
  expect(alert.querySelector("strong")).toBeNull();
  const requestCount = fetcher.mock.calls.length;

  rerender(<PersonalWorkspace external={false} text={messages["zh-CN"].personalWorkspace} />);

  expect(screen.getByRole("alert")).toHaveTextContent(
    "请求失败: Synthetic <strong>token detail</strong>",
  );
  expect(fetcher).toHaveBeenCalledTimes(requestCount);
});

it("identifies duplicate-key memory actions by accessible name and preserves their behavior", async () => {
  const entries = [
    { id: "opaque-a", key: "profile.alias", kind: "fact", content: "River Example", status: "pending", source: "manual", updated_at: "2026-01-01" },
    { id: "opaque-b", key: "profile.alias", kind: "preference", content: "Sky Example", status: "pending", source: "chat", updated_at: "2026-01-02" },
  ];
  let resolveConfirm!: (response: Response) => void;
  const confirmResponse = new Promise<Response>(resolve => { resolveConfirm = resolve; });
  const fetcher = vi.fn((url: string) => {
    if (url.endsWith("/entries/opaque-a/confirm")) return confirmResponse;
    return Promise.resolve(new Response(JSON.stringify(url.endsWith("/entries") ? entries : []), { status: 200 }));
  });
  vi.stubGlobal("fetch", fetcher);
  render(<PersonalWorkspace external={false} text={english} />);
  fireEvent.change(screen.getByLabelText(/Workspace token/), { target: { value: "synthetic-token" } });
  fireEvent.click(screen.getByRole("button", { name: /Unlock/ }));
  expect(await screen.findByText("River Example")).toBeInTheDocument();

  const firstConfirm = screen.getByRole("button", { name: "Confirm: profile.alias, memory 1" });
  const secondConfirm = screen.getByRole("button", { name: "Confirm: profile.alias, memory 2" });
  const firstEdit = screen.getByRole("button", { name: "Edit: profile.alias, memory 1" });
  const secondEdit = screen.getByRole("button", { name: "Edit: profile.alias, memory 2" });
  const firstDelete = screen.getByRole("button", { name: "Delete: profile.alias, memory 1" });
  const secondDelete = screen.getByRole("button", { name: "Delete: profile.alias, memory 2" });

  fireEvent.click(firstConfirm);
  await waitFor(() => expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("/entries/opaque-a/confirm"), expect.any(Object)));
  expect(firstConfirm).toBeDisabled();
  expect(secondConfirm).toBeDisabled();
  expect(firstEdit).toBeDisabled();
  expect(secondEdit).toBeDisabled();
  expect(firstDelete).toBeDisabled();
  expect(secondDelete).toBeDisabled();
  resolveConfirm(new Response(JSON.stringify({}), { status: 200 }));
  await waitFor(() => expect(secondEdit).toBeEnabled());

  fireEvent.click(secondEdit);
  expect(screen.getByLabelText(/Content/)).toHaveValue("Sky Example");
  fireEvent.click(secondDelete);
  await waitFor(() => expect(fetcher).toHaveBeenCalledWith(expect.stringContaining("/entries/opaque-b/delete"), expect.any(Object)));
});

it("binds compatibility confirmation and conflict replacement to displayed revisions", async () => {
  const entries = [
    { id: "new", revision: 2, key: "identity.name", kind: "fact", content: "Alex Example", status: "pending", source: "manual", updated_at: "2026-01-01" },
    { id: "old", revision: 4, key: "identity.name", kind: "fact", content: "River Example", status: "confirmed", source: "manual", updated_at: "2026-01-01" },
  ];
  let confirmations = 0;
  const fetcher = vi.fn(async (url: string) => {
    if (url.endsWith("/entries/new/confirm") && ++confirmations === 1) {
      return new Response(JSON.stringify({ detail: { conflict_ids: ["old"], conflict_revisions: { old: 4 } } }), { status: 409 });
    }
    return new Response(JSON.stringify(url.endsWith("/entries") ? entries : []), { status: 200 });
  });
  vi.stubGlobal("fetch", fetcher);
  render(<PersonalWorkspace external={false} text={english} />);
  fireEvent.change(screen.getByLabelText("Workspace token"), { target: { value: "synthetic" } });
  fireEvent.click(screen.getByRole("button", { name: "Unlock" }));
  fireEvent.click(await screen.findByRole("button", { name: "Confirm: identity.name, memory 1" }));
  const replace = await screen.findByRole("button", { name: "Replace" });
  await waitFor(() => expect(replace).toBeEnabled());
  fireEvent.click(replace);
  await waitFor(() => expect(confirmations).toBe(2));
  const bodies = (fetcher.mock.calls as unknown as [string, RequestInit][])
    .filter(([url]) => url.endsWith("/confirm")).map(([, options]) => JSON.parse(options.body as string));
  expect(bodies).toEqual([
    { replace_ids: [], expected_revision: 2 },
    { replace_ids: ["old"], expected_revision: 2, replace_revisions: { old: 4 } },
  ]);
});

it("preserves the reviewed revision while editing and sends it on deletion", async () => {
  const entries = [{ id: "one", revision: 3, key: "identity.name", kind: "fact", content: "Alex Example", status: "confirmed", source: "manual", updated_at: "2026-01-01" }];
  const fetcher = vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith("/entries") ? entries : []), { status: 200 }));
  vi.stubGlobal("fetch", fetcher);
  render(<PersonalWorkspace external={false} text={english} />);
  fireEvent.change(screen.getByLabelText("Workspace token"), { target: { value: "synthetic" } });
  fireEvent.click(screen.getByRole("button", { name: "Unlock" }));
  fireEvent.click(await screen.findByRole("button", { name: "Edit: identity.name, memory 1" }));
  fireEvent.change(screen.getByLabelText("Content"), { target: { value: "River Example" } });
  fireEvent.click(screen.getByRole("button", { name: "Save edit as pending" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "Delete: identity.name, memory 1" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Delete: identity.name, memory 1" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledWith(expect.stringMatching(/\/delete$/), expect.any(Object)));
  const calls = fetcher.mock.calls as unknown as [string, RequestInit][];
  expect(JSON.parse(calls.find(([url]) => url.endsWith("/edit"))![1].body as string)).toMatchObject({ expected_revision: 3 });
  expect(JSON.parse(calls.find(([url]) => url.endsWith("/delete"))![1].body as string)).toEqual({ expected_revision: 3 });
});

it("does not approve an unseen newer conflict revision in the compatibility form", async () => {
  const entries = [
    { id: "new", revision: 1, key: "identity.name", kind: "fact", content: "Alex Example", status: "pending", source: "manual", updated_at: "2026-01-01" },
    { id: "old", revision: 3, key: "identity.name", kind: "fact", content: "River Example", status: "confirmed", source: "manual", updated_at: "2026-01-01" },
  ];
  vi.stubGlobal("fetch", vi.fn(async (url: string) => url.endsWith("/confirm")
    ? new Response(JSON.stringify({ detail: { conflict_ids: ["old"], conflict_revisions: { old: 4 } } }), { status: 409 })
    : new Response(JSON.stringify(url.endsWith("/entries") ? entries : []), { status: 200 })));
  render(<PersonalWorkspace external={false} text={english} />);
  fireEvent.change(screen.getByLabelText("Workspace token"), { target: { value: "synthetic" } });
  fireEvent.click(screen.getByRole("button", { name: "Unlock" }));
  fireEvent.click(await screen.findByRole("button", { name: "Confirm: identity.name, memory 1" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Data changed"));
  expect(screen.queryByRole("button", { name: "Replace" })).not.toBeInTheDocument();
});
