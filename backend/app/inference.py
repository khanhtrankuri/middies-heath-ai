from __future__ import annotations

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

LOGGER = logging.getLogger(__name__)


def _env(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value
    return default


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
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        if not torch.cuda.is_available():
            raise RuntimeError("MODEL_PROVIDER=transformers requires an NVIDIA CUDA GPU")
        model_name = _env("MEDDIES_BASE_MODEL", "BASE_MODEL", default="Qwen/Qwen3-8B")
        adapter_path = _env(
            "MEDDIES_MODEL_PATH",
            "MODEL_PATH",
            "MEDDIES_ADAPTER_PATH",
            default="models/stage1_consult/final_adapter",
        )
        attention = os.getenv("MEDDIES_ATTENTION_IMPLEMENTATION", "sdpa")
        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
        )
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        base = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=quantization,
            dtype=torch.bfloat16,
            device_map={"": 0},
            attn_implementation=attention,
        )
        self.model = PeftModel.from_pretrained(base, adapter_path)
        self.model.eval()
        self.model.config.use_cache = True
        LOGGER.info("Loaded %s in NF4 4-bit with adapter %s", model_name, adapter_path)

    def generate(self, messages: list[dict[str, str]]) -> str:
        import torch

        if self.model is None or self.tokenizer is None:
            raise RuntimeError("Model provider has not been loaded")
        template_kwargs: dict[str, Any] = {
            "tokenize": True,
            "add_generation_prompt": True,
            "return_tensors": "pt",
        }
        try:
            input_ids = self.tokenizer.apply_chat_template(
                messages, enable_thinking=False, **template_kwargs
            )
        except TypeError:
            input_ids = self.tokenizer.apply_chat_template(messages, **template_kwargs)
        input_ids = input_ids.to(self.model.device)
        temperature = float(os.getenv("MEDDIES_TEMPERATURE", "0.3"))
        generation: dict[str, Any] = {
            "max_new_tokens": int(os.getenv("MEDDIES_MAX_NEW_TOKENS", "384")),
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
            output = self.model.generate(input_ids, **generation)
        return self.tokenizer.decode(output[0][input_ids.shape[-1] :], skip_special_tokens=True).strip()


class VLLMProvider(ModelProvider):
    def __init__(self) -> None:
        self.engine: Any = None

    def load(self) -> None:
        try:
            from vllm import LLM
        except ImportError as error:
            raise RuntimeError("Install the optional vllm dependency to use this provider") from error
        model = os.getenv("MEDDIES_VLLM_MODEL", "models/stage1_consult/merged")
        self.engine = LLM(model=model, tensor_parallel_size=1, dtype="bfloat16")

    def generate(self, messages: list[dict[str, str]]) -> str:
        from vllm import SamplingParams

        if self.engine is None:
            raise RuntimeError("Model provider has not been loaded")
        prompt = "\n".join(f"{item['role']}: {item['content']}" for item in messages) + "\nassistant:"
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
