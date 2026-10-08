# Hướng dẫn train và chạy Meddies Health AI

Đây là tài liệu vận hành duy nhất của repository. Mọi lệnh bên dưới được chạy từ
thư mục gốc dự án, trừ khi có ghi `cd backend`. Lệnh viết cho PowerShell; trên
Linux/WSL thay `npm.cmd` bằng `npm`, dấu xuống dòng `` ` `` bằng `\`.

## 1. Hệ thống hiện tại

Có hai đường train:

| Đường train | Script | Model | Kỹ thuật | Dùng khi |
| --- | --- | --- | --- | --- |
| Local (chính) | `training.train_stage1` | `Qwen/Qwen3-1.7B`, `Qwen/Qwen3-0.6B` | BF16 LoRA | GPU NVIDIA hỗ trợ BF16 (RTX 30/40, A100...) |
| Kaggle | `training.train_kaggle_t4` | mặc định `Qwen/Qwen3-8B` | QLoRA NF4 + FP16, 2×T4 | Không có GPU phù hợp ở máy |

Ở cả hai đường, base model bị đóng băng và chỉ tham số LoRA được train.

Backend, `evaluate_consultation` và `merge_lora` chỉ hỗ trợ chính thức
`Qwen/Qwen3-1.7B` và `Qwen/Qwen3-0.6B` (xem `SUPPORTED_MODELS` trong
`backend/training/config.py`). Adapter Qwen3-8B mặc định của Kaggle không đánh
giá hay merge được bằng các script này, và cần khoảng 16 GB VRAM ở BF16 khi chạy.
Vì vậy trên Kaggle nên train Qwen3-1.7B (xem mục 9).

Hardware profile cho đường local:

- `backend/training/configs/rtx4090_24gb.yaml`: ưu tiên throughput;
- `backend/training/configs/rtx4060_8gb.yaml`: ưu tiên tiết kiệm VRAM.

Hardware profile chỉ cung cấp giá trị mặc định. Model và tham số training có thể
override qua CLI (mục 10).

## 2. Quy trình train khuyến nghị

Train không tự động làm chatbot tốt hơn. Dữ liệu Meddies là hội thoại hỏi–đáp
thuần, **không có** khối "NGUỒN THAM KHẢO" và trích dẫn `[S1]` như lúc chạy thật,
nên adapter có thể làm giảm tỉ lệ trích dẫn đúng. Vì vậy luôn đo trước và sau:

```text
1. Cài môi trường                       (mục 3–4)
2. Tạo RAG index phát triển              (mục 5)
3. Đo baseline: model gốc, chưa train    (mục 6)  -> reports/quality-baseline.json
4. Chuẩn bị dataset                      (mục 7)
5. Smoke test                            (mục 8)
6. Train đầy đủ                          (mục 9)
7. Đo adapter với cùng bộ eval           (mục 11) -> reports/quality-adapter.json
8. So sánh (mục 11). Chỉ dùng adapter nếu không kém baseline.
```

Bộ lọc cấp cứu chạy bằng luật trước khi gọi model, nên recall cấp cứu không phụ
thuộc adapter. Chỉ số cần so sánh là tỉ lệ trích dẫn hợp lệ, nhóm `trap`/
`out_of_scope` và điểm judge (nếu bật).

Lưu ý giấy phép: dataset `Meddies/meddies-consultant` dùng **CC BY-NC 4.0** (phi
thương mại, dữ liệu tổng hợp). Kiểm tra điều khoản trước khi dùng adapter cho mục
đích thương mại.

## 3. Yêu cầu môi trường

- Python 3.11 hoặc 3.12;
- Node.js từ 22.13;
- NVIDIA GPU có CUDA và hỗ trợ BF16 để train/chạy provider Transformers;
- đủ dung lượng cho model cache, dataset và checkpoints;
- 32 GB RAM được khuyến nghị khi chuẩn bị toàn bộ dataset.

Kiểm tra GPU và BF16:

```powershell
nvidia-smi
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.is_bf16_supported())"
```

Cả hai giá trị phải là `True`. Nếu in `False` ở giá trị đầu, PyTorch đang là bản
CPU; cài lại bản CUDA.

## 4. Cài đặt

### Backend bằng Conda

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

### Backend bằng virtual environment

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

### Frontend

```powershell
npm.cmd ci
```

## 5. Tạo RAG index phát triển

Thư mục `backend/data/knowledge/` hiện chưa có tài liệu. Để chạy và đánh giá,
dùng bộ tham khảo khởi đầu `backend/data/reference_starter/` (6 bản tóm lược
NHS/CDC, chỉ dùng cho phát triển):

```powershell
npm.cmd run local:doctor
npm.cmd run local:prepare
```

`local:prepare` cần mạng ở lần đầu: tải Qwen3, `BAAI/bge-m3`,
`BAAI/bge-reranker-v2-m3` và tạo index tại `backend/data/rag_index`. Thêm
`-- --rebuild` để tạo lại index đã có.

Khi đã có tài liệu đã kiểm duyệt trong `backend/data/knowledge/`, tạo index thật:

```powershell
cd backend
python -m scripts.ingest_knowledge `
  --input-dir data/knowledge `
  --output-dir data/rag_index `
  --device cpu `
  --rebuild
cd ..
```

Không cần train lại model khi thay đổi tài liệu RAG.

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

## 6. Đo baseline trước khi train

Bộ eval chất lượng (210 ca) gửi request tới backend local. Mặc định mỗi IP chỉ
được 20 request tư vấn/phút; với server phát triển, tăng giới hạn **trước khi**
khởi động backend để không phải chờ.

Terminal 1, chạy Qwen3 gốc (không adapter, cấu hình `backend/configs/local-baseline.env`):

```powershell
$env:MEDDIES_RATE_CONSULTATION = "240"
$env:MEDDIES_RATE_GLOBAL = "240"
npm.cmd run backend:local
```

Terminal 2:

```powershell
npm.cmd run eval:quality -- --output reports/quality-baseline.json
```

Kết quả nằm ở `backend/reports/quality-baseline.json`. Lệnh trả mã lỗi nếu không
đạt ngưỡng (recall cấp cứu ≥ 0,98; trích dẫn hợp lệ ≥ 0,90...); với baseline,
ghi lại số liệu là đủ, chưa cần đạt. Chi tiết và judge tùy chọn: xem
[backend/evals/QUALITY.md](backend/evals/QUALITY.md).

## 7. Chuẩn bị Meddies dataset

Dataset nguồn là `Meddies/meddies-consultant` (public trên Hugging Face). Chạy từ
backend:

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

`vietnamese`, `english` và `RandomQA` được dùng cho SFT theo tỉ lệ
`dataset_mix` (mặc định 0,45 / 0,20 / 0,35). `RandomQuestion` không có câu trả
lời nên chỉ được lưu làm prompt cho các bước DPO/GRPO sau này. Validation mặc
định 5% (`--validation-ratio`).

Không truyền `--max-samples` khi chuẩn bị dữ liệu chính thức. Giới hạn sample chỉ
dành cho smoke/debug.

## 8. Smoke test trước khi train

Smoke test thực hiện model load, attach LoRA, forward, backward, optimizer step,
evaluation, save adapter, unload, reload và sinh một câu trả lời tiếng Việt.
Luôn chạy smoke test với đúng profile và model sẽ train.

| GPU | Model | Profile | Train/eval samples |
| --- | --- | --- | --- |
| RTX 4090 24 GB | Qwen3-1.7B | `rtx4090_24gb.yaml` | 32 / 8 |
| RTX 4090 24 GB | Qwen3-0.6B | `rtx4090_24gb.yaml` | 32 / 8 |
| RTX 4060 8 GB | Qwen3-1.7B | `rtx4060_8gb.yaml` | 16 / 4 |
| RTX 4060 8 GB | Qwen3-0.6B | `rtx4060_8gb.yaml` | 16 / 4 |

Ví dụ RTX 4090 + Qwen3-1.7B:

```powershell
cd backend
python -m training.train_stage1 `
  --config training/configs/rtx4090_24gb.yaml `
  --model-name Qwen/Qwen3-1.7B `
  --max-train-samples 32 `
  --max-eval-samples 8 `
  --output-dir models/smoke_4090_1p7b `
  --smoke-test
cd ..
```

Ví dụ RTX 4060 + Qwen3-1.7B:

```powershell
cd backend
python -m training.train_stage1 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-1.7B `
  --max-train-samples 16 `
  --max-eval-samples 4 `
  --output-dir models/smoke_4060_1p7b `
  --smoke-test
cd ..
```

Thay `--model-name Qwen/Qwen3-0.6B` cho model nhỏ hơn. Dùng `--output-dir` riêng
để smoke test không ghi đè vào thư mục train chính `models/stage1_consult`. Nếu
smoke test báo CUDA OOM, xử lý theo mục 12 trước khi train đầy đủ.

## 9. Train toàn bộ dataset

### Local: RTX 4090

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

### Local: RTX 4060 8 GB

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

Mỗi lần train ghi vào cùng `models/stage1_consult`. Để giữ adapter cũ khi train
lại (ví dụ thử model hoặc tham số khác), truyền `--output-dir` mới, chẳng hạn
`--output-dir models/stage1_1p7b_r16`.

Log bao gồm loss, tokens seen, tokens/giây, samples/giây, effective batch size,
peak GPU VRAM và thời gian ước lượng cho toàn epoch.

Theo dõi bằng Weights & Biases (tùy chọn, chạy `wandb login` trước):

```powershell
python -m training.train_stage1 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-1.7B `
  --wandb --wandb-project meddies --wandb-run-name 4060-1p7b
```

Dùng `--wandb-mode offline` nếu không muốn gửi log lên mạng.

### Kaggle: 2×T4

Dùng khi không có GPU hỗ trợ BF16. T4 không hỗ trợ BF16 nên script này dùng
QLoRA NF4 + FP16 và DDP trên 2 GPU.

1. Chuẩn bị dataset ở máy (mục 7), rồi tải thư mục `backend/data/processed` lên
   Kaggle dưới dạng Dataset, ví dụ tên `meddies-processed`.
2. Tạo notebook, chọn accelerator **GPU T4 x2**, bật Internet, clone repo và
   `cd backend`.
3. Cài thư viện (giữ nguyên PyTorch có sẵn của Kaggle):

   ```bash
   %pip install -q "transformers==4.57.6" "trl==0.29.1" "peft==0.20.0" \
     "accelerate>=1.4,<2" "bitsandbytes>=0.45.5,<1" "datasets>=3,<5"
   ```

4. Smoke test rồi train. **Truyền `--model-name Qwen/Qwen3-1.7B`** để adapter
   chạy được với backend hiện tại; mặc định của script là Qwen3-8B.

   ```bash
   !torchrun --standalone --nnodes=1 --nproc-per-node=2 \
     -m training.train_kaggle_t4 \
     --model-name Qwen/Qwen3-1.7B \
     --data-dir /kaggle/input/meddies-processed/processed \
     --output-dir /kaggle/working/stage1_t4_smoke \
     --smoke-test

   !torchrun --standalone --nnodes=1 --nproc-per-node=2 \
     -m training.train_kaggle_t4 \
     --model-name Qwen/Qwen3-1.7B \
     --data-dir /kaggle/input/meddies-processed/processed \
     --output-dir /kaggle/working/stage1_t4 \
     --max-train-samples 0 --max-eval-samples 0
   ```

   Mặc định script chỉ dùng 10.000 mẫu train và 256 mẫu eval; `0` nghĩa là dùng
   toàn bộ. Thư mục output phải trống, trừ khi resume bằng
   `--resume-from-checkpoint`. Khi OOM, thử `--max-seq-length 512 --lora-r 4
   --lora-alpha 8` với thư mục output mới.

5. Tải `/kaggle/working/stage1_t4/final_adapter` về
   `backend/models/stage1_t4/final_adapter` và đặt `MEDDIES_MODEL_PATH` trỏ tới
   thư mục đó (mục 13).

Adapter này được train trên base lượng tử hóa 4-bit nhưng chạy trên base BF16
khi suy luận, nên chất lượng có thể lệch nhẹ. Hãy đánh giá theo mục 11 như mọi
adapter khác.

## 10. Override cấu hình

Thứ tự ưu tiên: mặc định trong code → hardware YAML → CLI. Ví dụ:

```powershell
python -m training.train_stage1 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-0.6B `
  --max-seq-length 768 `
  --lora-r 4 `
  --gradient-accumulation-steps 32
```

Các tham số hay dùng: `--learning-rate`, `--num-train-epochs`,
`--lora-r`/`--lora-alpha`/`--lora-target-modules`, `--max-seq-length`,
`--eval-steps`/`--save-steps`, `--output-dir`. Xem đầy đủ bằng
`python -m training.train_stage1 --help`.

Chọn GPU vật lý:

```powershell
python -m training.train_stage1 `
  --gpu 0 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-0.6B
```

Resume checkpoint (dùng cùng config, model và output dir như lần train bị dừng):

```powershell
python -m training.train_stage1 `
  --config training/configs/rtx4060_8gb.yaml `
  --model-name Qwen/Qwen3-0.6B `
  --resume-from-checkpoint models/stage1_consult/checkpoint-500
```

## 11. Đánh giá adapter

### Kiểm tra nhanh 10 câu mẫu

```powershell
cd backend
python -m training.evaluate_consultation `
  --checkpoint models/stage1_consult/final_adapter `
  --output reports/consultation-eval.json
cd ..
```

Script này chỉ in câu trả lời để người đọc xem, không chấm điểm, và gọi model
**không** qua bộ lọc cấp cứu hay RAG. Base model được đọc từ
`adapter_config.json`.

### So sánh với baseline bằng bộ eval 210 ca

Đặt trong `backend/.env` (mục 13):

```dotenv
MEDDIES_MODEL_PATH=models/stage1_consult/final_adapter
MEDDIES_BASE_MODEL=Qwen/Qwen3-1.7B
```

Terminal 1:

```powershell
$env:MEDDIES_RATE_CONSULTATION = "240"
$env:MEDDIES_RATE_GLOBAL = "240"
npm.cmd run backend:win
```

Terminal 2:

```powershell
npm.cmd run eval:quality -- --output reports/quality-adapter.json
```

So sánh `backend/reports/quality-baseline.json` với
`backend/reports/quality-adapter.json`:

| Trường trong file báo cáo | Ý nghĩa | Adapter nên |
| --- | --- | --- |
| `valid_citation_rate` | tỉ lệ câu trả lời có nguồn gắn trích dẫn hợp lệ | ≥ baseline |
| `groups.trap.passed`, `groups.out_of_scope.passed` | từ chối kê đơn/liều, không bịa khi thiếu nguồn | ≥ baseline |
| `gates.no_certain_diagnosis_or_drug_dose` | không khẳng định chẩn đoán/đưa liều | `true` |
| `emergency_recall` | do bộ lọc luật quyết định | không đổi |
| `judge.*_mean` | điểm 1–5 nếu chạy `--judge` | ≥ baseline |

Nếu adapter kém baseline ở trích dẫn hoặc nhóm `trap`, giữ
`MEDDIES_MODEL_PATH=` rỗng (chạy model gốc) cho tới khi có dữ liệu train đúng
định dạng có nguồn và trích dẫn.

### Merge adapter nếu cần vLLM

Provider Transformers load adapter trực tiếp, không bắt buộc merge. Chỉ merge khi
dùng provider vLLM; merge trên CPU để không chiếm VRAM:

```powershell
cd backend
python -m training.merge_lora `
  --adapter models/stage1_consult/final_adapter `
  --output models/stage1_consult/merged `
  --device cpu
cd ..
```

## 12. Xử lý CUDA OOM trên RTX 4060

Không tự chuyển sang QLoRA ở đường local. Thử lần lượt:

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

Nếu vẫn OOM với Qwen3-1.7B, dùng Qwen3-0.6B hoặc đường Kaggle (mục 9).

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
MEDDIES_CRISIS_LINE=
```

- Adapter phải được train từ đúng `MEDDIES_BASE_MODEL`. Để chạy model gốc chưa
  fine-tune, đặt `MEDDIES_MODEL_PATH=` rỗng.
- `MEDDIES_CRISIS_LINE` là đường dây hỗ trợ tâm lý hiển thị cùng phản hồi khi
  người dùng có ý nghĩ tự tử/tự hại. Xác minh số với đơn vị vận hành trước khi
  điền; để trống thì phản hồi chỉ hướng dẫn gọi 115.
- Các biến `MEDDIES_RATE_*`, `MEDDIES_MAX_*` là giới hạn API; xem
  [SECURITY_REVIEW.md](SECURITY_REVIEW.md).

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

### Model gốc + RAG phát triển (không adapter)

```powershell
npm.cmd run local:doctor
npm.cmd run local:prepare
npm.cmd run backend:local
```

Các giá trị trong `backend/configs/local-baseline.env` ghi đè `backend/.env`,
nên profile này luôn chạy model gốc (adapter rỗng).

### Model + adapter + RAG theo `backend/.env`

Terminal 1:

```powershell
npm.cmd run backend:win
```

Terminal 2:

```powershell
npm.cmd run dev:win
```

Mở địa chỉ Vite in ra, thường là `http://localhost:5173`.

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
`npm.cmd run eval:quality -- --smoke`. Bộ 210 ca, các ngưỡng chấm điểm và
judge tùy chọn được mô tả tại [backend/evals/QUALITY.md](backend/evals/QUALITY.md).
Quy tắc bộ lọc cấp cứu: [backend/evals/TRIAGE_RULES.md](backend/evals/TRIAGE_RULES.md).

## 16. Lỗi thường gặp

### `Adapter base model does not match`

Đặt `MEDDIES_BASE_MODEL` đúng bằng model đã dùng khi train adapter (xem
`base_model_name_or_path` trong `adapter_config.json`).

### `Unsupported pretrained model` hoặc không dùng được adapter Qwen3-8B

Backend, `evaluate_consultation` và `merge_lora` chỉ hỗ trợ Qwen3-1.7B và
Qwen3-0.6B. Train lại trên Kaggle với `--model-name Qwen/Qwen3-1.7B`.

### `Adapter is incomplete`

`MEDDIES_MODEL_PATH` phải trỏ tới thư mục có cả `adapter_config.json` và
`adapter_model.safetensors` (thường là `final_adapter`, không phải
`checkpoint-*`).

### `RAG is not ready`

Kiểm tra `backend/data/rag_index`; chạy lại `npm.cmd run local:prepare -- --rebuild`
hoặc `scripts.ingest_knowledge`.

### Eval chạy rất chậm hoặc nhận HTTP 429

Backend đang dùng giới hạn mặc định 20 request tư vấn/phút. Dừng backend, đặt
`MEDDIES_RATE_CONSULTATION` và `MEDDIES_RATE_GLOBAL` (mục 6), rồi khởi động lại.

### Thiếu weights khi offline

Tắt `MEDDIES_LOCAL_FILES_ONLY` cho lần tải đầu, hoặc chạy `npm.cmd run local:prepare`.

### `The installed PyTorch build is CPU-only`

Cài lại PyTorch bản CUDA phù hợp với driver (xem `nvidia-smi`).

### `adamw_torch_fused` không được hỗ trợ

Profile 4090 tự log warning và fallback sang `adamw_torch`; không có silent crash.

### BF16 không được hỗ trợ

Đường train local yêu cầu BF16 và không tự chuyển sang quantization hay precision
khác. Dùng GPU phù hợp hoặc đường Kaggle (mục 9).

## 17. Ghi chú DPO/GRPO

`training/train_dpo.py` và `training/train_grpo.py` hiện chỉ là boundary module.
Chúng kiểm tra cấu hình và chủ động báo `NotImplementedError`; repository không
giả lập functionality khi chưa có preference data hoặc reward functions.
