import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";

const manifest = JSON.parse(await readFile(new URL("../dist/.openai/hosting.json", import.meta.url), "utf8"));
assert.ok(manifest.project_id, "Packaged Sites project ID is required");
const { default: worker } = await import(new URL("../dist/server/index.js", import.meta.url));
assert.equal(typeof worker?.fetch, "function", "Sites Worker must export default.fetch");
assert.ok((await stat(new URL("../dist/client/og.png", import.meta.url))).size > 0, "Social card must be packaged");
console.log("Validated Sites Worker, manifest, and social card.");
