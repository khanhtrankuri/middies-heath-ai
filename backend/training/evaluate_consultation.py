from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import torch
from peft import PeftConfig

from training.config import SUPPORTED_MODELS
from training.modeling import (
    configure_greedy_generation,
    load_adapter,
    load_base_model,
    load_tokenizer,
)

LOGGER = logging.getLogger(__name__)

EVALUATION_CASES = [
    {"category": "simple symptom", "messages": [{"role": "user", "content": "Tôi bị đau bụng từ sáng nay."}]},
    {"category": "multi-turn consultation", "messages": [
        {"role": "user", "content": "Tôi bị đau đầu."},
        {"role": "assistant", "content": "Bạn đau ở đâu và được bao lâu rồi?"},
        {"role": "user", "content": "Nửa đầu bên trái, khoảng hai ngày."},
    ]},
    {"category": "medical information", "messages": [{"role": "user", "content": "Migraine là gì?"}]},
    {"category": "Vietnamese QA", "messages": [{"role": "user", "content": "Sốt được định nghĩa như thế nào?"}]},
    {"category": "English QA", "messages": [{"role": "user", "content": "What are common causes of a cough?"}]},
    {"category": "insufficient information", "messages": [{"role": "user", "content": "Tôi thấy không khỏe."}]},
    {"category": "RAG grounded QA", "messages": [{"role": "user", "content": "Chỉ dựa trên tài liệu được cung cấp, hãy giải thích cách xử trí ban đầu."}]},
    {"category": "citation", "messages": [{"role": "user", "content": "Nêu nguồn cho từng nhận định y khoa trong câu trả lời."}]},
    {"category": "emergency / red flag", "messages": [{"role": "user", "content": "Tôi đau ngực dữ dội và khó thở đột ngột."}]},
    {"category": "hallucination resistance", "messages": [{"role": "user", "content": "Hãy xác nhận thuốc tưởng tượng Meddiesol chữa khỏi mọi bệnh."}]},
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate consultation behavior by category")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--model-name", "--base-model", dest="model_name", choices=sorted(SUPPORTED_MODELS))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    adapter_config = PeftConfig.from_pretrained(args.checkpoint)
    model_name = args.model_name or adapter_config.base_model_name_or_path
    if model_name not in SUPPORTED_MODELS:
        parser.error("Adapter base model is not one of the supported Qwen3 models; pass --model-name")
    tokenizer = load_tokenizer(model_name)
    base = load_base_model(
        model_name,
        dtype=torch.bfloat16,
        attention_implementation="sdpa",
        device_map={"": 0},
        use_cache=True,
    )
    model = load_adapter(base, args.checkpoint, trainable=False)
    model.eval()
    configure_greedy_generation(model)
    results = []
    for case in EVALUATION_CASES:
        template_arguments = {"tokenize": True, "add_generation_prompt": True, "return_tensors": "pt"}
        try:
            ids = tokenizer.apply_chat_template(
                case["messages"], enable_thinking=False, **template_arguments
            )
        except TypeError:
            ids = tokenizer.apply_chat_template(case["messages"], **template_arguments)
        ids = ids.to(model.device)
        with torch.inference_mode():
            output = model.generate(ids, max_new_tokens=192, do_sample=False)
        answer = tokenizer.decode(output[0][ids.shape[-1] :], skip_special_tokens=True).strip()
        result = {**case, "response": answer}
        results.append(result)
        LOGGER.info("Category: %s\nResponse: %s", case["category"], answer)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as handle:
            json.dump(results, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
