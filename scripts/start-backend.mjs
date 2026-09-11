import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const backend = join(root, "backend");
const windows = process.platform === "win32";
const environmentPython = (directory) => join(directory, windows ? "Scripts/python.exe" : "bin/python");
const candidates = [
  process.env.MEDDIES_PYTHON,
  process.env.VIRTUAL_ENV && environmentPython(process.env.VIRTUAL_ENV),
  process.env.CONDA_PREFIX && join(process.env.CONDA_PREFIX, windows ? "python.exe" : "bin/python"),
  environmentPython(join(root, ".venv")),
  environmentPython(join(root, ".venv-4060")),
].filter(Boolean);
const python = candidates.find((candidate) => existsSync(candidate)) ?? (windows ? "python" : "python3");
const demo = process.argv.includes("--demo");
const args = ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"];
if (existsSync(join(backend, ".env"))) args.push("--env-file", ".env");
if (demo) console.log("Demo mode: sample responses only; no model download or GPU required.");
const child = spawn(python, args, {
  cwd: backend,
  stdio: "inherit",
  env: { ...process.env, ...(demo ? { MEDDIES_MODEL_PROVIDER: "stub", MEDDIES_RAG_ENABLED: "false" } : {}) },
});
child.on("error", () => {
  console.error("Cannot start Python. Activate the backend environment or set MEDDIES_PYTHON to its interpreter path.");
  process.exitCode = 1;
});
child.on("exit", (code) => { process.exitCode = code ?? 1; });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
