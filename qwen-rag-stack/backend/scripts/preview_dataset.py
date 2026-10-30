"""Stream and print a small, schema-validated dataset preview."""

import argparse
import json
from typing import cast

from app.dataset_loader import DatasetConfig, CONFIG_SCHEMAS, iter_validated_rows, load_meddies_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", choices=CONFIG_SCHEMAS, default="vietnamese")
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download/materialize the selected config instead of streaming it.",
    )
    parser.add_argument("--revision", help="Optional Hub branch, tag, or commit hash.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = cast(DatasetConfig, args.config)
    dataset = load_meddies_dataset(
        config,
        streaming=not args.download,
        revision=args.revision,
    )
    for row in iter_validated_rows(dataset, config, limit=args.limit):
        print(json.dumps(row, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
