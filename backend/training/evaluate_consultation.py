from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from training.modeling import configure_greedy_generation

LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a small consultation behavior evaluation")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--base-model", default="Qwen/Qwen3-8B")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        quantization_config=quantization,
        dtype=torch.bfloat16,
        device_map={"": 0},
        attn_implementation="sdpa",
    )
    model = PeftModel.from_pretrained(model, args.checkpoint)
    configure_greedy_generation(model)
    prompts = [
        "Tôi bị đau bụng.",
        "Tôi đau đầu từ sáng nay.",
        "I have had a cough for two days.",
    ]
    results = []
    for prompt in prompts:
        messages = [{"role": "user", "content": prompt}]
        template_arguments = {
            "tokenize": True,
            "add_generation_prompt": True,
            "return_tensors": "pt",
        }
        try:
            ids = tokenizer.apply_chat_template(
                messages, enable_thinking=False, **template_arguments
            )
        except TypeError:
            ids = tokenizer.apply_chat_template(messages, **template_arguments)
        ids = ids.to(model.device)
        with torch.inference_mode():
            output = model.generate(ids, max_new_tokens=128, do_sample=False)
        answer = tokenizer.decode(output[0][ids.shape[-1] :], skip_special_tokens=True)
        results.append({"prompt": prompt, "response": answer})
        LOGGER.info("Prompt: %s\nResponse: %s", prompt, answer)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as handle:
            json.dump(results, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
