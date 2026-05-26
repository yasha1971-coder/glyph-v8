#!/usr/bin/env python3
"""glyph_make_headersketch.py — Build per-chunk content-bloom sketches for tail-path.

Each chunk gets a single-hash Bloom filter (k=1) populated with ALL 8-gram
CRC32 hashes from the uncompressed chunk content.

At query time, check ALL query 8-grams against the chunk's bloom. If ANY
bloom bit is NOT set, the chunk cannot contain the query (zero false negatives).

Parameters:
  SKETCH_BYTES = 4096 (32768 bits per chunk, fill ~0.39)
  SKETCH_K     = 1 (single hash)
  SKETCH_Q     = 8 (8-gram size)

Tail-path use: for queries with <=2 high-df minimizers, the content-bloom
filters ~4500 bloom-miss candidates down to ~80, enabling 5-6x speedup on
worst-case pathological queries while maintaining e2e_hit_rate=1.0.

Output: <glyph>.headersketch.bin — header(16B) + N*4096 bytes
Size: ~23.8 MB for 6104 chunks.
"""

import argparse
import os
import struct
import time
import zlib

HS_MAGIC = b"GLHS"
HS_VERSION = 7
SKETCH_BYTES = 4096
SKETCH_BITS = SKETCH_BYTES * 8
SKETCH_Q = 8
SKETCH_K = 1


def load_chunks(glyph_path):
    chunks = []
    with open(glyph_path, 'rb') as f:
        magic = f.read(6)
        if magic != b'GLYPH1':
            raise ValueError(f"Bad magic: {magic}")
        version, ng = struct.unpack('<BH', f.read(3))
        for _ in range(ng):
            sz = struct.unpack('<I', f.read(4))[0]
            chunks.append(zlib.decompress(f.read(sz)))
    return chunks


def build_headersketches(glyph_path, out_bin=None):
    t0 = time.perf_counter()
    chunks = load_chunks(glyph_path)
    nc = len(chunks)
    t_load = time.perf_counter() - t0

    if out_bin is None:
        out_bin = glyph_path + ".headersketch.bin"

    os.makedirs(os.path.dirname(out_bin) or ".", exist_ok=True)

    all_sketches = bytearray(nc * SKETCH_BYTES)
    _crc32 = zlib.crc32
    q = SKETCH_Q
    mask = SKETCH_BITS - 1

    t1 = time.perf_counter()
    total_grams = 0
    for ci, chunk in enumerate(chunks):
        base = ci * SKETCH_BYTES
        n = len(chunk)
        if n < q:
            continue
        sv = all_sketches
        for i in range(n - q + 1):
            h = _crc32(chunk[i:i + q]) & 0xFFFFFFFF
            pos = h & mask
            sv[base + (pos >> 3)] |= 1 << (pos & 7)
        total_grams += n - q + 1
        if (ci + 1) % 1000 == 0:
            elapsed = time.perf_counter() - t1
            print(f"  [{ci+1}/{nc}] {elapsed:.1f}s ({total_grams/1e6:.1f}M grams)")

    t_build = time.perf_counter() - t1

    with open(out_bin, 'wb') as f:
        f.write(HS_MAGIC)
        f.write(struct.pack('<B', HS_VERSION))
        f.write(struct.pack('<H', nc))
        f.write(struct.pack('<B', q))
        f.write(struct.pack('<B', SKETCH_K))
        f.write(struct.pack('<I', SKETCH_BITS))
        f.write(b'\x00' * (16 - 13))
        f.write(bytes(all_sketches))

    file_size = os.path.getsize(out_bin)

    print(f"[headersketch] Built {out_bin}")
    print(f"  chunks: {nc}, q-grams: {total_grams/1e6:.1f}M")
    print(f"  bloom: {SKETCH_BYTES}B/chunk ({SKETCH_BITS} bits, k={SKETCH_K}, q={q})")
    print(f"  total size: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)")
    print(f"  load time: {t_load:.2f}s, bloom build: {t_build:.2f}s")

    return out_bin


class HeaderSketchIndex:
    HEADER_SIZE = 16

    def __init__(self, hs_bin_path):
        with open(hs_bin_path, 'rb') as f:
            magic = f.read(4)
            if magic != HS_MAGIC:
                raise ValueError(f"Bad headersketch magic: {magic}")
            self.version = struct.unpack('<B', f.read(1))[0]
            self.num_chunks = struct.unpack('<H', f.read(2))[0]
            self.q = struct.unpack('<B', f.read(1))[0]
            self.k = struct.unpack('<B', f.read(1))[0]
            self.sketch_bits = struct.unpack('<I', f.read(4))[0]
            f.read(self.HEADER_SIZE - 13)
            self.sketch_bytes = self.sketch_bits // 8
            self.data = f.read(self.num_chunks * self.sketch_bytes)

        if len(self.data) != self.num_chunks * self.sketch_bytes:
            raise ValueError(f"Truncated headersketch data: got {len(self.data)}, expected {self.num_chunks * self.sketch_bytes}")
        if self.sketch_bits & (self.sketch_bits - 1) != 0:
            raise ValueError(f"sketch_bits must be power of 2, got {self.sketch_bits}")
        self.mv = memoryview(self.data)
        self.mask = self.sketch_bits - 1
        self._crc32 = zlib.crc32

    def check_chunk(self, chunk_idx, query):
        q = self.q
        qlen = len(query)
        if qlen < q:
            return True
        off = chunk_idx * self.sketch_bytes
        mv = self.mv
        mask = self.mask
        _crc32 = self._crc32
        for i in range(qlen - q + 1):
            h = _crc32(query[i:i + q]) & 0xFFFFFFFF
            pos = h & mask
            if not (mv[off + (pos >> 3)] & (1 << (pos & 7))):
                return False
        return True

    def reorder_candidates(self, candidates, query):
        header_hits = []
        rest = []
        q = self.q
        qlen = len(query)
        if qlen < q:
            return candidates, []
        off_mul = self.sketch_bytes
        mv = self.mv
        mask = self.mask
        _crc32 = self._crc32
        n_qgrams = qlen - q + 1
        qgram_checks = []
        for i in range(n_qgrams):
            h = _crc32(query[i:i + q]) & 0xFFFFFFFF
            pos = h & mask
            qgram_checks.append((pos >> 3, 1 << (pos & 7)))
        for ci in candidates:
            off = ci * off_mul
            match = True
            for byte_off, bitmask in qgram_checks:
                if not (mv[off + byte_off] & bitmask):
                    match = False
                    break
            if match:
                header_hits.append(ci)
            else:
                rest.append(ci)
        return header_hits, rest


def main():
    ap = argparse.ArgumentParser(description="Build per-chunk content-bloom sketches for .glyph")
    ap.add_argument("glyph", help="Path to .glyph archive")
    ap.add_argument("--out-bin", default=None, help="Output .headersketch.bin path")
    args = ap.parse_args()

    build_headersketches(args.glyph, out_bin=args.out_bin)


if __name__ == "__main__":
    main()
