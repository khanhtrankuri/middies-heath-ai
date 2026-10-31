# Kiến trúc — Qwen + RAG cho hỏi bệnh tiếng Việt

> Phạm vi: hệ thống `qwen-rag-stack/` (nền tảng nghiên cứu chính của đề tài *Ứng dụng AI cho bài toán Y tế*).
> Ứng dụng Gemini ở thư mục gốc là hệ thống riêng, không dùng chung backend/model.
> Đây là phần mềm nghiên cứu, **không phải thiết bị y tế** và không thay thế chẩn đoán của bác sĩ.

## 1. Luồng xử lý một lượt hội thoại

```text
POST /api/v1/consultation  {messages: [...]}         (app/main.py)
        │
        ▼
1. Safety Detection         app/triage.py  find_red_flags()  (mọi lượt user)
   + cờ nguy hiểm theo hồ sơ triệu chứng (state.emergency_flags)
        │  có cờ → EMERGENCY (provider = safety-router), không gọi model/RAG
        ▼
2. Domain Guardrails        app/services/dialogue/guardrails.py  check_scope()
        │  ngoài lĩnh vực / prompt injection → OUT_OF_SCOPE (provider = domain-guardrail)
        ▼
3. Dialogue State Tracking  app/services/dialogue/state.py  extract_dialogue_state()
        ▼
4. Missing-Information Analysis   (core / optional slots theo profiles.py)
        ▼
5. Next Question Selection  app/services/dialogue/planner.py  select_next_medical_question()
        │  còn thiếu thông tin cốt lõi → model diễn đạt câu hỏi đã chọn,
        │  validate_generated_question() kiểm tra; sai → dùng câu hỏi của planner
        │  → ASK_MORE
        ▼  đủ thông tin
6. Hypotheses + Recommendation   hypotheses.py generate_hypotheses()  (luật + knowledge.py)
   + câu trả lời grounded qua RAG (citations) hoặc degraded khi RAG không sẵn sàng
        │  → FINALIZE
        ▼
7. Structured API Response  app/models.py  ConsultationResponse
```

Câu hỏi kiến thức thuần túy (“Migraine là gì?”) đi nhánh `GROUNDED_ANSWER` (RAG) như trước.

## 2. Thành phần mới (`app/services/dialogue/`)

| Module | Vai trò | Ghi chú |
|---|---|---|
| `lexicon.py` | Từ điển triệu chứng tiếng Việt (có dấu/không dấu), mẫu slot, nhận diện chủ đề câu hỏi | Gập dấu giữ nguyên độ dài để ánh xạ span; từ dễ nhầm khi bỏ dấu (`ho`/`họ`, `đau họng`/`đau hông`) dùng mẫu có dấu |
| `features.py` | Token đặc điểm lâm sàng (`sym:`, `neg:`, `loc:`, `char:`, `trig:`, `prog:`, `dur:`, `hist:`) | Có xử lý phủ định |
| `profiles.py` | Hồ sơ phàn nàn (đau đầu, đau bụng/tiêu hóa, hô hấp, sốt, tiết niệu, da, cơ xương khớp, chóng mặt, chung): slot cốt lõi/tùy chọn, cờ cấp cứu/khẩn, câu hỏi mẫu | Do nhóm phát triển soạn, **chưa được chuyên gia thẩm định** |
| `state.py` | `DialogueState`: thông tin do người dùng cung cấp, slot còn thiếu, trạng thái hội thoại | `provenance = user_reported_only`; trường chưa biết để `null` |
| `planner.py` | `select_next_medical_question()` | Thứ tự: dừng khi cấp cứu → hỏi triệu chứng chính → ưu tiên sàng lọc dấu hiệu nguy hiểm khi có yếu tố nguy cơ → thời gian → information gain |
| `knowledge.py` | Bảng tình trạng tham khảo với trọng số liên quan | Trọng số **không phải xác suất**, không hiển thị |
| `hypotheses.py` | Danh sách khả năng liên quan, bằng chứng ủng hộ/còn thiếu, mức chăm sóc, bất định | Từ chối khi chưa đủ dữ liệu |
| `guardrails.py` | Phạm vi y tế, chống đổi vai/prompt injection | Chạy sau phát hiện cấp cứu |
| `prompts.py` | System prompt dùng chung cho dữ liệu huấn luyện, benchmark và API; bộ kiểm tra câu hỏi sinh ra | `SYSTEM_PROMPT_VERSION = consult-vi-v1` |

### Dialogue state

- Trạng thái được **tái dựng từ toàn bộ lịch sử** ở mỗi request (API không lưu phiên), nên không trôi lệch khỏi nội dung người dùng thực sự viết.
- Chỉ lượt `user` cung cấp giá trị. Lượt `assistant` chỉ được đọc để hiểu câu trả lời ngắn (“Không ạ”) cho đúng câu hỏi vừa hỏi.
- Mỗi giá trị có `source` (`user_reported` | `user_answer`) và `turn`.
- Trả lời “Có ạ” cho câu hỏi sàng lọc dấu hiệu nguy hiểm mà không nói rõ dấu hiệu nào → leo thang thành cấp cứu (thiên về an toàn).
- Giả thuyết của hệ thống nằm riêng trong `assessment`, không bao giờ ghi vào `dialogue_state`.

### Information gain (định nghĩa)

Tập ứng viên `C` = các tình trạng trong `knowledge.py` thuộc hồ sơ hiện tại và không bị loại bởi bằng chứng
(đặc điểm loại trừ, hoặc người dùng phủ nhận triệu chứng then chốt). Trọng số ứng viên `w_c = 1 + score_c`
(điểm phù hợp với đặc điểm đã biết) — trọng số liên quan, **không hiệu chuẩn, không phải xác suất**.

Với slot dạng phân loại `s` (vị trí, tính chất, yếu tố khởi phát, diễn biến), tập câu trả lời `A_s` là các token
đặc điểm thuộc `s` mà ít nhất một ứng viên hỗ trợ; ứng viên không hỗ trợ token nào thì phân bố đều trên
`A_s ∪ {khác}`:

```
IG(s) = H(C) − Σ_a P(a) · H(C | a)        IG_norm = IG / H(C)
```

Slot dạng có/không (triệu chứng kèm, tiền sử) dùng phép chia mềm 0.9/0.1 cho từng token và lấy token tốt nhất;
ba token tốt nhất được dùng để tạo câu hỏi (“Bạn có kèm theo … không?”). Điểm chọn slot =
`base_weight[slot] + 0.6 · IG_norm`. Mỗi lượt chỉ hỏi một câu; dừng khi đủ slot cốt lõi, sau 6 câu hỏi,
hoặc khi người dùng yêu cầu kết luận và đã có thời gian + ≥ ½ slot cốt lõi.

## 3. API

`POST /api/v1/consultation` trả về các trường cũ (`reply`, `action`, `grounding_status`, `citations`,
`patient_state`, `disclaimer`) và các trường mới:

| Trường | Ý nghĩa |
|---|---|
| `action` | `ASK_MORE` · `FINALIZE` · `GROUNDED_ANSWER` · `EMERGENCY` · `OUT_OF_SCOPE` |
| `dialogue_state` | Trạng thái đầy đủ (chỉ thông tin người dùng cung cấp) |
| `missing_information` | Nhãn tiếng Việt của slot cốt lõi còn thiếu |
| `next_question` | `slot`, `text`, `strategy`, `reason`, `information_gain`, `candidate_count` |
| `question_source` | `model` (câu hỏi model sinh, đã qua kiểm tra) hoặc `template` (câu của planner) |
| `assessment` | Khi `FINALIZE`: `candidate_conditions[]` (`name`, `supporting_evidence`, `missing_evidence`, `explanation`, `care_level`), `uncertainty`, `next_action`; không có phần trăm |
| `emergency_flags`, `limitations` | Cờ nguy hiểm đã khớp; giới hạn của kết quả |

Lỗi: model chưa sẵn sàng / timeout → `503` (không tạo câu trả lời giả); lỗi kiểu dữ liệu → `422`;
giới hạn kích thước/tốc độ giữ nguyên middleware hiện có (`request_limits.py`).

### Định dạng prompt cho nhánh hỏi thêm

| `MEDDIES_QUESTION_PROMPT_FORMAT` | Định dạng | Đánh đổi |
|---|---|---|
| `json` (mặc định) | 1 message system + 1 message user chứa JSON hội thoại | Ranh giới vai trò mạnh nhất (đã qua review, `SECURITY_REVIEW.md` §4); **khác** định dạng huấn luyện |
| `chat` | Hội thoại nhiều lượt như dữ liệu fine-tune; escape token điều khiển | Khớp định dạng huấn luyện; lượt assistant do trình duyệt gửi vẫn là dữ liệu không tin cậy |

Benchmark nghiên cứu luôn dùng định dạng `chat` giống nhau cho Qwen gốc và Qwen fine-tune.
Biến khác: `MEDDIES_OPTIONAL_QUESTIONS` (mặc định 0) cho phép hỏi thêm slot tùy chọn (tiền sử, thuốc, dị ứng).

## 4. Frontend (`app/`)

`app/page.tsx` hiển thị: khung chat, lý do của câu hỏi bổ sung, thông tin đã thu thập (chỉ từ người dùng),
thông tin còn thiếu, thẻ “Khả năng liên quan — không phải chẩn đoán” với bằng chứng ủng hộ/còn thiếu và mức
chăm sóc, cảnh báo khẩn cấp kèm các dấu hiệu được ghi nhận, và giới hạn của kết quả. Bộ phát hiện cấp cứu
offline trong trình duyệt (`app/consultation.ts`) vẫn chạy trước khi gọi API.

## 5. Huấn luyện và đánh giá

Xem [DATASET.md](DATASET.md), [TRAINING.md](TRAINING.md), [EVALUATION.md](EVALUATION.md),
[EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md). Kết quả kiểm tra hiện trạng ban đầu: [AUDIT.md](AUDIT.md).
