"""Deterministic MinHash/LSH near-duplicate detection.

Documents are represented by word shingles of diacritic-folded text. Hashes
use BLAKE2b (not Python's salted ``hash``), so results are reproducible across
processes. Candidate pairs from LSH banding are confirmed with the signature
Jaccard estimate before being merged with union-find.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Sequence

import numpy as np

from app.services.dialogue.lexicon import fold_aligned

_MERSENNE = np.uint64((1 << 61) - 1)
_MAX_HASH = np.uint64((1 << 32) - 1)


def shingles(text: str, size: int = 5) -> set[str]:
    words = re.findall(r"\w+", fold_aligned(text))
    if len(words) <= size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[index : index + size]) for index in range(len(words) - size + 1)}


def _hash32(values: set[str]) -> np.ndarray:
    return np.fromiter(
        (int.from_bytes(hashlib.blake2b(value.encode("utf-8"), digest_size=4).digest(), "little") for value in values),
        dtype=np.uint64, count=len(values),
    )


class MinHasher:
    def __init__(self, num_perm: int = 64, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.a = rng.integers(1, (1 << 31) - 1, size=num_perm, dtype=np.uint64)
        self.b = rng.integers(0, (1 << 31) - 1, size=num_perm, dtype=np.uint64)
        self.num_perm = num_perm

    def signature(self, items: set[str]) -> np.ndarray:
        if not items:
            return np.full(self.num_perm, _MAX_HASH, dtype=np.uint64)
        hashes = _hash32(items)
        # (a * x + b) mod p with x < 2^32 and a, b < 2^31 stays below 2^64.
        values = (np.outer(hashes, self.a) + self.b) % _MERSENNE
        return (values & _MAX_HASH).min(axis=0)


def estimated_jaccard(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.mean(left == right))


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        root_left, root_right = self.find(left), self.find(right)
        if root_left != root_right:
            # Smaller index wins so cluster representatives are deterministic.
            self.parent[max(root_left, root_right)] = min(root_left, root_right)


def near_duplicate_clusters(
    texts: Sequence[str], *, threshold: float = 0.7, num_perm: int = 64, bands: int = 16, seed: int = 42
) -> tuple[list[int], int]:
    """Return a cluster root per text (index-based) and the confirmed pair count."""
    if num_perm % bands:
        raise ValueError("num_perm must be divisible by bands")
    hasher = MinHasher(num_perm, seed)
    signatures = [hasher.signature(shingles(text)) for text in texts]
    rows = num_perm // bands
    union = UnionFind(len(texts))
    confirmed = 0
    checked: set[tuple[int, int]] = set()
    for band in range(bands):
        buckets: dict[bytes, list[int]] = defaultdict(list)
        for index, signature in enumerate(signatures):
            buckets[signature[band * rows : (band + 1) * rows].tobytes()].append(index)
        for members in buckets.values():
            if len(members) < 2:
                continue
            anchor = members[0]
            for other in members[1:]:
                pair = (anchor, other)
                if pair in checked:
                    continue
                checked.add(pair)
                if estimated_jaccard(signatures[anchor], signatures[other]) >= threshold:
                    union.union(anchor, other)
                    confirmed += 1
    return [union.find(index) for index in range(len(texts))], confirmed
