#!/usr/bin/env python3
"""glyph_pack.py — Pack a raw binary file into a GLYPH1 archive.

Splits the input into fixed-size chunks, compresses each with zlib,
and writes the GLYPH1 container format.

Usage:
    python3 glyph_pack.py --input corpus.bin --output data/corpus.glyph
    python3 glyph_pack.py --input corpus.bin --output data/corpus.glyph --chunk-size 16384 --level 6
"""

import argparse
import hashlib
import os
import struct
import sys
import time
import zlib

MAGIC = b'GLYPH1'
VERSION = 1


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def pack_glyph(input_path, output_path, chunk_size=16384, level=6):
    t0 = time.perf_counter()
    file_size = os.path.getsize(input_path)
    num_chunks = (file_size + chunk_size - 1) // chunk_size

    print(f"[glyph_pack] Input:      {input_path} ({file_size} bytes, "
          f"{file_size / (1 << 20):.1f} MB)")
    print(f"[glyph_pack] Chunk size: {chunk_size}")
    print(f"[glyph_pack] Chunks:     {num_chunks}")
    print(f"[glyph_pack] Zlib level: {level}")

    tmp_path = output_path + '.tmp'
    total_compressed = 0

    with open(input_path, 'rb') as fin, open(tmp_path, 'wb') as fout:
        fout.write(MAGIC)
        fout.write(struct.pack('<B', VERSION))
        fout.write(struct.pack('<H', num_chunks))

        for i in range(num_chunks):
            raw = fin.read(chunk_size)
            if not raw:
                break
            comp = zlib.compress(raw, level)
            fout.write(struct.pack('<I', len(comp)))
            fout.write(comp)
            total_compressed += len(comp)

    os.replace(tmp_path, output_path)
    out_size = os.path.getsize(output_path)
    elapsed = time.perf_counter() - t0

    ratio = out_size / file_size if file_size > 0 else 0
    print(f"[glyph_pack] Output:     {output_path} ({out_size} bytes, "
          f"{out_size / (1 << 20):.1f} MB)")
    print(f"[glyph_pack] Ratio:      {ratio:.3f} ({100 * ratio:.1f}%)")
    print(f"[glyph_pack] SHA256:     {sha256_file(output_path)}")
    print(f"[glyph_pack] Time:       {elapsed:.1f}s")


def main():
    ap = argparse.ArgumentParser(
        description='Pack raw file into GLYPH1 archive')
    ap.add_argument('--input', required=True, help='Raw input file')
    ap.add_argument('--output', required=True, help='Output .glyph path')
    ap.add_argument('--chunk-size', type=int, default=16384,
                    help='Chunk size in bytes (default: 16384)')
    ap.add_argument('--level', type=int, default=6,
                    help='Zlib compression level 1-9 (default: 6)')
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
    pack_glyph(args.input, args.output, args.chunk_size, args.level)


if __name__ == '__main__':
    main()
