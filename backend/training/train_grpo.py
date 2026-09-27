"""GRPO entry point boundary; reward functions are intentionally not implemented yet."""

from __future__ import annotations

import argparse

from training.config import add_training_overrides, apply_cli_overrides, load_config, validate_training_config


def resolve_config(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Validate configuration for a future GRPO stage")
    parser.add_argument("--config", required=True)
    add_training_overrides(parser)
    args = parser.parse_args(argv)
    config = apply_cli_overrides(load_config(args.config), args)
    validate_training_config(config)
    return config


def main() -> None:
    resolve_config()
    raise NotImplementedError("GRPO is not implemented; verifiable reward functions are still required")


if __name__ == "__main__":
    main()
