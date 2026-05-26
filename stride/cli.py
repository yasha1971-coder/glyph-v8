import argparse
import sys
from pathlib import Path

from . import (
    glyph_make_index,
    glyph_make_hotspots,
    glyph_make_fingerprint,
    glyph_make_headersketch,
)

from .container_reader import StrideContainer
from .container_bytefreq import compute_bytefreq
from .container_hotspots import compute_hotspots
from .container_fingerprint import compute_fingerprint
from .container_headersketch import compute_headersketch

VERSION = "0.1.0"


def run_module(module, argv):
    old_argv = sys.argv
    sys.argv = argv
    try:
        module.main()
    finally:
        sys.argv = old_argv


def cmd_version(args):
    print("STRIDE version:", VERSION)


def cmd_info(args):
    p = Path(args.glyph)
    if not p.exists():
        print("File not found:", p)
        sys.exit(1)

    print("File:", p)
    print("Size:", p.stat().st_size, "bytes")
    print("Absolute:", p.resolve())


def cmd_index(args):
    argv = ["glyph_make_index", args.glyph]
    if args.out:
        argv += ["--out", args.out]
    run_module(glyph_make_index, argv)


def cmd_hotspots(args):
    argv = ["glyph_make_hotspots", "--glyph", args.glyph]
    if args.q:
        argv += ["--q", str(args.q)]
    if args.w:
        argv += ["--w", str(args.w)]
    if args.max_df:
        argv += ["--max-df", str(args.max_df)]
    if args.out:
        argv += ["--out", args.out]
    run_module(glyph_make_hotspots, argv)


def cmd_fingerprint(args):
    argv = ["glyph_make_fingerprint", args.glyph]
    if args.q:
        argv += ["--q", str(args.q)]
    if args.w:
        argv += ["--w", str(args.w)]
    if args.bloom_bits:
        argv += ["--bloom-bits", str(args.bloom_bits)]
    if args.k:
        argv += ["--k", str(args.k)]
    if args.out_bin:
        argv += ["--out-bin", args.out_bin]
    if args.out_json:
        argv += ["--out-json", args.out_json]
    if args.verify:
        argv += ["--verify"]
    if args.verify_trials:
        argv += ["--verify-trials", str(args.verify_trials)]
    run_module(glyph_make_fingerprint, argv)


def cmd_headersketch(args):
    argv = ["glyph_make_headersketch", args.glyph]
    if args.out_bin:
        argv += ["--out-bin", args.out_bin]
    run_module(glyph_make_headersketch, argv)


# -------------------------
# STRIDE v0 CONTAINER COMMANDS
# -------------------------

def cmd_container_info(args):
    c = StrideContainer(args.container)
    print(f"File: {args.container}")
    print(f"Corpus size: {c.corpus_size} bytes")
    print(f"Chunk size: {c.chunk_size} bytes")
    print(f"Chunks: {sum(1 for _ in c.iter_chunks())}")


def cmd_container_bytefreq(args):
    total, top_items = compute_bytefreq(args.container, args.top)
    print(f"File: {args.container}")
    print(f"Total bytes processed: {total}")
    print(f"Top {args.top} bytes:")
    for b, cnt in top_items:
        print(f"  {b:3d}  0x{b:02X}  {cnt}  ({cnt/total:.4%})")


def cmd_container_hotspots(args):
    results = compute_hotspots(args.container, args.top)
    print(f"File: {args.container}")
    print(f"Top {args.top} hotspots (by entropy):")
    for ent, cid in results:
        print(f"  Chunk {cid:5d}   Entropy: {ent:.5f}")


def cmd_container_fingerprint(args):
    fp = compute_fingerprint(args.container, args.k, args.window)
    print(f"File: {args.container}")
    print(f"Fingerprint (k={args.k}, window={args.window}):")
    for h in fp:
        print(f"  0x{h:016X}")


def cmd_container_headersketch(args):
    sketch = compute_headersketch(args.container, args.size)
    print(f"File: {args.container}")
    print(f"HeaderSketch (size={args.size}):")
    for i, v in enumerate(sketch):
        print(f"  {i:3d}: {v:.5f}")


# -------------------------
# container-compare
# -------------------------

def jaccard(a, b):
    sa, sb = set(a), set(b)
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def l2(a, b):
    n = min(len(a), len(b))
    return sum((a[i] - b[i]) ** 2 for i in range(n)) ** 0.5


def cmd_container_compare(args):
    fp1 = compute_fingerprint(args.a, args.k, args.window)
    fp2 = compute_fingerprint(args.b, args.k, args.window)

    hs1 = compute_headersketch(args.a, args.size)
    hs2 = compute_headersketch(args.b, args.size)

    j = jaccard(fp1, fp2)
    d = l2(hs1, hs2)

    print("Comparing:")
    print(" A:", args.a)
    print(" B:", args.b)
    print()
    print(f"Fingerprint Jaccard: {j:.4f}")
    print(f"HeaderSketch L2:     {d:.4f}")
    print()
    print("Overall similarity score:", f"{(j * 0.7 + (1 - d) * 0.3):.4f}")


# -------------------------
# MAIN
# -------------------------

def main():
    parser = argparse.ArgumentParser(prog="stride", description="STRIDE CLI")
    sub = parser.add_subparsers(dest="cmd")

    # version
    p_ver = sub.add_parser("version")
    p_ver.set_defaults(func=cmd_version)

    # info
    p_info = sub.add_parser("info")
    p_info.add_argument("glyph")
    p_info.set_defaults(func=cmd_info)

    # index
    p_idx = sub.add_parser("index")
    p_idx.add_argument("glyph")
    p_idx.add_argument("--out")
    p_idx.set_defaults(func=cmd_index)

    # hotspots
    p_hs = sub.add_parser("hotspots")
    p_hs.add_argument("glyph")
    p_hs.add_argument("--q", type=int)
    p_hs.add_argument("--w", type=int)
    p_hs.add_argument("--max-df", type=int)
    p_hs.add_argument("--out")
    p_hs.set_defaults(func=cmd_hotspots)

    # fingerprint
    p_fp = sub.add_parser("fingerprint")
    p_fp.add_argument("glyph")
    p_fp.add_argument("--q", type=int)
    p_fp.add_argument("--w", type=int)
    p_fp.add_argument("--bloom-bits", type=int)
    p_fp.add_argument("--k", type=int)
    p_fp.add_argument("--out-bin")
    p_fp.add_argument("--out-json")
    p_fp.add_argument("--verify", action="store_true")
    p_fp.add_argument("--verify-trials", type=int)
    p_fp.set_defaults(func=cmd_fingerprint)

    # headersketch
    p_hsk = sub.add_parser("headersketch")
    p_hsk.add_argument("glyph")
    p_hsk.add_argument("--out-bin")
    p_hsk.set_defaults(func=cmd_headersketch)

    # container-info
    p_cinfo = sub.add_parser("container-info")
    p_cinfo.add_argument("container")
    p_cinfo.set_defaults(func=cmd_container_info)

    # container-bytefreq
    p_bf = sub.add_parser("container-bytefreq")
    p_bf.add_argument("container")
    p_bf.add_argument("--top", type=int, default=20)
    p_bf.set_defaults(func=cmd_container_bytefreq)

    # container-hotspots
    p_chs = sub.add_parser("container-hotspots")
    p_chs.add_argument("container")
    p_chs.add_argument("--top", type=int, default=20)
    p_chs.set_defaults(func=cmd_container_hotspots)

    # container-fingerprint
    p_cfp = sub.add_parser("container-fingerprint")
    p_cfp.add_argument("container")
    p_cfp.add_argument("--k", type=int, default=128)
    p_cfp.add_argument("--window", type=int, default=32)
    p_cfp.set_defaults(func=cmd_container_fingerprint)

    # container-headersketch
    p_hsk2 = sub.add_parser("container-headersketch")
    p_hsk2.add_argument("container")
    p_hsk2.add_argument("--size", type=int, default=64)
    p_hsk2.set_defaults(func=cmd_container_headersketch)

    # container-compare
    p_cmp = sub.add_parser("container-compare")
    p_cmp.add_argument("a")
    p_cmp.add_argument("b")
    p_cmp.add_argument("--k", type=int, default=128)
    p_cmp.add_argument("--window", type=int, default=32)
    p_cmp.add_argument("--size", type=int, default=64)
    p_cmp.set_defaults(func=cmd_container_compare)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return

    args.func(args)