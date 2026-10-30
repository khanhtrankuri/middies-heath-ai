from __future__ import annotations

from app.services.rag.context_budget import trim_conversation


def test_context_trimming_keeps_active_request_and_recent_history() -> None:
    active = "Đây là yêu cầu hiện tại và không được cắt. " * 50
    messages = [
        {"role": "user", "content": "old " * 1000},
        {"role": "assistant", "content": "recent assistant"},
        {"role": "user", "content": active},
    ]

    trimmed = trim_conversation(messages, max_older_tokens=20)

    assert trimmed[-1]["content"] == active
    assert any(item["content"] == "recent assistant" for item in trimmed)
    assert all(item["content"] != "old " * 1000 for item in trimmed)
