"""Loader for the public Meddies Consultant dataset on Hugging Face.

The dataset is synthetic and licensed CC BY-NC 4.0. It is suitable for
research and model-development experiments, not as cited clinical guidance.
"""

from collections.abc import Iterator, Mapping
from typing import Any, Literal, cast

from datasets import Dataset, IterableDataset, load_dataset

DATASET_ID = "Meddies/meddies-consultant"
DatasetConfig = Literal["vietnamese", "english", "RandomQA", "RandomQuestion"]

CONFIG_SCHEMAS: dict[DatasetConfig, frozenset[str]] = {
    "vietnamese": frozenset(
        {"id", "subset", "messages", "target_disease", "turns_count", "patient_persona"}
    ),
    "english": frozenset(
        {"id", "subset", "messages", "target_disease", "turns_count", "patient_persona"}
    ),
    "RandomQA": frozenset(
        {"id", "messages", "question", "answer", "category", "complexity", "turns_count"}
    ),
    "RandomQuestion": frozenset(
        {"id", "messages", "question", "category", "complexity", "turns_count"}
    ),
}


def load_meddies_dataset(
    config: DatasetConfig = "vietnamese",
    *,
    split: str = "train",
    streaming: bool = True,
    revision: str | None = None,
    token: str | None = None,
    cache_dir: str | None = None,
) -> Dataset | IterableDataset:
    """Load one Meddies Consultant config with an explicit split.

    Streaming is enabled by default because the complete repository is much
    larger than a small preview. Pass ``streaming=False`` only when a local
    Arrow dataset is required for training operations such as random access.
    """

    if config not in CONFIG_SCHEMAS:
        allowed = ", ".join(CONFIG_SCHEMAS)
        raise ValueError(f"Unknown config {config!r}. Expected one of: {allowed}")
    if split != "train":
        raise ValueError("Meddies Consultant currently publishes only the 'train' split")

    dataset = load_dataset(
        DATASET_ID,
        name=config,
        split=split,
        streaming=streaming,
        revision=revision,
        token=token,
        cache_dir=cache_dir,
    )
    return cast(Dataset | IterableDataset, dataset)


def validate_row(row: Mapping[str, Any], config: DatasetConfig) -> None:
    """Fail early when the remote schema no longer matches this application."""

    missing = CONFIG_SCHEMAS[config].difference(row)
    if missing:
        raise ValueError(f"Dataset row is missing required fields: {sorted(missing)}")

    messages = row.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("Dataset field 'messages' must be a non-empty list")
    for index, message in enumerate(messages):
        if not isinstance(message, Mapping):
            raise ValueError(f"messages[{index}] must be an object")
        if not isinstance(message.get("role"), str) or not isinstance(message.get("content"), str):
            raise ValueError(f"messages[{index}] must contain string 'role' and 'content' fields")


def iter_validated_rows(
    dataset: Dataset | IterableDataset,
    config: DatasetConfig,
    *,
    limit: int | None = None,
) -> Iterator[Mapping[str, Any]]:
    """Iterate over validated rows without materializing a streaming dataset."""

    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")

    for index, row in enumerate(dataset):
        if limit is not None and index >= limit:
            break
        validate_row(row, config)
        yield row
