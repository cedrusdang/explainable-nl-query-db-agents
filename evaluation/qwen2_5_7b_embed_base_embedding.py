"""Local embedding helper for Qwen2.5-7B-embed-base using sentence-transformers."""

from __future__ import annotations

import argparse
import json
from typing import List

from sentence_transformers import SentenceTransformer

DEFAULT_MODEL = "ssmits/Qwen2.5-7B-embed-base"


class LocalEmbeddingModel:
    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.model.encode([text], normalize_embeddings=True)[0].tolist()


def _load_texts(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return [str(item) for item in data]
    raise ValueError("Input must be a JSON list of strings.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local embeddings for Qwen2.5-7B-embed-base")
    parser.add_argument("--texts", required=True, help="Path to JSON list of strings")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Embedding model name")
    args = parser.parse_args()

    model = LocalEmbeddingModel(args.model)
    texts = _load_texts(args.texts)
    embeddings = model.embed_documents(texts)
    print(json.dumps(embeddings, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
