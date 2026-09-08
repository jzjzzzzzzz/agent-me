import { parseCollaborationResponse, type CollaborationResponse } from "./api";

export const MAX_RUN_FILE_BYTES = 1024 * 1024;
export type RunImportFailure = "replayTooLarge" | "replayInvalid" | "replayReadFailed";

export class RunImportError extends Error {
  constructor(readonly code: RunImportFailure) {
    super(code);
    this.name = "RunImportError";
  }
}

export async function readCollaborationRun(file: File): Promise<CollaborationResponse> {
  // Bound allocation before reading, decoding, or parsing untrusted file contents.
  if (file.size > MAX_RUN_FILE_BYTES) throw new RunImportError("replayTooLarge");
  if (!/\.json$/i.test(file.name)) throw new RunImportError("replayInvalid");

  const content = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => typeof reader.result === "string"
      ? resolve(reader.result)
      : reject(new RunImportError("replayReadFailed"));
    reader.onerror = reader.onabort = () => reject(new RunImportError("replayReadFailed"));
    reader.readAsText(file, "UTF-8");
  });

  try {
    return parseCollaborationResponse(JSON.parse(content));
  } catch {
    // Do not reflect the filename, file contents, or parser diagnostics into the UI.
    throw new RunImportError("replayInvalid");
  }
}
