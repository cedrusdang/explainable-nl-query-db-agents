"""Qwen2.5-7B-Instruct client using Hugging Face Inference API.

This script provides a ChatGPT-like input interface (messages[] with role/content).
Unsupported fields are logged as warnings.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

LOCAL_MODEL = None
LOCAL_TOKENIZER = None


def _load_local_model(model: str):
    global LOCAL_MODEL, LOCAL_TOKENIZER
    if LOCAL_MODEL is not None and LOCAL_TOKENIZER is not None:
        return LOCAL_MODEL, LOCAL_TOKENIZER

    from transformers import AutoModelForCausalLM, AutoTokenizer

    LOCAL_MODEL = AutoModelForCausalLM.from_pretrained(
        model,
        torch_dtype="auto",
        device_map="auto",
    )
    LOCAL_TOKENIZER = AutoTokenizer.from_pretrained(model)
    return LOCAL_MODEL, LOCAL_TOKENIZER

DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_API_URL = f"https://api-inference.huggingface.co/models/{DEFAULT_MODEL}"

UNSUPPORTED_FIELDS = {
    "stop",
    "logprobs",
    "top_logprobs",
    "frequency_penalty",
    "presence_penalty",
    "n",
    "response_format",
    "tools",
    "tool_choice",
    "seed",
    "stream",
}


def _build_prompt(messages: List[Dict[str, str]]) -> str:
    parts: List[str] = []
    for msg in messages:
        role = (msg.get("role") or "").lower()
        content = msg.get("content") or ""
        if role == "system":
            parts.append(f"System: {content}")
        elif role == "user":
            parts.append(f"User: {content}")
        elif role == "assistant":
            parts.append(f"Assistant: {content}")
        else:
            parts.append(f"User: {content}")
    parts.append("Assistant:")
    return "\n".join(parts)


def _load_config(config_path: str) -> Dict[str, Any]:
    if os.path.exists(config_path) and os.path.getsize(config_path) > 0:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            return {}
    return {}


def _pick_config_value(config: Dict[str, Any], key: str, default: Any) -> Any:
    if key in config:
        return config[key]
    return default


def chat_completion(
    *,
    messages: List[Dict[str, str]],
    api_key: Optional[str] = None,
    api_url: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    top_p: float = 1.0,
    max_tokens: int = 512,
    timeout_sec: int = 60,
    extra_params: Optional[Dict[str, Any]] = None,
    warn_unsupported: bool = True,
) -> Dict[str, Any]:
    if extra_params is None:
        extra_params = {}

    if warn_unsupported:
        unsupported = [k for k in extra_params.keys() if k in UNSUPPORTED_FIELDS]
        if unsupported:
            print(f"[WARN] Unsupported fields ignored: {unsupported}")

    url = api_url or DEFAULT_API_URL
    if url == "local":
        import torch

        model_obj, tokenizer = _load_local_model(model)
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        model_inputs = tokenizer([text], return_tensors="pt").to(model_obj.device)
        started = time.time()
        with torch.no_grad():
            generated_ids = model_obj.generate(
                **model_inputs,
                max_new_tokens=max_tokens,
                do_sample=temperature > 0,
                temperature=temperature,
                top_p=top_p,
            )
        elapsed = time.time() - started
        generated_ids = [
            output_ids[len(input_ids):]
            for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
        ]
        text = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
    else:
        prompt = _build_prompt(messages)
        headers = {
            "Authorization": f"Bearer {api_key}" if api_key else "",
            "Content-Type": "application/json",
        }

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "return_full_text": False,
            },
        }

        if temperature == 0:
            payload["parameters"]["do_sample"] = False

        started = time.time()
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
        elapsed = time.time() - started

        if not response.ok:
            raise RuntimeError(f"HF Inference API error {response.status_code}: {response.text}")

        data = response.json()
        if isinstance(data, list) and data:
            text = data[0].get("generated_text", "")
        elif isinstance(data, dict) and "generated_text" in data:
            text = data.get("generated_text", "")
        else:
            text = ""

    return {
        "id": "qwen-hf-inference",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "latency_sec": round(elapsed, 3),
        },
    }


def _load_messages(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "messages" in data:
        return data["messages"]
    if isinstance(data, list):
        return data
    raise ValueError("Messages must be a list or contain a 'messages' key.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Qwen2.5 HF Inference client")
    parser.add_argument("--messages", required=True, help="Path to messages JSON file")
    parser.add_argument("--config", default="config.json", help="Config JSON path")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--top_p", type=float, default=1.0)
    parser.add_argument("--max_tokens", type=int, default=512)
    parser.add_argument("--timeout_sec", type=int, default=60)
    args = parser.parse_args()

    config = _load_config(args.config)
    api_key = _pick_config_value(config, "qwen_hf_api_key", os.getenv("HUGGINGFACEHUB_API_TOKEN"))
    api_url = _pick_config_value(config, "qwen_api_url", DEFAULT_API_URL)
    model = _pick_config_value(config, "qwen_model", DEFAULT_MODEL)

    if api_url != "local" and not api_key:
        raise RuntimeError("Missing Hugging Face API token. Set qwen_hf_api_key or HUGGINGFACEHUB_API_TOKEN.")

    messages = _load_messages(args.messages)
    result = chat_completion(
        messages=messages,
        api_key=api_key,
        api_url=api_url,
        model=model,
        temperature=args.temperature,
        top_p=args.top_p,
        max_tokens=args.max_tokens,
        timeout_sec=args.timeout_sec,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
