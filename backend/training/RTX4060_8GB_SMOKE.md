# RTX 4060 Laptop 8GB diagnostic smoke result

This profile exists only to exercise and debug the complete Qwen3-8B QLoRA
code path on the available development laptop. Production training remains the
single-RTX-4090 configuration in `stage1_qwen3_8b_4090.yaml`.

## Verified environment

- Date: 2026-08-24
- GPU: NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB, WDDM
- Driver: 591.66
- Python: 3.11.15
- PyTorch: 2.13.0+cu130
- Transformers: 4.57.6
- TRL: 0.29.1
- PEFT: 0.20.0
- bitsandbytes: 0.50.1
- CUDA BF16 matmul: passed
- bitsandbytes NF4 `Linear4bit` forward: passed
- Backend tests: 18 passed

The test used `stage1_qwen3_8b_4060_8gb_smoke.yaml`:

- Qwen/Qwen3-8B, NF4 double quantization, BF16 compute, PyTorch SDPA
- sequence length 256
- LoRA rank 4 / alpha 8 on all 252 validated projection modules
- batch size 1, gradient accumulation 16
- 16 training and 4 evaluation conversations
- 3 optimizer steps with `paged_adamw_8bit`
- no packing and zero DataLoader subprocesses

## Result

The complete smoke workflow passed three times after debugging. The final run
completed forward, backward, optimizer steps, evaluation, adapter checkpoint,
adapter reload, and greedy Vietnamese generation with exit code 0.

```text
trainable parameters:       10,911,744 (0.133%)
represented parameters:     8,201,647,104
train runtime:               71.95 seconds
train tokens/second:         170.788
train loss:                  2.47717
eval loss:                   2.33934
eval samples/second:         1.943
final adapter size:          20.88 MiB
```

The local result is written to:

```text
models/debug_4060_8gb/final_adapter/
models/debug_4060_8gb/run_metadata/run.json
```

These generated artifacts and the diagnostic dataset are intentionally ignored
by Git.

## WDDM memory caveat

PyTorch reported a 9.87 GiB allocator peak during training and an 11.47 GiB
whole-process peak after adapter reload/generation, while dedicated VRAM is only
8 GiB. Under Windows WDDM this counter can include shared/virtual GPU memory.
It must not be interpreted as dedicated VRAM usage. The run succeeded, but it
was operating beyond the comfortable dedicated-memory envelope and can page or
fail when other desktop applications consume more memory.

This result does **not** make the 4060 profile suitable for full training. It
only proves the code path at sequence length 256 and rank 4. The 4090 profile
remains the supported production path at sequence length 4096 and rank 32.

The three-step adapter's generated text was fluent Vietnamese but started
listing possible causes instead of consistently asking follow-up questions.
That is expected from a tiny diagnostic run and is not a consultation-quality
acceptance result.

## Reproduction

On this Windows machine, PyPI initially selected a CPU-only Torch wheel. Install
the official CUDA wheel explicitly, then verify `torch.cuda.is_available()`
before training.

```powershell
uv venv .venv-4060 --python 3.11
uv pip install --python .venv-4060\Scripts\python.exe -e "backend[dev]"
uv pip install --python .venv-4060\Scripts\python.exe --reinstall --no-deps torch `
  --index-url https://download.pytorch.org/whl/cu130

cd backend
..\.venv-4060\Scripts\python.exe -m training.data.prepare_meddies `
  --configs vietnamese english `
  --output-dir data/processed_4060_smoke `
  --seed 42 `
  --max-samples 200

$env:CUDA_VISIBLE_DEVICES = "0"
$env:HF_HUB_DISABLE_XET = "1"
..\.venv-4060\Scripts\python.exe -m training.train_stage1 `
  --config training/configs/stage1_qwen3_8b_4060_8gb_smoke.yaml `
  --max-train-samples 16 `
  --max-eval-samples 4 `
  --smoke-test
```

`HF_HUB_DISABLE_XET=1` was needed because the Xet materialization path stalled
on this host; normal resumable HTTP completed all five 15.26 GiB model shards.

## Defects found and fixed by the real run

1. Setuptools package discovery failed after adding both `app` and `training`.
   Explicit package discovery is now configured in `pyproject.toml`.
2. Source conversations included malformed reasoning prefixes ending in
   `</think>`. Cleaning now removes those prefixes and rejects unresolved orphan
   tags before tokenization.
3. Assistant-only masking was validated against all 390 prepared smoke
   conversations and now fails closed if template spans cannot be proven.
4. Parameter counts now use PEFT's uncompressed count instead of the packed
   bitsandbytes storage count.
5. Current Transformers uses `dtype`; deprecated `torch_dtype` calls were
   removed.
6. WDDM allocator peaks above physical VRAM are labeled as shared/virtual-memory
   accounting in both logs and run metadata.

## End-to-end RAG + Qwen diagnostic

After the mandatory RAG subsystem was added, a second real diagnostic was run on
the same RTX 4060 Laptop GPU. It built a two-chunk FAISS index from the reviewed
test fixture using the deterministic CPU embedding provider, retrieved both
relevant chunks for `Migraine là gì?`, loaded the real Qwen3-8B NF4 base plus the
adapter above, passed the structured source context into Qwen, generated a
grounded Vietnamese answer, and returned citations `S1` and `S2`.

```text
action:                    GROUNDED_ANSWER
grounding status:          grounded
retrieved/indexed chunks:  2
structured citations:      S1, S2
peak Torch GPU allocation: 5.95 GiB
```

Reproduce the diagnostic from `backend/` after the adapter and cached base model
exist:

```powershell
..\.venv-4060\Scripts\python.exe scripts\smoke_rag_4060.py
```

The script intentionally resolves an existing Hugging Face snapshot in offline
mode, because Transformers otherwise attempted a metadata network request even
though all weights were cached. It also forces UTF-8 stdout so Vietnamese output
works in legacy Windows PowerShell. Both issues were found and fixed during the
real run.

This is a wiring/memory diagnostic, not a retrieval-quality evaluation: the
fixture uses a tiny deterministic embedding rather than production BGE-M3. The
production design still runs BGE-M3 on CPU and Qwen on the single RTX 4090.
