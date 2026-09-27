"""DPO entry point boundary; dataset/reward policy is intentionally not implemented yet."""

from __future__ import annotations

import argparse

from training.config import add_training_overrides, apply_cli_overrides, load_config, validate_training_config


def resolve_config(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="Validate configuration for a future DPO stage")
    parser.add_argument("--config", required=True)
    add_training_overrides(parser)
    args = parser.parse_args(argv)
    config = apply_cli_overrides(load_config(args.config), args)
    validate_training_config(config)
    return config


def main() -> None:
    resolve_config()
    raise NotImplementedError("DPO is not implemented; preference data and policy are still required")


if __name__ == "__main__":
    main()
