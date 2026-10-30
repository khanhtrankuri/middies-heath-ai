# Phase 1 — Kiểm tra hiện trạng repository (audit)

Ngày kiểm tra: 2026-10-30, nhánh gốc `main` @ `b1f509cc`. Môi trường kiểm tra: Windows 11, RTX 4060 Laptop
8 GB (driver 591.66, CUDA 13.1), Python 3.11.15, torch 2.13.0+cu130, transformers 4.57.6, peft 0.20.0,
trl 0.29.1, datasets 4.8.5. Mọi khẳng định “chạy được” bên dưới đều đã được kiểm tra trong môi trường này
trừ khi ghi “chưa kiểm thử”.

## 1. Có thể tái sử dụng (đã kiểm chứng)

| Thành phần | Trạng thái |
|---|---|
| `training/data/processing.py` — masking loss chỉ trên token assistant bằng marker span, chia cửa sổ hội thoại theo lượt user | Tái sử dụng nguyên vẹn; có unit test |
| `training/train_stage1.py`, `trainer.py`, `modeling.py`, `config.py` — LoRA BF16, kiểm tra chỉ LoRA được train, smoke reload adapter, log loss/LR/VRAM/throughput | Tái sử dụng; thêm cấu hình mới, không sửa cấu hình cũ |
| `app/triage.py` — luật cấp cứu có phủ định, mệnh đề, không dấu, người thân, câu hỏi kiến thức | Tái sử dụng làm lớp an toàn độc lập |
| `app/services/consultation.py` + RAG lai (BM25 + dense + rerank, citation) | Tái sử dụng; thêm DST/planner/hypothesis |
| `app/services/prompt_boundary.py` — ranh giới JSON chống chèn vai trò | Giữ làm mặc định |
| Bộ test backend | 216 test; 215 đạt, 1 lỗi môi trường (`wandb` chưa cài trong venv) |

## 2. Còn thiếu so với đề tài

- Không có Dialogue State Tracking đầy đủ: `PatientState` cũ chỉ có chief complaint (chuỗi thô), vị trí/thời gian/mức độ theo vài regex, đủ điều kiện kết thúc chỉ khi có triệu chứng + thời gian.
- Không có cơ chế chọn câu hỏi tiếp theo: prompt yêu cầu model “hỏi 1–2 câu”, chỉ ép hỏi thời gian bằng regex.
- Không có danh sách bệnh liên quan có cấu trúc (bằng chứng ủng hộ/còn thiếu); `/triage` chỉ có gợi ý cố định theo từ khóa.
- Không có guardrail phạm vi y tế cho câu hỏi ngoài lĩnh vực.
- Không có pipeline dữ liệu cho bài toán hỏi bệnh nhiều lượt có test split và kiểm soát rò rỉ; không có benchmark chung so sánh Qwen gốc và fine-tune.

## 3. Vấn đề trong pipeline dữ liệu/huấn luyện cũ

| # | Vấn đề | Ảnh hưởng | Xử lý |
|---|---|---|---|
| D1 | `prepare_meddies.py` chỉ chia train/validation, **không có test**, chia theo hash từng hội thoại | Không có tập đánh giá độc lập | Pipeline mới chia 80/10/10 |
| D2 | Chia ngẫu nhiên theo hội thoại trong khi 58.064 hội thoại chỉ có 1.236 `target_disease` (~47 ca/bệnh, kịch bản rất giống nhau) | Rò rỉ “gần giống” giữa train và test | Chia theo **nhóm bệnh**; test không chứa bệnh nào có trong train |
| D3 | Chỉ loại trùng lặp chính xác | Rò rỉ gần trùng lặp | MinHash/LSH trên lời bệnh nhân, loại trước khi chia |
| D4 | Không cố định revision dataset | Không tái lập | Pin revision `05428709…`, ghi vào metadata từng dòng |
| D5 | Chỉ bỏ thẻ `<think>`; dữ liệu còn `<thinking>` lọt vào lượt user | Huấn luyện trên suy luận ẩn / ghi chú lập kế hoạch | Bỏ `<think>/<thinking>/<reasoning>`; loại ghi chú “Phase/FIFE/OPQRST” ở mức strict |
| D6 | **Đảo vai trò**: lời bác sĩ (markdown, “Cảm ơn bác đã chia sẻ…”, “Tôi là trợ lý AI”) nằm trong lượt `user` ở 16.067/51.320 hội thoại (31%) | Model học ngữ cảnh sai vai | Lọc ở mức strict (E3), đo số lượng |
| D7 | `dataset_mix` mặc định trộn RandomQA (QA một lượt) và tiếng Anh với hội thoại tiếng Việt | Lệch mục tiêu hỏi bệnh | Cấu hình E2/E3 chỉ dùng hội thoại tiếng Việt |
| D8 | Không có metadata nguồn gốc, lý do loại | Không kiểm toán được | Manifest, stats, rejection log (chỉ id + mã lý do) |

## 4. Vấn đề huấn luyện / suy luận

| # | Vấn đề | Xử lý |
|---|---|---|
| T1 | `packing: true` nối nhiều hội thoại vào một chuỗi **không cô lập attention** → mẫu này nhìn thấy lượt của bệnh nhân khác | Tắt packing ở cấu hình hội thoại (giữ nguyên cấu hình cũ) |
| T2 | Lệch định dạng: dữ liệu huấn luyện là hội thoại nhiều lượt không system prompt, còn API gói toàn bộ hội thoại thành JSON trong 1 message user | System prompt dùng chung (`prompts.py`) cho dữ liệu, benchmark, API; định dạng `chat` là tùy chọn có ghi rõ đánh đổi bảo mật |
| T3 | `evaluate_consultation.py` cũ: 10 câu cố định, chỉ in phản hồi, bắt buộc có adapter (không chạy được Qwen gốc), không có chỉ số | Benchmark mới `evals/benchmark_dialogue.py` |
| T4 | Venv `.venv-4060\Scripts\python.exe` bị Windows Application Control chặn | Chạy qua CPython gốc + `PYTHONPATH` (cách `scripts/python-runtime.mjs` đã làm) |

## 5. Khả năng chạy trên GPU

- **8 GB (RTX 4060 Laptop):** Qwen3-1.7B BF16 (~3,4 GB trọng số) + LoRA r16 trên mọi lớp tuyến tính,
  batch 1, gradient checkpointing, `max_seq_length` 2048 — kết quả đo thực tế xem
  [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md). Hàng nghìn hội thoại dài trên 8 GB mất nhiều giờ.
- **24 GB (RTX 4090):** cấu hình `rtx4090_24gb.yaml` cũ hợp lệ về mặt cấu hình; **chưa kiểm thử** trong đợt này
  vì không có GPU 24 GB. Gợi ý ghi đè cho E2/E3 trong [TRAINING.md](TRAINING.md).

## 6. Tương thích phiên bản

`transformers 4.57.6` hỗ trợ kiến trúc Qwen3 và tham số `enable_thinking` trong chat template; đã kiểm tra
render template và sinh văn bản thực tế với Qwen3-0.6B/1.7B. `trl 0.29` dùng `SFTConfig` với
`dataset_kwargs.skip_prepare_dataset`; trainer cũ đã xử lý khác biệt `warmup_ratio`/`warmup_steps` giữa các
phiên bản.
