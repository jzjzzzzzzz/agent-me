import { expect, it } from "vitest";
import { readWorkflowMode, workflowUrl } from "./workflowLink";

it("reads a valid workflow value from a query string", () => {
  expect(readWorkflowMode("?workflow=collaboration")).toBe("collaboration");
  expect(readWorkflowMode("?workflow=verified")).toBe("verified");
  expect(readWorkflowMode("?workflow=standard")).toBe("standard");
});

it("falls back to standard for an absent or invalid workflow value", () => {
  expect(readWorkflowMode("")).toBe("standard");
  expect(readWorkflowMode("?workflow=")).toBe("standard");
  expect(readWorkflowMode("?workflow=not-a-real-mode")).toBe("standard");
  expect(readWorkflowMode("?other=value")).toBe("standard");
});

it("sets the workflow parameter while preserving path, hash, and other params", () => {
  const url = workflowUrl(
    { pathname: "/demo", search: "?foo=bar&workflow=standard", hash: "#top" },
    "verified",
  );
  expect(url).toBe("/demo?foo=bar&workflow=verified#top");
});
