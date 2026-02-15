#!/usr/bin/env python3
"""
bench_runner.py — L0 Index benchmark runner.

Usage:
    python3 bench_runner.py --glyph data/benchmark.glyph --l0 data/benchmark.glyph.l0
    python3 bench_runner.py --glyph data/benchmark.glyph --l0 data/new.l0 --trials 3000 --seed 42 --json-out results.json
"""

import sys
import struct
import zlib
import mmap
import bisect
import random
import hashlib
import json
import time
import argparse
import statistics
import os
from collections import deque, defaultdict

MAGIC = b"L0V2"
HEADER_SIZE = 64

def hash64(data):
    crc = zlib.crc32(data) & 0xFFFFFFFF
    return (crc << 32) | ((crc * 0x9e3779b9) & 0xFFFFFFFF)

def compute_minimizers(data, q, w):
    n = len(data)
    if n < q:
        return {hash64(data)}
    num_qgrams = n - q + 1
    hashes = [hash64(data[i:i+q]) for i in range(num_qgrams)]
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

def decode_varint(data, pos):
    result = 0; shift = 0
    while True:
        b = data[pos]; result |= (b & 0x7F) << shift; pos += 1
        if not (b & 0x80): break
        shift += 7
    return result, pos

def popcount_mask(mask):
    return sum(bin(b).count('1') for b in mask)

def mask_to_chunks(mask, block_size, num_chunks):
    chunks = []
    for byte_idx, b in enumerate(mask):
        for bit in range(8):
            if b & (1 << bit):
                block = byte_idx * 8 + bit
                start = block * block_size
                end = min(start + block_size, num_chunks)
                chunks.extend(range(start, end))
    return chunks


class L0Index:
    def __init__(self, path):
        self.f = open(path, 'rb')
        self.mm = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        if self.mm[0:4] != MAGIC:
            raise ValueError("Invalid L0 index magic")
        self.num_chunks = struct.unpack_from('<H', self.mm, 4)[0]
        self.q = struct.unpack_from('<B', self.mm, 6)[0]
        self.df_b_min = struct.unpack_from('<H', self.mm, 7)[0]
        self.df_b_max = struct.unpack_from('<H', self.mm, 9)[0]
        self.block_size = struct.unpack_from('<B', self.mm, 11)[0]
        self.b_count = struct.unpack_from('<I', self.mm, 12)[0]
        self.c_count = struct.unpack_from('<I', self.mm, 16)[0]
        self.b_bytes = struct.unpack_from('<I', self.mm, 20)[0]
        self.c_bytes = struct.unpack_from('<I', self.mm, 24)[0]
        self.mask_bytes = struct.unpack_from('<B', self.mm, 28)[0]
        self.w = struct.unpack_from('<B', self.mm, 29)[0] or 16
        self.b_start = HEADER_SIZE
        self.c_start = HEADER_SIZE + self.b_bytes
        self._build_b_index()
        self._build_c_index()

    def _build_b_index(self):
        self.b_keys = []; self.b_offsets = []
        pos = self.b_start
        for _ in range(self.b_count):
            h = struct.unpack_from('<Q', self.mm, pos)[0]
            self.b_keys.append(h); self.b_offsets.append(pos + 8); pos += 8
            count, pos = decode_varint(self.mm, pos)
            prev = 0
            for _ in range(count):
                delta, pos = decode_varint(self.mm, pos); prev += delta

    def _build_c_index(self):
        self.c_keys = []
        pos = self.c_start; es = 8 + self.mask_bytes
        for i in range(self.c_count):
            self.c_keys.append(struct.unpack_from('<Q', self.mm, pos)[0]); pos += es

    def lookup_b(self, h):
        i = bisect.bisect_left(self.b_keys, h)
        if i < len(self.b_keys) and self.b_keys[i] == h:
            chunks = []; pos = self.b_offsets[i]
            count, pos = decode_varint(self.mm, pos)
            prev = 0
            for _ in range(count):
                delta, pos = decode_varint(self.mm, pos); prev += delta; chunks.append(prev)
            return chunks
        return None

    def lookup_c(self, h):
        i = bisect.bisect_left(self.c_keys, h)
        if i < len(self.c_keys) and self.c_keys[i] == h:
            ms = self.c_start + i * (8 + self.mask_bytes) + 8
            return self.mm[ms:ms + self.mask_bytes]
        return None

    def search(self, query, adaptive=True):
        qlen = len(query)
        if adaptive:
            q_values = [8, 7, 6]; w_values = [self.w, self.w // 2, self.w // 4]
        else:
            q_values = [self.q]; w_values = [self.w]
        for q_try, w_try in zip(q_values, w_values):
            if qlen < q_try:
                continue
            result = self._search_with_q(query, q_try, max(1, w_try))
            if result['anchors_found'] > 0:
                result['q_used'] = q_try
                return result
        return {'method': 'l0_fallback', 'q_used': 0, 'anchors_found': 0,
                'best_df': 0, 'best_source': 'none',
                'candidates': list(range(self.num_chunks)),
                'cand_count': self.num_chunks, 'cand_pct': 100.0, 'l0_hit_rate': 0.0}

    def _search_with_q(self, query, q, w):
        MAX_ISECT_K = 4
        MAX_CAND = 256
        qlen = len(query)
        if qlen < q:
            return {'anchors_found': 0}
        if qlen < q + w:
            query_hashes = set(hash64(query[i:i+q]) for i in range(qlen - q + 1))
        else:
            query_hashes = compute_minimizers(query, q, w)
        b_anchors = []; c_anchors = []
        for h in query_hashes:
            br = self.lookup_b(h)
            if br is not None:
                b_anchors.append((h, set(br), len(br)))
            else:
                cr = self.lookup_c(h)
                if cr is not None:
                    c_anchors.append((h, cr, popcount_mask(cr) * self.block_size))
        total = len(b_anchors) + len(c_anchors)
        if total == 0:
            return {'anchors_found': 0}
        best_source = 'none'; best_df = 0; candidates = set(); method = 'union'
        if b_anchors:
            sorted_b = sorted(b_anchors, key=lambda x: x[2])
            best_df = sorted_b[0][2]; best_source = 'B'
            best2_union = sorted_b[0][1] | (sorted_b[1][1] if len(sorted_b) > 1 else set())
            if len(sorted_b) >= 2:
                k = min(MAX_ISECT_K, len(sorted_b))
                isect = set(sorted_b[0][1])
                for i in range(1, k):
                    trial = isect & sorted_b[i][1]
                    if not trial:
                        break
                    isect = trial
                    if len(isect) <= 64:
                        break
                candidates = isect | best2_union
                method = 'b_isect'; best_source = 'B_isect'
            else:
                candidates = best2_union; method = 'b_best'
            if len(candidates) > MAX_CAND:
                candidates = best2_union
                method = 'b_top2'
                if len(candidates) > MAX_CAND:
                    candidates = set(sorted_b[0][1])
                    method = 'b_best1'
        if not b_anchors or len(candidates) > MAX_CAND:
            if c_anchors:
                sorted_c = sorted(c_anchors, key=lambda x: x[2])
                best_c_df = sorted_c[0][2]
                if not b_anchors or best_c_df < best_df:
                    best_source = 'C'; best_df = best_c_df
                c_cands = set()
                for _, mask, _ in sorted_c[:2]:
                    c_cands.update(mask_to_chunks(mask, self.block_size, self.num_chunks))
                if not candidates or len(c_cands) < len(candidates):
                    candidates = c_cands; method = 'c_top2'
        if len(candidates) > self.num_chunks // 2:
            candidates = set(range(self.num_chunks))
            method = 'fallback'; best_source = 'fallback'
        extended = set()
        for c in candidates:
            extended.add(c)
            if c > 0: extended.add(c - 1)
            if c < self.num_chunks - 1: extended.add(c + 1)
        return {'method': f'l0_{method}_{total}', 'anchors_found': total,
                'b_anchors': len(b_anchors), 'c_anchors': len(c_anchors),
                'best_df': best_df, 'best_source': best_source,
                'candidates': sorted(extended), 'cand_count': len(extended),
                'cand_pct': 100.0 * len(extended) / self.num_chunks if self.num_chunks else 0,
                'l0_hit_rate': 1.0}

    def close(self):
        self.mm.close(); self.f.close()


def sha256_file(path):
    if not os.path.exists(path):
        return "NOT_FOUND"
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def load_raw_data(glyph_path):
    chunks = []
    with open(glyph_path, 'rb') as gf:
        magic = gf.read(6)
        if magic != b'GLYPH1':
            raise ValueError(f"Bad GLYPH magic: {magic}")
        version, ng = struct.unpack('<BH', gf.read(3))
        for _ in range(ng):
            sz = struct.unpack('<I', gf.read(4))[0]
            chunks.append(zlib.decompress(gf.read(sz)))
    return b''.join(chunks), ng


def bench_one(idx, raw, nc, L, trials, seed, adaptive):
    N = len(raw)
    if L > N:
        return None
    CS = N // nc if nc else 16384
    random.seed(seed)
    eff = 0; fb = 0; miss = 0; rf = 0
    cands = []
    for _ in range(trials):
        off = random.randint(0, N - L)
        q = raw[off:off + L]
        exp_start = off // CS
        exp_end = (off + L - 1) // CS
        exp = set(range(exp_start, min(exp_end + 1, nc)))
        r = idx.search(q, adaptive=adaptive)
        a = r.get('anchors_found', 0)
        cc = r.get('cand_count', nc)
        cs = set(r.get('candidates', []))
        if a == 0:
            miss += 1
        elif cc >= nc * 0.5:
            fb += 1
        else:
            eff += 1; cands.append(cc)
        if not (exp & cs or cc >= nc * 0.5 or a == 0):
            rf += 1
    return {
        'L': L, 'adaptive': adaptive, 'trials': trials, 'seed': seed,
        'hit_rate': round((eff + fb) / trials, 4),
        'effective_pct': round(eff / trials * 100, 1),
        'fallback': fb, 'miss': miss,
        'recall': round(1 - rf / trials, 4), 'recall_fail': rf,
        'avg_cand': round(statistics.mean(cands), 1) if cands else None,
        'med_cand': int(statistics.median(cands)) if cands else None,
    }


def main():
    ap = argparse.ArgumentParser(description='L0 bench runner')
    ap.add_argument('--glyph', required=True)
    ap.add_argument('--l0', required=True)
    ap.add_argument('--trials', type=int, default=2000)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--json-out', default=None)
    args = ap.parse_args()

    LENGTHS = [48, 96, 192, 384, 768, 1536]

    print(f"glyph : {args.glyph}")
    print(f"l0    : {args.l0}")
    raw, ng = load_raw_data(args.glyph)
    idx = L0Index(args.l0)
    print(f"chunks={idx.num_chunks}  q={idx.q}  w={idx.w}  "
          f"B={idx.b_count}  C={idx.c_count}  "
          f"index={os.path.getsize(args.l0)/1024/1024:.1f}MB")
    print(f"trials={args.trials}  seed={args.seed}\n")

    all_res = []
    for adaptive in [False, True]:
        tag = "adaptive" if adaptive else "fixed"
        print(f"--- {tag} ---")
        print(f"{'L':>6} | {'hit%':>6} | {'eff%':>6} | {'fb':>5} | {'miss':>5} | "
              f"{'recall':>7} | {'avg':>5} | {'med':>5}")
        print("-" * 66)
        for L in LENGTHS:
            t0 = time.time()
            r = bench_one(idx, raw, idx.num_chunks, L, args.trials, args.seed, adaptive)
            dt = time.time() - t0
            if r is None:
                print(f"{L:>6} | SKIP (L > data)")
                continue
            r['elapsed'] = round(dt, 2)
            all_res.append(r)
            avg_s = f"{r['avg_cand']:.0f}" if r['avg_cand'] is not None else "-"
            med_s = str(r['med_cand']) if r['med_cand'] is not None else "-"
            print(f"{L:>6} | {r['hit_rate']*100:>5.1f}% | {r['effective_pct']:>5.1f}% | "
                  f"{r['fallback']:>5} | {r['miss']:>5} | "
                  f"{r['recall']:>7.4f} | {avg_s:>5} | {med_s:>5}")
        print()

    print("SHA256:")
    for p in [args.glyph, args.l0, 'data/l0_search']:
        print(f"  {p}: {sha256_file(p)}")

    if args.json_out:
        out = {
            'index': {'chunks': idx.num_chunks, 'q': idx.q, 'w': idx.w,
                      'df_b_min': idx.df_b_min, 'df_b_max': idx.df_b_max,
                      'B': idx.b_count, 'C': idx.c_count,
                      'size_bytes': os.path.getsize(args.l0)},
            'trials': args.trials, 'seed': args.seed,
            'results': all_res,
            'sha256': {os.path.basename(p): sha256_file(p)
                       for p in [args.glyph, args.l0, 'data/l0_search']}
        }
        with open(args.json_out, 'w') as f:
            json.dump(out, f, indent=2)
        print(f"\nSaved: {args.json_out}")

    idx.close()


if __name__ == '__main__':
    main()
