import math
from .container_reader import StrideContainer

def chunk_entropy(chunk: bytes) -> float:
    """Shannon entropy of a chunk."""
    if not chunk:
        return 0.0

    freq = {}
    for b in chunk:
        freq[b] = freq.get(b, 0) + 1

    total = len(chunk)
    ent = 0.0
    for count in freq.values():
        p = count / total
        ent -= p * math.log2(p)

    return ent


def compute_hotspots(container_path: str, top: int = 20):
    """Return top-N chunks with highest entropy."""
    c = StrideContainer(container_path)

    results = []  # (entropy, chunk_id)

    chunk_id = 0
    for chunk in c.iter_chunks():
        ent = chunk_entropy(chunk)
        results.append((ent, chunk_id))
        chunk_id += 1

    # Sort by entropy descending
    results.sort(reverse=True, key=lambda x: x[0])

    return results[:top]
