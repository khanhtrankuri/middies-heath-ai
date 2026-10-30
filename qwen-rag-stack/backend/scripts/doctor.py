"""Local diagnostics: never download weights or allocate an inference model."""
from __future__ import annotations

import importlib.metadata
import json
import os
import sys
from pathlib import Path


def inspect() -> dict:
    checks = []

    def check(name, passed, detail):
        checks.append({"name": name, "passed": bool(passed), "detail": str(detail)})

    check("python", (3, 11) <= sys.version_info[:2] < (3, 13), sys.version.split()[0])
    for package in ("torch", "transformers", "peft", "fastapi", "faiss-cpu", "sentence-transformers"):
        try:
            check(package, True, importlib.metadata.version(package))
        except importlib.metadata.PackageNotFoundError:
            check(package, False, "Missing; install backend dependencies")
    try:
        import torch
        cuda = torch.cuda.is_available()
        check("cuda", cuda, torch.cuda.get_device_name(0) if cuda else "CUDA unavailable")
        if cuda:
            free, total = torch.cuda.mem_get_info()
            check("gpu_memory", free >= 5 * 1024**3, f"{free / 1024**3:.1f}/{total / 1024**3:.1f} GiB free; inference fit must be measured")
    except Exception as error:
        check("cuda", False, error)
    from app.inference import resolve_adapter
    model = os.getenv("MEDDIES_BASE_MODEL", "Qwen/Qwen3-1.7B")
    try:
        adapter = resolve_adapter(model, os.getenv("MEDDIES_MODEL_PATH", "models/stage1_consult/final_adapter"))
        check("adapter", True, str(adapter) if adapter else "Base model baseline, no fine-tuning")
    except Exception as error:
        check("adapter", False, error)
    from huggingface_hub import snapshot_download
    from app.services.rag.config import RAGConfig
    config = RAGConfig.from_env()
    models = [model, config.embedding_model]
    if config.reranker == "cross_encoder":
        models.append(config.reranker_model)
    for name in models:
        try:
            path = Path(name) if Path(name).is_dir() else Path(snapshot_download(name, local_files_only=True))
            weights = list(path.rglob("*.safetensors")) + list(path.glob("pytorch_model*.bin"))
            index = path / "model.safetensors.index.json"
            if index.exists():
                shards = set(json.loads(index.read_text())["weight_map"].values())
                complete = all((path / shard).is_file() for shard in shards)
            else:
                complete = bool(weights)
            check(f"weights:{name}", complete, "Cached" if complete else "Weights incomplete; run local:prepare")
        except Exception:
            check(f"weights:{name}", False, "Not cached; run local:prepare with network access")
    from app.services.rag.vector_store import FAISSVectorStore
    try:
        store = FAISSVectorStore.load(config.index_path)
        check("rag_index", store.manifest.get("embedding_model") == config.embedding_model, f"{len(store.chunks)} chunks")
    except Exception as error:
        check("rag_index", False, error)
    return {"ready": all(row["passed"] for row in checks), "checks": checks,
            "note": "Readiness is not clinical quality; run retrieval and expert-reviewed answer evaluations."}


def main():
    result = inspect()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ready"] else 1)


if __name__ == "__main__":
    main()
