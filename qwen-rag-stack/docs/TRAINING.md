# Huấn luyện Qwen3 LoRA cho hỏi bệnh tiếng Việt

Mục tiêu nghiên cứu: kiểm tra xem fine-tune Qwen3-1.7B trên hội thoại y tế tiếng Việt có cải thiện khả năng
hỏi bệnh và thu thập thông tin so với Qwen3-1.7B gốc hay không.

| Thí nghiệm | Model | Dữ liệu huấn luyện | Cấu hình |
|---|---|---|---|
| E1 | Qwen3-1.7B gốc | — | — |
| E2 | Qwen3-1.7B + LoRA | `vietnamese_dialogue_v1/train.jsonl` (mức *standard*) | `training/configs/medical_dialogue_v1.yaml` |
| E3 | Qwen3-1.7B + LoRA | `vietnamese_dialogue_v1_strict/train.jsonl` (mức *strict*) | `training/configs/medical_dialogue_v1_strict.yaml` |

E2 và E3 dùng **cùng** siêu tham số, cùng validation/test (mức strict); chỉ khác dữ liệu huấn luyện.
Stage 2 (Teacher–Student) **chưa triển khai** — theo kế hoạch chỉ làm sau khi có kết quả Stage 1 đầy đủ.

## 1. Môi trường

Từ `qwen-rag-stack/backend/` (Python 3.11):

```bash
pip install -e ".[dev]"
```

Trên Windows có Application Control chặn `python.exe` của venv, chạy CPython gốc với `PYTHONPATH` trỏ tới
`site-packages` của venv và thư mục `backend` (cách `scripts/python-runtime.mjs` đang làm).

Model được cố định revision trong cache Hugging Face; để chạy hoàn toàn offline sau khi đã tải:

```bash
export HF_HUB_OFFLINE=1        # PowerShell: $env:HF_HUB_OFFLINE = "1"
```

## 2. Chuẩn bị dữ liệu

```bash
python -m training.data.prepare_dialogue
# hoặc đọc parquet đã tải (cùng revision):
python -m training.data.prepare_dialogue --source-parquet <đường dẫn>/data/vietnamese/train.parquet
```

Chi tiết làm sạch, chia tập và thống kê: [DATASET.md](DATASET.md).

## 3. Smoke test (bắt buộc trước khi train thật)

Chạy 3 bước, lưu adapter, giải phóng bộ nhớ, **nạp lại adapter từ đĩa** và sinh thử một câu:

```bash
python -m training.train_stage1 --config training/configs/medical_dialogue_v1_strict.yaml \
    --model-name Qwen/Qwen3-0.6B --smoke-test --max-train-samples 32 --max-eval-samples 8 \
    --output-dir models/smoke_qwen3_0.6b

python -m training.train_stage1 --config training/configs/medical_dialogue_v1_strict.yaml \
    --smoke-test --max-train-samples 32 --max-eval-samples 8 --output-dir models/smoke_qwen3_1.7b
```

## 4. Siêu tham số (E2 = E3)

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| Model | `Qwen/Qwen3-1.7B` (revision `70d244cc…`) | `Qwen3-0.6B` chỉ dùng cho smoke test |
| Độ chính xác | BF16, không lượng tử hóa | |
| LoRA | r = 16, alpha = 32, dropout = 0.05 | q, k, v, o, gate, up, down projection |
| Loss | Cross-entropy chỉ trên token assistant | token system/user bị mask `-100` (`processing.py`) |
| `max_seq_length` | 2048 | hội thoại dài được cắt cửa sổ theo lượt user, system prompt lặp lại mỗi cửa sổ |
| Batch | 1 × grad accumulation 16 = 16 | |
| Optimizer / LR | AdamW, 1e-4, cosine, warmup 3%, weight decay 0.01, clip 1.0 | |
| Packing | **tắt** | packing hiện tại không cô lập attention giữa các hội thoại |
| Gradient checkpointing | bật | cần cho 8 GB |
| Seed | 42 | |

Log mỗi `logging_steps`: train loss, validation loss, learning rate, tokens/s, samples/s, VRAM đỉnh.
Adapter + tokenizer lưu ở `<output.dir>/final_adapter`, metadata (config + metrics) ở
`<output.dir>/run_metadata/run.json`.

## 5. Chạy đầy đủ

```bash
python -m training.train_stage1 --config training/configs/medical_dialogue_v1.yaml          # E2
python -m training.train_stage1 --config training/configs/medical_dialogue_v1_strict.yaml   # E3
```

Ước lượng trên RTX 4060 Laptop 8 GB (đo từ smoke test ~525–590 token/s, ~2.100 token/hội thoại):
E3 ≈ 26,6 nghìn hội thoại ≈ 28 giờ/epoch; E2 ≈ 41 nghìn hội thoại ≈ 43 giờ/epoch. Đây là ước lượng,
**chưa chạy**.

**GPU 24 GB** (chưa kiểm thử trong đợt này) — ghi đè qua CLI, giữ nguyên các tham số khác để so sánh được:

```bash
python -m training.train_stage1 --config training/configs/medical_dialogue_v1_strict.yaml \
    --per-device-train-batch-size 4 --gradient-accumulation-steps 4 --no-gradient-checkpointing \
    --optim adamw_torch_fused
```

Nếu hết bộ nhớ: giảm `--max-seq-length` 2048 → 1536, giữ batch 1 và tăng grad accumulation để giữ batch
hiệu dụng 16. Pipeline không tự chuyển sang lượng tử hóa.

## 6. Pilot có ngân sách giới hạn (đã chạy)

Huấn luyện E2 và E3 trên **cùng số hội thoại** với cùng siêu tham số, rồi chạy benchmark và so sánh:

```bash
python scripts/run_pilot_experiments.py --train-samples 640
```

Kết quả và giới hạn: [EXPERIMENT_RESULTS.md](EXPERIMENT_RESULTS.md).

## 7. Nạp adapter để suy luận

```bash
MEDDIES_BASE_MODEL=Qwen/Qwen3-1.7B MEDDIES_MODEL_PATH=models/pilot_E3/final_adapter npm run backend:win
```

`MEDDIES_MODEL_PATH` rỗng → chạy model gốc (baseline). Adapter thiếu file hoặc khác base model → lỗi rõ ràng,
không âm thầm quay về baseline (`app/inference.py`).
