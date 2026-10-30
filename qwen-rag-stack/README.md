# Middies Health AI — Qwen/RAG implementation

> Đây là **ứng dụng độc lập** được bảo toàn từ các nhánh `feat/initial-project` và `claude/youthful-meitner-0kodvk` sau khi merge vào `main`. Ứng dụng Gemini API nằm tại [thư mục gốc](../README.md). Hai ứng dụng **không dùng chung backend, dependencies hoặc model**.

## Mục đích và giới hạn

Ứng dụng nghiên cứu hỗ trợ tư vấn sức khỏe ban đầu bằng tiếng Việt với mô hình Qwen chạy local, bộ phát hiện dấu hiệu nguy hiểm, hỏi thêm thông tin, truy xuất tài liệu và dẫn nguồn. Không dùng để tự chẩn đoán, thay bác sĩ, kê thuốc hay quyết định xử trí cấp cứu.

## Kiến trúc

```text
Web (Next.js / React / Vinext)
    │
    ▼
FastAPI  (backend/app/main.py)
    │
    ├── Red-flag safety rules / scope handling
    ├── Multi-turn consultation and missing-data questions
    ├── Query construction
    ├── Hybrid RAG: BM25 + BGE-M3 dense
    ├── RRF fusion + reranking
    └── Qwen3 inference + optional LoRA adapter
                   └── Grounded answer and citations
```

**Supported local model candidates** in training/evaluation scripts: `Qwen/Qwen3-1.7B` and `Qwen/Qwen3-0.6B`. Separate Kaggle training path includes a Qwen3-8B option, but not all inference/evaluation scripts support that adapter. See [Training and operations](HUONG_DAN_TRAIN_VA_CHAY.md) rather than treating all model variants as drop-in replacements.

Retrieval requires a **built knowledge index** with documents vetted for provenance and permission to use. The six starter references are test fixtures, not clinically reviewed production knowledge.

## Quick start: demo backend without GPU (Windows PowerShell)

From the **`qwen-rag-stack/` directory**:

```powershell
npm.cmd ci
npm.cmd run backend:demo
```

In another terminal at the same directory:

```powershell
npm.cmd run dev:win
```

For Linux, WSL, or production-like environments, use the exact platform-specific commands in [Training and operations](HUONG_DAN_TRAIN_VA_CHAY.md). The demo/stub backend does not prove that a real Qwen checkpoint or RAG index is ready.

## Training, evaluation and testing

- [Full training/deployment guide](HUONG_DAN_TRAIN_VA_CHAY.md)
- [Evaluation definitions](backend/evals/QUALITY.md)
- [Triage regression rules](backend/evals/TRIAGE_RULES.md)
- [Medical knowledge corpus conventions](backend/data/knowledge/README.md)
- [Starter retrieval fixture](backend/data/reference_starter/README.md)
- [Historical security review](SECURITY_REVIEW.md)

Typical checks, from `qwen-rag-stack/`:

```powershell
npm.cmd run backend:test
npm.cmd run typecheck
npm.cmd run test:unit
npm.cmd run lint:win
```

These are **commands**, not claims that tests passed in the merged state. Run them on the target machine before deployment.

## Data, model selection and medical assurance

Meddies conversation data can help develop language behavior, but synthetic `target_disease` and synthetic answers are not validated clinical labels. Do not report clinical accuracy from those labels alone. Any training, inference or citation-quality improvement must be verified on an independent, clinician-reviewed holdout, with priority for emergency miss rate, unsafe advice and unsupported claims.

This application sends data to locally configured backend/model services; check configuration, logs, remote artifact downloads and deployment before claiming that information never leaves a device.

## Relationship to the Gemini application

The root project uses **React/Vite + Express + hosted Gemini**, with four user-facing functions. This app uses **Next.js/Vinext + FastAPI + Qwen/RAG** and focuses on consultation. The Gemini evaluation script under root `evaluation/` is not automatically compatible with this FastAPI response schema.

See [Repository architecture](../ARCHITECTURE.md) for the side-by-side comparison.
