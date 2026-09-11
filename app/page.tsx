"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ConsultationResponse, consultationError, localEmergency, MAX_HISTORY_MESSAGES, MAX_MESSAGE_LENGTH, safeSourceUrl } from "./consultation";

type Message = { id: number; role: "assistant" | "user"; text: string; failed?: boolean; result?: ConsultationResponse };
type ReadyResponse = { api: boolean; model: boolean; rag: boolean };

const API_URL = (process.env.NEXT_PUBLIC_MEDDIES_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const firstPrompts = ["Tôi bị đau đầu và hơi chóng mặt", "Tôi ho, đau họng và sốt nhẹ", "Tôi đau bụng sau khi ăn"];
const timePrompts = ["Dưới 24 giờ", "Khoảng 1–3 ngày", "Trên 3 ngày"];
const initialMessage: Message = {
  id: 1,
  role: "assistant",
  text: "Chào bạn, tôi là MedAI — trợ lý hỗ trợ sàng lọc sức khỏe ban đầu. Hôm nay bạn đang gặp triệu chứng gì?",
};

function Sources({ result }: { result: ConsultationResponse }) {
  if (result.action === "ASK_MORE" || result.action === "EMERGENCY") return null;
  return <div className="result-card source-panel">
    <div className="result-heading"><span>NGUỒN THAM KHẢO</span><em>{result.grounding_status === "grounded" ? "Có trích dẫn" : "Chưa kiểm chứng"}</em></div>
    <h2>Nguồn cho câu trả lời này</h2>
    {result.citations.length ? result.citations.map((source) => {
      const url = safeSourceUrl(source.source_url);
      return <article className="source-card" key={source.citation_id}>
        <div className="source-title"><span>[{source.citation_id}]</span><strong>{source.title ?? "Tài liệu tham khảo"}</strong></div>
        {(source.organization || source.publication_date) && <small>{[source.organization, source.publication_date].filter(Boolean).join(" · ")}</small>}
        <p>{source.snippet}</p>
        <div className="source-meta"><span>{[source.section && `Mục ${source.section}`, source.page && `Trang ${source.page}`].filter(Boolean).join(" · ")}</span>{url && <a href={url} target="_blank" rel="noopener noreferrer">Mở nguồn ↗</a>}</div>
      </article>;
    }) : <div className="grounding-warning">Câu trả lời chưa có nguồn tham khảo được xác nhận. Hãy trao đổi với nhân viên y tế để được đánh giá phù hợp.</div>}
    {result.disclaimer && <p className="result-disclaimer">{result.disclaimer}</p>}
  </div>;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([initialMessage]);
  const [input, setInput] = useState("");
  const [stage, setStage] = useState<"symptom" | "followup" | "result">("symptom");
  const [urgent, setUrgent] = useState(false);
  const [result, setResult] = useState<ConsultationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [modelReady, setModelReady] = useState<boolean | null>(null);
  const [ragReady, setRagReady] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [failedMessage, setFailedMessage] = useState<Message | null>(null);
  const nextMessageId = useRef(2);
  const activeRequest = useRef<AbortController | null>(null);
  const transcriptEnd = useRef<HTMLDivElement | null>(null);
  const composer = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    let controller: AbortController;
    let disposed = false;
    async function checkReadiness() {
      controller?.abort();
      controller = new AbortController();
      const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(8000)]);
      await fetch(`${API_URL}/ready`, { signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Backend health check failed");
        const readiness = (await response.json()) as ReadyResponse;
        if (disposed) return;
        setApiOnline(readiness.api);
        setModelReady(readiness.model);
        setRagReady(readiness.rag);
      })
      .catch((error: unknown) => {
        if (disposed || (error instanceof DOMException && error.name === "AbortError")) return;
        setApiOnline(false);
        setModelReady(false);
        setRagReady(false);
      });
    }
    void checkReadiness();
    const interval = window.setInterval(() => void checkReadiness(), 30000);
    return () => { disposed = true; controller?.abort(); window.clearInterval(interval); activeRequest.current?.abort(); activeRequest.current = null; };
  }, []);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ block: "nearest" });
  }, [messages, loading, error]);

  const progress = stage === "symptom" ? 1 : stage === "followup" ? 2 : 3;
  const quickPrompts = stage === "symptom" ? firstPrompts : stage === "followup" && !result?.patient_state.duration ? timePrompts : [];
  const summary = {
    symptom: result?.patient_state.chief_complaint ?? messages.find((item) => item.role === "user" && !item.failed)?.text ?? "Chưa ghi nhận",
    duration: result?.patient_state.duration ?? "Đang thu thập",
    severity: result?.patient_state.severity ?? "Chưa ghi nhận",
  };
  const historyFull = messages.filter((item) => !item.failed).length >= MAX_HISTORY_MESSAGES;

  function addExchange(userText: string, assistantText: string) {
    const id = nextMessageId.current;
    nextMessageId.current += 2;
    setMessages((current) => [...current, { id, role: "user", text: userText }, { id: id + 1, role: "assistant", text: assistantText }]);
  }

  async function callConsultation(nextUserMessage: string, signal: AbortSignal) {
    const conversation = [
      ...messages.filter((item) => !item.failed).map((item) => ({ role: item.role, content: item.text })),
      { role: "user" as const, content: nextUserMessage },
    ];
    const response = await fetch(`${API_URL}/api/v1/consultation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: conversation }),
      signal,
    });
    if (!response.ok) throw new Error(consultationError(response.status));
    return (await response.json()) as ConsultationResponse;
  }

  async function submit(text: string, retryId?: number) {
    const clean = text.trim();
    if (!clean || activeRequest.current) return;
    if (clean.length > MAX_MESSAGE_LENGTH) { setError(`Tin nhắn tối đa ${MAX_MESSAGE_LENGTH} ký tự.`); return; }
    setError(null);
    setFailedMessage(null);
    setInput("");

    // Luôn cảnh báo ngay tại trình duyệt, kể cả khi backend không kết nối được.
    if (localEmergency(clean)) {
      addExchange(clean, "Triệu chứng bạn mô tả có thể cần được đánh giá khẩn cấp. Hãy gọi 115 hoặc đến cơ sở cấp cứu gần nhất ngay; không nên chờ tư vấn trực tuyến.");
      setUrgent(true);
      setResult(null);
      setStage("result");
      return;
    }

    if (historyFull) { setInput(clean); setError("Phiên tư vấn đã đạt giới hạn. Hãy bắt đầu cuộc trò chuyện mới."); return; }
    const controller = new AbortController();
    activeRequest.current = controller;
    const timeout = window.setTimeout(() => controller.abort("timeout"), 90000);
    const id = retryId ?? nextMessageId.current++;
    setMessages((current) => retryId
      ? current.map((item) => item.id === retryId ? { ...item, failed: false } : item)
      : [...current, { id, role: "user", text: clean }]);
    setLoading(true);
    try {
      const data = await callConsultation(clean, controller.signal);
      if (activeRequest.current !== controller) return;
      const assistantId = nextMessageId.current++;
      setMessages((current) => [...current, { id: assistantId, role: "assistant", text: data.reply, result: data }]);
      setResult(data);
      if (data.action === "ASK_MORE") {
        setUrgent(false);
        setStage("followup");
      } else {
        setUrgent(data.action === "EMERGENCY");
        setStage("result");
      }
      setApiOnline(true);
      if (data.provider !== "safety-router") setModelReady(true);
    } catch (cause: unknown) {
      if (activeRequest.current !== controller) return;
      const failed: Message = { id, role: "user", text: clean, failed: true };
      setMessages((current) => current.map((item) => item.id === id ? failed : item));
      setFailedMessage(failed);
      setError(controller.signal.aborted ? "Phản hồi lâu hơn dự kiến. Bạn có thể thử gửi lại." : cause instanceof TypeError ? "Không thể kết nối dịch vụ tư vấn. Kiểm tra kết nối rồi thử lại." : cause instanceof Error ? cause.message : "Đã xảy ra lỗi. Vui lòng thử lại.");
    } finally {
      window.clearTimeout(timeout);
      if (activeRequest.current === controller) { activeRequest.current = null; setLoading(false); composer.current?.focus(); }
    }
  }

  function handleSubmit(event: FormEvent) { event.preventDefault(); void submit(input); }
  function resetChat() {
    activeRequest.current?.abort();
    activeRequest.current = null;
    const id = nextMessageId.current++;
    setMessages([{ ...initialMessage, id }]);
    setStage("symptom"); setUrgent(false); setResult(null); setInput(""); setLoading(false); setError(null); setFailedMessage(null);
    composer.current?.focus();
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Trang chủ MedAI"><span className="brand-mark">✦</span><span>MedAI</span></a>
        <div className="top-actions">
          <span className="secure-label" role="status"><span className={`status-dot ${apiOnline && modelReady && ragReady ? "" : "unavailable"}`} /> {apiOnline === null ? "Đang kiểm tra kết nối" : !apiOnline ? "Chưa kết nối dịch vụ" : !modelReady ? "Trợ lý chưa sẵn sàng" : ragReady ? "Nguồn tham khảo sẵn sàng" : "Nguồn tham khảo chưa sẵn sàng"}</span>
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
          <div className="chat-header"><div className="doctor-avatar">M</div><div><strong>Trợ lý sức khỏe MedAI</strong><span>Hỗ trợ thông tin và sàng lọc ban đầu</span></div></div>
          <div className="messages" aria-live="polite">
            {result?.provider === "stub" && <div className="grounding-warning">Chế độ kiểm thử: đang dùng phản hồi mẫu, chưa sử dụng mô hình AI tư vấn thật.</div>}
            <div className="date-divider"><span>HÔM NAY</span></div>
            {messages.map((message) => <div key={message.id}><div className={`message-row ${message.role} ${message.failed ? "failed" : ""}`}>{message.role === "assistant" && <div className="mini-avatar">M</div>}<div className="message-bubble">{message.text}{message.failed && <small>Chưa gửi thành công</small>}</div></div>{message.result && <Sources result={message.result} />}</div>)}
            {loading && <div className="message-row assistant"><div className="mini-avatar">M</div><div className="message-bubble">Đang tổng hợp thông tin…</div></div>}

            {urgent && <div className="emergency-card" role="alert"><strong>⚠ Cần trợ giúp khẩn cấp</strong><p>Gọi <a href="tel:115"><b>115</b></a> (Việt Nam) hoặc đến khoa Cấp cứu gần nhất. Nếu có thể, hãy nhờ người thân đi cùng.</p></div>}

            {error && <div className="request-error" role="alert"><p>{error}</p>{failedMessage && <button disabled={loading} onClick={() => void submit(failedMessage.text, failedMessage.id)}>Thử gửi lại</button>}</div>}
            {historyFull && <div className="grounding-warning">Phiên tư vấn đã đạt giới hạn. Chọn “Cuộc trò chuyện mới” để tiếp tục.</div>}

            {quickPrompts.length > 0 && !urgent && !historyFull && !failedMessage && <div className="quick-wrap"><p>Gợi ý trả lời</p><div className="quick-list">{quickPrompts.map((prompt) => <button disabled={loading} key={prompt} onClick={() => void submit(prompt)}>{prompt}<span>→</span></button>)}</div></div>}
            <div ref={transcriptEnd} />
          </div>

          <form className="composer" onSubmit={handleSubmit}>
            <label htmlFor="health-message" className="sr-only">Nhập triệu chứng</label>
            <textarea ref={composer} id="health-message" value={input} readOnly={loading} maxLength={MAX_MESSAGE_LENGTH} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submit(input); } }} placeholder="Mô tả triệu chứng hoặc đặt câu hỏi sức khỏe..." rows={2} aria-describedby="composer-help" />
            <button className="send-button" disabled={loading || !input.trim()} type="submit" aria-label="Gửi tin nhắn">↑</button><p id="composer-help">Enter để gửi · Shift + Enter để xuống dòng <span>{input.length}/{MAX_MESSAGE_LENGTH}</span></p>
          </form>
        </section>

        <aside className="right-panel">
          <p className="eyebrow">TÓM TẮT HIỆN TẠI</p><div className="summary-card"><div className="summary-item"><span>Mô tả ban đầu</span><strong>{summary.symptom}</strong></div><div className="summary-item"><span>Thời gian</span><strong>{summary.duration}</strong></div><div className="summary-item"><span>Mức độ triệu chứng</span><strong>{summary.severity}</strong></div><div className="summary-item"><span>Dấu hiệu khẩn cấp</span><strong className={urgent ? "urgent-text" : ""}>{urgent ? "Cần xử trí ngay" : result ? "Chưa ghi nhận qua mô tả" : "Chưa được đánh giá"}</strong></div></div>
          <div className="red-flags"><h3>Dấu hiệu cần cấp cứu</h3><p>Gọi 115 ngay nếu có:</p><ul><li>Khó thở hoặc đau ngực</li><li>Ngất, co giật</li><li>Yếu liệt hoặc méo miệng</li><li>Chảy máu nhiều</li></ul></div>
          <div className="data-note"><span>◇</span><p>Nội dung được gửi đến dịch vụ tư vấn để xử lý. Hội thoại chỉ hiển thị trong phiên này và sẽ mất khi tải lại trang.</p></div>
        </aside>
      </div>
    </main>
  );
}
