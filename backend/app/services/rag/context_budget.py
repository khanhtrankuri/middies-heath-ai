from __future__ import annotations

from collections.abc import Sequence

from .config import RetrievedChunk


def estimate_tokens(text: str) -> int:
    """Conservative tokenizer-independent estimate for Vietnamese/English text."""

    return max(1, (len(text) + 2) // 3)


def trim_conversation(
    messages: Sequence[dict[str, str]], *, max_older_tokens: int = 768
) -> list[dict[str, str]]:
    """Keep the active user request intact and retain only recent history that fits."""

    if not messages:
        return []
    active_index = next(
        (index for index in range(len(messages) - 1, -1, -1) if messages[index].get("role") == "user"),
        len(messages) - 1,
    )
    active = messages[active_index]
    selected_indices = {active_index}
    remaining = max_older_tokens
    for index in range(active_index - 1, -1, -1):
        cost = estimate_tokens(messages[index].get("content", ""))
        if cost > remaining:
            continue
        selected_indices.add(index)
        remaining -= cost
    return [messages[index] for index in sorted(selected_indices)] + list(messages[active_index + 1 :])


def select_chunks_within_budget(
    chunks: Sequence[RetrievedChunk],
    *,
    system_prompt: str,
    messages: Sequence[dict[str, str]],
    patient_summary: str,
    max_context_tokens: int = 4096,
    generation_reserve: int = 512,
) -> list[RetrievedChunk]:
    active_user = next(
        (item["content"] for item in reversed(messages) if item.get("role") == "user"), ""
    )
    # The active request is always fully reserved. Older history is budgeted but may be omitted.
    fixed = estimate_tokens(system_prompt) + estimate_tokens(active_user) + estimate_tokens(
        patient_summary
    )
    older = [item["content"] for item in messages[:-1]]
    history_cost = sum(estimate_tokens(item) for item in older)
    remaining = max_context_tokens - generation_reserve - fixed - history_cost
    selected: list[RetrievedChunk] = []
    for chunk in chunks:
        cost = estimate_tokens(chunk.text) + 32
        if cost > remaining:
            continue
        selected.append(chunk)
        remaining -= cost
    return selected
