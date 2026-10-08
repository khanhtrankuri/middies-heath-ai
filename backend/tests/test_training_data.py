from training.data.processing import (
    AssistantOnlyDataCollator,
    clean_messages,
    conversational_windows,
    load_jsonl_rows,
    pack_tokenized_examples,
    tokenize_with_assistant_only_loss,
)


class FakeChatTokenizer:
    pad_token_id = 0
    eos_token_id = 99
    padding_side = "right"

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        if not tokenize:
            # Return a non-string sentinel so processing exercises its minimal
            # tokenizer fallback rather than the fast-tokenizer offset path.
            return []
        result = [10]
        for message in messages:
            if message["role"] == "assistant":
                result.append(90)
            else:
                result.append(80)
            result.extend(ord(character) for character in message["content"])
            result.append(70)
        if add_generation_prompt:
            result.append(90)
        return result


class OffsetChatTokenizer:
    def apply_chat_template(
        self, messages, *, tokenize, add_generation_prompt, enable_thinking=False
    ):
        assert tokenize is False
        assert add_generation_prompt is False
        assert enable_thinking is False
        rendered = ""
        for index, message in enumerate(messages):
            prefix = "USER:" if message["role"] == "user" else "ASSISTANT:"
            # Deliberately make earlier and final assistant wrappers different.
            wrapper = "<old>" if message["role"] == "assistant" and index < len(messages) - 1 else ""
            rendered += f"{prefix}{wrapper}{message['content']}|"
        return rendered

    def __call__(self, rendered, **kwargs):
        assert kwargs["add_special_tokens"] is False
        return {
            "input_ids": [ord(character) for character in rendered],
            "offset_mapping": [(index, index + 1) for index in range(len(rendered))],
        }


def test_assistant_only_loss_masks_user_tokens() -> None:
    tokenizer = FakeChatTokenizer()
    encoded = tokenize_with_assistant_only_loss(
        tokenizer,
        [
            {"role": "user", "content": "pain"},
            {"role": "assistant", "content": "where"},
            {"role": "user", "content": "left"},
            {"role": "assistant", "content": "since"},
        ],
        max_length=128,
    )
    labels = encoded["labels"]
    first_assistant = encoded["input_ids"].index(90)
    assert all(label == -100 for label in labels[:first_assistant])
    assert labels[first_assistant] == -100
    assert labels[first_assistant + 1] == encoded["input_ids"][first_assistant + 1]
    assert any(label != -100 for label in labels)
    for token, label in zip(encoded["input_ids"], labels, strict=True):
        assert label in {-100, token}


def test_offset_masking_handles_context_sensitive_multiturn_template() -> None:
    tokenizer = OffsetChatTokenizer()
    encoded = tokenize_with_assistant_only_loss(
        tokenizer,
        [
            {"role": "user", "content": "USER_ONE"},
            {"role": "assistant", "content": "ANSWER_ONE"},
            {"role": "user", "content": "USER_TWO"},
            {"role": "assistant", "content": "ANSWER_TWO"},
        ],
        max_length=512,
    )
    rendered = "".join(chr(token) for token in encoded["input_ids"])
    for content in ("ANSWER_ONE", "ANSWER_TWO"):
        start = rendered.index(content)
        assert encoded["labels"][start : start + len(content)] == encoded["input_ids"][
            start : start + len(content)
        ]
    for content in ("USER_ONE", "USER_TWO"):
        start = rendered.index(content)
        assert encoded["labels"][start : start + len(content)] == [-100] * len(content)


def test_truncation_rejects_chat_without_assistant_tokens() -> None:
    tokenizer = FakeChatTokenizer()
    try:
        tokenize_with_assistant_only_loss(
            tokenizer,
            [{"role": "user", "content": "a very long user message"}, {"role": "assistant", "content": "ok"}],
            max_length=4,
        )
    except ValueError as error:
        assert "No assistant tokens" in str(error)
    else:
        raise AssertionError("Expected masking validation to reject the truncated sample")


def test_cleaning_removes_think_and_rejects_no_assistant() -> None:
    assert clean_messages(
        [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "<think>private</think> How can I help?"},
        ]
    ) == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "How can I help?"},
    ]
    assert clean_messages([{"role": "user", "content": "Hello"}]) is None
    assert clean_messages([{"role": "assistant", "content": "Hello"}]) is None


def test_prepared_loader_skips_conversations_without_user(tmp_path) -> None:
    path = tmp_path / "prepared.jsonl"
    path.write_text(
        '{"id":"bad","messages":[{"role":"assistant","content":"orphan"}]}\n'
        '{"id":"good","messages":[{"role":"user","content":"hello"},'
        '{"role":"assistant","content":"hi"}]}\n',
        encoding="utf-8",
    )

    rows = load_jsonl_rows([path])

    assert [row["id"] for row in rows] == ["good"]


def test_cleaning_removes_malformed_reasoning_prefix() -> None:
    assert clean_messages(
        [
            {"role": "user", "content": "Hello"},
            {
                "role": "assistant",
                "content": "<internal_reasoning>private chain</think>Visible response",
            },
        ]
    )[-1]["content"] == "Visible response"
    assert clean_messages(
        [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "<think>unclosed reasoning"},
        ]
    ) is None


def test_packing_preserves_masks_and_collator_masks_padding() -> None:
    examples = [
        {"input_ids": [1, 2], "attention_mask": [1, 1], "labels": [-100, 2]},
        {"input_ids": [3], "attention_mask": [1], "labels": [3]},
    ]
    packed = pack_tokenized_examples(examples, max_length=8, eos_token_id=99)
    assert packed[0]["labels"] == [-100, 2, -100, 3, -100]
    batch = AssistantOnlyDataCollator(FakeChatTokenizer())(packed)
    assert batch["input_ids"].shape == (1, 8)
    assert batch["labels"][0, -1].item() == -100


def test_long_conversation_becomes_overlapping_supervised_windows() -> None:
    tokenizer = FakeChatTokenizer()
    messages = []
    for index in range(5):
        messages.extend([
            {"role": "user", "content": f"u{index}"},
            {"role": "assistant", "content": f"a{index}"},
        ])
    windows = conversational_windows(tokenizer, messages, max_length=19, overlap_turns=1)
    assert len(windows) > 1
    supervised_answers = [
        item["content"] for window in windows for item in window if item["role"] == "assistant"
    ]
    assert set(supervised_answers) == {f"a{index}" for index in range(5)}
    assert any(
        set(item["content"] for item in left) & set(item["content"] for item in right)
        for left, right in zip(windows, windows[1:])
    )


def test_packing_never_labels_separator_or_splits_samples() -> None:
    examples = [
        {"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1], "labels": [-100, 2, 3]},
        {"input_ids": [4, 5, 6], "attention_mask": [1, 1, 1], "labels": [-100, 5, 6]},
    ]
    packed = pack_tokenized_examples(examples, max_length=4, eos_token_id=99)
    assert [item["input_ids"] for item in packed] == [[1, 2, 3, 99], [4, 5, 6, 99]]
    assert all(item["labels"][-1] == -100 for item in packed)
