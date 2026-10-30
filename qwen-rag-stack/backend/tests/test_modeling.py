from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch

from training.modeling import (
    assert_only_lora_trainable,
    load_base_model,
    validate_lora_targets,
)


class TinyArchitecture(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.q_proj = torch.nn.Linear(2, 2)
        self.v_proj = torch.nn.Linear(2, 2)


def test_configured_lora_targets_must_exist() -> None:
    model = TinyArchitecture()
    matched = validate_lora_targets(model, ["q_proj", "v_proj"])
    assert matched == ["q_proj", "v_proj"]
    with pytest.raises(ValueError, match="k_proj"):
        validate_lora_targets(model, ["q_proj", "k_proj"])


def test_non_lora_trainable_parameter_fails_immediately() -> None:
    model = TinyArchitecture()
    with pytest.raises(RuntimeError, match="Base model parameters"):
        assert_only_lora_trainable(model)


def test_base_loader_uses_bf16_without_quantization(monkeypatch) -> None:
    captured = {}
    fake = SimpleNamespace(config=SimpleNamespace(use_cache=True))

    def from_pretrained(name, **kwargs):
        captured.update(kwargs)
        return fake

    monkeypatch.setattr("training.modeling.AutoModelForCausalLM.from_pretrained", from_pretrained)
    model = load_base_model(
        "Qwen/Qwen3-0.6B",
        dtype=torch.bfloat16,
        attention_implementation="sdpa",
        device_map={"": 0},
    )
    assert model is fake
    assert captured["dtype"] is torch.bfloat16
    assert captured["device_map"] == {"": 0}
    assert "quantization_config" not in captured
