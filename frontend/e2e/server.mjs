/** Own-process test gateway, not a deployment server. No existing services/profiles are reused. */
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFile, mkdtemp, mkdir, writeFile, rm, chmod } from "node:fs/promises";
import { createServer, request as httpRequest } from "node:http";
import { tmpdir } from "node:os";
import { resolve, join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { once } from "node:events";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const dist = join(root, "frontend", "dist");
const port = Number(process.env.AGENT_ME_E2E_PORT ?? "4193");
if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("Invalid E2E gateway port");
const python = process.env.AGENT_ME_E2E_PYTHON || join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const workspace = await mkdtemp(join(tmpdir(), "agent-me-e2e-"));
const nonce = randomUUID();
await chmod(workspace, 0o700);
await writeFile(join(workspace, ".agent-me-e2e-fixture"), nonce, { mode: 0o600 });
await mkdir(join(workspace, "public"));
await writeFile(join(workspace, "public", "example.md"), "# Fictional corpus\n\nPublic fictional examples cannot establish the owner's identity.\n");
const env = { ...process.env };
for (const key of Object.keys(env)) if (["PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP"].includes(key.toUpperCase())) delete env[key];
const backend = spawn(python, [join(root, "scripts", "serve_e2e.py"), "--workspace", workspace, "--nonce", nonce], {
  cwd: workspace, env, stdio: ["ignore", "pipe", "pipe"],
});
const exitPromise = once(backend, "exit");
let apiPort;
let logs = "";
let stopping = false;
let gateway;
const delay = ms => new Promise(done => setTimeout(done, ms));

async function cleanup(code = 0) {
  if (stopping) return;
  stopping = true;
  gateway?.closeAllConnections();
  gateway?.close();
  if (backend.exitCode === null && backend.signalCode === null) backend.kill("SIGTERM");
  await Promise.race([exitPromise.catch(() => {}), delay(5000)]);
  if (backend.exitCode === null && backend.signalCode === null) {
    backend.kill("SIGKILL");
    await Promise.race([exitPromise.catch(() => {}), delay(5000)]);
  }
  if (backend.exitCode !== null || backend.signalCode !== null) await rm(workspace, { recursive: true, force: true });
  else code = 1; // Never erase a database while an owned backend may still be using it.
  process.exit(code);
}
process.once("SIGTERM", () => void cleanup());
process.once("SIGINT", () => void cleanup());
backend.once("error", error => { process.stderr.write(`${error.message}\n`); void cleanup(1); });
backend.once("exit", () => { if (!stopping) { process.stderr.write(logs); void cleanup(1); } });
backend.stdout.on("data", chunk => { logs = (logs + chunk).slice(-16000); });
backend.stderr.on("data", chunk => {
  logs = (logs + chunk).slice(-16000);
  const match = /Uvicorn running on http:\/\/127\.0\.0\.1:(\d+)/.exec(logs);
  if (match) apiPort = Number(match[1]);
});

try {
  await readFile(join(dist, "index.html"));
  const deadline = Date.now() + 30000;
  while (!apiPort && Date.now() < deadline && !stopping) await delay(50);
  if (!apiPort || stopping) throw new Error("Fixture API did not start");
  const readiness = await fetch(`http://127.0.0.1:${apiPort}/ready`);
  const state = await readiness.json();
  if (!readiness.ok || state.answer_mode !== "extractive") throw new Error("Fixture API is not local/ready");
  const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".webp": "image/webp" };
  gateway = createServer(async (incoming, outgoing) => {
    outgoing.setHeader("Cache-Control", "no-store");
    outgoing.setHeader("X-Content-Type-Options", "nosniff");
    let path;
    try { path = new URL(incoming.url, `http://127.0.0.1:${port}`).pathname; }
    catch { outgoing.writeHead(400).end(); return; }
    if (path === "/__e2e_health" && incoming.method === "GET") {
      outgoing.setHeader("Content-Type", "application/json");
      outgoing.end(JSON.stringify({ fixture: "agent-me-e2e-v1" })); return;
    }
    if (path === "/favicon.ico") { outgoing.writeHead(204).end(); return; }
    if (path.startsWith("/api/")) {
      const proxy = httpRequest({ hostname: "127.0.0.1", port: apiPort, path: incoming.url,
        method: incoming.method, headers: { ...incoming.headers, host: `127.0.0.1:${apiPort}` } }, response => {
        outgoing.writeHead(response.statusCode, { ...response.headers, "cache-control": "no-store", "x-content-type-options": "nosniff" });
        response.pipe(outgoing);
      });
      proxy.on("error", () => { if (!outgoing.headersSent) outgoing.writeHead(502); outgoing.end(); });
      outgoing.on("close", () => { if (!outgoing.writableFinished) proxy.destroy(); });
      incoming.pipe(proxy); return;
    }
    // A flat built-asset allowlist, not an arbitrary URL-to-filesystem mapping.
    if (incoming.method !== "GET" && incoming.method !== "HEAD") { outgoing.writeHead(405).end(); return; }
    const asset = /^\/assets\/([a-zA-Z0-9_-]+\.(js|css))$/.exec(path);
    const file = path === "/" || path === "/index.html" ? join(dist, "index.html")
      : asset ? join(dist, "assets", asset[1]) : null;
    if (!file) { outgoing.writeHead(404).end(); return; }
    try {
      const bytes = await readFile(file);
      const extension = file.slice(file.lastIndexOf("."));
      outgoing.setHeader("Content-Type", `${mime[extension]}; charset=utf-8`);
      outgoing.end(incoming.method === "HEAD" ? undefined : bytes);
    } catch { outgoing.writeHead(404).end(); }
  });
  gateway.once("error", error => { process.stderr.write(`${error.message}\n`); void cleanup(1); });
  await new Promise(done => gateway.listen(port, "127.0.0.1", done));
  process.stdout.write(`Isolated E2E fixture ready at http://127.0.0.1:${port}\n`);
} catch (error) {
  process.stderr.write(`${error.message}\n${logs}`);
  await cleanup(1);
}
