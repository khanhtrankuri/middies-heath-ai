# Ứng Dụng AI Cho Bài Toán Y Tế — Hệ Thống Tư Vấn Sức Khỏe & Sàng Lọc Triệu Chứng Đa Lượt (`Meddies/meddies-consultant`)

Tái cấu trúc và nâng cấp toàn diện ứng dụng Web/App và hệ thống Backend suy luận để bám sát 100% mục tiêu, sản phẩm dự kiến và mô tả trong bản đăng ký đề tài **"Ứng dụng AI cho bài toán Y Tế"**: tiếp nhận triệu chứng bằng ngôn ngữ tự nhiên, chủ động đặt câu hỏi bổ sung đa lượt để thu thập bệnh sử, dự đoán các bệnh có khả năng liên quan kèm thông tin y tế tham khảo, khuyến nghị thăm khám tại cơ sở y tế và tích hợp trực tiếp không gian trình diễn dữ liệu/mô hình `Meddies/meddies-consultant` phục vụ bảo vệ đề tài.

![Bản đăng ký đề tài Ứng dụng AI cho bài toán Y Tế](/public/assets/aistudio/image_58cff4b2.png)

## User Review & Critical Decisions

> [!IMPORTANT]
> Dưới đây là các quyết định kiến trúc và trải nghiệm cốt lõi đã được chốt từ phản hồi của bạn để đảm bảo sản phẩm khớp tuyệt đối với đề cương đăng ký đề tài:

- **Confirmed Decision 1 — Bố cục giao diện bám sát Đề tài & Bảo vệ Khoa học**: Tổ chức giao diện xoay quanh luồng cốt lõi của đề tài (**Hội thoại thu thập triệu chứng → Dự đoán các bệnh liên quan → Thông tin y tế tham khảo & Khuyến nghị cơ sở y tế**), đồng thời bổ sung chuyên mục **"Mô Hình & Dataset Meddies"** ngay trên thanh điều hướng chính để trình diễn trực quan bộ dữ liệu `Meddies/meddies-consultant`, quy trình tiền xử lý chống rò rỉ và kết quả huấn luyện thực nghiệm trước hội đồng. Các công cụ bổ trợ (Quét đơn thuốc OCR, Tra cứu tương tác thuốc, Hồ sơ cá nhân) được nhóm gọn làm tiện ích mở rộng.
- **Confirmed Decision 2 — Hệ thống Backend Suy luận Chế độ Kép (Dual Inference Backend)**: Hỗ trợ chuyển đổi linh hoạt giữa **(1) Chế độ Suy luận Trực tuyến Kết hợp RAG `Meddies/meddies-consultant` + 7-Stage Clinical Dialogue Engine** (hoạt động ổn định mọi lúc trên Cloud) và **(2) Chế độ Kết nối Trực tiếp FastAPI Qwen Fine-Tuned (`qwen-rag-stack`)** chạy mô hình `Qwen3-1.7B` / `Qwen2.5-7B` LoRA kèm tự động kiểm tra trạng thái `/ready` và cơ chế dự phòng mượt mà.
- **Confirmed Decision 3 — Bộ 4 Thành phần Kết quả Phân tích Lâm sàng Trực quan**: Trong mỗi phiên tư vấn, giao diện hiển thị đồng bộ:
  1. **Tiến trình thu thập triệu chứng 3 bước** (`Tiếp nhận triệu chứng` → `Hỏi bổ sung làm rõ` → `Dự đoán & Khuyến nghị`) kèm các gợi ý câu hỏi/câu trả lời nhanh từ Question Planner.
  2. **Danh sách các bệnh có khả năng liên quan (`Candidate Conditions`)** kèm mã `ICD-10`, mức độ tương khớp triệu chứng, bằng chứng ủng hộ (`Dựa trên`), thông tin cần làm rõ thêm (`Chưa xác nhận`) và phân tầng mức độ chăm sóc.
  3. **Thẻ thông tin y tế tham khảo chi tiết về bệnh & Khuyến nghị cơ sở y tế** (cơ chế bệnh sinh dễ hiểu, dấu hiệu cảnh báo đỏ cần đi khám ngay, chuyên khoa gợi ý và tuyên bố miễn trừ không thay thế chẩn đoán bác sĩ).
  4. **Trình khám phá mẫu hội thoại tương đồng từ tập dữ liệu `Meddies/meddies-consultant`** ngay trong phiên tư vấn và trong trang nghiên cứu chuyên biệt.

---

## 1. Overview & Core Concept

- **What It Does**: Hệ thống đóng vai trò trợ lý sàng lọc sức khỏe ban đầu bằng tiếng Việt. Khi người dùng mô tả triệu chứng bằng ngôn ngữ tự nhiên, hệ thống không vội vàng kết luận ngay ở lượt đầu mà tiến hành **hỏi bệnh đa lượt (Multi-turn History Taking)** để thu thập các thông tin còn thiếu (vị trí, thời gian khởi phát, mức độ, tính chất, triệu chứng đi kèm, tiền sử). Khi đã đủ căn cứ hoặc phát hiện dấu hiệu nguy hiểm, hệ thống đưa ra **danh sách các bệnh có khả năng liên quan**, **thông tin y tế tham khảo**, và **khuyến nghị đến cơ sở y tế phù hợp**.
- **Target Audience / Persona**:
  - **Người bệnh & người dùng cá nhân**: Cần công cụ sàng lọc triệu chứng ban đầu bằng tiếng Việt tự nhiên, dễ hiểu, an toàn, biết khi nào cần đi khám chuyên khoa hoặc cấp cứu 115.
  - **Hội đồng chấm khóa luận / đề tài nghiên cứu**: Cần kiểm chứng tính hoàn chỉnh của cả 3 thành phần trong đề cương đăng ký: **(1) Mô hình AI xử lý hội thoại y tế (`Meddies/meddies-consultant`)**, **(2) Hệ thống Backend phục vụ suy luận mô hình**, và **(3) Giao diện Web/App tương tác người dùng**.
- **Key Value**: Khắc phục nhược điểm của các LLM thông thường (thường liệt kê bệnh quá sớm hoặc bỏ sót dấu hiệu cấp cứu) bằng kiến trúc kết hợp **7-Stage Clinical Dialogue Engine + Fine-tuned Model / RAG trên `Meddies/meddies-consultant`**, đảm bảo tỷ lệ đặt câu hỏi khai thác bệnh sử đạt chuẩn lâm sàng và an toàn tuyệt đối trước các ca cấp cứu.

---

## 2. User Experience & Visual Design

### Key User Flows

1. **Luồng 1 — Tư vấn Hội thoại & Dự đoán Bệnh Liên quan (Trọng tâm Đề tài)**:
   - **Bước 1 (Tiếp nhận triệu chứng)**: Người dùng nhập triệu chứng tự nhiên (ví dụ: *"Tôi bị đau đầu âm ỉ 2 ngày nay kèm hơi buồn nôn"*) hoặc chọn kịch bản mẫu từ tập kiểm thử `Meddies/meddies-consultant`.
   - **Bước 2 (Hỏi bổ sung thu thập thông tin)**: Thanh tiến trình 3 giai đoạn ở đầu khung tư vấn chuyển sang giai đoạn `2. Hỏi bổ sung thu thập thông tin`. Trợ lý AI đặt 1–2 câu hỏi trọng tâm để làm rõ các thông tin còn thiếu (ví dụ: vị trí đau một bên hay hai bên, có sốt hay cứng cổ không, có nhạy cảm ánh sáng không) kèm các nút chọn trả lời nhanh cho người dùng.
   - **Bước 3 (Phân tích & Dự đoán các bệnh có khả năng liên quan)**: Khi đã thu thập đủ các trường thông tin cốt lõi, hệ thống cập nhật cột **Bảng Phân Tích Sàng Lọc Y Khoa** bên phải với:
     - **Hồ sơ triệu chứng đã thu thập (DST)**: Tóm tắt rõ các triệu chứng dương tính, triệu chứng âm tính đã loại trừ, thời gian, vị trí, mức độ.
     - **Danh sách các bệnh có khả năng liên quan**: Hiển thị các bệnh lý nghi ngờ (ví dụ: *Đau nửa đầu Migraine — ICD-10: G43*, *Đau đầu căng thẳng — ICD-10: G44.2*) kèm thanh mức độ khớp bằng chứng, danh sách triệu chứng ủng hộ, yếu tố chưa xác nhận và nhãn mức độ xử trí (`Theo dõi tại nhà`, `Khám trong 1–2 ngày`, `Khám ngay hôm nay`).
     - **Thẻ thông tin y tế tham khảo & Khuyến nghị cơ sở y tế**: Cung cấp mô tả y khoa dễ hiểu về từng bệnh, hướng dẫn theo dõi ban đầu, chuyên khoa cần đăng ký khám (ví dụ: *Chuyên khoa Nội Thần kinh*) và danh sách dấu hiệu cảnh báo cần đi cấp cứu 115.
     - **Đối chiếu mẫu hội thoại `Meddies/meddies-consultant`**: Hiển thị các đoạn hội thoại bác sĩ – bệnh nhân tương đồng trong tập dữ liệu huấn luyện để minh họa căn cứ tham khảo.

2. **Luồng 2 — Trình diễn Mô hình AI & Dataset `Meddies/meddies-consultant` (Phục vụ Bảo vệ Đề tài)**:
   - Người dùng hoặc giảng viên phản biện mở tab **"Mô Hình & Dataset Meddies"** trên thanh điều hướng chính:
     - **Khám phá Dataset `Meddies/meddies-consultant`**: Thống kê chi tiết bộ dữ liệu gốc (`58.064` hội thoại tiếng Việt, revision `05428709a...`, `1.236` nhóm bệnh `target_disease`), bộ lọc làm sạch 2 tầng (`Standard: 51.320` hội thoại và `Strict: 33.237` hội thoại), biểu đồ phân bố lý do loại bỏ (`role_inversion`, `unclosed_reasoning`, `medication_dose`, `emergency_not_escalated`) và cơ chế chia tập `80/10/10` theo nhóm bệnh chống rò rỉ dữ liệu (`0` nhóm bệnh trùng lặp).
     - **Trình duyệt Mẫu Hội thoại Thực tế (Interactive Dataset Explorer)**: Cho phép tìm kiếm, lọc theo nhóm bệnh (Hô hấp, Tiêu hóa, Thần kinh, Tim mạch, Da liễu, Cơ xương khớp, Tiết niệu) và xem chi tiết từng lượt hỏi – đáp giữa Bác sĩ và Bệnh nhân trong tập `Meddies/meddies-consultant`, đồng thời có nút **"Chạy thử kịch bản này trên Chatbot"** chỉ với 1 cú nhấp chuột.
     - **Kết quả Thực nghiệm & So sánh Mô hình (`E1 Base` vs `E2 LoRA Standard` vs `E3 LoRA Strict` vs `P0 Planner`)**: Hiển thị bảng đối chiếu trực quan các chỉ số đánh giá từ quá trình huấn luyện QLoRA (`Validation Loss` giảm từ `2.263` xuống `1.376`, tỷ lệ lượt có câu hỏi bổ sung tăng từ `29.8%` lên `88.1%`, giảm lỗi nêu bệnh sớm từ `44.1%` xuống `8.8%`, cùng kết quả kiểm thử `90/90` ca an toàn cấp cứu đạt `Recall 1.00`).
     - **Cấu hình Backend Suy luận Mô hình**: Cho phép chuyển đổi trực tiếp giữa **Cloud Hybrid Inference (Gemini + Meddies RAG)** và **Local Qwen Fine-Tuned FastAPI (`http://localhost:8000`)** kèm kiểm tra trạng thái kết nối thời gian thực.

3. **Luồng 3 — Các Tiện ích Lâm sàng Mở rộng**:
   - Giữ nguyên tính năng **Quét Đơn Thuốc & Xét Nghiệm (OCR)**, **Kiểm Tra Tương Tác Thuốc (kèm Autocomplete tên thuốc)**, **Hồ Sơ Sức Khỏe Cá Nhân** và **Cẩm Nang Cấp Cứu 115** để hệ thống vừa bám sát đề cương nghiên cứu vừa hoàn chỉnh như một sản phẩm thực tiễn.

### Visual Identity & Theme

- **Aesthetic Direction**: **Clinical Precision & Academic Clarity** — Phong cách y tế số chuẩn mực kết hợp tính minh bạch khoa học, truyền tải sự tin cậy của một hệ thống hỗ trợ quyết định lâm sàng (Clinical Decision Support) và một công trình nghiên cứu AI nghiêm túc.
- **Color Palette & Mood**:
  - Bề mặt nền sáng sạch (`#F8FAFC` Slate-50) và khung nội dung trắng tinh khiết (`#FFFFFF`) với đường viền mảnh `1px solid #E2E8F0`.
  - Màu nhấn chủ đạo: **Clinical Teal (`#0F766E` / `#0D9488`)** cho các tác vụ tư vấn và định hướng y khoa; **Academic Indigo (`#1E293B` / `#334155`)** cho khu vực phân tích mô hình và dữ liệu `Meddies/meddies-consultant`.
  - Màu ngữ nghĩa phân tầng mức độ chăm sóc:
    - `Theo dõi & Chăm sóc ban đầu`: Emerald (`#15803D`, nền `#F0FDF4`)
    - `Cần theo dõi sát`: Amber (`#B45309`, nền `#FFFBEB`)
    - `Khuyến nghị khám chuyên khoa sớm (1–2 ngày)`: Orange (`#C2410C`, nền `#FFF7ED`)
    - `Cấp cứu y tế khẩn cấp (115)`: Crimson (`#B91C1C`, nền `#FEF2F2`)
- **Typography & Hierarchy**:
  - Tiêu đề: `Plus Jakarta Sans` (SemiBold/Bold, hỗ trợ tiếng Việt sắc nét).
  - Nội dung hội thoại & văn bản tham khảo y khoa: `Be Vietnam Pro` (`14px–15px`, chiều cao dòng `1.6` dễ đọc).
  - Số liệu thống kê, tỷ lệ khớp triệu chứng, mã `ICD-10`, kết quả benchmark: `JetBrains Mono` với `font-variant-numeric: tabular-nums`.
- **Component Styling & Layout**:
  - Tuân thủ kỷ luật **Top Bar 3 Vùng**: Trái (Nhận diện đề tài **"Ứng dụng AI cho bài toán Y Tế — Meddies Health AI"**), Giữa (Thanh chuyển phân hệ), Phải (Chỉ báo chế độ Backend suy luận & Nút Cấp cứu 115).
  - Bố cục màn hình Tư vấn chia 2 cột cân đối trên Desktop (`7 cột` cho Hội thoại & Tiến trình hỏi bệnh + `5 cột` cho Bảng Dự đoán Bệnh Liên quan, Thông tin Tham khảo & Khuyến nghị Cơ sở Y tế).

---

## 3. Key Product Decisions & Trade-Offs

- **Decision 1 — Kết hợp Planner Luật Lâm sàng (7-Stage DST) với Mô hình Sinh Ngôn ngữ (LLM / Fine-tuned Qwen)**:
  - *Chosen Approach*: Mọi tin nhắn của người dùng đều đi qua bộ máy **7-Stage Clinical Dialogue Engine** (Sàng lọc cấp cứu → Kiểm tra phạm vi y tế → Trích xuất triệu chứng DST → Xác định thông tin thiếu → Lập kế hoạch câu hỏi bổ sung → Xếp hạng các bệnh có khả năng liên quan) trước và sau khi mô hình AI sinh câu trả lời.
  - *Why*: Kết quả thực nghiệm trên tập `Meddies/meddies-consultant` chứng minh mô hình thuần túy có thể bỏ sót dấu hiệu cấp cứu hoặc hỏi dồn quá nhiều câu; sự kết hợp giữa **Dialogue State Tracker + Question Planner** và **Mô hình AI** giúp đảm bảo hệ thống luôn hỏi đúng trọng tâm, đưa ra các bệnh liên quan có căn cứ triệu chứng rõ ràng và đạt `Recall 100%` trên bộ kiểm thử cấp cứu.
  - *Alternatives Considered*: Chỉ gọi prompt LLM đơn thuần — bị loại bỏ vì dễ kết luận bệnh quá sớm ở lượt 1 và thiếu tính nhất quán khi bảo vệ đề tài.
- **Decision 2 — Kiến trúc Backend Suy luận Chế độ Kép (Cloud Hybrid + Local FastAPI Qwen Adapter)**:
  - *Chosen Approach*: Backend Express (`/api/health/chat` và `/api/meddies/*`) vừa tích hợp bộ máy suy luận trực tuyến kèm RAG mẫu hội thoại `Meddies/meddies-consultant`, vừa hỗ trợ proxy/chuyển tiếp trực tiếp sang cổng FastAPI (`http://localhost:8000/api/v1/consultation`) của mô hình Qwen fine-tuned khi người dùng bật server GPU cục bộ.
  - *Why*: Giúp ứng dụng luôn hoạt động tức thì trên trình duyệt phục vụ demo mọi lúc, đồng thời liên kết chặt chẽ với mã nguồn huấn luyện/suy luận Qwen LoRA có sẵn trong dự án.

---

## 4. Technical Architecture & Data Strategy *(Technical Reference)*

### Architecture & Component Diagram

```text
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                  GIAO DIỆN WEB/APP: ỨNG DỤNG AI CHO BÀI TOÁN Y TẾ                        │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ Top Bar: Thương hiệu Đề tài │ [Tư Vấn & Dự Đoán Bệnh] [Mô Hình & Dataset Meddies]  │  │
│  │                             │ [Quét Đơn/XN] [Tương Tác Thuốc] [Hồ Sơ]  │ [115 SOS] │  │
│  └────────────────────────────────────────────────────────────────────────────────────┘  │
│                 │                                                  │                     │
│                 ▼                                                  ▼                     │
│  ┌─────────────────────────────────────────┐    ┌─────────────────────────────────────┐  │
│  │ PHÂN HỆ 1: TƯ VẤN & SÀNG LỌC TRIỆU CHỨNG│    │ PHÂN HỆ 2: MÔ HÌNH & DATASET MEDDIES│  │
│  │ • Thanh Tiến Trình 3 Giai Đoạn Khai Thác│    │ • Thống Kê & Pipeline Làm Sạch      │  │
│  │   (Tiếp nhận -> Hỏi bổ sung -> Dự đoán) │    │   Meddies/meddies-consultant        │  │
│  │ • Khung Hội Thoại Tự Nhiên + Gợi Ý Trả  │    │ • Trình Khám Phá Mẫu Hội Thoại Thực │  │
│  │   Lời Nhanh Từ Question Planner         │    │   Tế + Nút "Chạy Thử Trên Chatbot"  │  │
│  │ • Bảng Dự Đoán Các Bệnh Có Khả Năng     │    │ • Bảng Benchmark Thực Nghiệm        │  │
│  │   Liên Quan (Tỷ lệ khớp, ICD-10, Bằng   │    │   (E1 Base vs E2/E3 LoRA vs P0)     │  │
│  │   chứng ủng hộ, Thông tin chưa xác nhận)│    │ • Bộ Chuyển Đổi Chế Độ Suy Luận     │  │
│  │ • Thẻ Thông Tin Y Tế Tham Khảo Về Bệnh  │    │   (Cloud Hybrid RAG <-> Qwen LoRA)  │  │
│  │ • Khuyến Nghị Cơ Sở Y Tế & Chuyên Khoa  │    └─────────────────────────────────────┘  │
│  └────────────────────┬────────────────────┘                                             │
└───────────────────────┼──────────────────────────────────────────────────────────────────┘
                        │  HTTP JSON (/api/health/chat, /api/meddies/samples)
                        ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                 HỆ THỐNG BACKEND PHỤC VỤ SUY LUẬN MÔ HÌNH (SERVER GATEWAY)               │
│                                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐  │
│  │ TẦNG 1: 7-STAGE CLINICAL DIALOGUE ENGINE & MEDDIES KNOWLEDGE BASE                  │  │
│  │ 1. Emergency Red-Flag Router (90 ca chuẩn)   4. Missing-Information Analyzer       │  │
│  │ 2. Medical Domain & Injection Guardrail      5. Follow-up Question Planner (P0)    │  │
│  │ 3. Dialogue State Tracker (DST 8 nhóm bệnh)  6. Candidate Condition Scorer (26 bệnh│  │
│  └───────────────────────────────────────┬────────────────────────────────────────────┘  │
│                                          │                                               │
│                     ┌────────────────────┴────────────────────┐                          │
│                     ▼                                         ▼                          │
│  ┌──────────────────────────────────────┐  ┌──────────────────────────────────────────┐  │
│  │ CHẾ ĐỘ A: CLOUD HYBRID MEDDIES RAG   │  │ CHẾ ĐỘ B: LOCAL QWEN FINE-TUNED BACKEND  │  │
│  │ • Truy xuất mẫu hội thoại tương đồng │  │ • Kết nối FastAPI (/api/v1/consultation) │  │
│  │   từ tập Meddies/meddies-consultant  │  │ • Suy luận Qwen3-1.7B / Qwen2.5-7B LoRA  │  │
│  │ • Suy luận Gemini 3.8 Flash theo     │  │   đã huấn luyện trên Meddies-consultant  │  │
│  │   đúng cấu trúc JSON sàng lọc y tế   │  │ • Hybrid RAG (BM25 + ChromaDB bge-m3)    │  │
│  └──────────────────────────────────────┘  └──────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

### Data Model & State

1. **Cấu trúc Kết quả Phân tích & Dự đoán Bệnh (`TriageResponse` & `CandidateHypothesis`)**:
   - `conversationStage`: `"COLLECTING_SYMPTOMS"` | `"FOLLOW_UP_QUESTIONING"` | `"DISEASE_PREDICTION_READY"` | `"EMERGENCY_ALERT"`
   - `candidateDiseases`: Danh sách các bệnh có khả năng liên quan, mỗi bệnh gồm:
     - `name`: Tên bệnh lý (ví dụ: *Viêm dạ dày – tá tràng cấp*, *Đau nửa đầu Migraine*, *Sốt xuất huyết Dengue*)
     - `icd10`: Mã phân loại quốc tế (`K29`, `G43`, `A97`...)
     - `matchScore`: Điểm độ khớp triệu chứng (`0–100%` dựa trên trọng số triệu chứng đã xác nhận)
     - `supportingEvidence`: Các triệu chứng của người bệnh khớp với bệnh lý này
     - `missingOrUnconfirmed`: Các dấu hiệu cần hỏi hoặc xét nghiệm thêm để phân biệt
     - `referenceInfo`: Thông tin y tế tham khảo về bệnh (nguyên nhân thường gặp, diễn tiến, cách chăm sóc ban đầu)
     - `careLevel`: `"routine"` (Theo dõi tại nhà) | `"soon"` (Khám trong 1–2 ngày) | `"urgent"` (Khám ngay trong ngày / Cấp cứu)
     - `recommendedFacility`: Khuyến nghị cơ sở y tế & chuyên khoa phù hợp (ví dụ: *Phòng khám/Khoa Nội Tiêu hóa*, *Khoa Cấp cứu — Bệnh viện đa khoa*)
2. **Kho mẫu hội thoại chuẩn `Meddies/meddies-consultant` (`MeddiesConversationSample`)**:
   - Lưu trữ tập mẫu tiêu biểu trích từ các nhóm bệnh của bộ dữ liệu `Meddies/meddies-consultant` (revision `05428709a7572f6f0d4aa5045e6ba255fa85af51`) kèm metadata: `conversationId`, `targetDisease`, `clinicalGroup`, `turnsCount`, `cleaningStatus` (`strict` / `standard`), `extractedSlots`, và danh sách các lượt hội thoại `messages` để phục vụ cả truy xuất RAG lẫn trình diễn trên giao diện.

### Interactive Component & State Mapping

- **Thanh Tiến trình Khai thác Triệu chứng 3 Giai đoạn**: Tự động cập nhật theo số lượng trường thông tin đã thu thập trong `dialogueState`. Khi ở giai đoạn 1–2, hệ thống làm nổi bật hộp **"Câu hỏi bổ sung cần làm rõ"** với các nút chọn nhanh (ví dụ: *"Đau âm ỉ hay từng cơn?"*, *"Dưới 24 giờ"*, *"Khoảng 1–3 ngày"*, *"Không có sốt"*).
- **Bảng Dự đoán Các Bệnh Có Khả Năng Liên Quan & Thông tin Tham khảo**: Cho phép người dùng nhấp vào từng bệnh lý dự đoán để mở rộng thẻ **"Thông tin y tế tham khảo & Khuyến nghị thăm khám"** (bao gồm: Giải thích bệnh lý, Dấu hiệu cần đến cơ sở y tế ngay, Chuyên khoa khuyến nghị, và Nguồn tham khảo Bộ Y tế / ICD-10).
- **Nút "Chạy thử kịch bản Meddies trên Chatbot"**: Từ tab **Mô Hình & Dataset Meddies**, khi người dùng chọn một ca hội thoại mẫu trong tập dữ liệu và nhấn nút thử nghiệm, hệ thống tự động chuyển sang màn hình **Tư vấn & Sàng lọc** và nạp triệu chứng mở đầu của bệnh nhân đó vào cuộc hội thoại để trình diễn trực tiếp.
