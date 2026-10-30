from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence

from .config import RetrievedChunk, TextChunk

TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


def lexical_tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return TOKEN_PATTERN.findall(normalized)


class BM25Retriever:
    """Small in-memory BM25 index over the same chunks persisted for FAISS."""

    def __init__(self, chunks: Sequence[TextChunk], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = list(chunks)
        self.k1 = k1
        self.b = b
        self.term_frequencies = [Counter(lexical_tokens(chunk.text)) for chunk in self.chunks]
        self.lengths = [sum(frequencies.values()) for frequencies in self.term_frequencies]
        self.average_length = sum(self.lengths) / len(self.lengths) if self.lengths else 1.0
        document_frequency: Counter[str] = Counter()
        for frequencies in self.term_frequencies:
            document_frequency.update(frequencies.keys())
        count = len(self.chunks)
        self.idf = {
            term: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def search(self, query: str, top_k: int) -> list[RetrievedChunk]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query_terms = lexical_tokens(query)
        scored: list[RetrievedChunk] = []
        for chunk, frequencies, length in zip(
            self.chunks, self.term_frequencies, self.lengths, strict=True
        ):
            score = 0.0
            for term in query_terms:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + self.k1 * (
                    1 - self.b + self.b * length / self.average_length
                )
                score += self.idf.get(term, 0.0) * frequency * (self.k1 + 1) / denominator
            if score > 0:
                scored.append(RetrievedChunk(**chunk.model_dump(), score=score))
        return sorted(scored, key=lambda item: (-item.score, item.chunk_id))[:top_k]
