# Kiến Trúc Middies Health AI (Sau Khi Hợp Nhất Toàn Bộ Các Nhánh)

## 1. Tổng Quan Hợp Nhất Các Nhánh (Branch Unification Summary)

Toàn bộ lịch sử phát triển và tính năng từ **6 nhánh** trong kho mã nguồn (`khanhtrankuri/middies-heath-ai`) đã được đọc rà soát, hợp nhất về nhánh `main` và đồng bộ kiến trúc:

| Nhánh Nguồn (Source Branch) | Thành Phần Đóng Góp Chính | Vị Trí Sau Hợp Nhất & Tích Hợp |
|---|---|---|
| `main` & `research/open-teacher-qwen` | Ứng dụng Full-stack React 19 + Vite + Express + Gemini (`gemini-3.8-flash`), danh mục thuốc (`medicationCatalog.ts`), đọc đơn thuốc/xét nghiệm OCR, kiểm tra tương tác thuốc, quản lý hồ sơ sức khỏe cục bộ | `/` (`server.ts`, `src/*`) |
| `feat/medical-dialogue-research` | Quy trình hội thoại y khoa 7 bước: Bộ định tuyến cấp cứu xác định (`triage.py`), Ràng buộc phạm vi y tế & chống Prompt Injection (`guardrails.py`), Theo dõi trạng thái hội thoại (`DialogueState` - `state.py`), Bộ lập kế hoạch câu hỏi (`Question Planner` - `planner.py`), Giả thuyết bệnh có dẫn chứng (`hypotheses.py`), Làm sạch dữ liệu `Meddies/meddies-consultant` chống rò rỉ (`prepare_dialogue.py`) và kết quả thực nghiệm LoRA E1/E2/E3 (`docs/EXPERIMENT_RESULTS.md`) | Đã giữ nguyên trọn vẹn tại `/qwen-rag-stack/` **VÀ** tích hợp trực tiếp mô-đun DST + Question Planner + Guardrails + Hypotheses vào ứng dụng gốc tại `/src/services/dialogueEngine.ts` & `/src/components/SymptomChatView.tsx` |
| `eval/meddies-consultant` | Pipeline đánh giá tự động endpoint `/api/health/chat` trên bộ dữ liệu `Meddies/meddies-consultant` (`meddies_eval.py` + unit tests) | `/evaluation/` |
| `claude/youthful-meitner-0kodvk` & `feat/initial-project` | Hệ thống Qwen3 (0.6B/1.7B) + Hybrid RAG (BM25 + BGE-M3 + RRF + Reranker) + FastAPI + Next.js/Vinext | `/qwen-rag-stack/` |

---

## 2. Luồng Kiến Trúc Thống Nhất Tại Ứng Dụng Chính (`/server.ts` & `/src/*`)

```text
Người dùng gửi câu hỏi / triệu chứng / hình ảnh y tế
        │
        ▼
[Bước 1] Deterministic Safety Router (src/services/dialogueEngine.ts)
        │  • Quét dấu hiệu Cờ đỏ Cấp cứu (Đột quỵ F.A.S.T, đau ngực/khó thở cấp,
        │    nôn ra máu/phân đen, co giật/lơ mơ, phản vệ, tự hại) có xét phủ định
        ▼
[Bước 2] Deterministic Medical Scope & Anti-Injection Guardrail
        │  • Chặn câu hỏi ngoài lĩnh vực y tế (code, toán, bóng đá, chứng khoán...)
        │    và chặn Prompt Injection trước khi gọi LLM -> trả về OUT_OF_SCOPE
        ▼
[Bước 3] Dialogue State Tracking (DST) & Missing-Slot Analysis
        │  • Bóc tách triệu chứng dương tính, triệu chứng âm tính đã loại trừ,
        │    thời gian khởi phát, vị trí, mức độ/nhiệt độ, tính chất, yếu tố khởi phát
        ▼
[Bước 4] Question Planner & Candidate Hypotheses Engine
        │  • Chọn câu hỏi ưu tiên tiếp theo cho trường thông tin cốt lõi còn thiếu
        │  • Tạo danh sách khả năng liên quan (kèm mã ICD-10, bằng chứng ủng hộ & còn thiếu)
        ▼
[Bước 5] Local Clinical RAG + Patient Profile Context Injection
        │  • Kết hợp phác đồ Bộ Y tế / ICD-10 (clinicalReferenceDataset.ts),
        │    Dược thư (medicationCatalog.ts) và Hồ sơ Dị ứng/Bệnh nền của người dùng
        ▼
[Bước 6] Suy luận Đa phương thức (Gemini 3.8 Flash Structured JSON)
        │
        ▼
[Bước 7] Giao diện React Hiển thị Trực quan (SymptomChatView.tsx)
        • Hộp phân tầng khẩn cấp (Triage) + Khung Trạng Thái Khai Thác Bệnh Sử (DST)
        • Ẩn toàn bộ khung nguyên nhân/nguồn y khoa khi câu hỏi thuộc nhóm OUT_OF_SCOPE
```

---

## 3. Cấu Trúc Thư Mục Toàn Dự Án

```text
.
├── server.ts                              # Máy chủ Express tích hợp 7-Stage DST Engine + Gemini API
├── src/
│   ├── App.tsx                            # Giao diện chính 4 phân khu y tế + Thẻ Cấp Cứu 115
│   ├── services/
│   │   └── dialogueEngine.ts              # Động cơ DST, Question Planner, Safety Router & Hypotheses
│   ├── data/
│   │   ├── clinicalReferenceDataset.ts    # Bộ dữ liệu phác đồ lâm sàng ICD-10 / Bộ Y tế & chuẩn xét nghiệm
│   │   ├── medicationCatalog.ts           # Danh mục dược điển & tìm kiếm thuốc nhanh (Autocomplete)
│   │   └── defaultHealthData.ts           # Hồ sơ mẫu & dữ liệu kiểm thử lâm sàng
│   └── components/
│       ├── SymptomChatView.tsx            # Tư vấn triệu chứng + Hiển thị DST, Missing Info & Hypotheses
│       ├── DocumentScannerView.tsx        # Đọc đơn thuốc & phiếu xét nghiệm qua ảnh (OCR)
│       ├── DrugInteractionView.tsx        # Kiểm tra tương tác đa hoạt chất & gợi ý thuốc nhanh
│       ├── HealthProfileView.tsx          # Quản lý hồ sơ sức khỏe, BMI, sinh hiệu & lịch nhắc thuốc
│       └── EmergencyGuideModal.tsx        # Cẩm nang sơ cứu cấp cứu 115 & Thẻ Y tế cá nhân
├── evaluation/                            # Pipeline đánh giá chuẩn trên tập Meddies/meddies-consultant
├── qwen-rag-stack/                        # Toàn bộ mã nguồn Qwen3 LoRA + FastAPI + Hybrid RAG + Tài liệu nghiên cứu
│   ├── backend/app/services/dialogue/     # Bản Python gốc của DST, Planner, Lexicon, Hypotheses, Guardrails
│   ├── backend/training/                  # Pipeline làm sạch dữ liệu & huấn luyện LoRA Qwen3 (E1/E2/E3)
│   ├── backend/evals/                     # Bộ đo DST, Question Rubric, Safety Cases & Error Analysis
│   └── docs/                              # ARCHITECTURE.md, AUDIT.md, DATASET.md, TRAINING.md, EXPERIMENT_RESULTS.md
└── ARCHITECTURE.md                        # Tài liệu kiến trúc hợp nhất
```
