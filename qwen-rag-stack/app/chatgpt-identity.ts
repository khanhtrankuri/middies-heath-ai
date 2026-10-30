export type ChatGPTUser = {
  displayName: string;
  email: string;
  fullName: string | null;
};

/** Only enable behind Sites ingress after verifying origin isolation and header stripping. */
export function readChatGPTIdentity(
  requestHeaders: Pick<Headers, "get">,
  mode: string | undefined,
): ChatGPTUser | null {
  // A request header, hostname or NODE_ENV cannot establish proxy trust.
  if (mode !== "sites-proxy") return null;
  const email = requestHeaders.get("oai-authenticated-user-email")?.trim();
  if (!email || email.length > 254 || !/^[^\s,@]+@[^\s,@]+$/.test(email)) return null;

  let fullName: string | null = null;
  const name = requestHeaders.get("oai-authenticated-user-full-name");
  if (name && name.length <= 2048 && requestHeaders.get(
    "oai-authenticated-user-full-name-encoding",
  ) === "percent-encoded-utf-8") {
    try {
      fullName = decodeURIComponent(name).trim() || null;
    } catch {
      // A malformed optional display name does not authenticate another user.
    }
  }
  return { displayName: fullName ?? email, email, fullName };
}
