"""Fail closed before E5C training if prepared split provenance has changed."""
import hashlib
import json
from pathlib import Path

from app.services.dialogue.prompts import PLANNER_PROMPT_VERSION, PLANNER_SYSTEM_PROMPT
from training.data.prepare_dialogue import DEFAULT_REVISION


def verify_prepared(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest["dataset_revision"] != DEFAULT_REVISION or manifest["prompt_version"] != PLANNER_PROMPT_VERSION:
        raise ValueError("Prepared planner data uses a different revision or prompt")
    if manifest["allow_unreviewed_templates"]:
        raise ValueError("E5C default training excludes unreviewed template labels")
    conversations = {}
    for split in ("train", "validation"):
        path = directory / f"{split}.jsonl"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != manifest["output_sha256"][path.name]:
            raise ValueError("Prepared planner split hash mismatch")
        conversations[split] = set()
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                meta = row["metadata"]
                if meta["split"] != split or meta["system_prompt_version"] != PLANNER_PROMPT_VERSION:
                    raise ValueError("Invalid planner row split or prompt")
                if meta["label_source"] != "auto_filtered_dataset_question":
                    raise ValueError("Unexpected label provenance")
                if [m["role"] for m in row["messages"]] != ["system", "user", "assistant"]:
                    raise ValueError("Planner SFT must supervise only the final assistant question")
                if not row["messages"][0]["content"].startswith(PLANNER_SYSTEM_PROMPT):
                    raise ValueError("Training/inference system prompt mismatch")
                conversations[split].add(row["conversation_id"])
    if conversations["train"] & conversations["validation"]:
        raise ValueError("Train/validation conversation leakage")
    return manifest
