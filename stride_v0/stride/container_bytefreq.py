from collections import Counter
from .container_reader import StrideContainer

def compute_bytefreq(container_path: str, top: int = 20):
    c = StrideContainer(container_path)
    freq = Counter()

    for chunk in c.iter_chunks():
        freq.update(chunk)

    total = sum(freq.values())
    top_items = freq.most_common(top)

    return total, top_items
