#!/usr/bin/env python3
"""glyph_make_fingerprint.py — Build per-chunk Bloom fingerprints using winnowing minimizers.

Spec: Glyph v8 Fingerprint Layer v1
  q=8, w=16, bloom_bits=16384 (2048 bytes/chunk), k=11
  FN=0 guarantee requires winnowing minimizers, identical in offline and runtime
  verify-mode=bloom: candidate passes if ANY(query minimizer) present in chunk bloom
  guard: if L < w+q-1 → disable bloom verify for that L

Output:
  <glyph>.fingerprints.bin   — binary: header + N bloom filters (2048 bytes each)
  <glyph>.fingerprints.json  — build stats (minimizers_per_chunk avg/p95/max, timing)
"""

import argparse
import hashlib
import json
import math
import os
import statistics
import struct
import time
import zlib
from collections import deque

FP_MAGIC = b"GLFP"
FP_VERSION = 1

DEFAULT_Q = 8
DEFAULT_W = 40
DEFAULT_BLOOM_BITS = 16384
DEFAULT_K = 11


def hash64(data):
    crc = zlib.crc32(data) & 0xFFFFFFFF
    return (crc << 32) | ((crc * 0x9E3779B9) & 0xFFFFFFFF)


def _hash64_batch(data, q):
    n = len(data)
    if n < q:
        return []
    mv = memoryview(data)
    out = [0] * (n - q + 1)
    _crc32 = zlib.crc32
    for i in range(n - q + 1):
        crc = _crc32(mv[i:i+q]) & 0xFFFFFFFF
        out[i] = (crc << 32) | ((crc * 0x9E3779B9) & 0xFFFFFFFF)
    return out


def compute_minimizers(data, q, w):
    n = len(data)
    if n < q:
        return set()
    num_qgrams = n - q + 1
    hashes = _hash64_batch(data, q)
    if num_qgrams <= w:
        return set(hashes)
    minimizers = set()
    dq = deque()
    for i in range(num_qgrams):
        while dq and dq[0] <= i - w:
            dq.popleft()
        while dq and hashes[dq[-1]] >= hashes[i]:
            dq.pop()
        dq.append(i)
        if i >= w - 1:
            minimizers.add(hashes[dq[0]])
    return minimizers


def bloom_add(bloom, h, k, bloom_bits, _offset=0):
    h1 = h & 0xFFFFFFFF
    h2 = (h >> 32) & 0xFFFFFFFF
    for i in range(k):
        pos = (h1 + i * h2) % bloom_bits
        bloom[_offset + (pos >> 3)] |= (1 << (pos & 7))


def bloom_check(bloom, h, k, bloom_bits):
    h1 = h & 0xFFFFFFFF
    h2 = (h >> 32) & 0xFFFFFFFF
    for i in range(k):
        pos = (h1 + i * h2) % bloom_bits
        byte_idx = pos >> 3
        bit_idx = pos & 7
        if not (bloom[byte_idx] & (1 << bit_idx)):
            return False
    return True


def bloom_check_mv(mv, off, h, k, bloom_bits):
    mask = bloom_bits - 1
    h1 = h & 0xFFFFFFFF
    h2 = (h >> 32) & 0xFFFFFFFF
    for i in range(k):
        pos = (h1 + i * h2) & mask
        byte_idx = off + (pos >> 3)
        if not (mv[byte_idx] & (1 << (pos & 7))):
            return False
    return True


def bloom_check_any(bloom_bytes, minimizer_hashes, k, bloom_bits):
    for h in minimizer_hashes:
        if bloom_check(bloom_bytes, h, k, bloom_bits):
            return True
    return False


def load_chunks(glyph_path):
    chunks = []
    with open(glyph_path, 'rb') as f:
        magic = f.read(6)
        if magic != b'GLYPH1':
            raise ValueError(f"Bad magic: {magic}")
        hdr = f.read(3)
        version, ng = struct.unpack('<BH', hdr)
        for _ in range(ng):
            sz = struct.unpack('<I', f.read(4))[0]
            chunks.append(zlib.decompress(f.read(sz)))
    return chunks


def build_fingerprints(glyph_path, q=DEFAULT_Q, w=DEFAULT_W,
                       bloom_bits=DEFAULT_BLOOM_BITS, k=DEFAULT_K,
                       out_bin=None, out_json=None):
    t0 = time.perf_counter()

    chunks = load_chunks(glyph_path)
    nc = len(chunks)
    bloom_bytes = bloom_bits // 8

    print(f"[fp] chunks={nc} q={q} w={w} bloom_bits={bloom_bits} k={k} bloom_bytes_per_chunk={bloom_bytes}")

    all_blooms = bytearray(nc * bloom_bytes)
    min_counts = []

    for ci, chunk in enumerate(chunks):
        mins = compute_minimizers(chunk, q, w)
        min_counts.append(len(mins))
        base = ci * bloom_bytes
        for h in mins:
            bloom_add(all_blooms, h, k, bloom_bits, _offset=base)
        if (ci + 1) % 2000 == 0 or ci == nc - 1:
            elapsed = time.perf_counter() - t0
            rate = (ci + 1) / elapsed
            print(f"  chunk {ci+1}/{nc} minimizers={len(mins)} rate={rate:.0f} chunks/s")

    build_s = time.perf_counter() - t0

    if out_bin is None:
        out_bin = glyph_path + ".fingerprints.bin"
    if out_json is None:
        out_json = glyph_path + ".fingerprints.json"

    os.makedirs(os.path.dirname(out_bin) or ".", exist_ok=True)

    with open(out_bin, 'wb') as f:
        f.write(FP_MAGIC)
        f.write(struct.pack('<B', FP_VERSION))
        f.write(struct.pack('<H', nc))
        f.write(struct.pack('<B', q))
        f.write(struct.pack('<B', w))
        f.write(struct.pack('<I', bloom_bits))
        f.write(struct.pack('<B', k))
        f.write(b'\x00' * (32 - 14))
        f.write(bytes(all_blooms))

    sorted_mc = sorted(min_counts)
    p95_idx = int(0.95 * (len(sorted_mc) - 1))

    stats = {
        "glyph_path": glyph_path,
        "sha256": sha256_file(glyph_path),
        "num_chunks": nc,
        "q": q,
        "w": w,
        "bloom_bits": bloom_bits,
        "bloom_bytes_per_chunk": bloom_bytes,
        "k": k,
        "min_query_len": w + q - 1,
        "total_fingerprint_bytes": nc * bloom_bytes,
        "total_fingerprint_mb": round(nc * bloom_bytes / (1024 * 1024), 3),
        "minimizers_per_chunk_avg": round(statistics.mean(min_counts), 1),
        "minimizers_per_chunk_p50": sorted_mc[len(sorted_mc) // 2],
        "minimizers_per_chunk_p95": sorted_mc[p95_idx],
        "minimizers_per_chunk_max": max(min_counts),
        "minimizers_per_chunk_min": min(min_counts),
        "build_s": round(build_s, 3),
        "fp_bin_path": out_bin,
        "fp_json_path": out_json,
    }

    with open(out_json, 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"\n[fp] Build complete in {build_s:.3f}s")
    print(f"  fingerprints: {out_bin} ({os.path.getsize(out_bin)} bytes)")
    print(f"  stats: {out_json}")
    print(f"  minimizers/chunk: avg={stats['minimizers_per_chunk_avg']} "
          f"p95={stats['minimizers_per_chunk_p95']} max={stats['minimizers_per_chunk_max']}")
    print(f"  total fingerprint size: {stats['total_fingerprint_mb']:.3f} MB")

    return out_bin, out_json, stats, chunks, all_blooms


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


class FingerprintIndex:
    def __init__(self, fp_bin_path):
        with open(fp_bin_path, 'rb') as f:
            magic = f.read(4)
            if magic != FP_MAGIC:
                raise ValueError(f"Bad fingerprint magic: {magic}")
            self.version = struct.unpack('<B', f.read(1))[0]
            self.num_chunks = struct.unpack('<H', f.read(2))[0]
            self.q = struct.unpack('<B', f.read(1))[0]
            self.w = struct.unpack('<B', f.read(1))[0]
            self.bloom_bits = struct.unpack('<I', f.read(4))[0]
            self.k = struct.unpack('<B', f.read(1))[0]
            f.read(32 - 14)
            self.bloom_bytes = self.bloom_bits // 8
            self.data = f.read(self.num_chunks * self.bloom_bytes)

        self.mv = memoryview(self.data)
        self.min_query_len = self.w + self.q - 1
        if len(self.data) != self.num_chunks * self.bloom_bytes:
            raise ValueError(f"Truncated fingerprint data: expected {self.num_chunks * self.bloom_bytes}, got {len(self.data)}")

    def get_bloom(self, chunk_idx):
        off = chunk_idx * self.bloom_bytes
        return self.data[off:off + self.bloom_bytes]

    def _precompute_checks(self, query_minimizers):
        mask = self.bloom_bits - 1
        k = self.k
        checks = []
        for h in query_minimizers:
            h1 = h & 0xFFFFFFFF
            h2 = (h >> 32) & 0xFFFFFFFF
            positions = []
            for i in range(k):
                pos = (h1 + i * h2) & mask
                positions.append((pos >> 3, 1 << (pos & 7)))
            checks.append(tuple(positions))
        return tuple(checks)

    def _check_precomputed(self, off, checks):
        mv = self.mv
        for positions in checks:
            for byte_off, bitmask in positions:
                if not (mv[off + byte_off] & bitmask):
                    break
            else:
                return True
        return False

    def _count_precomputed(self, off, checks):
        mv = self.mv
        count = 0
        for positions in checks:
            for byte_off, bitmask in positions:
                if not (mv[off + byte_off] & bitmask):
                    break
            else:
                count += 1
        return count

    def check_chunk(self, chunk_idx, query_minimizers):
        off = chunk_idx * self.bloom_bytes
        mv = self.mv
        k = self.k
        bb = self.bloom_bits
        for h in query_minimizers:
            if bloom_check_mv(mv, off, h, k, bb):
                return True
        return False

    def scan_all(self, query):
        if len(query) < self.min_query_len:
            return list(range(self.num_chunks))

        q_mins = compute_minimizers(query, self.q, self.w)
        if not q_mins:
            return list(range(self.num_chunks))

        checks = self._precompute_checks(q_mins)
        bs = self.bloom_bytes
        nc = self.num_chunks
        _check = self._check_precomputed

        passed = []
        for ci in range(nc):
            if _check(ci * bs, checks):
                passed.append(ci)
        return passed

    def scan_all_strict(self, query, need=2):
        if len(query) < self.min_query_len:
            return list(range(self.num_chunks))

        q_mins = compute_minimizers(query, self.q, self.w)
        if not q_mins:
            return list(range(self.num_chunks))

        checks = self._precompute_checks(q_mins)
        n_checks = len(checks)

        if n_checks < need:
            need = max(1, n_checks)

        bs = self.bloom_bytes
        nc = self.num_chunks
        _count = self._count_precomputed

        passed = []
        for ci in range(nc):
            if _count(ci * bs, checks) >= need:
                passed.append(ci)
        return passed

    def scan_all_scored(self, query, return_df=False):
        if len(query) < self.min_query_len:
            r = list(range(self.num_chunks))
            return (r, []) if return_df else r

        q_mins = compute_minimizers(query, self.q, self.w)
        if not q_mins:
            r = list(range(self.num_chunks))
            return (r, []) if return_df else r

        q_mins_list = list(q_mins)
        checks = self._precompute_checks(q_mins_list)
        bs = self.bloom_bytes
        nc = self.num_chunks
        mv = self.mv

        df = [0] * len(checks)
        for ci in range(nc):
            off = ci * bs
            for j, positions in enumerate(checks):
                for byte_off, bitmask in positions:
                    if not (mv[off + byte_off] & bitmask):
                        break
                else:
                    df[j] += 1

        idf_weights = []
        for d in df:
            idf_weights.append(1.0 / d if d > 0 else 0.0)

        scored = []
        for ci in range(nc):
            off = ci * bs
            score = 0.0
            for j, positions in enumerate(checks):
                for byte_off, bitmask in positions:
                    if not (mv[off + byte_off] & bitmask):
                        break
                else:
                    score += idf_weights[j]
            if score > 0:
                scored.append((score, ci))
        scored.sort(key=lambda x: -x[0])
        result = [ci for _, ci in scored]
        return (result, df) if return_df else result

    def filter_candidates_fast(self, candidates, query):
        if len(query) < self.min_query_len:
            return candidates

        q_mins = compute_minimizers(query, self.q, self.w)
        if not q_mins:
            return candidates

        checks = self._precompute_checks(q_mins)
        bs = self.bloom_bytes
        _check = self._check_precomputed

        passed = []
        for ci in candidates:
            if _check(ci * bs, checks):
                passed.append(ci)
        return passed

    def filter_candidates(self, candidates, query, skip_bloom=False):
        if skip_bloom:
            return candidates

        if len(query) < self.min_query_len:
            return candidates

        q_mins = tuple(compute_minimizers(query, self.q, self.w))
        if not q_mins:
            return candidates

        passed = []
        for ci in candidates:
            if self.check_chunk(ci, q_mins):
                passed.append(ci)

        return passed


def verify_sync(glyph_path, fp_bin_path, num_tests=100, seed=42):
    import random
    rng = random.Random(seed)
    chunks = load_chunks(glyph_path)
    fp = FingerprintIndex(fp_bin_path)

    q, w = fp.q, fp.w
    min_L = w + q - 1

    print(f"\n[verify] Synchronicity test: {num_tests} trials, q={q} w={w} min_L={min_L}")

    fn = 0
    tested = 0
    for _ in range(num_tests):
        ci = rng.randint(0, len(chunks) - 1)
        chunk = chunks[ci]
        if len(chunk) < min_L:
            continue

        L = rng.choice([min_L, 48, 96, 192])
        if len(chunk) < L:
            L = min_L
        if len(chunk) < L:
            continue

        off = rng.randint(0, len(chunk) - L)
        query = chunk[off:off + L]

        q_mins = compute_minimizers(query, q, w)
        c_mins = compute_minimizers(chunk, q, w)

        overlap = q_mins & c_mins
        if not overlap:
            print(f"  WARNING: no minimizer overlap ci={ci} off={off} L={L} q_mins={len(q_mins)} c_mins={len(c_mins)}")
            fn += 1
            tested += 1
            continue

        bloom_ok = fp.check_chunk(ci, q_mins)
        if not bloom_ok:
            print(f"  BLOOM FAIL: ci={ci} off={off} L={L} overlap={len(overlap)} q_mins={len(q_mins)}")
            fn += 1

        tested += 1

    print(f"[verify] tested={tested} FN={fn} FN_rate={fn/tested:.6f}" if tested > 0 else "[verify] no tests run")
    return fn == 0


def main():
    ap = argparse.ArgumentParser(description="Build per-chunk Bloom fingerprints for .glyph")
    ap.add_argument("glyph", help="Path to .glyph archive")
    ap.add_argument("--q", type=int, default=DEFAULT_Q, help=f"q-gram size (default {DEFAULT_Q})")
    ap.add_argument("--w", type=int, default=DEFAULT_W, help=f"window size (default {DEFAULT_W})")
    ap.add_argument("--bloom-bits", type=int, default=DEFAULT_BLOOM_BITS, help=f"bits per bloom (default {DEFAULT_BLOOM_BITS})")
    ap.add_argument("--k", type=int, default=DEFAULT_K, help=f"hash functions (default {DEFAULT_K})")
    ap.add_argument("--out-bin", default=None, help="Output .fingerprints.bin path")
    ap.add_argument("--out-json", default=None, help="Output .fingerprints.json path")
    ap.add_argument("--verify", action="store_true", help="Run synchronicity verification after build")
    ap.add_argument("--verify-trials", type=int, default=200, help="Number of verification trials")
    args = ap.parse_args()

    out_bin, out_json, stats, chunks, all_blooms = build_fingerprints(
        args.glyph, q=args.q, w=args.w, bloom_bits=args.bloom_bits, k=args.k,
        out_bin=args.out_bin, out_json=args.out_json
    )

    if args.verify:
        ok = verify_sync(args.glyph, out_bin, num_tests=args.verify_trials)
        if ok:
            print("\n[verify] PASS — all synchronicity checks passed")
        else:
            print("\n[verify] FAIL — false negatives detected!")
            exit(1)


if __name__ == "__main__":
    main()
