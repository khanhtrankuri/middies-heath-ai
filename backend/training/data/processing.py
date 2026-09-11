from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import torch

THINK_PATTERN = re.compile(r"<think>.*?</think>", flags=re.IGNORECASE | re.DOTALL)
LEADING_REASONING_PATTERN = re.compile(r"^.*?</think>", flags=re.IGNORECASE | re.DOTALL)
ORPHAN_THINK_TAG = re.compile(r"</?think>", flags=re.IGNORECASE)
ALLOWED_ROLES = {"system", "user", "assistant"}


def clean_messages(messages: Any) -> list[dict[str, str]] | None:
    if not isinstance(messages, list) or not messages:
        return None
    cleaned: list[dict[str, str]] = []
    for item in messages:
        if not isinstance(item, Mapping):
            return None
        role = item.get("role")
        content = item.get("content")
        if role not in ALLOWED_ROLES or not isinstance(content, str):
            return None
        content = THINK_PATTERN.sub("", content).strip()
        # Some source rows contain a malformed reasoning opener but a valid
        # closing tag. Drop that entire private prefix rather than teaching it.
        content = LEADING_REASONING_PATTERN.sub("", content).strip()
        if ORPHAN_THINK_TAG.search(content):
            return None
        if not content:
            return None
        cleaned.append({"role": role, "content": content})
    if not any(message["role"] == "assistant" for message in cleaned):
        return None
    return cleaned


def conversation_key(messages: Sequence[Mapping[str, str]]) -> str:
    canonical = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def deterministic_split(key: str, validation_ratio: float, *, seed: int = 42) -> str:
    if not 0 < validation_ratio < 1:
        raise ValueError("validation_ratio must be between 0 and 1")
    seeded_key = hashlib.sha256(f"{seed}:{key}".encode("utf-8")).hexdigest()
    bucket = int(seeded_key[:8], 16) / 0xFFFFFFFF
    return "validation" if bucket < validation_ratio else "train"


def load_jsonl_rows(
    paths: Iterable[str | Path], *, limit: int | None = None
) -> list[dict[str, Any]]:
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")
    rows: list[dict[str, Any]] = []
    for path in paths:
        with Path(path).open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict) or not isinstance(value.get("messages"), list):
                    raise ValueError(f"Invalid prepared row at {path}:{line_number}")
                rows.append(value)
                if limit is not None and len(rows) >= limit:
                    return rows
    return rows


def _chat_ids(tokenizer: Any, messages: list[dict[str, str]], add_generation_prompt: bool) -> list[int]:
    arguments = {
        "tokenize": True,
        "add_generation_prompt": add_generation_prompt,
    }
    try:
        # Qwen3 thinking prompts alter the assistant prefix and make boundaries unstable.
        result = tokenizer.apply_chat_template(messages, enable_thinking=False, **arguments)
    except TypeError:
        result = tokenizer.apply_chat_template(messages, **arguments)
    if isinstance(result, torch.Tensor):
        result = result.tolist()
    if result and isinstance(result[0], list):
        result = result[0]
    return list(result)


def tokenize_with_assistant_only_loss(
    tokenizer: Any,
    messages: list[dict[str, str]],
    *,
    max_length: int,
) -> dict[str, list[int]]:
    """Tokenize a chat and mask every token not emitted by the assistant."""

    if not messages:
        raise ValueError("messages cannot be empty")
    template_arguments = {"tokenize": False, "add_generation_prompt": False}
    try:
        rendered = tokenizer.apply_chat_template(
            messages, enable_thinking=False, **template_arguments
        )
    except TypeError:
        rendered = tokenizer.apply_chat_template(messages, **template_arguments)

    if isinstance(rendered, str):
        marked_messages = [dict(message) for message in messages]
        markers: list[tuple[str, str, str]] = []
        for index, message in enumerate(messages):
            if message["role"] != "assistant":
                continue
            digest = hashlib.sha256(f"{index}:{message['content']}".encode("utf-8")).hexdigest()[:16]
            start_marker = f"<MEDDIES_ASSISTANT_{digest}_START>"
            end_marker = f"<MEDDIES_ASSISTANT_{digest}_END>"
            if start_marker in rendered or end_marker in rendered:
                raise ValueError("Unexpected assistant span marker collision")
            marked_messages[index]["content"] = start_marker + message["content"] + end_marker
            markers.append((start_marker, end_marker, message["content"]))
        try:
            marked_rendered = tokenizer.apply_chat_template(
                marked_messages, enable_thinking=False, **template_arguments
            )
        except TypeError:
            marked_rendered = tokenizer.apply_chat_template(marked_messages, **template_arguments)
        if not isinstance(marked_rendered, str):
            raise ValueError("Tokenizer must render its chat template as text for exact loss masking")

        spans: list[tuple[int, int]] = []
        cursor = 0
        removed_characters = 0
        stripped = marked_rendered
        for start_marker, end_marker, content in markers:
            marker_start = marked_rendered.find(start_marker, cursor)
            content_start = marker_start + len(start_marker)
            marker_end = marked_rendered.find(end_marker, content_start)
            if marker_start < 0 or marker_end < 0 or marked_rendered[content_start:marker_end] != content:
                raise ValueError(
                    "Could not locate assistant span markers in the rendered chat template; "
                    "assistant-only masking cannot be guaranteed"
                )
            start = content_start - removed_characters - len(start_marker)
            spans.append((start, start + len(content)))
            removed_characters += len(start_marker) + len(end_marker)
            cursor = marker_end + len(end_marker)
            stripped = stripped.replace(start_marker, "", 1).replace(end_marker, "", 1)
        if stripped != rendered:
            raise ValueError(
                "Chat template changed when assistant span markers were inserted; "
                "assistant-only masking cannot be guaranteed"
            )
        encoded = tokenizer(
            rendered,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=True,
            max_length=max_length,
        )
        input_ids = list(encoded["input_ids"])
        offsets = encoded.get("offset_mapping")
        if offsets is None or len(offsets) != len(input_ids):
            raise ValueError("A fast tokenizer with offset mappings is required for exact loss masking")
        labels = [
            token_id
            if any(
                token_start < span_end and token_end > span_start
                for span_start, span_end in spans
            )
            else -100
            for token_id, (token_start, token_end) in zip(input_ids, offsets, strict=True)
        ]
        if all(label == -100 for label in labels):
            raise ValueError("No assistant tokens remain after truncation")
        return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels}

    # Minimal tokenizer fallback used by unit tests. It validates prefix stability
    # and refuses templates (such as context-sensitive multi-turn templates) that
    # cannot guarantee exact boundaries.
    input_ids = _chat_ids(tokenizer, messages, add_generation_prompt=False)[:max_length]
    labels = [-100] * len(input_ids)

    for index, message in enumerate(messages):
        if message["role"] != "assistant":
            continue
        before = _chat_ids(tokenizer, messages[:index], add_generation_prompt=True)
        after = _chat_ids(tokenizer, messages[: index + 1], add_generation_prompt=False)
        start = min(len(before), len(input_ids))
        end = min(len(after), len(input_ids))
        if start >= len(input_ids):
            continue
        if start >= end or input_ids[:start] != before[:start]:
            raise ValueError(
                "Tokenizer chat template does not provide stable assistant boundaries; "
                "assistant-only masking cannot be guaranteed"
            )
        labels[start:end] = input_ids[start:end]

    if all(label == -100 for label in labels):
        raise ValueError("No assistant tokens remain after truncation")
    return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids), "labels": labels}


def pack_tokenized_examples(
    examples: Sequence[dict[str, list[int]]], *, max_length: int, eos_token_id: int
) -> list[dict[str, list[int]]]:
    """Pack complete masked streams while preserving their label boundaries."""

    packed: list[dict[str, list[int]]] = []
    current = {"input_ids": [], "attention_mask": [], "labels": []}
    for example in examples:
        ids = example["input_ids"] + [eos_token_id]
        labels = example["labels"] + [-100]
        offset = 0
        while offset < len(ids):
            remaining = max_length - len(current["input_ids"])
            take = min(remaining, len(ids) - offset)
            current["input_ids"].extend(ids[offset : offset + take])
            current["attention_mask"].extend([1] * take)
            current["labels"].extend(labels[offset : offset + take])
            offset += take
            if len(current["input_ids"]) == max_length:
                packed.append(current)
                current = {"input_ids": [], "attention_mask": [], "labels": []}
    if current["input_ids"]:
        packed.append(current)
    return packed


class AssistantOnlyDataCollator:
    def __init__(self, tokenizer: Any, pad_to_multiple_of: int = 8) -> None:
        self.tokenizer = tokenizer
        self.pad_to_multiple_of = pad_to_multiple_of

    def __call__(self, features: list[dict[str, list[int]]]) -> dict[str, torch.Tensor]:
        max_length = max(len(feature["input_ids"]) for feature in features)
        multiple = self.pad_to_multiple_of
        max_length = ((max_length + multiple - 1) // multiple) * multiple
        pad_id = self.tokenizer.pad_token_id
        if pad_id is None:
            raise ValueError("Tokenizer must have a pad token")
        right_padding = self.tokenizer.padding_side != "left"
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for feature in features:
            padding = max_length - len(feature["input_ids"])
            if right_padding:
                batch["input_ids"].append(feature["input_ids"] + [pad_id] * padding)
                batch["attention_mask"].append(feature["attention_mask"] + [0] * padding)
                batch["labels"].append(feature["labels"] + [-100] * padding)
            else:
                batch["input_ids"].append([pad_id] * padding + feature["input_ids"])
                batch["attention_mask"].append([0] * padding + feature["attention_mask"])
                batch["labels"].append([-100] * padding + feature["labels"])
        return {key: torch.tensor(value, dtype=torch.long) for key, value in batch.items()}
