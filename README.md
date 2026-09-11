# Meddies Health AI

Hướng dẫn từng bước bằng tiếng Việt, có chú thích cho từng lệnh:
[Huấn luyện và chạy project](HUONG_DAN_TRAIN_VA_CHAY.md).

Ứng dụng hỗ trợ thông tin và sàng lọc sức khỏe bằng tiếng Việt, gồm giao diện
React/TypeScript, API FastAPI và luồng Qwen + RAG. Hội thoại được giữ trong bộ nhớ
của trang và mất khi tải lại; không tự lưu vào trình duyệt.

## Chạy nhanh trên Windows

Sau khi cài Node.js và môi trường Python theo phần bên dưới, mở hai terminal ở
thư mục gốc dự án. Nếu chưa có `node_modules`, chạy `npm.cmd ci` trước.

```powershell
# Terminal 1: kiểm tra giao diện và API, không tải mô hình hoặc dùng GPU
npm.cmd run backend:demo

# Terminal 2: mở địa chỉ Local mà lệnh in ra
npm.cmd run dev:win
```

Chế độ demo dùng phản hồi mẫu và được ghi rõ trong hội thoại. Nó cho phép thử mô tả
triệu chứng → câu hỏi bổ sung → phản hồi mẫu, cảnh báo khẩn cấp, lỗi kết nối, gửi lại
và tạo phiên mới. **Demo không đưa ra đánh giá y khoa và không chứng minh chất lượng AI.**

Lệnh backend ưu tiên `MEDDIES_PYTHON`, môi trường Python/Conda đang kích hoạt, rồi
`.venv` hoặc `.venv-4060` trong dự án. Cấu hình `backend/.env` được nạp nếu có;
chế độ demo luôn ghi đè provider thành `stub` và tắt RAG.

Để chạy mô hình thật, sao chép `backend/.env.example` thành `backend/.env`, cấu hình
đường dẫn adapter đã huấn luyện và chỉ mục tài liệu đã kiểm duyệt, rồi chạy
`npm.cmd run backend:win`. Không tự động chuyển sang demo nếu cấu hình thật bị lỗi.
Hướng dẫn huấn luyện và tạo chỉ mục được giữ ở các phần bên dưới.

```powershell
# Kiểm tra TypeScript, lint, logic giao diện, build và HTML từ Worker
npm.cmd run test:win

# Khi backend:demo và dev:win đang chạy ở các terminal khác
npm.cmd run smoke:local

# Trong môi trường Python backend đã kích hoạt
cd backend
python -m pytest
```

API tư vấn chỉ nhận role `user` và `assistant`, phải kết thúc bằng tin nhắn `user`,
tối đa 64 tin nhắn / 32.000 ký tự. Chỉ hệ thống tự đặt system prompt. Giao diện giới
hạn 2.000 ký tự mỗi lần gửi, chờ tối đa 90 giây và cho gửi lại khi thất bại. Tạo phiên
mới hủy chờ ở trình duyệt; tác vụ GPU đã chạy có thể vẫn hoàn tất phía máy chủ.

Nguồn được gắn với từng câu trả lời. Ký hiệu nguồn không có trong kết quả truy xuất
bị loại bỏ; nếu mô hình không dẫn nguồn hợp lệ, câu trả lời được đánh dấu chưa kiểm
chứng. Có trích dẫn không đồng nghĩa nội dung đã được xác nhận đúng về lâm sàng.

## Trạng thái triển khai

Frontend có thể đóng gói cho Sites; backend Python/CUDA cần chạy riêng. Trước khi
đưa ứng dụng lên mạng, cấu hình `NEXT_PUBLIC_MEDDIES_API_URL` trỏ tới API HTTPS thực,
thêm origin của giao diện vào `MEDDIES_CORS_ORIGINS`, và kiểm tra `/ready`. Địa chỉ
`localhost:8000` mặc định chỉ phục vụ phát triển trên máy. Bản sửa này chưa triển
khai lên website đang hoạt động và chưa thực hiện huấn luyện hay thẩm định lâm sàng.

Ảnh chia sẻ `public/og.png` được tạo bằng ImageGen tích hợp, theo yêu cầu: thẻ ngang
MedAI, nền kem và xanh teal, bong bóng hội thoại, dòng “Hiểu triệu chứng, chủ động
chăm sóc.” và “Trợ lý thông tin sức khỏe bằng tiếng Việt”.

Kiểm tra ngày 08/09/2026 trên Windows: 54 kiểm thử Python, 3 kiểm thử logic frontend
và 1 kiểm thử HTML từ Worker đều đạt; TypeScript, lint và build thành công. Smoke
HTTP trên hai dịch vụ đang chạy đã kiểm tra CORS, luồng hỏi bổ sung, kết quả demo,
định tuyến khẩn cấp và từ chối system prompt từ client. Chưa kiểm thử thao tác bằng
trình duyệt hay suy luận với adapter sản xuất trong đợt hoàn thiện này.

## Prerequisites

- Node.js `>=22.13.0`
- Conda (for the Python/FastAPI backend)
- Linux with `flock`, `curl`, and GNU `timeout` for the Sites shell scripts;
  Windows users can use the `:win` commands above.

## Hybrid development (React + Python)

The user interface remains in React/TypeScript. Health-triage and grounded
consultation requests are handled by the FastAPI service under `backend/`.
The backend checks red flags before generation and uses a local, reviewed RAG
index for factual medical answers. It is not a medical diagnosis service.

The Conda environment is defined in `backend/environment.yml` and is named
`meddies-health-ai`. Create it once from an Anaconda Prompt or PowerShell:

```powershell
cd backend
conda env create -f environment.yml
conda activate meddies-health-ai
```

Start the backend in the first terminal:

```powershell
cd backend
conda activate meddies-health-ai
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then start the frontend in a second terminal:

```powershell
npm.cmd run dev:win
```

The frontend uses `http://localhost:8000` by default. To use another backend,
copy `.env.example` to `.env.local` and change `NEXT_PUBLIC_MEDDIES_API_URL`.
The API documentation is available at `http://localhost:8000/docs`.

Run backend tests with:

```powershell
cd backend
conda run -n meddies-health-ai pytest
```

### Preview the Meddies Consultant dataset

The loader defaults to the Vietnamese config and streaming mode, so it does
not download the complete dataset just to inspect a few rows:

```powershell
cd backend
conda activate meddies-health-ai
python scripts/preview_dataset.py --config vietnamese --limit 2
```

Other published configs are `english`, `RandomQA`, and `RandomQuestion`. Add
`--download` only when you intentionally need a materialized local dataset.
The dataset is synthetic and licensed CC BY-NC 4.0; do not treat its QA rows
as cited clinical guidance or assume commercial-use permission.

## Mandatory medical RAG

RAG is part of the production answer path, not an optional demonstration. Qwen3-8B stays on the
single RTX 4090 while the default `BAAI/bge-m3` embedding model runs on CPU. This separation keeps
GPU memory reserved for generation. CUDA embeddings are supported explicitly, but are not the
production default.

The factual corpus must contain reviewed, redistribution-safe external references such as WHO,
CDC, NIH, NICE, a national ministry of health, or internally reviewed guidance with traceable
provenance. The Meddies training set and RandomQA can shape consultation behavior; they are never
treated as a factual source or citation.

```text
reviewed medical documents
  -> text/metadata loaders (TXT, Markdown, JSON, HTML, text PDF)
  -> normalization + document dedupe
  -> heading/page-aware chunks (700 characters, 100 overlap)
  -> BGE-M3 embeddings on CPU
  -> local FAISS index

user request
  -> deterministic emergency/sufficiency router
  -> structured patient state + retrieval queries
  -> FAISS top 8 -> reranker interface -> final 4
  -> context budget -> Qwen3-8B NF4 on one RTX 4090
  -> safety pass + structured citations
```

### Add and index trusted documents

Put source documents under `backend/data/knowledge/<authority>/`. Supported files are UTF-8
`.txt`, `.md`, `.json`, `.html`, and text-based `.pdf`; PDFs are read page by page and OCR is not
performed. Add `<file>.<ext>.metadata.json` sidecars for provenance. The complete schema and an
example are in `backend/data/knowledge/README.md`. Unknown fields remain null—do not guess titles,
publishers, dates, or URLs.

Install the backend, then build the git-ignored index:

```powershell
cd backend
python -m pip install -e ".[dev]"
python scripts/ingest_knowledge.py `
  --input-dir data/knowledge `
  --output-dir data/rag_index `
  --embedding-model BAAI/bge-m3 `
  --device cpu `
  --batch-size 16 `
  --chunk-size 700 `
  --chunk-overlap 100 `
  --rebuild
```

The command reports loaded and duplicate records, unique document count, chunk count, duplicate
chunks, and embedding dimension. The generated directory contains `vectors.faiss`,
`chunks.jsonl`, `metadata.json`, and `manifest.json`. The manifest records embedding model and
dimension, chunk parameters, build time, document/chunk counts, and corpus hash. Exact document
and chunk duplicates are removed before embedding.

Search the built index without starting the API:

```powershell
cd backend
python scripts/search_knowledge.py --query "Migraine là gì?" --top-k 5
```

When a reviewed document changes, rerun ingestion with `--rebuild`. Updating factual knowledge
does not require Qwen training or adapter changes.

### Runtime behavior and API

Copy `backend/.env.example` to a private environment file and keep these production defaults:

```dotenv
MEDDIES_MODEL_PROVIDER=transformers
MEDDIES_BASE_MODEL=Qwen/Qwen3-8B
MEDDIES_MODEL_PATH=models/stage1_consult/final_adapter
MEDDIES_RAG_ENABLED=true
MEDDIES_RAG_INDEX_PATH=data/rag_index
MEDDIES_EMBEDDING_MODEL=BAAI/bge-m3
MEDDIES_EMBEDDING_DEVICE=cpu
MEDDIES_RAG_TOP_K=8
MEDDIES_RAG_FINAL_K=4
MEDDIES_EMERGENCY_COUNTRY=VN
MEDDIES_EMERGENCY_PHONE=115
MEDDIES_LOG_CONTENT=false
```

`POST /api/v1/rag/search` is the retrieval/debug endpoint and returns snippets, metadata, and
scores. `POST /api/v1/consultation` is the user-facing endpoint; it returns citations without raw
similarity scores. The frontend renders them as “Nguồn tham khảo” cards.

The consultation router behaves as follows:

1. Red flags are checked first and produce emergency guidance without waiting for RAG or Qwen.
2. A direct medical-information question retrieves sources immediately.
3. An incomplete symptom description returns `ASK_MORE` without RAG.
4. Once duration and a chief complaint are available, it retrieves sources and returns
   `FINALIZE` with patient summary, possible explanations, when-to-seek-care guidance, citations,
   and a medical disclaimer. It must not state a certain diagnosis.

RAG can be disabled technically for CI or incident recovery with `MEDDIES_RAG_ENABLED=false`. Triage and
question collection continue, but factual generation is marked `degraded`, explicitly warns that
grounding is reduced, and returns no fabricated citations. A missing or incompatible index behaves
the same way. `GET /ready` returns only `api`, `model`, and `rag` booleans and never exposes local
filesystem paths. Content logging is off by default; retrieval logs use query hashes and counts.

Run RAG evaluation and tests with:

```powershell
cd backend
pytest
python evals/evaluate_rag.py --cases evals/rag_cases.yaml
```

The evaluation reports Recall@K, MRR, and source-hit rate. Citation correctness and unsupported
claim rate require generation outputs and human-labeled claims; the evaluator intentionally does
not invent those labels. Retrieval quality is not proof of clinical safety.

The implementation stages are deliberately independent:

```text
Stage A: QLoRA consultation training -> adapter
Stage B: reviewed-document ingestion -> FAISS index
Stage C: safety router + RAG + Qwen runtime -> grounded response
```

The complete project roadmap is:

- Stage 0 — Dataset preparation: Meddies cleaning and deterministic train/validation/test splits.
- Stage 1 — Consultation fine-tuning: Qwen3-8B + Vietnamese/English QLoRA.
- Stage 2 — Consultation runtime: safety, structured patient state, and dynamic next questions.
- Stage 3 — RAG: trusted knowledge + BGE-M3 + FAISS + grounded generation.
- Stage 4 — Research disease candidates: conversation to non-diagnostic Top-K candidate concepts.
- Stage 5 — Optional RandomQA, only if evaluation demonstrates benefit.
- Stage 6 — Complete web application: React + FastAPI + Qwen + safety + RAG.

## Training on RTX 4090 24GB

The production training profile targets exactly one NVIDIA GeForce RTX 4090
with 24GB VRAM. It uses `Qwen/Qwen3-8B` with 4-bit NF4 double quantization,
BF16 compute, QLoRA adapters, gradient checkpointing, and the
`paged_adamw_8bit` optimizer. Full fine-tuning would require far more memory;
the base weights therefore remain frozen and checkpoints contain LoRA adapters
only. PyTorch SDPA works out of the box. FlashAttention2 is used when detected,
but is never required.

Use Linux or WSL2 with a CUDA-capable PyTorch install. Recommended host RAM is
at least 32GB; 64GB is preferable. Base weights remain in the Hugging Face
cache and are not duplicated into every checkpoint.

Prepare deterministic train/validation splits, remove `<think>` content,
validate messages, and deduplicate conversations:

```bash
cd backend
python -m training.data.prepare_meddies \
  --configs vietnamese english \
  --output-dir data/processed \
  --seed 42
```

The Stage-1 mix is Vietnamese-first (65% Vietnamese, 35% English). User and
system tokens receive label `-100`; loss is calculated only on assistant
tokens. Data is preprocessed on CPU and dynamically padded per batch. Optional
packing can be enabled with `--packing`; it preserves labels across conversation
boundaries. Correct masking takes priority over packing.
Benchmark both `--packing` and `--no-packing` smoke runs on the target machine
and compare the recorded tokens/second and peak GPU memory before enabling it
for a full run.

Run the mandatory smoke test before a full run. It loads the 4-bit model,
attaches LoRA, tokenizes data, executes forward/backward and optimizer steps,
evaluates, saves and reloads the adapter, then generates a response:

```bash
CUDA_VISIBLE_DEVICES=0 python -m training.train_stage1 \
  --config training/configs/stage1_qwen3_8b_4090.yaml \
  --max-train-samples 100 \
  --max-eval-samples 30 \
  --smoke-test
```

After it succeeds, run full Stage 1:

```bash
CUDA_VISIBLE_DEVICES=0 python -m training.train_stage1 \
  --config training/configs/stage1_qwen3_8b_4090.yaml
```

The safe default is sequence length 4096, device batch size 1, and 16 gradient
accumulation steps (effective batch size 16). Do not assume batch size 2 fits.
The separate `stage1_qwen3_8b_4090_8k_experimental.yaml` profile is slower and
may require LoRA rank 16; it is not the production default. YAML values can be
overridden explicitly on the CLI, for example `--max-seq-length 3072`,
`--lora-r 16`, or `--gradient-accumulation-steps 32`.

Training logs the GPU name, total/allocated/reserved VRAM, quantization mode,
parameter counts, losses, learning rate, speed, remaining steps, elapsed time,
and peak allocated VRAM. Inspect live usage separately with `nvidia-smi`. If a
CUDA OOM occurs, the process reports it and does not silently alter parameters.
Apply fallbacks in this order:

1. Use device batch size 1.
2. Keep gradient checkpointing enabled.
3. Reduce sequence length from 4096 to 3072, then 2048.
4. Reduce LoRA rank from 32 to 16.
5. Increase gradient accumulation to retain the effective batch size.

If `paged_adamw_8bit` is incompatible with the installed bitsandbytes build,
retry explicitly with `--optim adamw_torch`.

Checkpoints are written every 250 steps, with the latest three retained.
Resume without distributed launchers:

```bash
CUDA_VISIBLE_DEVICES=0 python -m training.train_stage1 \
  --config training/configs/stage1_qwen3_8b_4090.yaml \
  --resume-from-checkpoint models/stage1_consult/checkpoint-1000
```

`accelerate` is optional environment management and remains single-process:

```bash
CUDA_VISIBLE_DEVICES=0 accelerate launch --num_processes 1 \
  -m training.train_stage1 \
  --config training/configs/stage1_qwen3_8b_4090.yaml
```

Evaluate the saved adapter:

```bash
CUDA_VISIBLE_DEVICES=0 python -m training.evaluate_consultation \
  --checkpoint models/stage1_consult/final_adapter
```

Stage 2 is optional and uses 60% RandomQA, 30% Vietnamese consultation replay,
and 10% English consultation replay. The default `continue` strategy resumes
training the Stage-1 adapter; it minimizes storage and compute, but the final
adapter state represents both stages. The `fresh-after-merge` strategy gives
Stage 2 a separate adapter and cleaner separation, but first requires a merged
Stage-1 base and considerably more storage. Prepare `RandomQA` alongside the
consultation configs before running it:

```bash
python -m training.data.prepare_meddies \
  --configs vietnamese english RandomQA \
  --output-dir data/processed --seed 42

CUDA_VISIBLE_DEVICES=0 python -m training.train_stage2 \
  --config training/configs/stage2_qwen3_8b_4090.yaml \
  --stage1-adapter models/stage1_consult/final_adapter
```

Merging is not needed for ordinary inference. When a merged model is needed,
use CPU merging because a complete BF16 8B merge must not be assumed to fit in
24GB VRAM; ensure adequate system RAM and disk space:

```bash
python -m training.merge_lora \
  --base-model Qwen/Qwen3-8B \
  --adapter models/stage1_consult/final_adapter \
  --output models/stage1_consult/merged \
  --device cpu
```

### RTX 4090 inference

The default FastAPI provider loads Qwen3-8B in NF4 4-bit plus the PEFT adapter
once during application startup and keeps it GPU-resident. A semaphore limits
generation concurrency to one by default. Conservative sampling uses 384 new
tokens, temperature 0.3, top-p 0.9, and repetition penalty 1.05; set temperature
to `0` for deterministic structured extraction. Configure values in
`backend/.env.example`, then serve with:

```bash
cd backend
CUDA_VISIBLE_DEVICES=0 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`MEDDIES_MODEL_PROVIDER=transformers` is the production default,
`MEDDIES_MODEL_PROVIDER=stub` is for CI, and vLLM is optional. Shorter unprefixed
model variable names remain accepted as compatibility aliases. Neither normal
training nor serving requires `torchrun`, DDP, FSDP, DeepSpeed, tensor
parallelism, multiple GPUs, or merged BF16 weights.

The model-training path is:

```text
Meddies dataset
  -> CPU cleaning (<think> removal, message validation, deduplication,
     deterministic splitting, language weighting)
  -> chat tokenization with assistant-only labels
  -> Qwen3-8B NF4 4-bit + QLoRA on one RTX 4090
  -> Stage-1 adapter
     -> evaluation
     -> FastAPI Transformers inference with mandatory reviewed-document RAG
     -> optional mixed-replay Stage 2
```

A separate, non-production RTX 4060 Laptop 8GB diagnostic was also executed to
debug the full code path at sequence length 256 and LoRA rank 4. It does not
replace or relax the RTX 4090 production defaults. See
[`backend/training/RTX4060_8GB_SMOKE.md`](backend/training/RTX4060_8GB_SMOKE.md)
for the measured training result, WDDM memory caveat, and reproduction commands.
The follow-up real RAG + Qwen diagnostic also passed on that GPU with structured
citations and a 5.95 GiB peak Torch allocation; it uses deterministic CPU
embeddings only to validate wiring, not to replace production BGE-M3.

## Sites Lifecycle

The Sites lifecycle CLI runs the locked dependency install before returning this checkout. Edit the source under `app/`, then checkpoint when a coherent milestone is ready to inspect or share. The remote Sites builder runs `npm run build` against the pushed commit. Do not repeat install or build as a normal pre-checkpoint step.

This starter does not use `wrangler.jsonc`.

`install:ci` is intentionally a single, non-retrying `npm ci`. It refuses a concurrent install for the same project, consumes a matching image-seeded npm cache with `--prefer-offline` while retaining registry fallback for a missing cache object, otherwise downloads and verifies the complete vinext tarball recorded in `package-lock.json`, limits npm to one socket, and terminates a stalled install. `build` applies a short timeout and then validates the Sites artifact. These helpers target Linux and use GNU `timeout`; they are not native macOS scripts.

Scripts that need writable project-scoped home, npm, XDG, and temporary paths use `scripts/sites-env.sh`. The `dev` and `start` scripts honor the caller's runtime environment and keep Wrangler logs inside the checkout. The generated `.sites-runtime/` directory is disposable and ignored by Git.

## Included Shape

- edit site code under `app/`
- `app/chatgpt-auth.ts` provides optional dispatch-owned ChatGPT sign-in helpers
- `.openai/hosting.json` declares optional Sites D1 and R2 bindings
- `vite.config.ts` simulates declared bindings for local development
- `db/index.ts` reads the D1 binding from the Cloudflare Worker environment
- `db/schema.ts` starts intentionally empty
- `examples/d1/` contains an optional D1 example surface
- `drizzle.config.ts` supports local migration generation when needed

## Workspace Auth Headers

OpenAI workspace sites can read the current user's email from
`oai-authenticated-user-email`.

SIWC-authenticated workspace sites may also receive
`oai-authenticated-user-full-name` when the user's SIWC profile has a non-empty
`name` claim. The full-name value is percent-encoded UTF-8 and is accompanied by
`oai-authenticated-user-full-name-encoding: percent-encoded-utf-8`.

Treat the full name as optional and fall back to email when it is absent:

```tsx
import { headers } from "next/headers";

export default async function Home() {
  const requestHeaders = await headers();
  const email = requestHeaders.get("oai-authenticated-user-email");
  const encodedFullName = requestHeaders.get("oai-authenticated-user-full-name");
  const fullName =
    encodedFullName &&
    requestHeaders.get("oai-authenticated-user-full-name-encoding") ===
      "percent-encoded-utf-8"
      ? decodeURIComponent(encodedFullName)
      : null;

  const displayName = fullName ?? email;
  // ...
}
```

## Optional Dispatch-Owned ChatGPT Sign-In

Import the ready-to-use helpers from `app/chatgpt-auth.ts` when the site needs
optional or required ChatGPT sign-in:

- Use `getChatGPTUser()` for optional signed-in UI.
- Use `requireChatGPTUser(returnTo)` for server-rendered pages that should send
  anonymous visitors through Sign in with ChatGPT.
- Use `chatGPTSignInPath(returnTo)` and `chatGPTSignOutPath(returnTo)` for
  browser links or actions.
- Pass a same-origin relative `returnTo` path for the destination after sign-in
  or sign-out. The helper validates and safely encodes it.
- Mark protected pages with `export const dynamic = "force-dynamic"` because
  they depend on per-request identity headers.

Dispatch owns `/signin-with-chatgpt`, `/signout-with-chatgpt`, `/callback`, the
OAuth cookies, and identity header injection. Do not implement app routes for
those reserved paths. Routes that do not import and call the helper remain
anonymous-compatible.

SIWC establishes identity only; it does not prove workspace membership. Use the
Sites hosting platform's access policy controls for workspace-wide restrictions,
or enforce explicit server-side membership or allowlist checks.

Use SIWC for account pages, user-specific dashboards, saved records, and write
actions tied to the current ChatGPT user. Leave public content anonymous.

## Diagnostic Commands

- `npm run install:ci`: perform the one bounded lockfile install
- `npm run dev`: start the Vite/Vinext development server
- `npm run build`: build and validate the deployable Sites artifact
- `npm run start`: start the built Vinext application
- `npm test`: build, validate, and verify the rendered development-preview metadata
- `npm run validate:artifact`: recheck an existing artifact's manifest and ESM `default.fetch` export
- `npm run db:generate`: generate Drizzle migrations after schema changes

Use build and validation commands for targeted diagnosis after a remote failure, not as part of the normal checkpoint path.

The timeout defaults can be overridden for a controlled canary with `SITES_INSTALL_TIMEOUT`, `SITES_INSTALL_KILL_AFTER`, `SITES_BUILD_TIMEOUT`, and `SITES_BUILD_KILL_AFTER`. A timeout fails the command; the helpers never retry an unchanged install or build.

## Learn More

- [vinext Documentation](https://github.com/cloudflare/vinext)
- [Drizzle D1 Guide](https://orm.drizzle.team/docs/get-started/d1-new)
