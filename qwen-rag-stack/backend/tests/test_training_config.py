from __future__ import annotations

import logging
import os
from argparse import Namespace

import pytest

from training.config import apply_cli_overrides, load_config, validate_training_config
from training.train_stage1 import (
    _select_gpu_from_cli_before_cuda,
    configure_logging,
    parse_args,
    select_gpu,
)


def test_stage1_accepts_gpu_index_and_supported_model() -> None:
    args = parse_args([
        "--config", "profile.yaml", "--gpu", "2", "--model-name", "Qwen/Qwen3-0.6B"
    ])
    assert args.gpu == 2
    assert args.model_name == "Qwen/Qwen3-0.6B"


def test_select_gpu_sets_cuda_visibility(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("training.train_stage1.torch.cuda.is_initialized", lambda: False)
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    select_gpu(2)
    assert os.environ["CUDA_VISIBLE_DEVICES"] == "2"


def test_gpu_is_selected_from_cli_before_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    _select_gpu_from_cli_before_cuda(["--config", "profile.yaml", "--gpu", "1"])
    assert os.environ["CUDA_VISIBLE_DEVICES"] == "1"


def test_training_logging_keeps_metrics_and_hides_http_noise() -> None:
    configure_logging()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger().manager.disable < logging.INFO


@pytest.mark.parametrize("profile", ["rtx4090_24gb.yaml", "rtx4060_8gb.yaml"])
def test_hardware_profiles_are_valid_bf16_lora(profile: str) -> None:
    config = load_config(f"training/configs/{profile}")
    validate_training_config(config)
    assert config["model"]["dtype"] == "bfloat16"
    assert config["training"]["packing"] is True
    assert "quantization" not in config


def test_cli_has_priority_over_hardware_profile() -> None:
    config = load_config("training/configs/rtx4060_8gb.yaml")
    resolved = apply_cli_overrides(
        config,
        Namespace(model_name="Qwen/Qwen3-0.6B", max_seq_length=1536, lora_r=16),
    )
    assert resolved["model"]["name"] == "Qwen/Qwen3-0.6B"
    assert resolved["training"]["max_seq_length"] == 1536
    assert resolved["lora"]["r"] == 16


def test_prompt_only_subset_cannot_enter_sft_mix() -> None:
    config = load_config("training/configs/rtx4060_8gb.yaml")
    config["dataset_mix"]["RandomQuestion"] = 1
    with pytest.raises(ValueError, match="RandomQuestion"):
        validate_training_config(config)
