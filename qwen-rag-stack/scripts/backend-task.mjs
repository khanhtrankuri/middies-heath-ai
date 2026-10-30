import { runPython } from "./python-runtime.mjs";

const args = process.argv.slice(2);
const baseline = args[0] === "--baseline";
if (baseline) args.shift();
try {
  if (!args.length) throw new Error("Supply Python arguments, e.g. -m pytest");
  runPython(args, baseline ? "baseline" : undefined);
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
