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

// Keep the offline detector aligned with the backend's deterministic router.
export function localEmergency(text: string): boolean {
  const folded = text.toLowerCase().replaceAll("đ", "d").normalize("NFD")
    .replace(/\p{M}/gu, "").replace(/\s+/g, " ").trim();
  const question = /(?:la gi\s*[?？]?$|\b(?:toi (?:muon|can) biet|cho toi biet|liet ke|giai thich|thong tin ve|nguyen nhan cua|trieu chung cua|dau hieu cua|what is|what are|tell me (?:about|what))\b)/;
  const personalReport = /\b(?:toi|minh|em|chau|con toi|me toi|bo toi|i|my (?:mother|father|child))\s+(?:bi|dang|vua|da|cam thay|thay|dau|tuc|kho|ngat|co giat|cannot|can't|have|has|am|is)\b/;
  if (question.test(folded) && !personalReport.test(folded)) return false;
  const phrases = ["kho tho", "khong tho duoc", "khong the tho", "cannot breathe", "can't breathe", "difficulty breathing", "shortness of breath", "dau nguc", "tuc nguc", "chest pain", "chest pressure", "ngat", "bat tinh", "unconscious", "passed out", "co giat", "seizure", "yeu liet", "liet", "yeu mot ben", "one sided weakness", "meo mieng", "chay mau nhieu", "mau khong cam", "noi kho dot ngot", "dot ngot noi kho", "noi ngong dot ngot", "slurred speech", "moi tim tai", "tim moi", "blue lips", "sung luoi", "sung hong", "swollen tongue", "throat swelling", "non ra mau", "vomiting blood", "dau dau du doi dot ngot", "dot ngot dau dau du doi", "sudden severe headache"];
  return phrases.some((phrase) => {
    for (const match of folded.matchAll(new RegExp(`\\b${phrase}\\b`, "g"))) {
      if (phrase === "liet" && /^\s+ke\b/.test(folded.slice(match.index + phrase.length))) continue;
      const prefix = folded.slice(0, match.index);
      const clause = (prefix.split(/\b(?:va|nhung|ma|tuy nhien|and|but|however)\b|[,.;!?\n]/).at(-1) ?? "")
        .replace(/\b(?:khong (?:chi|het|giam)|not only)\b/g, "");
      if (/\b(?:khong|chua|ko|no|not|without|deny|denies)\b(?:\s+\w+){0,4}\s*$/.test(clause)) continue;
      return true;
    }
    return false;
  });
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
