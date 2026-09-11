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
  const phrases = ["kho tho", "khong tho duoc", "dau nguc", "tuc nguc", "ngat", "bat tinh", "co giat", "yeu liet", "liet", "meo mieng", "chay mau nhieu", "mau khong cam"];
  return phrases.some((phrase) => {
    for (const match of folded.matchAll(new RegExp(`\\b${phrase}\\b`, "g"))) {
      const prefix = folded.slice(Math.max(0, match.index - 28), match.index);
      const clause = prefix.split(/\b(?:nhung|ma|tuy nhien)\b|[,.;]/).at(-1) ?? "";
      if (clause.trim().split(/\s+/).slice(-4).some((word) => ["khong", "chua", "ko"].includes(word))) continue;
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
