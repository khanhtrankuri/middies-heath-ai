import assert from "node:assert/strict";

// Start the root server in benchmark mode on :5300 with QWEN_BACKEND_URL
// pointing to an unavailable local port. No cloud credentials are required.
const post = (body) => fetch("http://127.0.0.1:5300/api/health/chat", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body), signal: AbortSignal.timeout(15000),
});
const unavailable = await post({ message: "Tôi bị đau bụng từ hôm qua", inferenceMode: "qwen_local" });
assert.equal(unavailable.status, 503);
assert.equal((await unavailable.json()).provider, "qwen-unavailable");
const cloud = await post({ message: "Tôi bị đau bụng", inferenceMode: "cloud_hybrid" });
assert.equal(cloud.status, 400);
const emergency = await post({ message: "Bây giờ tôi đau thắt ngực dữ dội", inferenceMode: "qwen_local",
  history: [{ role: "user", content: "Tôi không đau thắt ngực" }] });
assert.equal(emergency.status, 200);
const urgent = await emergency.json();
assert.equal(urgent.triageLevel, "EMERGENCY");
assert.equal(urgent.activeEngine, "safety-router");
console.log("Root HTTP smoke passed: no Qwen-to-cloud fallback, benchmark provider lock, independent emergency routing.");
