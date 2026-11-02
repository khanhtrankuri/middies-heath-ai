# Middies Health AI — research completion and release criteria

**Project scope:** Vietnamese symptom consultation, multi-turn clinical history collection, candidate-condition explanations, medical safety routing. **Not** diagnosis, treatment recommendation, a regulated/approved clinical product, or a medication-management platform.

## State of the project (verified GitHub main at 2026-11-03)

- Canonical research implementation: `qwen-rag-stack/backend` FastAPI + `qwen-rag-stack/app` frontend.
- Qwen3-1.7B + LoRA, Planner, DST, RAG and E1–E5A/B/C pipelines **already exist**. Reuse; do not create redundant modules.
- Freeze the Meddies Consultant Vietnamese source revision `05428709a7572f6f0d4aa5045e6ba255fa85af51` and the existing split manifest.
- Historical pilot E5C trained on approximately 100 samples; reported model-answer acceptance **0.473** vs E5A **0.878**, on 131 asking opportunities. E5C is **not** the recommended default adapter based on these results.
- Reported safety benchmarks are from synthetic/developer-authored cases; there is **no demonstrated independent clinical validation**.
- Historical artifacts: `docs/PLANNER_E5_RESULTS_20261031.md` and `.json`. Preserve them unmodified.
- Qwen main frontend Vite config now imports `./scripts/vite/sites-vite-plugin`; the earlier missing-import issue was corrected in main.
- Source-level checks are not substitutes for actually running builds, GPU inference and clinician review.

## Release gate (new)

From `qwen-rag-stack/backend`:

```bash
python -m pytest tests/test_release_gate.py -q
python -m evals.release_gate --evidence ../docs/PLANNER_E5_RESULTS_20261031.json
```

The gate returns exit code **2** (NO_GO) for a rejected adapter, including the current E5C pilot. Exit code **0** means only **eligible for a supervised research demo**; **never** clinical approval. It compares the candidate against E5A acceptance/fallback and requires full coverage on included automated emergency/injection/out-of-domain fixtures. A gate result is an internal engineering policy rather than a validated medical performance standard.

## Necessary work before claiming a complete research application

1. **Reproduce build and test:** `python -m pytest`, `npm ci`, `npm run typecheck`, `npm run test:unit`, `npm run build:win` and HTTP/browser smoke checks. Store machine, commit and command logs. Do not claim success for unexecuted commands.
2. **Complete clinician-reviewed test sets:** prioritize multi-turn emergency/negation, domain handling, missing-information tracking, and reference-supported candidate conditions. Record reviewers and adjudication. Never use Meddies synthetic target_disease as verified diagnosis.
3. **Calibrate auto-metrics:** manually review examples where E5C fails, notably `off_target` and `extra_content`. Validate the slot extractor before changing model/data to optimize it.
4. **Run paired closed-loop evaluation** for E4/E5A/E5B/E5C on fixed simulated profiles; keep simulation scores separate from human evaluations.
5. **Improve training targets (E5D):** prioritize verified, exactly-one-slot questions, removal of noisy role inversions and target leakage, dynamic selection of reliable labels. Freeze another versioned dataset and prompt. Compare before/after on untouched holdout; do not rewrite E5C evidence.
6. **Single front-end research route:** use FastAPI consultation endpoint and Next.js client as the demonstration path; flag stub vs real model; show the actual planner slot, collected symptom state, explicit uncertainty, and model identity.
7. **Grounded hypotheses:** source-version and clinically review any condition/triage rules and RAG knowledge. Remove percent likelihood claims not supported by validation. Support 'insufficient information' termination.
8. **Operational safety:** no silent provider switching, failures are visible and fail closed; protect patient data and avoid public deployments with real patient data without privacy/security assessment.

## Proposed next research comparison

E5A Planner+Qwen Base vs E5B Planner+LoRA E3 vs E5C pilot vs E5D after manual data improvement. Compare question acceptance, target-slot hit, fallback, missing-slot coverage, repetition, unsafe outputs, emergency misses, real latency/VRAM; use the same frozen evaluation cases. Prefer smaller, reviewed high-quality examples over automatically scaling synthetic data.

## Acceptance and honesty

A software-only delivery may satisfy code/test/build gates but **cannot** be called medically validated. Clinician review, fresh benchmark runs and GPU training may be unavailable on this assistant's runtime. Note those as outstanding tasks instead of filling in fabricated results.

See [CODEX_COMPLETION_PROMPT.md](CODEX_COMPLETION_PROMPT.md) for an executable next-agent brief.
