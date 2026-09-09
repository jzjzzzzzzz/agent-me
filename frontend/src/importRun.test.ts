import { afterEach, describe, expect, it, vi } from "vitest";
import baseline from "./__fixtures__/collaboration/baseline.json";
import verified from "./__fixtures__/collaboration/verified.json";
import { MAX_RUN_FILE_BYTES, readCollaborationRun } from "./importRun";

afterEach(() => vi.restoreAllMocks());

it.each([baseline, verified])("reads the current $workflow export", async (payload) => {
  await expect(readCollaborationRun(new File([JSON.stringify(payload)], "run.json")))
    .resolves.toEqual(payload);
});

describe.each([baseline, verified])("source scores in $workflow replay", (fixture) => {
  it.each([0, 0.5, 1])("accepts the normalized score %s", async (score) => {
    const payload = {
      ...fixture,
      sources: fixture.sources.map((source) => ({ ...source, score })),
    };

    await expect(readCollaborationRun(new File([JSON.stringify(payload)], "run.json")))
      .resolves.toEqual(payload);
  });

  it.each(["-0.25", "1.5", "NaN", "Infinity", "-Infinity", "1e400", "-1e400"])(
    "rejects score %s with only the safe replay error",
    async (score) => {
      const payload = {
        ...fixture,
        answer: "Synthetic untrusted file content must not appear in the error",
        sources: fixture.sources.map((source) => ({ ...source, score: "SCORE_PLACEHOLDER" })),
      };
      // Preserve overflow and non-JSON literals instead of JSON.stringify converting them to null.
      const content = JSON.stringify(payload).replace('"SCORE_PLACEHOLDER"', score);

      await expect(readCollaborationRun(new File([content], "untrusted-score.json")))
        .rejects.toMatchObject({ code: "replayInvalid", message: "replayInvalid" });
    },
  );
});

const validJSON = JSON.stringify(baseline);
it.each([
  ["malformed JSON", "{not json}"],
  ["null", "null"],
  ["array", "[]"],
  ["version envelope", JSON.stringify({ version: 2, response: baseline })],
  ["explicit unsupported version", JSON.stringify({ ...baseline, version: 2 })],
  ["explicit schema version", JSON.stringify({ ...baseline, schema_version: 2 })],
  ["unknown workflow", JSON.stringify({ ...baseline, workflow: "future-workflow" })],
  ["invalid stage order", JSON.stringify({ ...baseline, trace: [...baseline.trace].reverse() })],
  ["missing verifier", JSON.stringify({ ...verified, trace: verified.trace.slice(0, 4) })],
  ["non-finite metric", validJSON.replace('"task_count":3', '"task_count":1e400')],
  ["non-finite source score", validJSON.replace('"score":0.75', '"score":1e400')],
  ["unsupported metric", validJSON.replace('"task_count":3', '"task_count":"three"')],
])("rejects %s without exposing file contents", async (_, content) => {
  await expect(readCollaborationRun(new File([content], "untrusted.json")))
    .rejects.toMatchObject({ code: "replayInvalid", message: "replayInvalid" });
});

it("enforces the byte limit before reading and accepts the exact boundary", async () => {
  const read = vi.spyOn(FileReader.prototype, "readAsText");
  const oversized = new File([" ".repeat(MAX_RUN_FILE_BYTES + 1)], "large.json");
  await expect(readCollaborationRun(oversized)).rejects.toMatchObject({ code: "replayTooLarge" });
  expect(read).not.toHaveBeenCalled();

  const boundary = new File([validJSON.padEnd(MAX_RUN_FILE_BYTES)], "boundary.JSON");
  expect(boundary.size).toBe(MAX_RUN_FILE_BYTES);
  await expect(readCollaborationRun(boundary)).resolves.toEqual(baseline);
});

it("rejects a non-JSON extension before reading, regardless of its MIME type", async () => {
  const read = vi.spyOn(FileReader.prototype, "readAsText");
  await expect(readCollaborationRun(new File([validJSON], "run.html", { type: "application/json" })))
    .rejects.toMatchObject({ code: "replayInvalid" });
  expect(read).not.toHaveBeenCalled();
});

it("reports a safe file read failure", async () => {
  vi.spyOn(FileReader.prototype, "readAsText").mockImplementation(function (this: FileReader) {
    this.dispatchEvent(new ProgressEvent("error"));
  });
  await expect(readCollaborationRun(new File([validJSON], "run.json")))
    .rejects.toMatchObject({ code: "replayReadFailed" });
});
