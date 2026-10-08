# Hướng dẫn train và chạy Meddies Health AI

Đây là tài liệu vận hành duy nhất của repository. Mọi lệnh bên dưới được chạy từ
thư mục gốc dự án, trừ khi có ghi `cd backend`.

## 1. Hệ thống hiện tại

Training production dùng BF16 LoRA, không dùng QLoRA/NF4. Base model luôn bị
đóng băng và chỉ tham số có tên `lora_` được train.

Model hỗ trợ:

- `Qwen/Qwen3-1.7B`
- `Qwen/Qwen3-0.6B`

Hardware profile:

- `backend/training/configs/rtx4090_24gb.yaml`: ưu tiên throughput;
- `backend/training/configs/rtx4060_8gb.yaml`: ưu tiên tiết kiệm VRAM.

Hardware profile chỉ cung cấp giá trị mặc định. Model và các tham số training có
thể override qua CLI.

## 2. Yêu cầu môi trường

- Python 3.11 hoặc 3.12;
- Node.js từ 22.13;
- NVIDIA GPU có CUDA và hỗ trợ BF16 để train/chạy provider Transformers;
- đủ dung lượng cho model cache, dataset và checkpoints;
- 32 GB RAM được khuyến nghị khi chuẩn bị toàn bộ dataset.

Kiểm tra GPU:

```powershell
nvidia-smi
```

## 3. Cài backend

### Conda

```powershell
cd backend
conda env create -f environment.yml
conda activate meddies-health-ai
cd ..
```

Nếu environment đã tồn tại:

```powershell
cd backend
conda env update -f environment.yml --prune
cd ..
```

### Virtual environment thay cho Conda

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".\backend[dev]"
```

Trên Linux/WSL:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e './backend[dev]'
```

## 4. Cài frontend

```powershell
npm.cmd ci
```

Trên Linux/WSL dùng `npm ci`.

## 5. Chuẩn bị toàn bộ Meddies dataset

Dataset nguồn là `Meddies/meddies-consultant`. Chạy từ backend:

```powershell
cd backend
python -m training.data.prepare_meddies `
  --configs vietnamese english RandomQA RandomQuestion `
  --output-dir data/processed `
  --seed 42
cd ..
```

Kết quả:

```text
backend/data/processed/
  metadata.json
  vietnamese/{train,validation}.jsonl
  english/{train,validation}.jsonl
  RandomQA/{train,validation}.jsonl
  RandomQuestion/{prompts_train,prompts_validation}.jsonl
```

`vietnamese`, `english` và `RandomQA` được dùng cho SFT. `RandomQuestion` không
có assistant answer nên chỉ được lưu làm prompt cho RAG hoặc các bước DPO/GRPO
sau này.

Không truyền `--max-samples` khi chuẩn bị hoặc train chính thức. Giới hạn sample
chỉ dành cho smoke/debug.

## 6. Smoke test trước khi train

Smoke test thực hiện model load, attach LoRA, forward, backward, optimizer step,
evaluation, save adapter, unload, reload và sinh một câu trả lời tiếng Việt.

### RTX 4090 24 GB + Qwen3-1.7B

```powershell
cd backend
python -m training.train_stage1 `
  --config training/configs/rtx4090_24gb.yaml `
  --model-name Qwen/Qwen3-1.7B `
  --max-train-samples 32 `
  --max-eval-samples 8 `
  --smoke-test
cd ..
```

### RTX 4090 24 GB + Qwen3-0.6B

```powershell
cd backend
python -m training.train_stage1 `
  --config training/configs/rtx4090_24gb.yaml `
  --model-name Qwen/Qwen3-0.6B `
  --max-train-samples 32 `
  --max-eval-samples 8 `
  --smoke-test
cd ..
```

### RTX 4060 8 GB + Qwen3-1.7B

```powershell
cd backend
python -m training.train_stage1 `
  --config training/configs/rtx4090_24gb.yaml `
  --model-name Qwen/Qwen3-0.6B `
  --max-train-samples 32 `
  --max-eval-samples 8 `
  --smoke-test
cd ..
```

### RTX 4060 8 GB + Qwen3-0.6B

```powershell
cd backend
python -m training.train_stage1 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-0.6B `
  --max-train-samples 16 `
  --max-eval-samples 4 `
  --smoke-test
cd ..
```

## 7. Train toàn bộ dataset

### RTX 4090

```powershell
cd backend

# Qwen3-1.7B
python -m training.train_stage1 `
  --config training/configs/rtx4090_24gb.yaml `
  --model-name Qwen/Qwen3-1.7B

# Qwen3-0.6B
python -m training.train_stage1 `
  --config training/configs/rtx4090_24gb.yaml `
  --model-name Qwen/Qwen3-0.6B
```

### RTX 4060 8 GB

```powershell
cd backend

# Qwen3-1.7B
python -m training.train_stage1 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-1.7B

# Qwen3-0.6B
python -m training.train_stage1 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-0.6B
```

Output mặc định:

```text
backend/models/stage1_consult/
  checkpoint-*/
  final_adapter/
  run_metadata/run.json
```

Log bao gồm loss, tokens seen, tokens/giây, samples/giây, effective batch size,
peak GPU VRAM và thời gian ước lượng cho toàn epoch.

## 8. Override cấu hình

CLI có độ ưu tiên cao nhất:

```powershell
python -m training.train_stage1 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-0.6B `
  --max-seq-length 768 `
  --lora-r 4 `
  --gradient-accumulation-steps 32
```

Chọn GPU vật lý:

```powershell
python -m training.train_stage1 `
  --gpu 0 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-0.6B
```

Resume checkpoint:

```powershell
python -m training.train_stage1 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-0.6B `
  --resume-from-checkpoint models/stage1_consult/checkpoint-500
```

## 9. Xử lý CUDA OOM trên RTX 4060

Không tự chuyển sang QLoRA. Thử lần lượt:

1. giảm `max_seq_length` từ 1024 xuống 768;
2. giảm tiếp từ 768 xuống 512;
3. giảm LoRA rank từ 8 xuống 4;
4. giữ `per_device_train_batch_size=1`;
5. tăng gradient accumulation nếu cần giữ effective batch.

Ví dụ:

```powershell
python -m training.train_stage1 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-1.7B `
  --max-seq-length 768 `
  --lora-r 4
```

## 10. Đánh giá adapter

```powershell
cd backend
python -m training.evaluate_consultation `
  --checkpoint models/stage1_consult/final_adapter `
  --output reports/consultation-eval.json
cd ..
```

Base model được đọc từ `adapter_config.json`; chỉ cần truyền `--model-name` khi
muốn kiểm tra rõ model kỳ vọng.

## 11. Merge adapter nếu cần vLLM

Merge trên CPU để không chiếm VRAM:

```powershell
cd backend
python -m training.merge_lora `
  --adapter models/stage1_consult/final_adapter `
  --output models/stage1_consult/merged `
  --device cpu
cd ..
```

Transformers provider có thể load adapter trực tiếp; không bắt buộc merge.

## 12. Chuẩn bị RAG

Đặt tài liệu đã kiểm duyệt vào:

```text
backend/data/knowledge/
```

Tạo index:

```powershell
cd backend
python -m scripts.ingest_knowledge `
  --input-dir data/knowledge `
  --output-dir data/rag_index `
  --device cpu `
  --rebuild
cd ..
```

Runtime retrieval:

```text
query builder
  -> BM25 top 30 + BGE-M3 top 30
  -> RRF top 20
  -> BAAI/bge-reranker-v2-m3
  -> final top 4
  -> context budgeting
  -> Qwen3
```

Trên RTX 4060, embedding và reranker nên giữ ở CPU.

## 13. Cấu hình backend

Tạo file môi trường:

```powershell
Copy-Item backend/.env.example backend/.env
```

Các giá trị quan trọng:

```dotenv
MEDDIES_MODEL_PROVIDER=transformers
MEDDIES_BASE_MODEL=Qwen/Qwen3-1.7B
MEDDIES_MODEL_DTYPE=bfloat16
MEDDIES_MODEL_PATH=models/stage1_consult/final_adapter
MEDDIES_RAG_ENABLED=true
MEDDIES_RAG_INDEX_PATH=data/rag_index
MEDDIES_EMBEDDING_DEVICE=cpu
MEDDIES_RERANKER_DEVICE=cpu
```

Adapter phải được train từ đúng `MEDDIES_BASE_MODEL`. Để chạy baseline chưa
fine-tune, đặt `MEDDIES_MODEL_PATH=` rỗng.

## 14. Chạy hệ thống

### Demo không cần GPU

Terminal 1:

```powershell
npm.cmd run backend:demo
```

Terminal 2:

```powershell
npm.cmd run dev:win
```

### Model thật + adapter + RAG

Terminal 1:

```powershell
npm.cmd run backend:win
```

Terminal 2:

```powershell
npm.cmd run dev:win
```

Mở địa chỉ Vite in ra, thường là `http://localhost:5173`.

### Baseline local không adapter

```powershell
npm.cmd run local:doctor
npm.cmd run local:prepare
npm.cmd run backend:local
```

`local:prepare` cần mạng ở lần đầu để tải model và tạo development RAG index.

## 15. Kiểm tra project

Backend:

```powershell
npm.cmd run backend:test
```

Frontend và build:

```powershell
npm.cmd run typecheck
npm.cmd run lint:win
npm.cmd run test:unit
npm.cmd run build:win
npm.cmd run validate:artifact:win
node --test tests/rendered-html.test.mjs
```

Đánh giá hệ thống:

```powershell
npm.cmd run eval:safety
npm.cmd run eval:system
npm.cmd run eval:rag
npm.cmd run eval:quality
```

Để kiểm tra nhanh pipeline với backend `stub`, chạy
`npm.cmd run eval:quality -- --smoke`. Bộ 200 ca, các ngưỡng chấm điểm và
judge tùy chọn được mô tả tại [backend/evals/QUALITY.md](backend/evals/QUALITY.md).

## 16. Lỗi thường gặp

### `Adapter base model does not match`

Đặt `MEDDIES_BASE_MODEL` đúng bằng model đã dùng khi train adapter.

### `RAG is not ready`

Kiểm tra `backend/data/rag_index` và chạy lại `scripts.ingest_knowledge`.

### Thiếu weights khi offline

Tắt `MEDDIES_LOCAL_FILES_ONLY` cho lần tải đầu, hoặc chạy `npm.cmd run local:prepare`.

### `adamw_torch_fused` không được hỗ trợ

Profile 4090 tự log warning và fallback sang `adamw_torch`; không có silent crash.

### BF16 không được hỗ trợ

Training production yêu cầu BF16. Dùng GPU phù hợp; pipeline không tự chuyển
sang quantization hoặc một precision khác.

## 17. Ghi chú DPO/GRPO

`training/train_dpo.py` và `training/train_grpo.py` hiện chỉ là boundary module.
Chúng kiểm tra cấu hình và chủ động báo `NotImplementedError`; repository không
giả lập functionality khi chưa có preference data hoặc reward functions.
