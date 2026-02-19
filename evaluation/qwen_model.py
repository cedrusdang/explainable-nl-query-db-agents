"""Qwen model loader and chat helper for evaluation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class QwenChatClient:
    model_name: str = "Qwen/Qwen2.5-7B-Instruct"
    max_new_tokens: int = 256
    device: Optional[str] = None

    def __post_init__(self) -> None:
        self._pipe = None
        if self.device is None:
            self.device = _detect_device()

    def invoke(self, prompt: str) -> str:
        messages = [{"role": "user", "content": prompt}]
        return self._invoke_pipeline(messages)

    def _invoke_pipeline(self, messages: List[Dict[str, str]]) -> str:
        if self._pipe is None:
            try:
                from transformers import pipeline
            except ImportError as exc:
                raise ImportError("Please install transformers to use Qwen.") from exc
            device = 0 if self.device == "cuda" else -1
            self._pipe = pipeline(
                "text-generation",
                model=self.model_name,
                device=device,
            )

        outputs = self._pipe(messages, max_new_tokens=self.max_new_tokens)
        return _extract_pipeline_text(outputs)


def _extract_pipeline_text(outputs: Any) -> str:
    if not outputs:
        return ""
    first = outputs[0]
    if isinstance(first, dict):
        generated = first.get("generated_text")
        if isinstance(generated, list) and generated:
            last_msg = generated[-1]
            if isinstance(last_msg, dict):
                return str(last_msg.get("content", ""))
        if isinstance(generated, str):
            return generated
    return str(outputs)


def _detect_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"
