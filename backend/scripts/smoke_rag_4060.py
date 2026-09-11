from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from app.inference import InferenceManager, TransformersProvider
from app.services.consultation import ConsultationOrchestrator
from app.services.rag.config import RAGConfig
from app.services.rag.embeddings import DeterministicHashEmbeddingProvider
from app.services.rag.service import RAGService, build_knowledge_index


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnostic-only end-to-end RAG + Qwen smoke test on an 8GB RTX 4060"
    )
    parser.add_argument("--base-model", default="Qwen/Qwen3-8B")
    parser.add_argument("--adapter", type=Path, default=Path("models/debug_4060_8gb/final_adapter"))
    parser.add_argument(
        "--knowledge-dir", type=Path, default=Path("tests/fixtures/knowledge")
    )
    parser.add_argument("--query", default="Migraine là gì?")
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="Allow Hugging Face network checks instead of requiring a cached base-model snapshot",
    )
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import torch

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required for this diagnostic")
    gpu_name = torch.cuda.get_device_name(0)
    total_gib = torch.cuda.get_device_properties(0).total_memory / 1024**3
    if "RTX 4060" not in gpu_name or total_gib > 9:
        raise SystemExit(f"Expected an 8GB RTX 4060 diagnostic GPU, found {gpu_name} ({total_gib:.1f} GiB)")

    provider = DeterministicHashEmbeddingProvider()
    with tempfile.TemporaryDirectory(prefix="meddies-rag-4060-") as temporary:
        index_path = Path(temporary) / "index"
        config = RAGConfig(
            enabled=True,
            index_path=index_path,
            embedding_model=provider.model_name,
            embedding_device="cpu",
            top_k=4,
            final_k=2,
            chunk_size=700,
            chunk_overlap=100,
        )
        stats = build_knowledge_index(
            args.knowledge_dir,
            index_path,
            config=config,
            embedding_provider=provider,
        )
        rag = RAGService(config, embedding_provider=provider)
        rag.load()
        if not rag.ready:
            raise SystemExit(f"RAG failed readiness: {rag.error}")

        model_path = args.base_model
        if not args.allow_network:
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            from huggingface_hub import snapshot_download

            model_path = snapshot_download(args.base_model, local_files_only=True)
        os.environ["MEDDIES_BASE_MODEL"] = model_path
        os.environ["MEDDIES_MODEL_PATH"] = str(args.adapter.resolve())
        os.environ["MEDDIES_MAX_NEW_TOKENS"] = "192"
        os.environ["MEDDIES_TEMPERATURE"] = "0"
        inference = InferenceManager(TransformersProvider(), max_generations=1)
        inference.load()
        orchestrator = ConsultationOrchestrator(inference, rag, "transformers")
        response = await orchestrator.respond(
            [{"role": "user", "content": args.query}]
        )
        if response.grounding_status != "grounded" or not response.citations:
            raise SystemExit("Grounded generation did not return a citation")
        print(
            json.dumps(
                {
                    "gpu": gpu_name,
                    "gpu_total_gib": round(total_gib, 2),
                    "index_chunks": stats.chunk_count,
                    "action": response.action,
                    "grounding_status": response.grounding_status,
                    "citation_ids": [item.citation_id for item in response.citations],
                    "reply": response.reply,
                    "peak_torch_allocated_gib": round(
                        torch.cuda.max_memory_allocated() / 1024**3, 2
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(run())
