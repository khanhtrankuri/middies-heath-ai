# Repository consolidation — 2026-11-01

`main` is the canonical development branch. The repository retains the root Express/React application
and the research stack under `qwen-rag-stack/`. Consolidation preserves both runtimes and the published
research evidence; it does not combine their dependencies or replace their model providers.

## Branch audit

| Source | Resolution |
|---|---|
| `feat/qwen-lora-question-planner` | Merged into `main`, preserving all five implementation/evidence commits and PR #5 code |
| `origin/feat/medical-dialogue-research` | Research modules already incorporated in the previous `main`; ancestry reconciled while retaining the newer Planner implementation and tracked Sites plugin |
| `origin/claude/youthful-meitner-0kodvk`, `origin/feat/initial-project`, `origin/eval/meddies-consultant`, `origin/research/open-teacher-qwen` | Already ancestors of `main`; their source was retained by earlier integration commits |
| Local `feat/initial-project` | Rewritten duplicate history; final application source matched the corresponding remote branch apart from generated pytest fixtures |
| Local `feat/medical-dialogue-research` | Snapshot of already integrated source plus environment/runtime/dependency files; unique runtime state archived locally rather than published |
| Local `ready-for-main` | Older integration snapshot; Qwen source already present, old build plugin superseded, newer root UI retained, matching root lockfile retained |
| Local `backup/local-initial` | Original README-only snapshot superseded by the current documentation; archived with the other refs |

No unpublished environment/cache snapshot history was attached to `main`. Useful application code
was checked before branch deletion; historical snapshots remain recoverable from the local bundle.

## Local archive

The ignored directory `.sites-runtime/consolidation-20261101/` contains:

- `all-branches.bundle`: complete Git bundle of the pre-consolidation refs; `git bundle verify` passed.
- `refs-before.txt`: exact branch names and commit IDs before changes.
- `workspace-backend/`: former root-level generated runtime state, including old data/models/reports.
- `workspace-aistudio/`: editor-generated planning artifacts removed from the tracked source tree.
- `workspace-SystemDrive/` and `root-run-logs/`: archived shell/runtime artifacts and old root logs.
- `checks/`: verification logs for this cleanup.

The archive may include environment files from old snapshots. Keep it local; do not commit or upload it.
The active models, processed datasets and original reports under `qwen-rag-stack/backend/` were preserved
in place. The current `.env` and local editor settings were preserved and remain ignored.

## Code cleanup

- Removed an unused duplicate emergency-pattern table; the root app keeps using the shared detector.
- Removed unconsumed `matchScore` properties/calculations and unused imports/counters.
- Removed unreachable cloud fallback-notice assignment; historical client payload compatibility remains.
- Consolidated Qwen request timeouts into one helper that clears its timer in `finally`.
- Added concrete Planner/state/validation types and clarified conditional-expression precedence.
- Enabled root TypeScript checks for unused locals/parameters and retained a validated npm lockfile.
- Expanded ignore rules for local environment variants, tool state, test temp files and the obsolete root runtime directory.
- Rewrote architecture documentation to describe the actual provider bridge and canonical backend.

## Verification

- Backend: 374 pytest tests passed; no GPU training was repeated.
- Root application: TypeScript with unused-symbol checks, five safety tests and Vite build passed.
- Root HTTP smoke: unavailable readiness, explicit Qwen 503, benchmark provider lock and emergency routing passed.
- Qwen frontend: TypeScript, ESLint, nine unit tests, build, artifact validation and rendered-HTML test passed.
- Historical E1–E5 results and raw experiment artifacts were not overwritten.

For research protocols and existing limitations, see
[PLANNER_GUIDED.md](../qwen-rag-stack/docs/PLANNER_GUIDED.md) and
[the E5 report](../qwen-rag-stack/docs/PLANNER_E5_RESULTS_20261031.md).
