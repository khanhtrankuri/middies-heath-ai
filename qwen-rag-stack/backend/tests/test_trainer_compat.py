from __future__ import annotations

import os

from training.config import load_config
from training.trainer import (
    _resolve_dataloader_workers,
    build_dataset,
    build_sft_config,
    configure_wandb,
    load_mixed_rows,
)


class TinyChatTokenizer:
    eos_token_id = 99

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        if not tokenize:
            return []
        result = [10]
        for message in messages:
            result.append(90 if message["role"] == "assistant" else 80)
            result.extend(ord(character) for character in message["content"])
            result.append(70)
        if add_generation_prompt:
            result.append(90)
        return result


def test_windows_disables_spawned_dataloader_workers(caplog) -> None:
    assert _resolve_dataloader_workers(2, platform_name="nt") == 0
    assert "forcing dataloader_num_workers=0" in caplog.text
    assert _resolve_dataloader_workers(2, platform_name="posix") == 2


def test_dataset_skips_only_conversations_without_supervised_window(caplog) -> None:
    rows = [
        {
            "id": "too-long",
            "messages": [
                {"role": "user", "content": "long user message"},
                {"role": "assistant", "content": "answer"},
            ],
        },
        {
            "id": "trainable",
            "messages": [
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "a"},
            ],
        },
    ]

    dataset = build_dataset(rows, TinyChatTokenizer(), max_length=8, packing=False)

    assert len(dataset) == 1
    assert "Skipped 1/2 conversation(s)" in caplog.text


def test_sft_config_supports_installed_transformers_api(tmp_path) -> None:
    config = load_config("training/configs/rtx4060_8gb.yaml")
    args = build_sft_config(
        config["training"], str(tmp_path / "output"), smoke_test=True
    )

    assert args.max_steps == 3
    assert args.logging_steps == 1
    if hasattr(args, "warmup_ratio"):
        assert args.warmup_ratio == config["training"]["warmup_ratio"]
    else:
        assert args.warmup_steps == config["training"]["warmup_ratio"]


def test_wandb_tracking_configuration(monkeypatch, tmp_path) -> None:
    for name in ("WANDB_PROJECT", "WANDB_MODE", "WANDB_LOG_MODEL", "WANDB_SILENT"):
        monkeypatch.setenv(name, "")
    report_to, run_name = configure_wandb(
        {
            "enabled": True,
            "project": "meddies-test",
            "run_name": "offline-smoke",
            "mode": "offline",
            "log_model": "false",
        },
        str(tmp_path),
    )

    assert report_to == "wandb"
    assert run_name == "offline-smoke"
    assert os.environ["WANDB_PROJECT"] == "meddies-test"
    assert os.environ["WANDB_MODE"] == "offline"


def test_full_training_loads_every_sft_row_without_weight_truncation(tmp_path) -> None:
    for subset, count in (("vietnamese", 5), ("english", 2), ("RandomQA", 3)):
        root = tmp_path / subset
        root.mkdir()
        rows = "".join(
            '{"id":"%s-%d","messages":[{"role":"user","content":"q"},'
            '{"role":"assistant","content":"a"}]}\n' % (subset, index)
            for index in range(count)
        )
        (root / "train.jsonl").write_text(rows, encoding="utf-8")
    loaded = load_mixed_rows(
        tmp_path,
        {"vietnamese": 0.45, "english": 0.20, "RandomQA": 0.35},
        "train",
        max_samples=None,
        seed=42,
    )
    assert len(loaded) == 10
