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


def compute_headersketch(container_path: str, size: int = 64):
    """Compute structural sketch of the corpus based on chunk entropy."""
    c = StrideContainer(container_path)

    entropies = []
    for chunk in c.iter_chunks():
        entropies.append(chunk_entropy(chunk))

    if not entropies:
        return []

    # Normalize 0..1
    mn = min(entropies)
    mx = max(entropies)
    if mx == mn:
        norm = [0.0] * len(entropies)
    else:
        norm = [(e - mn) / (mx - mn) for e in entropies]

    # Downsample to fixed size
    if len(norm) <= size:
        # pad or return as is
        return norm + [0.0] * (size - len(norm))

    step = len(norm) / size
    sketch = []
    for i in range(size):
        idx = int(i * step)
        sketch.append(norm[idx])

    return sketch
