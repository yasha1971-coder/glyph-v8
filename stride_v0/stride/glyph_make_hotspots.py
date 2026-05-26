#!/usr/bin/env python3
"""glyph_make_hotspots.py — Build minimizer→chunk_ids inverted index.

Binary format:
  Header (32 bytes):
    MAGIC: "HOTS" (4B)
    VERSION: uint8 (1B)
    NUM_ENTRIES: uint32 (4B)
    Q: uint8 (1B)
    W: uint8 (1B)
    NUM_CHUNKS: uint16 (2B)
    MAX_DF: uint16 (2B)
    RESERVED: 17B

  Hash array (sorted): NUM_ENTRIES × 8 bytes (uint64)
  DF array: NUM_ENTRIES × 2 bytes (uint16)
  Offset array: NUM_ENTRIES × 4 bytes (uint32, byte offset into postings)
  Postings: concatenated uint16 chunk_ids (sorted per entry)
"""

import argparse
import struct
import zlib
import os
import sys
from collections import deque

HOTS_MAGIC = b"HOTS"
HOTS_VERSION = 1
HEADER_SIZE = 32


def hash64(data):
    crc = zlib.crc32(data) & 0xFFFFFFFF
    return (crc << 32) | ((crc * 0x9e3779b9) & 0xFFFFFFFF)


def compute_minimizers(data, q, w):
    n = len(data)
    if n < q:
        return set()
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


def load_chunks(glyph_path):
    chunks = []
    with open(glyph_path, 'rb') as f:
        magic = f.read(6)
        if magic != b'GLYPH1':
            raise ValueError(f"Bad magic: {magic}")
        version = struct.unpack('<B', f.read(1))[0]
        ng = struct.unpack('<H', f.read(2))[0]
        for _ in range(ng):
            sz = struct.unpack('<I', f.read(4))[0]
            chunks.append(zlib.decompress(f.read(sz)))
    return chunks


def build_hotspots(glyph_path, q=8, w=40, max_df=4096):
    chunks = load_chunks(glyph_path)
    nc = len(chunks)
    print(f"[hotspots] {nc} chunks, q={q} w={w} max_df={max_df}")

    inv = {}
    for ci, chunk in enumerate(chunks):
        if ci % 1000 == 0:
            print(f"  extracting minimizers: {ci}/{nc}...", flush=True)
        mins = compute_minimizers(chunk, q, w)
        for m in mins:
            if m not in inv:
                inv[m] = []
            inv[m].append(ci)

    print(f"  total unique minimizers: {len(inv)}")

    effective_max_df = min(max_df, 65535)
    filtered = {h: sorted(set(cids)) for h, cids in inv.items() if len(set(cids)) <= effective_max_df}
    dropped = len(inv) - len(filtered)
    print(f"  entries with df <= {effective_max_df}: {len(filtered)} (dropped {dropped})")

    sorted_hashes = sorted(filtered.keys())
    n = len(sorted_hashes)

    hash_arr = struct.pack(f'<{n}Q', *sorted_hashes)
    df_arr = bytearray()
    off_arr = bytearray()
    postings = bytearray()
    post_offset = 0

    for h in sorted_hashes:
        cids = filtered[h]
        df = len(cids)
        df_arr += struct.pack('<H', df)
        off_arr += struct.pack('<I', post_offset)
        for ci in cids:
            postings += struct.pack('<H', ci)
        post_offset += df * 2

    header = bytearray(HEADER_SIZE)
    struct.pack_into('<4sBIBBHH', header, 0,
                     HOTS_MAGIC, HOTS_VERSION, n, q, w, nc, effective_max_df)

    total_size = HEADER_SIZE + len(hash_arr) + len(df_arr) + len(off_arr) + len(postings)
    print(f"  index size: {total_size / 1024 / 1024:.2f} MB")

    dfs = [len(filtered[h]) for h in sorted_hashes]
    dfs_sorted = sorted(dfs)
    print(f"  df stats: min={dfs_sorted[0]} max={dfs_sorted[-1]} median={dfs_sorted[n//2]}")

    return bytes(header) + hash_arr + bytes(df_arr) + bytes(off_arr) + bytes(postings)


class HotspotsIndex:
    def __init__(self, path):
        with open(path, 'rb') as f:
            hdr = f.read(HEADER_SIZE)

        magic = hdr[0:4]
        if magic != HOTS_MAGIC:
            raise ValueError(f"Bad hotspots magic: {magic}")

        self.version = struct.unpack_from('<B', hdr, 4)[0]
        self.num_entries = struct.unpack_from('<I', hdr, 5)[0]
        self.q = struct.unpack_from('<B', hdr, 9)[0]
        self.w = struct.unpack_from('<B', hdr, 10)[0]
        self.num_chunks = struct.unpack_from('<H', hdr, 11)[0]
        self.max_df = struct.unpack_from('<H', hdr, 13)[0]

        with open(path, 'rb') as f:
            f.seek(HEADER_SIZE)
            self.hashes = struct.unpack(f'<{self.num_entries}Q',
                                        f.read(self.num_entries * 8))
            self.dfs = struct.unpack(f'<{self.num_entries}H',
                                     f.read(self.num_entries * 2))
            self.offsets = struct.unpack(f'<{self.num_entries}I',
                                         f.read(self.num_entries * 4))
            self.postings_data = f.read()

        self.min_query_len = self.w + self.q - 1

    def lookup(self, hash_val):
        lo, hi = 0, self.num_entries
        while lo < hi:
            mid = (lo + hi) // 2
            if self.hashes[mid] < hash_val:
                lo = mid + 1
            else:
                hi = mid
        if lo < self.num_entries and self.hashes[lo] == hash_val:
            df = self.dfs[lo]
            off = self.offsets[lo]
            cids = struct.unpack_from(f'<{df}H', self.postings_data, off)
            return list(cids)
        return None

    def search(self, query, max_cand_pct=0.1):
        if len(query) < self.min_query_len:
            return None

        q_mins = compute_minimizers(query, self.q, self.w)
        if not q_mins:
            return None

        best_cids = None
        for m in q_mins:
            cids = self.lookup(m)
            if cids is not None:
                if best_cids is None or len(cids) < len(best_cids):
                    best_cids = cids

        if best_cids is None:
            return None

        max_cand = int(self.num_chunks * max_cand_pct)
        if len(best_cids) > max_cand:
            return None

        extended = set()
        for c in best_cids:
            extended.add(c)
            if c > 0:
                extended.add(c - 1)
            if c < self.num_chunks - 1:
                extended.add(c + 1)
        return sorted(extended)


def main():
    ap = argparse.ArgumentParser(description='Build hotspots index')
    ap.add_argument('--glyph', default='data/benchmark.glyph')
    ap.add_argument('--q', type=int, default=8)
    ap.add_argument('--w', type=int, default=40)
    ap.add_argument('--max-df', type=int, default=4096)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    out = args.out or args.glyph + '.hotspots.bin'
    data = build_hotspots(args.glyph, q=args.q, w=args.w, max_df=args.max_df)
    with open(out, 'wb') as f:
        f.write(data)
    print(f"[hotspots] Saved to {out} ({len(data)} bytes)")


if __name__ == '__main__':
    main()
