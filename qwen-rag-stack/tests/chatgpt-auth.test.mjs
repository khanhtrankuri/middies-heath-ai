import assert from "node:assert/strict";
import test from "node:test";
import { readChatGPTIdentity } from "../app/chatgpt-identity.ts";

const identity = () => new Headers({
  "oai-authenticated-user-email": "patient@example.test",
  "oai-authenticated-user-full-name": encodeURIComponent("Nguyễn An"),
  "oai-authenticated-user-full-name-encoding": "percent-encoded-utf-8",
});

test("forged identity and trust headers cannot enable authentication", () => {
  const headers = identity();
  headers.set("MEDDIES_AUTH_MODE", "sites-proxy");
  headers.set("x-forwarded-host", "trusted.chatgpt.com");
  for (const mode of [undefined, "disabled", "production", "true"]) {
    assert.equal(readChatGPTIdentity(headers, mode), null);
  }
});

test("explicit Sites deployment accepts identity and decodes optional name", () => {
  assert.deepEqual(readChatGPTIdentity(identity(), "sites-proxy"), {
    email: "patient@example.test", fullName: "Nguyễn An", displayName: "Nguyễn An",
  });
});

test("malformed names fall back to email; ambiguous identities fail closed", () => {
  const headers = identity();
  headers.set("oai-authenticated-user-full-name", "%invalid");
  assert.equal(readChatGPTIdentity(headers, "sites-proxy").displayName, "patient@example.test");
  headers.append("oai-authenticated-user-email", "other@example.test");
  assert.equal(readChatGPTIdentity(headers, "sites-proxy"), null);
  assert.equal(readChatGPTIdentity(new Headers(), "sites-proxy"), null);
});
