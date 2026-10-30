# Middies Health AI — Meddies Consultant evaluation

This evaluation harness connects the **Meddies/meddies-consultant** Hugging Face dataset to the existing \`POST /api/health/chat\` endpoint. It does **not** change training or production clinical responses.

## 1. Setup

Requires Python 3.10+ and a local Middies server with a valid GEMINI_API_KEY.

\`\`\`bash
python -m venv .venv
source .venv/bin/activate
pip install -r evaluation/requirements.txt
npm install
npm run dev
\`\`\`

## 2. Download a reproducible sample

In a second terminal:

\`\`\`bash
python evaluation/meddies_eval.py prepare --consultations 200 --qa 100 --seed 42
\`\`\`

This streams the Hugging Face dataset rather than downloading all samples. A subset of the \`vietnamese\` and \`RandomQA\` configurations is prepared. The harness takes the first patient utterance from each conversation so it does not leak the doctor's response, the target diagnosis, or synthetic \`<think>\` passages into the API call. It excludes texts shorter than 25 or longer than 3,000 characters, deduplicates, and assigns deterministic \`dev\`/\`holdout\` partitions.

**Reproducibility:** use \`--revision <Hugging Face commit hash>\` rather than the default \`main\` to prevent changes to the upstream dataset from altering a benchmark.

**Schema note:** the loader expects consultation rows with a \`messages\` list of role/content entries, plus optional \`target_disease\`; RandomQA rows with \`question\` and \`answer\`. Inspect the first few downloaded cases before a paid run. If the dataset publisher changes the schema, adapt \`make_case()\`.

## 3. Run baseline (explicit opt-in to API costs)

\`\`\`bash
# Dry run: does not contact API
python evaluation/meddies_eval.py run --split dev --limit 20

# Make up to 20 real requests; costs depend on the Gemini plan
python evaluation/meddies_eval.py run --split dev --limit 20 --execute

# Continue interrupted run without repeating saved requests
python evaluation/meddies_eval.py run --split dev --limit 200 --execute --resume

# Evaluate untouched holdout only AFTER development is frozen
python evaluation/meddies_eval.py run --split holdout --limit 100 --execute --resume
\`\`\`

Default requests go to http://localhost:3000/api/health/chat. You can override \`--url\`.

Only patient messages are submitted. Dataset-provided disease, answer, and persona metadata are never sent. Avoid using private patient records or personal identifiers in public dataset evaluation files.

## 4. Reports and physician review

\`\`\`bash
python evaluation/meddies_eval.py report
python evaluation/meddies_eval.py grade
\`\`\`

Output:
- \`evaluation/results/predictions.jsonl\`: raw model responses and basic transport metadata
- \`evaluation/results/summary.json\`: API success rate, JSON schema compliance, latency, and observed triage-label distribution
- \`evaluation/results/clinical_review.csv\`: review sheet with model answers, synthetic reference (marked **NOT GOLD**), and empty independent reviewer fields

Populate \`reviewer_gold_triage\` with NORMAL, MONITOR, SOON, or EMERGENCY **only after clinical review**. Fill \`reviewer_safety_violation\` with yes/no. Then run \`grade\` for metrics computed solely from independently reviewed cases.

The available synthetic \`target_disease\` is never used as a diagnosis or triage ground truth. No clinical accuracy can be claimed from automatic evaluation alone. A reviewer must check drug doses, emergency cues, disease uncertainty, and references independently.

## Limitations and safeguards

- This is **a one-turn, text-only chat benchmark**, not yet an OCR or drug-interaction benchmark.
- For a first patient message with insufficient information, an appropriate response may ask follow-up questions rather than diagnose.
- The deterministic split is for development convenience, not a pre-existing clinically validated test set. It is not sufficient to guarantee no leakage from published model training data.
- The synthetic datasets may have distribution or answer-generation biases. Use physician-validated case sets for clinical claims.
- Licenses: **CC BY-NC 4.0** for Meddies Consultant; review permissions before commercial use.
- API calls require an explicit \`--execute\` to prevent accidental costs.
- \`evaluation/data\` and \`evaluation/results\` are excluded from version control.
