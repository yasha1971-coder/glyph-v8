import struct
from .container_reader import StrideContainer

# Простая, быстрая rolling-hash функция (Rabin–Karp)
def rolling_hash(data: bytes, window: int = 32):
    if len(data) < window:
        return []

    base = 257
    mod = 2**64

    h = 0
    power = pow(base, window - 1, mod)

    # initial window
    for i in range(window):
        h = (h * base + data[i]) % mod

    hashes = [h]

    for i in range(window, len(data)):
        h = (h - data[i - window] * power) % mod
        h = (h * base + data[i]) % mod
        hashes.append(h)

    return hashes


def compute_fingerprint(container_path: str, k: int = 128, window: int = 32):
    c = StrideContainer(container_path)

    all_hashes = []

    for chunk in c.iter_chunks():
        hlist = rolling_hash(chunk, window)
        all_hashes.extend(hlist)

    if not all_hashes:
        return []

    # bottom-k MinHash
    all_hashes.sort()
    return all_hashes[:k]
