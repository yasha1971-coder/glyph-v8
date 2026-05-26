#!/usr/bin/env python3
"""build_l0v2.py — Build L0V2 binary index from a .glyph archive.

Format (compatible with L0Index in bench_text_mode.py / bench_l0.py):

  Header (64 bytes):
    [0:4]   MAGIC       b"L0V2"
    [4:6]   num_chunks  uint16
    [6:7]   q           uint8
    [7:9]   df_b_min    uint16   (min DF to include a key)
    [9:11]  df_b_max    uint16   (max DF for B-layer; above → C-layer)
    [11:12] block_size  uint8    (chunks per block for C-layer bitmask)
    [12:16] b_count     uint32   (number of B-layer entries)
    [16:20] c_count     uint32   (number of C-layer entries)
    [20:24] b_bytes     uint32   (total B-layer size in bytes)
    [24:28] c_bytes     uint32   (total C-layer size in bytes)
    [28:29] mask_bytes  uint8    (bytes per C-layer bitmask)
    [29:30] w           uint8    (minimizer window size)
    [30:64] reserved    (34 zero bytes)

  B-layer (sorted by hash):
    Per entry: uint64 hash | varint(count) | varint-delta-encoded chunk_ids

  C-layer (sorted by hash):
    Per entry: uint64 hash | mask_bytes bitmask (bit per block)

Usage:
    python3 build_l0v2.py --glyph data/corpus2.glyph --out data/corpus2.glyph.l0
    python3 build_l0v2.py --glyph data/corpus2.glyph --out data/corpus2.glyph.l0 \\
        --q 8 --w 8 --df-min 1 --df-max 256 --block-size 64
"""

import argparse
import hashlib
import json
import math
import os
import struct
import sys
import time
import zlib
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
    hashes = [hash64(data[i:i + q]) for i in range(num_qgrams)]
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


def encode_varint(n):
    parts = []
    while n >= 0x80:
        parts.append((n & 0x7F) | 0x80)
        n >>= 7
    parts.append(n)
    return bytes(parts)


def load_chunks(glyph_path):
    chunks = []
    with open(glyph_path, 'rb') as f:
        magic = f.read(6)
        if magic != b'GLYPH1':
            raise ValueError(f"Bad glyph magic: {magic!r} (expected GLYPH1)")
        version = struct.unpack('<B', f.read(1))[0]
        ng = struct.unpack('<H', f.read(2))[0]
        for i in range(ng):
            sz = struct.unpack('<I', f.read(4))[0]
            raw = f.read(sz)
            if len(raw) != sz:
                raise ValueError(f"Truncated chunk {i}")
            chunks.append(zlib.decompress(raw))
    return chunks


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def build_l0v2(glyph_path, out_path, q=8, w=8, df_min=1, df_max=256,
               block_size=64, progress_every=500):
    t0 = time.perf_counter()

    print(f"[L0V2] Loading chunks from {glyph_path}")
    chunks = load_chunks(glyph_path)
    num_chunks = len(chunks)
    total_bytes = sum(len(c) for c in chunks)
    print(f"[L0V2] {num_chunks} chunks, {total_bytes} bytes "
          f"({total_bytes / (1 << 20):.1f} MB)")

    print(f"[L0V2] Pass 1: computing minimizers (q={q}, w={w})")
    inv = defaultdict(set)
    t1 = time.perf_counter()
    for ci, chunk in enumerate(chunks):
        mins = compute_minimizers(chunk, q, w)
        for h in mins:
            inv[h].add(ci)
        if (ci + 1) % progress_every == 0 or ci == num_chunks - 1:
            elapsed = time.perf_counter() - t1
            print(f"  chunk {ci + 1}/{num_chunks} "
                  f"({100 * (ci + 1) / num_chunks:.0f}%) "
                  f"keys={len(inv)} {elapsed:.1f}s")

    total_keys = len(inv)
    print(f"[L0V2] Pass 1 done: {total_keys} unique minimizer keys")

    print(f"[L0V2] Pass 2: partitioning (df_min={df_min}, df_max={df_max}, "
          f"block_size={block_size})")
    b_entries = []
    c_entries = []
    skipped = 0

    num_blocks = math.ceil(num_chunks / block_size)
    mask_bytes = math.ceil(num_blocks / 8)

    for h, chunk_set in inv.items():
        df = len(chunk_set)
        if df < df_min:
            skipped += 1
            continue
        if df <= df_max:
            b_entries.append((h, sorted(chunk_set)))
        else:
            mask = bytearray(mask_bytes)
            for cid in chunk_set:
                block = cid // block_size
                mask[block // 8] |= 1 << (block % 8)
            c_entries.append((h, bytes(mask)))

    b_entries.sort(key=lambda x: x[0])
    c_entries.sort(key=lambda x: x[0])

    b_count = len(b_entries)
    c_count = len(c_entries)
    print(f"[L0V2] B-layer: {b_count} keys, C-layer: {c_count} keys, "
          f"skipped: {skipped} (df < {df_min})")

    tmp_path = out_path + '.tmp'
    with open(tmp_path, 'wb') as f:
        f.write(b'\x00' * HEADER_SIZE)

        print(f"[L0V2] Serializing B-layer (streaming)...")
        b_bytes_written = 0
        for idx_i, (h, cids) in enumerate(b_entries):
            buf = bytearray()
            buf += struct.pack('<Q', h)
            buf += encode_varint(len(cids))
            prev = 0
            for cid in cids:
                buf += encode_varint(cid - prev)
                prev = cid
            f.write(buf)
            b_bytes_written += len(buf)
            if (idx_i + 1) % 1000000 == 0:
                print(f"  B: {idx_i + 1}/{b_count} "
                      f"({b_bytes_written / (1 << 20):.1f} MB)")
        b_bytes = b_bytes_written
        print(f"[L0V2] B-layer: {b_bytes} bytes ({b_bytes / (1 << 20):.1f} MB)")

        print(f"[L0V2] Serializing C-layer (streaming)...")
        c_bytes_written = 0
        for h, mask in c_entries:
            f.write(struct.pack('<Q', h))
            f.write(mask)
            c_bytes_written += 8 + len(mask)
        c_bytes_total = c_bytes_written
        print(f"[L0V2] C-layer: {c_bytes_total} bytes "
              f"({c_bytes_total / (1 << 20):.1f} MB)")

        header = bytearray(HEADER_SIZE)
        header[0:4] = MAGIC
        struct.pack_into('<H', header, 4, num_chunks)
        struct.pack_into('<B', header, 6, q)
        struct.pack_into('<H', header, 7, df_min)
        struct.pack_into('<H', header, 9, df_max)
        struct.pack_into('<B', header, 11, block_size)
        struct.pack_into('<I', header, 12, b_count)
        struct.pack_into('<I', header, 16, c_count)
        struct.pack_into('<I', header, 20, b_bytes)
        struct.pack_into('<I', header, 24, c_bytes_total)
        struct.pack_into('<B', header, 28, mask_bytes)
        struct.pack_into('<B', header, 29, w)

        f.seek(0)
        f.write(header)

    os.replace(tmp_path, out_path)

    total_size = HEADER_SIZE + b_bytes + c_bytes_total
    elapsed = time.perf_counter() - t0
    print(f"[L0V2] Written: {out_path}")
    print(f"[L0V2] Total: {total_size} bytes ({total_size / (1 << 20):.1f} MB)")
    print(f"[L0V2] Build time: {elapsed:.1f}s")

    result = {
        'status': 'ok',
        'num_chunks': num_chunks,
        'q': q,
        'w': w,
        'b_keys': b_count,
        'c_keys': c_count,
        'b_bytes': b_bytes,
        'c_bytes': c_bytes_total,
        'total_bytes': total_size,
        'df_b_min': df_min,
        'df_b_max': df_max,
        'block_size': block_size,
        'mask_bytes': mask_bytes,
        'skipped_keys': skipped,
        'build_time_s': round(elapsed, 2),
        'glyph_sha256': sha256_file(glyph_path),
        'l0_sha256': sha256_file(out_path),
    }
    return result


def main():
    ap = argparse.ArgumentParser(
        description='Build L0V2 binary index from a .glyph archive')
    ap.add_argument('--glyph', required=True,
                    help='Path to .glyph archive (GLYPH1 format)')
    ap.add_argument('--out', default=None,
                    help='Output path (default: <glyph>.l0)')
    ap.add_argument('--q', type=int, default=8,
                    help='Q-gram size (default: 8)')
    ap.add_argument('--w', type=int, default=8,
                    help='Minimizer window size (default: 8)')
    ap.add_argument('--df-min', type=int, default=1,
                    help='Minimum DF to include key (default: 1)')
    ap.add_argument('--df-max', type=int, default=256,
                    help='Max DF for B-layer; above goes to C-layer (default: 256)')
    ap.add_argument('--block-size', type=int, default=64,
                    help='Chunks per block for C-layer bitmask (default: 64)')
    ap.add_argument('--json', action='store_true',
                    help='Print build stats as JSON to stdout')
    ap.add_argument('--json-out', default=None,
                    help='Save build stats to JSON file')
    args = ap.parse_args()

    if not os.path.exists(args.glyph):
        print(f"ERROR: glyph file not found: {args.glyph}", file=sys.stderr)
        sys.exit(1)

    out_path = args.out or (args.glyph + '.l0')
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)

    result = build_l0v2(
        glyph_path=args.glyph,
        out_path=out_path,
        q=args.q,
        w=args.w,
        df_min=args.df_min,
        df_max=args.df_max,
        block_size=args.block_size,
    )

    if args.json:
        print(json.dumps(result, indent=2))

    if args.json_out:
        with open(args.json_out, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"[L0V2] Stats saved to {args.json_out}")


if __name__ == '__main__':
    main()
