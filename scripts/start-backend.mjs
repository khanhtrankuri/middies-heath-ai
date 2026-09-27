import { runPython } from "./python-runtime.mjs";

const profile = process.argv.includes("--demo") ? "demo" : process.argv.includes("--baseline") ? "baseline" : undefined;
if (profile === "demo") console.log("Demo mode: sample responses only; no model download or GPU required.");
if (profile === "baseline") console.log("Local Qwen baseline: real model, no fine-tuned adapter; requires model weights and a RAG index.");
if (profile === "baseline") process.env.MEDDIES_LOCAL_FILES_ONLY ??= "true";
try {
  runPython(["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], profile);
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
