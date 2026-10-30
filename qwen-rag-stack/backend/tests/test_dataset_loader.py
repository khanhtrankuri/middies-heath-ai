from unittest.mock import patch

import pytest

from app.dataset_loader import DATASET_ID, iter_validated_rows, load_meddies_dataset, validate_row


CONSULTATION_ROW = {
    "id": "example-id",
    "subset": "vietnamese",
    "messages": [
        {"role": "assistant", "content": "Chào bạn."},
        {"role": "user", "content": "Tôi bị đau đầu."},
    ],
    "target_disease": "Đau đầu",
    "turns_count": 2,
    "patient_persona": "Example persona",
}


@patch("app.dataset_loader.load_dataset")
def test_loads_named_config_in_streaming_mode(mock_load_dataset) -> None:
    expected = object()
    mock_load_dataset.return_value = expected

    result = load_meddies_dataset("vietnamese")

    assert result is expected
    mock_load_dataset.assert_called_once_with(
        DATASET_ID,
        name="vietnamese",
        split="train",
        streaming=True,
        revision=None,
        token=None,
        cache_dir=None,
    )


def test_rejects_nonexistent_split_without_downloading() -> None:
    with pytest.raises(ValueError, match="only the 'train' split"):
        load_meddies_dataset("vietnamese", split="validation")


def test_validates_consultation_schema() -> None:
    validate_row(CONSULTATION_ROW, "vietnamese")


def test_rejects_invalid_messages() -> None:
    row = {**CONSULTATION_ROW, "messages": [{"role": "user"}]}
    with pytest.raises(ValueError, match="role.*content"):
        validate_row(row, "vietnamese")


def test_limits_stream_without_materializing_all_rows() -> None:
    rows = (CONSULTATION_ROW for _ in range(10))
    assert len(list(iter_validated_rows(rows, "vietnamese", limit=2))) == 2
