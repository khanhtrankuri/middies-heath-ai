import { existsSync, readFileSync } from "node:fs";
import { spawn, spawnSync } from "node:child_process";
import { delimiter, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseEnv } from "node:util";

export const root = fileURLToPath(new URL("../", import.meta.url));
export const backend = join(root, "backend");
const windows = process.platform === "win32";
const envPython = (directory) => join(directory, windows ? "Scripts/python.exe" : "bin/python");

export function runtimeEnvironment(profile) {
  const local = join(backend, ".env");
  const env = { ...(existsSync(local) ? parseEnv(readFileSync(local, "utf8")) : {}), ...process.env };
  if (profile === "baseline") Object.assign(env, parseEnv(readFileSync(join(backend, "configs/local-baseline.env"), "utf8")));
  if (profile === "demo") Object.assign(env, { MEDDIES_MODEL_PROVIDER: "stub", MEDDIES_RAG_ENABLED: "false" });
  env.PYTHONUTF8 = "1";
  env.PYTHONUNBUFFERED = "1";
  if (["true", "1", "yes"].includes(env.MEDDIES_LOCAL_FILES_ONLY?.toLowerCase())) {
    env.HF_HUB_OFFLINE = "1";
    env.TRANSFORMERS_OFFLINE = "1";
  }
  return env;
}

export function resolvePython(env) {
  const candidates = [
    env.MEDDIES_PYTHON,
    env.VIRTUAL_ENV && envPython(env.VIRTUAL_ENV),
    env.CONDA_PREFIX && join(env.CONDA_PREFIX, windows ? "python.exe" : "bin/python"),
    envPython(join(root, ".venv")), envPython(join(root, ".venv-4060")),
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (!existsSync(candidate)) continue;
    const probe = spawnSync(candidate, ["-c", "import fastapi, huggingface_hub"], { env, timeout: 10000, windowsHide: true });
    if (probe.status === 0) return { python: candidate, env };
    if (candidate === env.MEDDIES_PYTHON) throw new Error("MEDDIES_PYTHON cannot run. Choose a working Python interpreter.");
    // A managed Windows system may allow CPython but block a venv launcher.
    const venv = dirname(dirname(candidate));
    const cfg = join(venv, "pyvenv.cfg");
    if (!windows || !existsSync(cfg)) continue;
    const home = /^home\s*=\s*(.+)$/m.exec(readFileSync(cfg, "utf8"))?.[1].trim();
    if (!home) continue;
    const base = join(home, "python.exe");
    if (spawnSync(base, ["--version"], { env, timeout: 10000, windowsHide: true }).status !== 0) continue;
    return { python: base, env: { ...env, PYTHONPATH: [join(venv, "Lib/site-packages"), backend, env.PYTHONPATH].filter(Boolean).join(delimiter) } };
  }
  const command = windows ? "python" : "python3";
  if (spawnSync(command, ["--version"], { env, timeout: 10000, windowsHide: true }).status === 0) return { python: command, env };
  throw new Error("No working Python found. Install the backend environment or set MEDDIES_PYTHON.");
}

export function runPython(args, profile) {
  const { python, env } = resolvePython(runtimeEnvironment(profile));
  const child = spawn(python, args, { cwd: backend, stdio: "inherit", env, windowsHide: true });
  child.on("error", (error) => { console.error(error.message); process.exitCode = 1; });
  child.on("exit", (code) => { process.exitCode = code ?? 1; });
  for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
  return child;
}
