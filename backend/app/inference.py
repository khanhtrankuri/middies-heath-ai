from __future__ import annotations

import asyncio
import logging
import os
import json
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Any

LOGGER = logging.getLogger(__name__)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def resolve_adapter(model_name: str, configured_path: str) -> Path | None:
    """Empty explicitly selects the base model; a broken adapter never falls back."""
    if not configured_path.strip():
        return None
    path = Path(configured_path).expanduser()
    path = path if path.is_absolute() else BACKEND_ROOT / path
    config_path = path / "adapter_config.json"
    if not config_path.is_file() or not (path / "adapter_model.safetensors").is_file():
        raise RuntimeError("Adapter is incomplete. Set a trained adapter path or explicitly use an empty MEDDIES_MODEL_PATH for baseline evaluation.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    expected_base = config.get("base_model_name_or_path")
    base_path = Path(model_name)
    canonical_name = model_name
    if base_path.is_dir() and base_path.parent.name == "snapshots" and base_path.parent.parent.name.startswith("models--"):
        canonical_name = base_path.parent.parent.name.removeprefix("models--").replace("--", "/")
    if expected_base not in {model_name, canonical_name}:
        raise RuntimeError("Adapter base model does not match MEDDIES_BASE_MODEL")
    return path


def _env(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value
    return default


def apply_qwen_chat_template(
    tokenizer: Any, messages: list[dict[str, str]], **kwargs: Any
) -> Any:
    """One template path shared by every inference provider."""
    try:
        return tokenizer.apply_chat_template(messages, enable_thinking=False, **kwargs)
    except TypeError:
        return tokenizer.apply_chat_template(messages, **kwargs)


class ModelProvider(ABC):
    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def generate(self, messages: list[dict[str, str]]) -> str: ...


class StubProvider(ModelProvider):
    def load(self) -> None:
        LOGGER.info("Loaded stub model provider")

    def generate(self, messages: list[dict[str, str]]) -> str:
        if messages and "Chỉ hỏi 1–2 câu" not in messages[0]["content"]:
            return "Đây là chế độ kiểm thử giao diện, chưa sử dụng mô hình tư vấn thật. Thông tin của bạn đã được tiếp nhận; chế độ này không đưa ra nhận định y khoa."
        return "Bạn có thể mô tả vị trí, thời điểm bắt đầu và mức độ của triệu chứng không?"


class TransformersProvider(ModelProvider):
    def __init__(self) -> None:
        self.model: Any = None
        self.tokenizer: Any = None

    def load(self) -> None:
        if self.model is not None:
            return
        import torch
        from training.modeling import load_adapter, load_base_model, load_tokenizer

        if not torch.cuda.is_available():
            raise RuntimeError("MODEL_PROVIDER=transformers requires an NVIDIA CUDA GPU")
        model_name = _env("MEDDIES_BASE_MODEL", "BASE_MODEL", default="Qwen/Qwen3-1.7B")
        adapter_path = _env(
            "MEDDIES_MODEL_PATH",
            "MODEL_PATH",
            "MEDDIES_ADAPTER_PATH",
            default="models/stage1_consult/final_adapter",
        )
        adapter = resolve_adapter(model_name, adapter_path)
        local_only = os.getenv("MEDDIES_LOCAL_FILES_ONLY", "false").lower() in {"1", "true", "yes"}
        dtype_name = os.getenv("MEDDIES_MODEL_DTYPE", "bfloat16")
        if dtype_name not in {"bfloat16", "float16"}:
            raise ValueError("MEDDIES_MODEL_DTYPE must be bfloat16 or float16")
        dtype = torch.bfloat16 if dtype_name == "bfloat16" else torch.float16
        if dtype is torch.bfloat16 and not torch.cuda.is_bf16_supported():
            raise RuntimeError("Configured inference dtype is BF16 but this GPU does not support BF16")
        attention = os.getenv("MEDDIES_ATTENTION_IMPLEMENTATION", "sdpa")
        self.tokenizer = load_tokenizer(model_name, local_files_only=local_only)
        base = load_base_model(
            model_name,
            dtype=dtype,
            device_map={"": 0},
            attention_implementation=attention,
            local_files_only=local_only,
            use_cache=True,
        )
        if adapter is not None:
            self.model = load_adapter(base, str(adapter), trainable=False)
        else:
            self.model = base
        self.model.eval()
        self.model.config.use_cache = True
        LOGGER.info("Loaded %s with dtype=%s and adapter=%s", model_name, dtype_name, adapter)

    def generate(self, messages: list[dict[str, str]]) -> str:
        import torch

        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model provider has not been loaded")
        template_kwargs: dict[str, Any] = {
            "tokenize": True,
            "add_generation_prompt": True,
            "return_tensors": "pt",
        }
        input_ids = apply_qwen_chat_template(self.tokenizer, messages, **template_kwargs)
        input_ids = input_ids.to(self.model.device)
        max_context = int(os.getenv("MEDDIES_MAX_CONTEXT_TOKENS", "4096"))
        max_new_tokens = int(os.getenv("MEDDIES_MAX_NEW_TOKENS", "384"))
        if max_new_tokens < 1 or input_ids.shape[-1] + max_new_tokens > max_context:
            # Never truncate system safety instructions or the active user turn.
            raise RuntimeError("Conversation exceeds the configured model context budget")
        temperature = float(os.getenv("MEDDIES_TEMPERATURE", "0.3"))
        generation: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "repetition_penalty": float(os.getenv("MEDDIES_REPETITION_PENALTY", "1.05")),
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        if temperature > 0:
            generation.update(
                do_sample=True,
                temperature=temperature,
                top_p=float(os.getenv("MEDDIES_TOP_P", "0.9")),
            )
        else:
            generation["do_sample"] = False
            for name in ("temperature", "top_p", "top_k", "min_p"):
                if hasattr(self.model.generation_config, name):
                    setattr(self.model.generation_config, name, None)
        with torch.inference_mode():
            output = self.model.generate(input_ids, attention_mask=torch.ones_like(input_ids), **generation)
        return self.tokenizer.decode(output[0][input_ids.shape[-1] :], skip_special_tokens=True).strip()


class VLLMProvider(ModelProvider):
    def __init__(self) -> None:
        self.engine: Any = None
        self.tokenizer: Any = None

    def load(self) -> None:
        try:
            from vllm import LLM
        except ImportError as error:
            raise RuntimeError("Install the optional vllm dependency to use this provider") from error
        from training.modeling import load_tokenizer

        model = os.getenv("MEDDIES_VLLM_MODEL") or _env(
            "MEDDIES_BASE_MODEL", "BASE_MODEL", default="Qwen/Qwen3-1.7B"
        )
        tokenizer_name = _env("MEDDIES_BASE_MODEL", "BASE_MODEL", default=model)
        local_only = os.getenv("MEDDIES_LOCAL_FILES_ONLY", "false").lower() in {"1", "true", "yes"}
        self.tokenizer = load_tokenizer(tokenizer_name, local_files_only=local_only)
        self.engine = LLM(
            model=model,
            tensor_parallel_size=int(os.getenv("MEDDIES_VLLM_TENSOR_PARALLEL_SIZE", "1")),
            dtype=os.getenv("MEDDIES_MODEL_DTYPE", "bfloat16"),
        )

    def generate(self, messages: list[dict[str, str]]) -> str:
        from vllm import SamplingParams

        if self.engine is None or self.tokenizer is None:
            raise RuntimeError("Model provider has not been loaded")
        template_kwargs = {"tokenize": False, "add_generation_prompt": True}
        prompt = apply_qwen_chat_template(self.tokenizer, messages, **template_kwargs)
        if not isinstance(prompt, str):
            raise RuntimeError("Qwen chat template did not render a text prompt for vLLM")
        params = SamplingParams(
            max_tokens=int(os.getenv("MEDDIES_MAX_NEW_TOKENS", "384")),
            temperature=float(os.getenv("MEDDIES_TEMPERATURE", "0.3")),
            top_p=float(os.getenv("MEDDIES_TOP_P", "0.9")),
            repetition_penalty=float(os.getenv("MEDDIES_REPETITION_PENALTY", "1.05")),
        )
        return self.engine.generate([prompt], params)[0].outputs[0].text.strip()


def create_provider(name: str) -> ModelProvider:
    providers = {"stub": StubProvider, "transformers": TransformersProvider, "vllm": VLLMProvider}
    try:
        return providers[name]()
    except KeyError as error:
        raise ValueError(f"Unknown MODEL_PROVIDER={name!r}") from error


class InferenceManager:
    """Own the one process-wide model instance and bound GPU generation work."""

    def __init__(self, provider: ModelProvider, max_generations: int = 1) -> None:
        if max_generations < 1:
            raise ValueError("MEDDIES_MAX_GENERATIONS must be at least 1")
        self.provider = provider
        self.semaphore = asyncio.Semaphore(max_generations)
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        self.provider.load()
        self._loaded = True

    @property
    def loaded(self) -> bool:
        return self._loaded

    async def generate(self, messages: list[dict[str, str]]) -> str:
        await self.semaphore.acquire()
        work = asyncio.create_task(asyncio.to_thread(self.provider.generate, messages))

        def release_when_finished(task: asyncio.Task[str]) -> None:
            self.semaphore.release()
            # A disconnected caller may no longer await an inference failure.
            if not task.cancelled():
                task.exception()

        work.add_done_callback(release_when_finished)
        # Cancelling an HTTP request cannot stop an already-running GPU thread.
        # Retain its generation slot until the thread actually completes.
        return await asyncio.shield(work)
