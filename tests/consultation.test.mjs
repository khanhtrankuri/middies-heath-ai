import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { localEmergency, localEmergencyKind, safeSourceUrl } from "../app/consultation.ts";

const safetyCases = JSON.parse(readFileSync(new URL("../backend/evals/safety_cases.json", import.meta.url), "utf8"));
test("offline safety matches shared Vietnamese and English regression cases", () => {
  for (const item of safetyCases) assert.equal(localEmergency(item.text), item.emergency, item.id);
});

test("offline red flags recognize accented and unaccented reports", () => {
  for (const text of ["Tôi khó thở", "Toi dau nguc", "Tôi không thở được", "Tôi bị bất tỉnh", "Máu không cầm"]) {
    assert.equal(localEmergency(text), true, text);
  }
});

test("offline red flags respect negation, clauses, and word boundaries", () => {
  for (const text of ["Tôi không khó thở", "không yếu liệt", "không đau ngực", "A string containing ngatTest is not a symptom"]) {
    assert.equal(localEmergency(text), false, text);
  }
  assert.equal(localEmergency("không đau đầu nhưng khó thở"), true);
  assert.equal(localEmergency("không khó thở; tôi đau ngực"), true);
  assert.equal(localEmergency("khó thở rồi ngất".normalize("NFD")), true);
});

test("citation links permit only absolute HTTP(S) destinations without credentials", () => {
  assert.equal(safeSourceUrl("https://example.org/reference"), "https://example.org/reference");
  for (const url of [null, "javascript:alert(1)", "data:text/html,test", "file:///etc/passwd", "/relative", "https://user:password@example.org/"]) {
    assert.equal(safeSourceUrl(url), null);
  }
});

test("offline detector separates self-harm from medical emergencies", () => {
  assert.equal(localEmergencyKind("Tôi không muốn sống nữa"), "self_harm");
  assert.equal(localEmergencyKind("toi muon tu tu"), "self_harm");
  assert.equal(localEmergencyKind("Mẹ đang khó thở, cho tôi biết phải làm gì"), "medical");
  assert.equal(localEmergencyKind("Tôi đau bụng từ từ tăng dần"), null);
});
