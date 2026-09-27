from __future__ import annotations

import json

from training.data.prepare_meddies import _qa_messages, prepare_config


def test_qa_fallback_sanitizes_reasoning_tags() -> None:
    assert _qa_messages(
        {
            "question": "What should I do?",
            "answer": "<think>private reasoning</think> Contact a clinician.",
        }
    ) == [
        {"role": "user", "content": "What should I do?"},
        {"role": "assistant", "content": "Contact a clinician."},
    ]
    assert _qa_messages(
        {
            "question": "What should I do?",
            "answer": "<think>unclosed private reasoning",
        }
    ) is None


def test_random_question_is_preserved_as_prompt_not_sft(monkeypatch, tmp_path) -> None:
    rows = [
        {"id": "q1", "question": "What should I ask a doctor?", "messages": []},
        {"id": "q1-duplicate", "question": "What should I ask a doctor?", "messages": []},
        {"id": "bad", "question": "", "messages": []},
    ]
    monkeypatch.setattr(
        "training.data.prepare_meddies.load_meddies_dataset", lambda *args, **kwargs: rows
    )
    stats = prepare_config(
        "RandomQuestion", tmp_path, validation_ratio=0.5, max_samples=None, seed=42
    )
    assert stats == {
        "total_seen": 3,
        "valid": 1,
        "invalid": 1,
        "duplicates": 1,
        "train": stats["train"],
        "validation": stats["validation"],
    }
    assert stats["train"] + stats["validation"] == 1
    assert not (tmp_path / "RandomQuestion" / "train.jsonl").exists()
    prompt_files = list((tmp_path / "RandomQuestion").glob("prompts_*.jsonl"))
    saved = [json.loads(line) for path in prompt_files for line in path.read_text(encoding="utf-8").splitlines()]
    assert saved[0]["usage"] == "rag_or_preference_prompt"
    assert saved[0]["messages"] == [{"role": "user", "content": "What should I ask a doctor?"}]
