import assert from "node:assert/strict";
import test from "node:test";
import { localEmergency, safeSourceUrl } from "../app/consultation.ts";

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
