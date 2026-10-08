export type Citation = {
  citation_id: string;
  source_id: string | null;
  title: string | null;
  organization: string | null;
  source_url: string | null;
  publication_date: string | null;
  section: string | null;
  page: number | null;
  snippet: string;
};

export type ConsultationResponse = {
  reply: string;
  provider: string;
  action: "ASK_MORE" | "FINALIZE" | "GROUNDED_ANSWER" | "EMERGENCY";
  grounding_status: "grounded" | "degraded" | "not_used";
  citations: Citation[];
  patient_state: { chief_complaint?: string | null; duration?: string | null; severity?: string | null };
  disclaimer: string;
};

export const MAX_MESSAGE_LENGTH = 2000;
export const MAX_HISTORY_MESSAGES = 64;

// Keep the offline detector aligned with backend/app/triage.py; both must pass
// backend/evals/safety_cases.json.
const MEDICAL_PHRASES = ["kho tho", "khong tho duoc", "khong the tho", "tho khong noi", "hut hoi", "ngop tho", "nghet tho", "tho doc", "cannot breathe", "can't breathe", "difficulty breathing", "shortness of breath", "can't catch my breath", "dau nguc", "tuc nguc", "dau that nguc", "that nguc", "chest pain", "chest pressure", "ngat", "bat tinh", "ngat xiu", "bi xiu", "xiu xuong", "xỉu", "unconscious", "passed out", "fainted", "co giat", "seizure", "convulsion", "yeu liet", "liet", "yeu mot ben", "one sided weakness", "meo mieng", "meo mat", "lech mieng", "facial droop", "chay mau nhieu", "máu không cầm", "mau khong cam", "noi kho dot ngot", "dot ngot noi kho", "noi ngong dot ngot", "dot ngot noi ngong", "bong nhien noi ngong", "tu nhien noi ngong", "slurred speech", "moi tim tai", "tim moi", "blue lips", "sung luoi", "sung hong", "swollen tongue", "throat swelling", "non ra mau", "vomiting blood", "dau dau du doi dot ngot", "dot ngot dau dau du doi", "sudden severe headache", "li bi", "kho danh thuc", "khong danh thuc duoc", "lơ mơ", "unresponsive", "qua lieu", "uong ca vi", "uong het vi", "uong ca lo", "uong het lo", "uong ca hop", "uong nhieu thuoc", "uong thuoc tru sau", "uong hoa chat", "nuot hoa chat", "nuot pin", "ngo doc", "overdose", "overdosed", "poisoned", "swallowed poison", "phan ve", "soc phan ve", "anaphylaxis", "anaphylactic"];
const SELF_HARM_PHRASES = ["tự tử", "tự sát", "tự vẫn", "tự hại", "muon tu tu", "dinh tu tu", "nghi den tu tu", "tu lam hai ban than", "muon chet", "khong muon song", "chan song", "ket lieu ban than", "ket lieu doi minh", "kill myself", "suicide", "suicidal", "end my life", "want to die", "self harm", "self-harm", "hurt myself"];
const COMBINED: [RegExp, string[]][] = [
  [/\b(?:mang thai|co thai|co bau|dang bau|bau \d+|thai \d+ (?:tuan|thang)|pregnant)\b/g, ["ra mau", "chay mau", "bleeding", "dau bung du doi", "severe abdominal pain"]],
  [/(?:\bso sinh\b|\bnewborn\b|\b\d{1,2} (?:ngay|tuan) tuoi\b|\b(?:be|con|chau|em be)(?: \w+)? \d{1,2} (?:ngay|tuan)\b|\b[0-2] thang tuoi\b|\b(?:be|con|chau)(?: \w+)? [0-2] thang\b|\b\d{1,2} (?:days?|weeks?) old\b|\b[0-2] months? old\b)/g, ["sot", "fever", "bo bu", "refusing to feed"]],
  [/\b(?:di ung|noi me day|me day|allergic|hives)\b/g, ["sung moi", "sung mat", "sung mi mat", "swollen lips", "face swelling", "choang", "tut huyet ap"]],
];
const EDU_PREFIX = /^(?:(?:toi muon biet|toi can biet|cho toi biet|hay|vui long|xin)\s+)?/;
const EDU_START = new RegExp(EDU_PREFIX.source + /(?:giai thich|thong tin ve|nguyen nhan (?:cua|gay)|trieu chung|dau hieu|bieu hien|liet ke (?:cac )?(?:trieu chung|dau hieu|nguyen nhan)|what (?:is|are|causes)|tell me about|explain)\b/.source);
const REPORT = /\b(?:toi|minh|me|bo|ong|vo|chong|chau|be|con toi|bi|dang|vua|cam thay|bat dau|bay gio|luc nay|i|i'm|my|he|she|mom|dad|has|have|having|had|am|suddenly|now)\b/;
const IDIOM_BEFORE_DIE = /\b(?:dau(?! kho\b)|met|doi|nong|lanh|ret|ngua|buon ngu|cuoi|so)\b(?: \w+){0,2}(?: qua)?\s*$/;

function fold(value: string, strip = true): string {
  const collapsed = value.toLowerCase().replaceAll("đ", "d").normalize("NFD").replace(/\p{M}/gu, "").replace(/\s+/g, " ");
  return strip ? collapsed.trim() : collapsed;
}

function isInformationQuestion(text: string): boolean {
  const body = fold(text).replace(/[\s?？.]+$/, "");
  if (!body || /[,.;:!?？\n]/.test(body)) return false;
  if (!EDU_START.test(body) && !/\bla gi$/.test(body)) return false;
  return !REPORT.test(body.replace(EDU_PREFIX, ""));
}

function affirmed(needle: string, prefix: string, suffix: string): boolean {
  if (needle === "liet" && /^\s*ke\b/.test(suffix)) return false;
  if (needle === "ngo doc" && /^\s*(?:thuc pham|thuc an)\b/.test(suffix)) return false;
  if (needle === "non" && /\bbuon\s*$/.test(prefix)) return false;
  if (needle === "muon chet" && IDIOM_BEFORE_DIE.test(prefix)) return false;
  const clause = (prefix.split(/\b(?:va|nhung|ma|tuy nhien|and|but|however)\b|[,.;!?\n]/).at(-1) ?? "")
    .replace(/\b(?:khong (?:chi|het|giam)|not only)\b/g, "");
  return !/\b(?:khong|chua|ko|no|not|without|deny|denies)\b(?:\s+\w+){0,4}\s*$/.test(clause);
}

function phrasePresent(text: string, phrase: string): boolean {
  const accented = !/^[\x00-\x7f]*$/.test(phrase);
  const haystack = accented ? text.normalize("NFC").toLowerCase().replace(/\s+/g, " ").trim() : fold(text);
  const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  // JavaScript's \b is ASCII-only, so accented phrases need Unicode-aware edges.
  for (const match of haystack.matchAll(new RegExp(`(?<![\\p{L}\\p{N}_])${escaped}(?![\\p{L}\\p{N}_])`, "gu"))) {
    const end = match.index + match[0].length;
    if (affirmed(fold(phrase), fold(haystack.slice(0, match.index), false), fold(haystack.slice(end), false))) return true;
  }
  return false;
}

export function localEmergencyKind(text: string): "self_harm" | "medical" | null {
  if (isInformationQuestion(text)) return null;
  if (SELF_HARM_PHRASES.some((phrase) => phrasePresent(text, phrase))) return "self_harm";
  if (MEDICAL_PHRASES.some((phrase) => phrasePresent(text, phrase))) return "medical";
  const folded = fold(text);
  const combined = COMBINED.some(([context, symptoms]) =>
    [...folded.matchAll(context)].some((m) => affirmed(m[0], folded.slice(0, m.index), folded.slice(m.index + m[0].length)))
    && symptoms.some((symptom) => phrasePresent(text, symptom)));
  return combined ? "medical" : null;
}

export function localEmergency(text: string): boolean {
  return localEmergencyKind(text) !== null;
}

export function safeSourceUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}

export function consultationError(status: number): string {
  if (status === 422 || status === 413) return "Nội dung hoặc độ dài hội thoại chưa phù hợp. Hãy rút ngắn tin nhắn hoặc bắt đầu cuộc trò chuyện mới.";
  if (status === 429) return "Dịch vụ đang bận. Vui lòng đợi một lát rồi thử lại.";
  if (status === 503) return "Dịch vụ tư vấn chưa sẵn sàng. Bạn có thể thử lại sau.";
  return "Không thể nhận câu trả lời lúc này. Vui lòng thử lại.";
}
