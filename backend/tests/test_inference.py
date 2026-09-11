from app.inference import InferenceManager, ModelProvider, StubProvider, create_provider
import asyncio
import threading

import pytest


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
