import assert from "node:assert/strict";
import test from "node:test";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { once } from "node:events";
import { fileURLToPath } from "node:url";

test("local Node runtime serves the consultation page without workerd", { timeout: 120000 }, async () => {
  const reservation = createServer();
  reservation.listen(0, "127.0.0.1");
  await once(reservation, "listening");
  const port = reservation.address().port;
  await new Promise((resolve) => reservation.close(resolve));
  const child = spawn(process.execPath, [
    fileURLToPath(new URL("../node_modules/vite/bin/vite.js", import.meta.url)),
    "--mode", "local-node", "--host", "127.0.0.1", "--port", String(port), "--strictPort",
  ], { windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
  let output = "";
  child.stderr.on("data", (chunk) => { output += chunk.toString(); });
  const exited = once(child, "exit");
  try {
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`Vite startup timed out: ${output}`)), 30000);
      child.once("error", (error) => { clearTimeout(timer); reject(error); });
      child.once("exit", () => { clearTimeout(timer); reject(new Error(output)); });
      child.stdout.on("data", (chunk) => {
        output += chunk.toString();
        if (output.includes(`http://127.0.0.1:${port}/`)) { clearTimeout(timer); resolve(); }
      });
    });
    const response = await fetch(`http://127.0.0.1:${port}/`, { signal: AbortSignal.timeout(75000) });
    assert.equal(response.status, 200);
    const html = await response.text();
    assert.match(html, /Meddies Health AI/);
    assert.match(html, /health-message/);
    assert.match(html, /lang="vi"/);
    assert.doesNotMatch(output, /runInRunnerObject|getWorkerEntryExportTypes/);
  } catch (error) {
    throw new Error(`Local runtime failed:\n${output}`, { cause: error });
  } finally {
    child.kill();
    await exited;
  }
});
