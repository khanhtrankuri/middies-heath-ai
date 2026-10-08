from pathlib import Path

import pytest
import torch

from training.train_kaggle_t4 import (
    DATASET_MIX,
    distributed_ranks,
    parse_args,
    prepare_adapter_precision,
    trainer_kwargs,
    validate_paths,
)


def test_t4_profile_and_smoke_limits() -> None:
    args = parse_args(
        ["--data-dir", "processed", "--smoke-test", "--max-train-samples", "0"]
    )
    config = trainer_kwargs(args, 1)

    assert args.max_train_samples == 100
    assert args.max_eval_samples == 30
    assert config["max_steps"] == 3
    assert config["fp16"] and not config["bf16"] and not config["tf32"]
    assert config["local_rank"] == 1
    assert config["ddp_backend"] == "nccl"
    assert config["ddp_find_unused_parameters"] is False
    assert config["dataloader_num_workers"] == 0
    assert config["gradient_checkpointing_kwargs"] == {"use_reentrant": False}
    effective_batch = (
        config["per_device_train_batch_size"]
        * config["gradient_accumulation_steps"]
        * 2
    )
    assert effective_batch == 16


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--max-seq-length", "127"),
        ("--max-seq-length", "129"),
        ("--gradient-accumulation-steps", "0"),
        ("--max-steps", "0"),
        ("--max-train-samples", "-1"),
        ("--lora-r", "0"),
        ("--lora-dropout", "1"),
    ],
)
def test_rejects_invalid_training_options(option: str, value: str) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--data-dir", "processed", option, value])


def test_requires_exactly_two_local_torchrun_workers() -> None:
    for rank in ("0", "1"):
        environment = {
            "WORLD_SIZE": "2",
            "LOCAL_WORLD_SIZE": "2",
            "LOCAL_RANK": rank,
            "RANK": rank,
        }
        assert distributed_ranks(environment) == (int(rank), int(rank))

    invalid_environments = (
        {},
        {"WORLD_SIZE": "1"},
        {
            "WORLD_SIZE": "2",
            "LOCAL_WORLD_SIZE": "1",
            "LOCAL_RANK": "0",
            "RANK": "0",
        },
    )
    for environment in invalid_environments:
        with pytest.raises(RuntimeError, match="torchrun"):
            distributed_ranks(environment)


def test_preflight_preserves_outputs_and_rejects_partial_checkpoint(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "processed"
    output_dir = tmp_path / "output"
    args = parse_args(
        ["--data-dir", str(data_dir), "--output-dir", str(output_dir)]
    )
    with pytest.raises(FileNotFoundError, match="Missing prepared data"):
        validate_paths(args)

    for source in DATASET_MIX:
        (data_dir / source).mkdir(parents=True)
        for split in ("train", "validation"):
            (data_dir / source / f"{split}.jsonl").touch()
    validate_paths(args)

    output_dir.mkdir()
    marker = output_dir / "keep.txt"
    marker.write_text("existing output", encoding="utf-8")
    with pytest.raises(ValueError, match="not empty"):
        validate_paths(args)

    args.resume_from_checkpoint = tmp_path / "partial-checkpoint"
    args.resume_from_checkpoint.mkdir()
    (args.resume_from_checkpoint / "adapter_config.json").write_text(
        "{}", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="complete resumable"):
        validate_paths(args)
    assert marker.read_text(encoding="utf-8") == "existing output"


def test_fp16_amp_keeps_only_lora_parameters_trainable_in_fp32() -> None:
    model = torch.nn.Module()
    model.register_parameter(
        "base",
        torch.nn.Parameter(torch.ones(2, dtype=torch.float16), requires_grad=False),
    )
    model.register_parameter(
        "lora_A", torch.nn.Parameter(torch.ones(2, dtype=torch.bfloat16))
    )

    prepare_adapter_precision(model)

    assert model.base.dtype == torch.float16
    assert not model.base.requires_grad
    assert model.lora_A.dtype == torch.float32
    assert model.lora_A.requires_grad

    model.base.requires_grad_(True)
    with pytest.raises(RuntimeError, match="Unexpected trainable base"):
        prepare_adapter_precision(model)
    model.requires_grad_(False)
    with pytest.raises(RuntimeError, match="No trainable LoRA"):
        prepare_adapter_precision(model)
