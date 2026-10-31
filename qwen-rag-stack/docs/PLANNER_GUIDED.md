# Planner-guided Qwen research track — E5

This track uses FastAPI in `backend/`. E1–E3 and their historical pilot artifacts remain intact.
The application is a research prototype, not certified for clinical use. Neither synthetic Meddies
labels nor developer-authored condition tables constitute clinical validation.

## Runtime contract

`POST /api/v1/consultation` runs turn-local emergency detection, scope checking, DST, and the deterministic
Planner before generation. Safety and scope replies bypass Qwen and RAG. Temporal boundaries such as
“bây giờ” prevent an earlier negation from suppressing a new emergency. Educational definition questions
are not recorded as patient symptoms. Previously reported emergencies are conservatively retained.

`consult-planner-vi-v2` is shared by preparation, API inference and E5 benchmarks. The native Qwen chat
template receives a fixed system message, one JSON data message containing the historical conversation,
reported state and Planner decision, and a final assistant JSON target. External role tokens are escaped.
Historical assistant messages stay inside data, so only the final assistant target receives SFT loss.
The old `consult-vi-v1` prompt stays available for E1–E3 reproduction.

The model returns exactly `{"question":"... ?"}`. Invalid JSON, multiple questions/slots, repeated known
information, invented symptoms, diagnosis, doses and internal instructions cause deterministic template
replacement. Responses disclose `question_source`, `model_validation`, `provider` and `model_identity`.
The `next_question.text` is the actual rendered question. Invalid output never changes the selected slot.

Unavailable Qwen returns HTTP 503 by default. `MEDDIES_ALLOW_TEMPLATE_FALLBACK=true` explicitly permits
degraded questions with provider `planner-template`. The offline benchmark propagates inference errors;
it never substitutes a provider. The root Gemini application also returns 503 for failed Qwen requests,
and `MEDDIES_BENCHMARK_MODE=true` rejects non-Qwen benchmark requests.

The Planner stops at core completeness, a sufficient assessment request, six questions, exhausted
unanswered slots, or inability to continue. “Tôi không biết” is never stored as an answer to a clinical slot.
Insufficient information permits a final response without conditions. IG values are heuristic rankings,
not disease probabilities. Patient-facing percentage matches have been removed.

## Frozen data and reproducibility

Source: [Meddies Consultant](https://huggingface.co/datasets/Meddies/meddies-consultant), config `vietnamese`,
revision `05428709a7572f6f0d4aa5045e6ba255fa85af51`, CC BY-NC 4.0. Source material is synthetic and is not
assumed suitable for commercial use. Model: [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B).

Run all Python commands from `backend/` with the existing CUDA environment:

```powershell
python -m training.data.prepare_planner_sft --max-conversations 2000
python -m scripts.prepare_planner_review --output reports/annotation/planner_filter_review.csv
```

Without `--max-conversations`, the preparation command processes the complete frozen splits. Existing
output directories fail rather than overwrite. The implemented pilot deliberately caps each source split
at 2,000 conversations, preserving the original ordering; it is not a representative full-dataset estimate.

Preparation verifies source hashes, manifest membership, revision, and disjoint conversation/group IDs.
It never re-splits. Shared opening patient messages across splits are excluded from derived rows while
the original files remain untouched. Only the source **train** split supplies optimization targets.
Validation targets are independently derived from the original validation split. Test content is read
solely for leakage exclusion and never exported as SFT targets.

For each user-ended prefix, DST and Planner see no future turns. Exactly one independently valid,
on-target question sentence may be extracted from the next synthetic doctor turn. The target has no
reasoning tags, disease metadata or teacher output. Metadata retains conversation ID, source/revision,
cleaning version, split, selected slot, prefix boundary and label provenance. Automatic acceptance is
`auto_filtered_dataset_question`, never `reviewed_dataset_question`.

An explicit preparation flag can export `planner_template_unreviewed` targets for inspection, but default
E5C training rejects these. The actual pilot uses zero template targets. A separate 200-row review export
contains 100 retained and 100 rejected examples with blank reviewer judgments. Human filter precision
and clinician safety review remain pending.

`manifest.json` records counts, rejection reasons, source/output/code hashes, cap and review status.
E5C verifies the prepared hashes, label provenance, split separation and shared prompt before loading
training data. System/user tokens are masked by the existing assistant-only collator.

## LoRA smoke and pilot

```powershell
python -m training.train_stage1 --config training/configs/medical_planner_sft_v1.yaml --smoke-test --max-train-samples 32 --max-eval-samples 8 --output-dir models/E5C_smoke_unique
python -m training.train_stage1 --config training/configs/medical_planner_sft_v1.yaml --max-train-samples 100 --max-eval-samples 32 --eval-steps 2 --save-steps 2 --output-dir models/E5C_pilot_unique
```

E5C starts from Qwen Base; continuing an E3 adapter requires another experiment ID. Defaults are BF16,
SDPA, seven projection modules, r16/alpha32/dropout0.05, 2,048 tokens, batch1/accumulation16, LR1e-4,
one epoch, seed42, no packing. Best checkpoint selection uses validation loss. Smoke mode runs three
updates, saves adapter/tokenizer, releases the training graph, reloads the adapter, and generates using
the shared Planner prompt. Metadata records losses, best checkpoint, tokenized example counts, revision,
data manifest, GPU and peak allocator memory. Overlong individual examples are rejected by tokenization
and logged; maximum sequence length is never silently changed to fit a GPU.

Existing output directories are protected. Checkpoints resume only with an explicit resume argument.
`python -m scripts.run_planner_experiments --prefix UNIQUE --e3-adapter models/pilot_E3/final_adapter`
provides a sequential smoke/train/E5A/E5B/E5C runner; its default training budget is 640 examples.
Add `--e5c-adapter models/E5C_pilot_unique/final_adapter` to evaluate an existing E5C pilot without retraining.

## Evaluation and interpretation

```powershell
python -m evals.benchmark_dialogue --backend guided --experiment E5A --run-name UNIQUE_E5A --conversations 100 --max-turn 3 --batch-size 2 --local-files-only
python -m evals.benchmark_dialogue --backend guided --experiment E5B --adapter models/pilot_E3/final_adapter --run-name UNIQUE_E5B --conversations 100 --max-turn 3 --batch-size 2 --local-files-only
python -m evals.benchmark_dialogue --backend guided --experiment E5C --adapter models/E5C_pilot_unique/final_adapter --run-name UNIQUE_E5C --conversations 100 --max-turn 3 --batch-size 2 --local-files-only
python -m evals.closed_loop_dialogue --output reports/closed_loop_UNIQUE.json
python -m evals.closed_loop_dialogue --backend guided --adapter models/E5C_pilot_unique/final_adapter --output reports/closed_loop_E5C_UNIQUE.json
```

Three-turn teacher-forced evaluation uses the same 295 items from 100 held-out conversations plus
29 behavior cases, greedy decoding and a 160-token generation cap. API/simulator question limits are
six. Teacher forcing measures a next turn on reference history, not full-dialogue effectiveness.
E1–E3 are unconstrained model baselines; E5 includes deterministic routing and validation. Their safety
differences therefore measure the complete pipeline, not isolated model learning.

Model acceptance and template fallback have their own denominators. Successful validated output must
not be interpreted as model-only success. Emergency/stop cases are not question opportunities.
`repeated_information_rate` is scored only when a question slot is recognized, otherwise null; the old
`non_redundant` field stays solely for historical compatibility. Rule-based slot metrics and DST have
known blind spots; raw scores do not establish clinical quality.

Rescoring writes new `*-rescored-dialogue-metrics-v4` directories. Historical predictions and metrics
remain unchanged. Comparison checks exact item IDs, test hash, behavior cases and scoring protocol.
The 107 fixed simulator cases use only predefined answers. Unknown answers stop without fabrication;
their results and developer-authored safety/DST regression scores are separate from expert evaluation.
Expert hypothesis quality/Recall@3 remain null until verified labels exist. Blind annotation tools in
`evals.annotation` support independent scoring and Cohen's kappa; no human scores are pre-filled.

## Knowledge and UI

The frozen pilot dataset records generation code hashes from commit `e691818a` (all 12 recorded
file hashes were checked against that commit). Reproduce that published dataset snapshot with
that commit; current preparation uses the corrected Planner and may retain a different set of rows.
The later Planner v2.1 fix recognizes urinary screening and musculoskeletal trigger questions;
all final E5 runs use this same corrected version. Metric v4 reflects the corresponding question cues.

Document ingestion retains `source_version`, `review_status`, `reviewed_by`, and `reviewed_at`.
Missing status defaults to `unreviewed`. Only source-checked or clinician-reviewed documents with
complete review provenance may ground a response; otherwise the response discloses degraded grounding.
Source checking is distinct from clinical review. Two short attributed MedlinePlus/NHS excerpt cards
were checked against publisher pages and added under `backend/data/knowledge/`; they are not a
clinician-reviewed corpus or expert labels. Rebuild the local index to use them. Their limited coverage
does not support treatment decisions. Static condition hypotheses disclose developer-authored provenance.
Final response checks suppress definite diagnoses and medication doses independently of the model.

The reused UI displays reported facts, missing slots, actual next question, candidate evidence,
uncertainty, emergency warnings, source review status, model/template identity and research limitations.
Windows build uses a tracked, MIT-licensed Sites Vite plugin under `scripts/vite/`, outside the ignored
`build/` directory. Nothing is deployed by this repository task.

## Real-adapter and retrieval smoke checks

Start the frontend with `npm run dev:win` from `qwen-rag-stack/`. From `backend/`, configure
`MEDDIES_MODEL_PROVIDER=transformers`, `MEDDIES_MODEL_PATH=models/E5C_pilot_20261031/final_adapter`,
`MEDDIES_BASE_MODEL=Qwen/Qwen3-1.7B`, `MEDDIES_TEMPERATURE=0`, and `MEDDIES_RAG_ENABLED=false`,
then run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Once `/ready` reports a
loaded model, `npm run smoke:model` from `qwen-rag-stack/` exercises the real adapter, CORS,
new emergencies after negation, scope refusal, unknown answers and unavailable grounding.

For the two source cards, ingest into a fresh index directory; use the same
`SENTENCE_TRANSFORMERS_HOME` cache at ingest and retrieval time. The executed cache was
`<repository>/.uv-cache/sentence-transformers`. First-time ingestion needs network access to
download BGE-M3; subsequent checks can set `MEDDIES_LOCAL_FILES_ONLY=true` and run offline.

```powershell
python -m scripts.ingest_knowledge --input-dir data/knowledge --output-dir data/rag_index/NEW_SOURCE_CHECK --device cpu --batch-size 2
python -m scripts.check_source_retrieval --index data/rag_index/NEW_SOURCE_CHECK --output reports/NEW_RETRIEVAL_SMOKE.json
```

The retrieval check uses real BGE-M3 embeddings, FAISS and score reranking on two source excerpts.
It tests indexing/provenance plumbing; it does not establish clinical retrieval recall.
