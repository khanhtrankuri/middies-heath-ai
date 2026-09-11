from pathlib import Path

import pytest
import torch

from training.train_kaggle_t4 import (
    distributed_ranks,
    parse_args,
    prepare_adapter_precision,
    tokenize_rows,
    trainer_kwargs,
    validate_paths,
)
from test_training_data import FakeChatTokenizer


def test_t4_profile_and_smoke_limits() -> None:
    args = parse_args(["--data-dir", "processed", "--smoke-test", "--max-train-samples", "0"])
    config = trainer_kwargs(args, 1)
    assert args.max_train_samples == 100
    assert args.max_eval_samples == 30
    assert config["max_steps"] == 3
    assert config["fp16"] and not config["bf16"] and not config["tf32"]
    assert config["local_rank"] == 1
    assert config["ddp_find_unused_parameters"] is False
    assert config["gradient_checkpointing_kwargs"] == {"use_reentrant": False}
    assert config["per_device_train_batch_size"] * config["gradient_accumulation_steps"] * 2 == 16
    assert config["save_only_model"] is False


@pytest.mark.parametrize("option,value", [
    ("--max-seq-length", "127"), ("--max-seq-length", "129"),
    ("--gradient-accumulation-steps", "0"), ("--max-steps", "0"),
    ("--max-train-samples", "-1"), ("--lora-r", "0"),
])
def test_reject_invalid_training_options(option: str, value: str) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--data-dir", "processed", option, value])


def test_requires_two_local_torchrun_workers() -> None:
    for rank in ("0", "1"):
        assert distributed_ranks({
            "WORLD_SIZE": "2", "LOCAL_WORLD_SIZE": "2", "LOCAL_RANK": rank, "RANK": rank,
        }) == (int(rank), int(rank))
    for environment in ({}, {"WORLD_SIZE": "1"}, {
        "WORLD_SIZE": "2", "LOCAL_WORLD_SIZE": "1", "LOCAL_RANK": "0", "RANK": "0",
    }):
        with pytest.raises(RuntimeError, match="torchrun"):
            distributed_ranks(environment)


def test_preflight_preserves_existing_outputs_and_rejects_partial_checkpoint(tmp_path: Path) -> None:
    data_dir = tmp_path / "processed"
    output_dir = tmp_path / "output"
    args = parse_args(["--data-dir", str(data_dir), "--output-dir", str(output_dir)])
    with pytest.raises(FileNotFoundError, match="Missing prepared data"):
        validate_paths(args)
    for source in ("vietnamese", "english"):
        (data_dir / source).mkdir(parents=True)
        for split in ("train", "validation"):
            (data_dir / source / f"{split}.jsonl").touch()
    validate_paths(args)
    output_dir.mkdir()
    (output_dir / "keep.txt").write_text("existing output", encoding="utf-8")
    with pytest.raises(ValueError, match="not empty"):
        validate_paths(args)
    args.resume_from_checkpoint = tmp_path / "partial-checkpoint"
    args.resume_from_checkpoint.mkdir()
    (args.resume_from_checkpoint / "adapter_config.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="complete resumable"):
        validate_paths(args)
    assert (output_dir / "keep.txt").read_text(encoding="utf-8") == "existing output"


def test_truncation_skips_all_masked_rows_but_keeps_assistant_loss() -> None:
    rows = [
        {"messages": [{"role": "user", "content": "x" * 200}, {"role": "assistant", "content": "answer"}]},
        {"messages": [{"role": "user", "content": "pain"}, {"role": "assistant", "content": "where"}]},
    ]
    tokenized, skipped = tokenize_rows(rows, FakeChatTokenizer(), 128)
    assert skipped == 1
    assert len(tokenized) == 1
    assert tokenized[0]["labels"][0] == -100
    assert any(label != -100 for label in tokenized[0]["labels"])
    with pytest.raises(ValueError, match="No usable conversations"):
        tokenize_rows(rows[:1], FakeChatTokenizer(), 128)
    with pytest.raises(ValueError, match="messages cannot be empty"):
        tokenize_rows([{"messages": []}], FakeChatTokenizer(), 128)
def test_fp16_amp_keeps_only_lora_trainable_in_fp32() -> None:
    model = torch.nn.Module()
    model.register_parameter("base", torch.nn.Parameter(torch.ones(2, dtype=torch.float16), requires_grad=False))
    model.register_parameter("lora_A", torch.nn.Parameter(torch.ones(2, dtype=torch.bfloat16)))
    prepare_adapter_precision(model)
    assert model.base.dtype == torch.float16
    assert not model.base.requires_grad
    assert model.lora_A.dtype == torch.float32 and model.lora_A.requires_grad
    model.base.requires_grad_(True)
    with pytest.raises(RuntimeError, match="Unexpected trainable base"):
        prepare_adapter_precision(model)
    model.requires_grad_(False)
    with pytest.raises(RuntimeError, match="No trainable LoRA"):
        prepare_adapter_precision(model)

