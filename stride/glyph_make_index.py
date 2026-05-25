#!/usr/bin/env python3
import argparse, json, os, struct, zlib, time, hashlib

MAGIC = b'GLYPH1'

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()

def make_index(glyph_path, out_path=None, verify_decompress=True):
    t0 = time.perf_counter()
    with open(glyph_path, 'rb') as f:
        magic = f.read(6)
        if magic != MAGIC:
            raise ValueError(f"Bad magic: {magic}")

        hdr = f.read(3)
        if len(hdr) != 3:
            raise ValueError("Short header")
        version, ng = struct.unpack('<BH', hdr)

        chunks = []
        for i in range(ng):
            csize_bytes = f.read(4)
            if len(csize_bytes) != 4:
                raise ValueError(f"Truncated at chunk {i}")
            csize = struct.unpack('<I', csize_bytes)[0]
            off = f.tell()
            comp = f.read(csize)
            if len(comp) != csize:
                raise ValueError(f"Truncated payload at chunk {i}")

            if verify_decompress:
                raw = zlib.decompress(comp)
                usize = len(raw)
            else:
                usize = None

            chunks.append({"off": off, "csize": csize, "usize": usize})

    if out_path is None:
        out_path = glyph_path + ".idx.json"

    out = {
        "path": glyph_path,
        "sha256": sha256_file(glyph_path),
        "magic": "GLYPH1",
        "version": int(version),
        "num_chunks": int(ng),
        "verify_decompress": bool(verify_decompress),
        "chunks": chunks,
        "build_s": round(time.perf_counter() - t0, 6),
    }

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as w:
        json.dump(out, w, indent=2)

    return out_path, out

def main():
    ap = argparse.ArgumentParser(description="Build random-access index for .glyph")
    ap.add_argument("glyph", help="Path to .glyph")
    ap.add_argument("--out", default=None, help="Output index path (default: <glyph>.idx.json)")
    ap.add_argument("--no-verify", action="store_true",
                    help="Do NOT decompress chunks while building index (usize will be null)")
    args = ap.parse_args()

    out_path, meta = make_index(args.glyph, args.out, verify_decompress=not args.no_verify)
    print(f"Saved: {out_path}")
    print(f"Chunks: {meta['num_chunks']} build_s={meta['build_s']} sha256={meta['sha256']} verify={meta['verify_decompress']}")

if __name__ == "__main__":
    main()
