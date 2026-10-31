# Middies Health AI

Middies Health AI is a research-stage Vietnamese medical information and symptom-support project. The repository contains **two distinct implementations** with different runtimes and model strategies. They are intentionally kept separate to preserve both applications after merging development branches.

> **Medical safety:** This software is not a medical device, diagnostic service, or substitute for a licensed clinician. Do not use generated advice as the sole basis for diagnosis, prescription, medication safety, or emergency decisions. For immediate danger in Vietnam, contact emergency services (115).

## Choose an implementation

| | Gemini API application (repository root) | Local Qwen + RAG application (`qwen-rag-stack/`) |
|---|---|---|
| Frontend | React 19, Vite 6, TypeScript | Next.js/Vinext, React |
| Backend | Express, TypeScript (`server.ts`) | FastAPI, Python |
| Model | Hosted `gemini-3.8-flash` via Google GenAI API | Qwen3 0.6B/1.7B, optional LoRA adapters |
| Features | Symptom chat, document interpretation, drug interaction assistant, editable health profile | Multi-turn consultation, emergency rules, retrieval and citation-oriented generation |
| Retrieval | No knowledge-base retrieval in current root implementation | Hybrid BM25 + dense retrieval, reranking and grounded-answer pipeline |
| Training | **No local fine-tuning** | Separate LoRA/QLoRA training tools; see dedicated documentation |
| Application port | 3000 by default | API 8000; frontend configured separately |

The two implementations are **not yet one integrated product**. Do not run commands or assume dependencies are interchangeable between their directories.

## A. Start the Gemini API application (repository root)

Prerequisites: Node.js, npm and a valid Google Gemini API key. The required model must be accessible to your API account.

```bash
npm install
```

Create a local environment file or inject environment variables:

```env
GEMINI_API_KEY=your_key_here
PORT=3000
```

Run the application:

```bash
npm run dev
```

Open http://localhost:3000.

Main API endpoints:

- `POST /api/health/chat` — symptom-oriented chat and four-level triage (`NORMAL`, `MONITOR`, `SOON`, `EMERGENCY`).
- `POST /api/health/analyze-doc` — multimodal extraction and explanation of medical documents.
- `POST /api/health/interactions` — LLM-based medication interaction discussion.

The current application stores health profile and chat/document history in **browser localStorage**. The profile and submitted content are sent to the backend and then to the configured external Gemini API during inference. It is **not** end-to-end local/offline processing; do not submit real patient data without appropriate consent, privacy controls, and organizational approvals.

Additional implementation details: [Architecture](ARCHITECTURE.md).

## B. Run the Qwen/RAG implementation

See the separate application entry point and full instructions:

- [Qwen/RAG README](qwen-rag-stack/README.md)
- Research track (Vietnamese intelligent history-taking, Qwen base vs LoRA): [architecture](qwen-rag-stack/docs/ARCHITECTURE.md), [dataset](qwen-rag-stack/docs/DATASET.md), [training](qwen-rag-stack/docs/TRAINING.md), [evaluation](qwen-rag-stack/docs/EVALUATION.md), [experiment results](qwen-rag-stack/docs/EXPERIMENT_RESULTS.md)
- [Local setup, training and deployment](qwen-rag-stack/HUONG_DAN_TRAIN_VA_CHAY.md)
- [Security review](qwen-rag-stack/SECURITY_REVIEW.md)

Its `package.json`, configuration, model artifacts and Python backend are **independent** of the Gemini application. Commands documented under `qwen-rag-stack/` should be executed in that directory unless explicitly stated otherwise.

## Evaluation with Meddies Consultant

The new benchmark pipeline is under [`evaluation/`](evaluation/README.md) and targets the **Gemini Express** chat endpoint. It uses subsets of [Meddies/meddies-consultant](https://huggingface.co/datasets/Meddies/meddies-consultant).

```bash
pip install -r evaluation/requirements.txt
python -m unittest discover -s evaluation -p "test_*.py"
python evaluation/meddies_eval.py prepare --consultations 200 --qa 100
python evaluation/meddies_eval.py run --limit 20             # dry-run; no API calls
python evaluation/meddies_eval.py run --limit 20 --execute   # real API calls / potential cost
python evaluation/meddies_eval.py report
```

Dataset records and synthetic answer labels are **not physician-validated clinical ground truth**. The pipeline reports API success, output format compliance and latency automatically. Clinical triage and safety metrics require independent review. Dataset license: **CC BY-NC 4.0**; obtain appropriate rights for commercial uses.

For the Qwen/RAG system, use its own `backend/evals/` tools. Those and the root Gemini benchmark use different request/response interfaces.

## Repository map

```text
.
├── server.ts                  # Express/Gemini API
├── src/                       # Original React health application
├── evaluation/                # Gemini API evaluation using Meddies Consultant
├── qwen-rag-stack/            # Preserved independent Next.js/FastAPI/Qwen/RAG project
├── ARCHITECTURE.md            # Side-by-side technical overview
└── README.md
```

## Quality and security status

- This repository has **no demonstrated clinical validation or regulatory clearance**.
- A well-formed JSON response or plausible medical text is not proof of correctness.
- The root Gemini app currently has no independent, comprehensive medical scope gate, drug interaction database, or certified emergency-triage rule engine.
- Never expose Gemini API keys to browser code, commit secrets, or publish patient-identifying test records.
- Evaluate severe medical errors separately from aggregate answer accuracy.
- Run each implementation's own test and build commands before deploying. Merging source history does not imply both implementations have passed end-to-end tests.

## License and third-party data

No repository-wide license grant is declared here. Do not assume the source repository or third-party clinical documents/datasets may be redistributed commercially. Verify model terms, dataset license obligations, privacy regulations, and medical-software requirements for your intended use.

## Planner-guided Qwen research track

Triển khai mới tiếp tục dùng FastAPI tại `qwen-rag-stack/backend/` và frontend tại `qwen-rag-stack/app/`.
Xem [hướng dẫn E5](qwen-rag-stack/docs/PLANNER_GUIDED.md) và
[báo cáo thực nghiệm 31/10/2026](qwen-rag-stack/docs/PLANNER_E5_RESULTS_20261031.md).
Đây là nguyên mẫu nghiên cứu chưa được chứng nhận sử dụng lâm sàng.
