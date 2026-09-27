import { spawn } from "node:child_process";
import { join } from "node:path";
import { root, runPython } from "./python-runtime.mjs";

process.env.MEDDIES_LOCAL_FILES_ONLY ??= "true";
console.log("Meddies local: loading the configured Qwen3 model, BGE-M3, and reranker. First startup may take a minute.");
const children = [];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  process.exitCode = code;
  for (const child of children) child.kill();
}
try {
  children.push(runPython(["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], "baseline"));
  children.push(spawn(process.execPath, [join(root, "node_modules/vite/bin/vite.js"), "--mode", "local-node", "--host", "127.0.0.1", "--port", "5173", "--strictPort"], {
    cwd: root, stdio: "inherit", env: process.env, windowsHide: true,
  }));
  for (const child of children) {
    child.on("error", (error) => { console.error(error.message); stop(1); });
    child.on("exit", (code) => { if (!stopping) stop(code ?? 1); });
  }
  for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => stop());
} catch (error) {
  console.error(error.message);
  stop(1);
}
