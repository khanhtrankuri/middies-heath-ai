# Dữ liệu — Meddies Consultant (tiếng Việt)

## 1. Nguồn và giấy phép

| Mục | Giá trị |
|---|---|
| Dataset | [`Meddies/meddies-consultant`](https://huggingface.co/datasets/Meddies/meddies-consultant), config `vietnamese` |
| Revision cố định | `05428709a7572f6f0d4aa5045e6ba255fa85af51` |
| Số hội thoại | 58.064 (một split `train` duy nhất do nhà phát hành cung cấp) |
| Trường | `id`, `subset`, `messages` (role/content), `target_disease`, `turns_count`, `patient_persona` |
| Giấy phép | **CC BY-NC 4.0** — chỉ phi thương mại; mọi mục đích thương mại phải xác minh quyền trước |

Dữ liệu là **synthetic** (bệnh nhân và bác sĩ đều do LLM mô phỏng). Không mặc định: câu trả lời đúng chuyên môn;
`target_disease` là chẩn đoán lâm sàng đã xác minh; câu trả lời của bác sĩ mô phỏng là an toàn. Tên người
trong hội thoại là tên giả do mô phỏng sinh ra; pipeline không ghi nội dung hội thoại vào log hay file từ chối.

`RandomQA` / `english` **không** được trộn vào thí nghiệm hỏi bệnh (E2/E3); có thể dùng trong thí nghiệm riêng
bằng `training/data/prepare_meddies.py` cũ.

## 2. Đặc điểm quan sát được (kiểm tra thực tế)

- 1.236 giá trị `target_disease` khác nhau, mỗi bệnh ~47 hội thoại có kịch bản rất giống nhau.
- Gần như mọi lượt assistant mở đầu bằng khối `<think>…</think>`; 2.547 hội thoại có thẻ suy luận không đóng.
- Hội thoại bắt đầu bằng lời chào của trợ lý; trung vị 11–13 lượt.
- **Đảo vai:** lời của bác sĩ (markdown, “Cảm ơn bác đã chia sẻ…”, “Tôi là Dr. Meddies, trợ lý AI…”) nằm trong
  lượt `user` ở 16.067/51.320 hội thoại (31%) theo bộ phát hiện; lời bệnh nhân nằm trong lượt `assistant` ở 1.111.
- Ghi chú lập kế hoạch lọt ra ngoài (“Phase”, “FIFE”, “OPQRST”), trộn tiếng Anh (“regularly”), câu meta của mô
  phỏng (“Dựa trên persona, tôi sẽ đóng vai…”).
- 2.539 hội thoại có liều thuốc cụ thể trong lời bác sĩ; 830 hội thoại bệnh nhân báo dấu hiệu cấp cứu
  (theo `app/triage.py`) mà bác sĩ không khuyên cấp cứu/khám ngay.

## 3. Pipeline (`training/data/prepare_dialogue.py`, `cleaning_version = dialogue-clean-v1`)

```text
parquet (revision cố định)
  → chuẩn hóa role/content (NFC), bỏ message system gốc
  → bỏ <think>/<thinking>/<reasoning>; còn thẻ lẻ ⇒ loại
  → kiểm tra cấu trúc: không rỗng, không 2 lượt cùng vai liên tiếp, ≥ 2 lượt user và ≥ 2 lượt assistant,
    bỏ lượt user cuối không có phản hồi, lời bệnh nhân phải là tiếng Việt
  → mức STANDARD: loại lời bác sĩ có liều thuốc, khẳng định chẩn đoán chắc chắn, hoặc không leo thang cấp cứu
  → loại trùng lặp chính xác (sha256 hội thoại đã làm sạch)
  → loại gần trùng lặp: MinHash 64 hoán vị, LSH 16 băng, shingle 5 từ trên lời bệnh nhân, ngưỡng Jaccard 0,7
  → mức STRICT (tập con): thêm loại đảo vai, ghi chú lập kế hoạch, trộn tiếng Anh, câu meta mô phỏng,
    lượt đầu không hỏi lại / nêu bệnh sớm, < 2 trong 3 lượt đầu có câu hỏi
  → chia 80/10/10 theo NHÓM BỆNH (target_disease chuẩn hóa), seed 42
  → thêm system prompt dùng chung (consult-vi-v1), ghi JSONL + metadata
```

Mỗi dòng JSONL có `id`, `conversation_id`, `messages` (system + hội thoại) và `metadata`: dataset, revision,
`source_config`, `split`, `cleaning_version`, `quality_level`, `system_prompt_version`, `group_id`, số lượt,
`target_disease`. **`target_disease` chỉ để phân tích, không bao giờ nằm trong `messages`** (có unit test).

## 4. Thống kê (lần chạy cuối, `reports` tái lập bằng lệnh trên)

| | Số hội thoại |
|---|---|
| Đầu vào | 58.064 |
| Giữ ở mức standard | 51.320 |
| Giữ ở mức strict | 33.237 |
| Bị loại ở mức standard | 6.744 |

Lý do loại (mức standard; một hội thoại có thể dính nhiều lý do an toàn, chỉ lý do cấu trúc đầu tiên được ghi):

| Lý do | Số |
|---|---|
| `unclosed_reasoning` | 2.547 |
| `medication_dose` | 2.539 |
| `emergency_not_escalated` | 830 |
| `empty_message` | 324 |
| `consecutive_same_role` | 283 |
| `certain_diagnosis` | 179 |
| `too_few_turns` | 96 |
| `not_vietnamese` | 7 |
| `exact_duplicate` / `near_duplicate` | 0 / 0 |

Lý do bị loại khỏi mức strict (trong số 51.320 hội thoại standard; có thể trùng nhau):
`role_inversion_user` 16.067 · `role_inversion_assistant` 1.111 · `insufficient_history_taking` 948 ·
`leaked_planning_notes` 645 · `no_followup_question` 611 · `code_mixing` 260 · `simulation_artifact` 99 ·
`premature_diagnosis` 20.

Phân chia:

| Mức | Train | Validation | Test |
|---|---|---|---|
| standard (E2 train) | 41.067 | 5.151 | 5.102 |
| strict (E3 train; val/test dùng chung cho E2 và E3) | 26.561 | 3.353 | 3.323 |

## 5. Kiểm soát rò rỉ

| Kiểm tra | Kết quả |
|---|---|
| Nhóm bệnh trùng giữa train–val / train–test / val–test | 0 / 0 / 0 |
| Cặp gần trùng lặp (Jaccard ≥ 0,7) | 0 — kiểm chứng thêm: Jaccard lớn nhất trong cùng nhóm bệnh (40 nhóm ngẫu nhiên) là 0,11 |
| Lượt user đầu tiên giống hệt giữa các tập | 19 / 20 / 3 — đều là câu mở đầu chung chung (Jaccard toàn hội thoại ≤ 0,05) |
| Nhãn bệnh trong input của model | Không (unit test) |
| Test dùng để chọn prompt/siêu tham số | Không (xem lưu ý minh bạch trong EVALUATION.md §2) |

Chia theo nhóm bệnh nghĩa là test đo khả năng hỏi bệnh trên **bệnh chưa gặp khi huấn luyện** — nghiêm ngặt hơn
chia ngẫu nhiên, và không phù hợp để đo “độ chính xác chẩn đoán”.

## 6. Độ chính xác của bộ lọc (kiểm tra thủ công, 1 người — nhóm phát triển)

- `role_inversion_user`: 21/25 mẫu ngẫu nhiên bị gắn cờ là lời bác sĩ thật (precision ≈ 84%); 4 dương tính giả
  là lời bệnh nhân có dùng `**`. Bộ lọc thiên về loại thừa.
- Recall chưa đo; đã thấy ít nhất một mẫu bị bỏ sót (“tôi là **Bác sĩ** Meddies” trong lượt user) — để lại cho
  phiên bản làm sạch sau, không sửa giữa chừng thí nghiệm.

## 7. Tái lập

```bash
cd qwen-rag-stack/backend
python -m training.data.prepare_dialogue           # ~20–25 phút CPU
```

Đầu ra: `data/processed/{vietnamese_dialogue_v1,vietnamese_dialogue_v1_strict}/{train,validation,test}.jsonl`,
`meddies_dialogue_v1_manifest.json` (id theo split + sha256 từng file), `meddies_dialogue_v1_stats.json`,
`meddies_dialogue_v1_rejected.jsonl` (chỉ id + mã lý do). Thư mục `data/processed/` nằm trong `.gitignore`;
không commit dữ liệu.
