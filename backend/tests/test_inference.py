from app.inference import InferenceManager, ModelProvider, StubProvider, VLLMProvider, create_provider
import asyncio
import threading
import json
import sys
from types import SimpleNamespace

import pytest
from app.inference import resolve_adapter


def test_adapter_mismatch_and_missing_adapter_fail_before_model_load(tmp_path):
    assert resolve_adapter("Qwen/Qwen3-1.7B", "") is None
    with pytest.raises(RuntimeError, match="incomplete"):
        resolve_adapter("Qwen/Qwen3-1.7B", str(tmp_path))
    (tmp_path / "adapter_model.safetensors").write_bytes(b"test")
    (tmp_path / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "other-model"}))
    with pytest.raises(RuntimeError, match="does not match"):
        resolve_adapter("Qwen/Qwen3-1.7B", str(tmp_path))


def test_adapter_accepts_cached_snapshot_of_its_base_model(tmp_path):
    base = tmp_path / "models--Qwen--Qwen3-1.7B" / "snapshots" / "revision"
    base.mkdir(parents=True)
    adapter = tmp_path / "adapter"
    adapter.mkdir()
    (adapter / "adapter_model.safetensors").write_bytes(b"test")
    (adapter / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "Qwen/Qwen3-1.7B"}))
    assert resolve_adapter(str(base), str(adapter)) == adapter


class CountingProvider(ModelProvider):
    def __init__(self) -> None:
        self.loads = 0

    def load(self) -> None:
        self.loads += 1

    def generate(self, messages: list[dict[str, str]]) -> str:
        return messages[-1]["content"]


def test_inference_manager_loads_model_once() -> None:
    provider = CountingProvider()
    manager = InferenceManager(provider)
    manager.load()
    manager.load()
    assert provider.loads == 1


def test_stub_provider_is_available_for_ci() -> None:
    assert isinstance(create_provider("stub"), StubProvider)


def test_vllm_uses_tokenizer_chat_template(monkeypatch) -> None:
    captured = {}

    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            captured["template"] = (messages, kwargs)
            return "QWEN_TEMPLATE_PROMPT"

    class Engine:
        def generate(self, prompts, params):
            captured["prompts"] = prompts
            return [SimpleNamespace(outputs=[SimpleNamespace(text="answer")])]

    monkeypatch.setitem(sys.modules, "vllm", SimpleNamespace(SamplingParams=lambda **kwargs: kwargs))
    provider = VLLMProvider()
    provider.tokenizer = Tokenizer()
    provider.engine = Engine()
    answer = provider.generate([{"role": "user", "content": "hello"}])
    assert answer == "answer"
    assert captured["prompts"] == ["QWEN_TEMPLATE_PROMPT"]
    assert captured["template"][1]["enable_thinking"] is False


def test_cancelling_a_caller_does_not_release_an_active_generation_slot() -> None:
    entered = threading.Event()
    finish = threading.Event()

    class BlockingProvider(CountingProvider):
        def generate(self, messages):
            entered.set()
            assert finish.wait(timeout=5)
            return "done"

    async def exercise():
        manager = InferenceManager(BlockingProvider())
        caller = asyncio.create_task(manager.generate([{"role": "user", "content": "test"}]))
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            caller.cancel()
            with pytest.raises(asyncio.CancelledError):
                await caller
            assert manager.semaphore.locked()
        finally:
            finish.set()
        await asyncio.wait_for(manager.semaphore.acquire(), timeout=3)
        manager.semaphore.release()

    asyncio.run(exercise())
