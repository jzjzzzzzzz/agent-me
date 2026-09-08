import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import baseline from "./__fixtures__/collaboration/baseline.json";
import verified from "./__fixtures__/collaboration/verified.json";
import { App } from "./App";
import { LocalRunReplay } from "./LocalRunReplay";
import { messages, type Locale } from "./i18n";
import { MAX_RUN_FILE_BYTES } from "./importRun";
import * as exporter from "./exportRun";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it.each([baseline, verified])("replays $workflow locally with keyboard focus and live feedback", async (payload) => {
  const user = userEvent.setup();
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  const storage = vi.spyOn(Storage.prototype, "setItem");
  const pushState = vi.spyOn(window.history, "pushState");
  const replaceState = vi.spyOn(window.history, "replaceState");
  const beacon = vi.fn();
  vi.stubGlobal("navigator", Object.assign(Object.create(navigator), { sendBeacon: beacon }));
  const download = vi.spyOn(exporter, "downloadCollaborationRun").mockImplementation(() => undefined);
  render(<LocalRunReplay text={messages.en} />);
  const picker = screen.getByLabelText("Open run record", { selector: "input" });

  await user.tab();
  expect(picker).toHaveFocus();
  expect(picker).toHaveAttribute("accept", ".json,application/json");
  await user.upload(picker, new File([JSON.stringify(payload)], "run.json", { type: "application/json" }));

  const heading = await screen.findByRole("heading", { name: messages.en.replayLabel });
  await waitFor(() => expect(heading).toHaveFocus());
  expect(screen.getByText(messages.en.replayLoaded)).toHaveAttribute("aria-live", "polite");
  expect(screen.getByText(payload.run_id)).toBeInTheDocument();
  expect(screen.getByText(payload.answer, { normalizer: (value) => value })).toBeInTheDocument();
  expect(screen.getByText("Grounded")).toBeInTheDocument();
  expect(screen.getByText(payload.sources[0].excerpt)).toBeInTheDocument();
  for (const stage of payload.trace) expect(screen.getByText(stage.agent)).toBeInTheDocument();
  expect(screen.getByText("0.5714")).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
  expect(storage).not.toHaveBeenCalled();
  expect(pushState).not.toHaveBeenCalled();
  expect(replaceState).not.toHaveBeenCalled();
  expect(beacon).not.toHaveBeenCalled();
  expect(download).not.toHaveBeenCalled();
});

it("shows localized accessible errors, clears stale records, and retries the same file", async () => {
  const user = userEvent.setup();
  render(<LocalRunReplay text={messages["zh-CN"]} />);
  const picker = screen.getByLabelText(messages["zh-CN"].openRun, { selector: "input" });
  await user.upload(picker, new File([JSON.stringify(baseline)], "run.json"));
  await screen.findByText(baseline.run_id);

  const invalid = new File(["private malformed content"], "bad.json");
  await user.upload(picker, invalid);
  const error = await screen.findByRole("alert");
  await waitFor(() => expect(error).toHaveFocus());
  expect(error).toHaveTextContent(messages["zh-CN"].replayInvalid);
  expect(screen.queryByText(baseline.run_id)).not.toBeInTheDocument();
  expect(document.body).not.toHaveTextContent("private malformed content");

  await user.upload(picker, invalid);
  expect(await screen.findByRole("alert")).toHaveTextContent(messages["zh-CN"].replayInvalid);
  await user.upload(picker, new File([JSON.stringify(verified)], "run.json"));
  expect(await screen.findByText(verified.run_id)).toBeInTheDocument();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("rejects oversized files accessibly without reading or making network requests", async () => {
  const read = vi.spyOn(FileReader.prototype, "readAsText");
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  render(<LocalRunReplay text={messages.en} />);
  await userEvent.upload(screen.getByLabelText("Open run record", { selector: "input" }),
    new File([" ".repeat(MAX_RUN_FILE_BYTES + 1)], "large.json"));
  expect(await screen.findByRole("alert")).toHaveTextContent(messages.en.replayTooLarge);
  expect(read).not.toHaveBeenCalled();
  expect(fetchMock).not.toHaveBeenCalled();
});

it("renders imported markup, paths, and metric names as plain text", async () => {
  const markup = '<img src="https://example.invalid/tracker" onerror="alert(1)">';
  const payload = {
    ...baseline,
    answer: `<script>alert(1)</script> ${markup}`,
    sources: [{ title: markup, path: "javascript:alert(1)", excerpt: "[link](https://example.invalid)", score: 1 }],
    trace: baseline.trace.map((stage) => ({ ...stage, summary: markup, metrics: { [markup]: true } })),
  };
  render(<LocalRunReplay text={messages.en} />);
  await userEvent.upload(screen.getByLabelText("Open run record", { selector: "input" }), new File([JSON.stringify(payload)], "run.json"));
  expect(await screen.findByText(payload.answer)).toBeInTheDocument();
  expect(screen.getByText("javascript:alert(1)")).toBeInTheDocument();
  expect(screen.getByText(payload.sources[0].excerpt)).toBeInTheDocument();
  expect(document.querySelector("script, img, a, iframe")).toBeNull();
});

it("does not cause extra requests or storage writes when imported in the full app", async () => {
  const fetchMock = vi.fn().mockRejectedValue(new Error("offline"));
  vi.stubGlobal("fetch", fetchMock);
  const storage = vi.spyOn(Storage.prototype, "setItem");
  render(<App />);
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1)); // Existing profile load only.
  fetchMock.mockClear();
  storage.mockClear(); // Existing locale preference only.
  await userEvent.upload(screen.getByLabelText(messages[document.documentElement.lang as Locale].openRun, { selector: "input" }),
    new File([JSON.stringify(baseline)], "run.json"));
  await screen.findByText(baseline.run_id);
  expect(fetchMock).not.toHaveBeenCalled();
  expect(storage).not.toHaveBeenCalled();
});
