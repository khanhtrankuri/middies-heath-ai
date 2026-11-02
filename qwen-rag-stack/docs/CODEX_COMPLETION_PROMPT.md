# Codex implementation brief — finish Middies Health AI research application

You are a senior ML research + Python/FastAPI + Next.js engineer. WORK IN CODE, not just in a design document.

## Repository and priority

Repository: https://github.com/khanhtrankuri/middies-heath-ai
Target application: `qwen-rag-stack/`. Begin from the latest `main`, or the PR that adds `docs/RESEARCH_RELEASE_CHECKLIST.md` and `backend/evals/release_gate.py` if merged. Do not overwrite newer human commits. Open a feature branch/PR; do not rewrite Git history or silently merge to main.

Project title: **Ứng dụng AI cho bài toán Y Tế**. Build a Vietnamese multi-turn medical-information and symptom-screening research web app; collect symptoms, ask pertinent follow-up questions, summarize user-reported evidence, suggest a few possible related conditions only with uncertainty and source traceability, and recommend appropriate professional help. No definitive diagnosis, medication dosing or clinical approval claims.

## Critical reality check — ALREADY IMPLEMENTED

Before writing ANY code read:
- `qwen-rag-stack/docs/PLANNER_GUIDED.md`
- `qwen-rag-stack/docs/PLANNER_E5_RESULTS_20261031.md`
- `qwen-rag-stack/docs/EXPERIMENT_RESULTS.md`
- `qwen-rag-stack/backend/app/services/consultation.py`
- `qwen-rag-stack/backend/app/services/dialogue/{state,planner,question_generator,prompts,hypotheses,knowledge}.py`
- `qwen-rag-stack/backend/training/data/prepare_planner_sft.py`
- `qwen-rag-stack/backend/evals/{benchmark_dialogue,closed_loop_dialogue,release_gate}.py`
- `qwen-rag-stack/app/page.tsx`
- `qwen-rag-stack/docs/RESEARCH_RELEASE_CHECKLIST.md`

The repo already implements Qwen3-1.7B LoRA, Meddies data cleaning, deterministic Planner, DST, Qwen rendering of one follow-up question, JSON validator and template fallback, RAG, emergency/scope router, E1–E5 and closed-loop simulator, plus tests. **Do not recreate any of those modules or report them as missing.** Review current code and test behavior first.

Meddies Consultant `vietnamese`, frozen revision `05428709a7572f6f0d4aa5045e6ba255fa85af51`, is synthetic and licensed CC BY-NC 4.0. Honor the frozen split manifest; no target_disease in model inputs; no train/test contamination; label provenance required.

Historical E5C is NOT a winner: published E5C model acceptance **47.3%** vs E5A **87.8%** (131 asking opportunities); off-target and extra-content rejections are common. Existing pilot is ~100 SFT samples, not full training. New work must confront this regression and avoid claims of proven clinical correctness.

## Execution order

### Phase A — establish an executable, truthful baseline

1. Inspect git status/HEAD and current project config.
2. Run from `qwen-rag-stack/backend`: `python -m pytest -q` and `python -m evals.release_gate --evidence ../docs/PLANNER_E5_RESULTS_20261031.json`. The gate should currently return NO_GO (exit 2); that is an EXPECTED policy result, not a broken test.
3. Run from `qwen-rag-stack`: `npm ci`, `npm run typecheck`, `npm run test:unit`, and the platform-appropriate build command. Earlier Vite import had been fixed to `./scripts/vite/sites-vite-plugin`; verify current state instead of blindly changing it.
4. Run backend API smoke with stub and real model (if model/GPU is available), and browser E2E using the selected Qwen frontend. Test one-turn, multi-turn, emergency, out of scope, missing history, model unavailable, RAG unavailable.
5. Record commands, environment versions, exit codes, failures and passing evidence. Fix genuine code defects, not environment artifacts, and rerun.

### Phase B — define the ONE demonstration application

Choose `qwen-rag-stack/app` (Next.js/Vinext) as user-facing research demo and `qwen-rag-stack/backend/app/main.py` as its only medical consultation API. Keep root Gemini app in the repo but clearly mark it as a separate legacy/reference implementation. Do not silently route a Qwen demo request to Gemini/OpenAI. Show visible provider/model/adapter/stub flags.

Confirm that `POST /api/v1/consultation` supports:
- Patient first complaint in Vietnamese.
- Prompted questions with a single target slot.
- DST state with user-reported evidence/provenance and unknown values.
- A safe stop when data is insufficient.
- Final related conditions only when the server deems assessment eligible.
- Emergency bypasses GPU/RAG/model errors.
- Source/citation and unreviewed medical-rule disclaimers.

Do not replace the existing state/planner/hypotheses pipeline; fix gaps with narrow tests.

### Phase C — remedy E5C quality regression, not just its loss

Audit on frozen validation:
- E5C off_target, extra_content, no_question, condition_naming, and JSON schema failures.
- Slot detector false positives/negatives and question validator over-rejection.
- Train vs inference prompt parity, chat template, special tokens, masking, tokenizer and decoding.
- Potential teacher/reference contamination and Meddies role inversions.

Export stratified annotation samples of accepted/rejected questions to a CSV; leave human labels blank. Distinguish `auto_filtered_dataset_question`, `planner_template_unreviewed`, and independently clinician-reviewed labels. Do NOT pretend synthetic outputs are expert answers.

Make the smallest justified improvements, version them (e.g. `planner-sft-v2`, `consult-planner-vi-v3`) and keep E5C pilot immutable. Name the improved candidate **E5D**, train it from Qwen Base if appropriate, and compare E5A/E5B/E5C/E5D with the same frozen test protocol. First run 32-example smoke, then 100/640-sample pilot, then scale only if it helps on validation. Log source hashes, config, seed, compute time, GPU memory, adapter hash, raw acceptance before fallback and template fallback rate. If no GPU, complete CPU-only work and write reproducible GPU commands; never invent training outputs.

### Phase D — serious safety + medical evaluation

Extend multi-turn safety cases, including:
- "Tôi không đau ngực" then "Bây giờ tôi đau ngực dữ dội".
- Contradictory or temporal corrections and statements from family members.
- Denials, questions about conditions, Vietnamese without accents, prompt injection.
- Short patient replies "không", "có", "tôi không biết".
- Safety router available with Qwen GPU unloaded.
- Harmful ungrounded diagnosis and medication doses must not be displayed as facts.

Run paired, closed-loop simulator tests across Planner-only, Planner+Base, Planner+E3 and Planner+E5C/E5D. Do not hallucinate patient answers. Human-annotated clinical scenarios must be separately reviewed with explicit adjudication and provenance. Never label simulated emergency recall as clinical sensitivity.

### Phase E — model promotion policy

Use `backend/evals/release_gate.py` and expand it only with defensible gates: dataset hashes, paired sample counts, question acceptance/fallback, emergency regressions, no hallucinated diagnosis or drug dosing, and no silent provider substitution. Enforce a fail-closed NO_GO when evidence is missing. **A passing research demo gate is not permission to deploy medical advice clinically.**

Keep any pilot E5C/E5D unpromoted until it beats the defined baseline on relevant holdout metrics and a competent human review has been completed. If E5D is worse, recommend E5A/E4 for the demonstration rather than concealing regression.

### Phase F — documentation & delivery

Update only necessary README, ARCHITECTURE.md, DATASET.md, TRAINING.md, EVALUATION.md, EXPERIMENT_RESULTS.md and deployment docs to reflect ACTUAL code/test results. Preserve E1–E5 historical evidence. Add a concise runbook for Windows and Linux that tells a researcher which commands work without GPU vs require GPU; clarify dataset license/privacy, nonmedical queries, emergency safeguards and scope.

Deliver a PR with:
1. Working end-to-end Qwen consultation demo, one frontend, one backend.
2. Reproducible train/eval (E5D if justified) with no leakage.
3. Tests covering failures and regression.
4. Honest comparisons with raw model acceptance *separate from* template-rescued outputs.
5. Clinician review template (not fabricated clinical gold).
6. Audit of remaining medical/quality limitations.
7. Exact changed files, test commands and exit codes, and any prerequisites for later validation.

## Strict exclusions

Do NOT:
- claim model is clinically validated, diagnose, prescribe, or present arbitrary percent likelihood of disease;
- train Qwen on Gemini/OpenAI outputs or LLM-generated grades unless legally authorized;
- treat Meddies synthetic `target_disease` as clinical ground truth;
- merge two framework runtimes by overwriting config files;
- replace missing GPU logs/medical labels with fabricated metrics;
- "fix" a failing gate by loosening it until E5C passes;
- silently substitute provider or mark a stub/demo response as a real Qwen model;
- discard or rewrite the historical E1–E5 evidence.

## Completion checklist

Return a reproducible final report with: architecture overview, demo route, tested scenarios, model/adapter identity, frozen dataset hashes, train/eval command lines, paired comparison tables with denominator and CI, clinical review status, NO_GO/eligible demo result, privacy/security risks, PR URL, and exact tasks blocked by GPU or clinicians.

Begin code changes now. Do not stop at an implementation plan. Prioritize engineering correctness and valid research comparisons over adding peripheral features.
