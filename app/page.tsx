"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type Message = { id: number; role: "assistant" | "user"; text: string };
type Possibility = { name: string; note: string };
type TriageResponse = {
  urgency: "emergency" | "routine";
  reply: string;
  disclaimer: string;
  matched_red_flags: string[];
  possibilities: Possibility[];
  next_step: string | null;
};

const API_URL = (process.env.NEXT_PUBLIC_MEDDIES_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const firstPrompts = ["Tôi bị đau đầu và hơi chóng mặt", "Tôi ho, đau họng và sốt nhẹ", "Tôi đau bụng sau khi ăn"];
const timePrompts = ["Dưới 24 giờ", "Khoảng 1–3 ngày", "Trên 3 ngày"];
const emergencyWords = [
  "khó thở", "kho tho", "đau ngực", "dau nguc", "ngất", "ngat", "co giật", "co giat",
  "liệt", "liet", "méo miệng", "meo mieng", "chảy máu nhiều", "chay mau nhieu",
];
const initialMessage: Message = {
  id: 1,
  role: "assistant",
  text: "Chào bạn, tôi là MedAI — trợ lý hỗ trợ sàng lọc sức khỏe ban đầu. Hôm nay bạn đang gặp triệu chứng gì?",
};

function localEmergency(text: string) {
  const normalized = text.toLocaleLowerCase("vi");
  return emergencyWords.some((word) => normalized.includes(word));
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([initialMessage]);
  const [input, setInput] = useState("");
  const [stage, setStage] = useState<"symptom" | "followup" | "result">("symptom");
  const [symptom, setSymptom] = useState("");
  const [urgent, setUrgent] = useState(false);
  const [result, setResult] = useState<TriageResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const nextMessageId = useRef(2);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_URL}/health`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("Backend health check failed");
        setApiOnline(true);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setApiOnline(false);
      });
    return () => controller.abort();
  }, []);

  const progress = stage === "symptom" ? 1 : stage === "followup" ? 2 : 3;
  const quickPrompts = stage === "symptom" ? firstPrompts : stage === "followup" ? timePrompts : [];
  const summary = useMemo(() => {
    const userMessages = messages.filter((item) => item.role === "user");
    return { symptom: userMessages[0]?.text ?? "Chưa ghi nhận", duration: userMessages[1]?.text ?? "Đang thu thập" };
  }, [messages]);

  function addExchange(userText: string, assistantText: string) {
    const id = nextMessageId.current;
    nextMessageId.current += 2;
    setMessages((current) => [...current, { id, role: "user", text: userText }, { id: id + 1, role: "assistant", text: assistantText }]);
  }

  async function callTriage(payload: { symptom: string; duration?: string }) {
    const response = await fetch(`${API_URL}/api/v1/triage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`API trả về HTTP ${response.status}`);
    return (await response.json()) as TriageResponse;
  }

  async function submit(text: string) {
    const clean = text.trim();
    if (!clean || loading) return;
    setInput("");

    // Luôn cảnh báo ngay tại trình duyệt, kể cả khi backend không kết nối được.
    if (localEmergency(clean)) {
      addExchange(clean, "Triệu chứng bạn mô tả có thể cần được đánh giá khẩn cấp. Hãy gọi 115 hoặc đến cơ sở cấp cứu gần nhất ngay; không nên chờ tư vấn trực tuyến.");
      setUrgent(true);
      setStage("result");
      return;
    }

    setLoading(true);
    try {
      if (stage === "symptom") {
        const data = await callTriage({ symptom: clean });
        addExchange(clean, data.reply);
        setSymptom(clean);
        setUrgent(data.urgency === "emergency");
        setStage(data.urgency === "emergency" ? "result" : "followup");
        setResult(data.urgency === "emergency" ? data : null);
      } else {
        const data = await callTriage({ symptom: symptom || clean, duration: clean });
        addExchange(clean, data.reply);
        setResult(data);
        setUrgent(data.urgency === "emergency");
        setStage("result");
      }
      setApiOnline(true);
    } catch {
      addExchange(clean, "Không thể kết nối dịch vụ tư vấn lúc này. Vui lòng khởi động backend Python rồi thử lại. Nếu triệu chứng nghiêm trọng hoặc tăng nhanh, hãy liên hệ cơ sở y tế.");
      setApiOnline(false);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: FormEvent) { event.preventDefault(); void submit(input); }
  function resetChat() {
    const id = nextMessageId.current++;
    setMessages([{ ...initialMessage, id }]);
    setStage("symptom"); setSymptom(""); setUrgent(false); setResult(null); setInput("");
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Trang chủ MedAI"><span className="brand-mark">✦</span><span>MedAI</span></a>
        <div className="top-actions">
          <span className="secure-label"><span className="status-dot" /> {apiOnline === null ? "Đang kiểm tra backend" : apiOnline ? "Dịch vụ Python sẵn sàng" : "Backend chưa kết nối"}</span>
          <button className="new-chat" onClick={resetChat}>＋ Cuộc trò chuyện mới</button>
        </div>
      </header>

      <section className="notice" role="note"><span>ⓘ</span><p><strong>Lưu ý quan trọng:</strong> MedAI chỉ cung cấp thông tin tham khảo, không thay thế chẩn đoán hoặc điều trị của bác sĩ.</p></section>

      <div className="workspace" id="top">
        <aside className="left-panel">
          <div><p className="eyebrow">PHIÊN TƯ VẤN</p><h1>Hiểu triệu chứng,<br />chủ động chăm sóc.</h1><p className="intro">Trả lời một vài câu hỏi để nhận định hướng chăm sóc sức khỏe ban đầu phù hợp hơn.</p></div>
          <div className="steps" aria-label="Tiến trình tư vấn">
            {[["01", "Mô tả triệu chứng", "Bạn đang cảm thấy thế nào?"], ["02", "Câu hỏi bổ sung", "Thời gian và mức độ"], ["03", "Gợi ý tham khảo", "Khả năng và bước tiếp theo"]].map((item, index) => (
              <div className={`step ${progress >= index + 1 ? "active" : ""}`} key={item[0]}><span className="step-number">{progress > index + 1 ? "✓" : item[0]}</span><div><strong>{item[1]}</strong><small>{item[2]}</small></div></div>
            ))}
          </div>
          <div className="privacy-card"><span>⌾</span><div><strong>Quyền riêng tư của bạn</strong><p>Không nhập họ tên, số điện thoại hoặc thông tin định danh cá nhân.</p></div></div>
        </aside>

        <section className="chat-panel" aria-label="Hội thoại tư vấn sức khỏe">
          <div className="chat-header"><div className="doctor-avatar">M</div><div><strong>Trợ lý sức khỏe MedAI</strong><span><i /> FastAPI hỗ trợ sàng lọc</span></div></div>
          <div className="messages" aria-live="polite">
            <div className="date-divider"><span>HÔM NAY</span></div>
            {messages.map((message) => <div className={`message-row ${message.role}`} key={message.id}>{message.role === "assistant" && <div className="mini-avatar">M</div>}<div className="message-bubble">{message.text}</div></div>)}
            {loading && <div className="message-row assistant"><div className="mini-avatar">M</div><div className="message-bubble">Đang tổng hợp thông tin…</div></div>}

            {urgent && <div className="emergency-card"><strong>⚠ Cần trợ giúp khẩn cấp</strong><p>Gọi <b>115</b> hoặc đến khoa Cấp cứu gần nhất. Nếu có thể, hãy nhờ người thân đi cùng.</p></div>}

            {stage === "result" && result && !urgent && <div className="result-card">
              <div className="result-heading"><span>KẾT QUẢ THAM KHẢO</span><em>Đã tổng hợp</em></div><h2>Một số khả năng liên quan</h2>
              {result.possibilities.map((item, index) => <div className={`condition ${index === 0 ? "primary-condition" : ""}`} key={item.name}><div><strong>{item.name}</strong><small>{item.note}</small></div>{index === 0 && <span>Tham khảo</span>}</div>)}
              {result.next_step && <div className="recommendation"><strong>Bước tiếp theo</strong><p>{result.next_step}</p></div>}
            </div>}

            {quickPrompts.length > 0 && !urgent && <div className="quick-wrap"><p>Gợi ý trả lời</p><div className="quick-list">{quickPrompts.map((prompt) => <button disabled={loading} key={prompt} onClick={() => void submit(prompt)}>{prompt}<span>→</span></button>)}</div></div>}
          </div>

          <form className="composer" onSubmit={handleSubmit}>
            <label htmlFor="health-message" className="sr-only">Nhập triệu chứng</label>
            <textarea id="health-message" value={input} disabled={loading} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(input); } }} placeholder="Mô tả triệu chứng của bạn..." rows={2} />
            <button className="send-button" disabled={loading} type="submit" aria-label="Gửi tin nhắn">↑</button><p>Nhấn Enter để gửi · Shift + Enter để xuống dòng</p>
          </form>
        </section>

        <aside className="right-panel">
          <p className="eyebrow">TÓM TẮT HIỆN TẠI</p><div className="summary-card"><div className="summary-item"><span>Triệu chứng chính</span><strong>{summary.symptom}</strong></div><div className="summary-item"><span>Thời gian</span><strong>{summary.duration}</strong></div><div className="summary-item"><span>Mức độ khẩn cấp</span><strong className={urgent ? "urgent-text" : "safe-text"}>{urgent ? "Cần xử trí ngay" : "Chưa phát hiện dấu hiệu đỏ"}</strong></div></div>
          <div className="red-flags"><h3>Dấu hiệu cần cấp cứu</h3><p>Gọi 115 ngay nếu có:</p><ul><li>Khó thở hoặc đau ngực</li><li>Ngất, co giật</li><li>Yếu liệt hoặc méo miệng</li><li>Chảy máu nhiều</li></ul></div>
          <div className="data-note"><span>◇</span><p>Không nhập thông tin định danh. Dữ liệu triệu chứng được gửi tới backend Python để xử lý trong phiên hiện tại.</p></div>
        </aside>
      </div>
    </main>
  );
}
