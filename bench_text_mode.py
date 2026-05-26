#!/usr/bin/env python3
"""bench_text_mode.py — TEXT-mode benchmark: queries from decompressed glyph chunks."""

import struct, zlib, random, json, os, hashlib, time, statistics
from bench_runner import L0Index

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

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()

def bench_text(idx, chunks, L, trials, seed):
    nc = len(chunks)
    rng = random.Random(seed)
    eligible = [i for i in range(nc) if len(chunks[i]) >= L]
    if not eligible:
        return None
    eff = 0; fb = 0; miss = 0; rf = 0
    cands = []
    for _ in range(trials):
        ci = rng.choice(eligible)
        chunk = chunks[ci]
        off = rng.randint(0, len(chunk) - L)
        q = chunk[off:off + L]
        r = idx.search(q, adaptive=False)
        af = r.get('anchors_found', 0)
        cc = r.get('cand_count', nc)
        cs = set(r.get('candidates', []))
        if af == 0:
            miss += 1
        elif cc >= nc * 0.5:
            fb += 1
        else:
            eff += 1
            cands.append(cc)
        if ci not in cs and cc < nc * 0.5 and af > 0:
            rf += 1
    return {
        'L': L, 'trials': trials, 'seed': seed,
        'hit_rate': round((eff + fb) / trials, 4),
        'effective_pct': round(eff / trials * 100, 1),
        'fallback': fb, 'miss': miss,
        'recall': round(1 - rf / trials, 4), 'recall_fail': rf,
        'avg_cand': round(statistics.mean(cands), 1) if cands else None,
        'med_cand': int(statistics.median(cands)) if cands else None,
    }

def main():
    GLYPH = 'data/benchmark.glyph'
    OLD_L0 = 'data/benchmark.glyph.l0'
    NEW_L0 = 'data/indexes/benchmark_5M_df1.glyph.l0'
    LENGTHS = [48, 96, 192, 384]
    TRIALS = 2000; SEED = 1

    chunks = load_chunks(GLYPH)
    print(f"Chunks: {len(chunks)}, sizes: min={min(len(c) for c in chunks)}, max={max(len(c) for c in chunks)}")

    idx_old = L0Index(OLD_L0)
    idx_new = L0Index(NEW_L0)
    print(f"OLD: B={idx_old.b_count:,} C={idx_old.c_count}")
    print(f"NEW: B={idx_new.b_count:,} C={idx_new.c_count}")
    print(f"trials={TRIALS} seed={SEED}\n")

    old_r = {}; new_r = {}
    for L in LENGTHS:
        old_r[L] = bench_text(idx_old, chunks, L, TRIALS, SEED)
        new_r[L] = bench_text(idx_new, chunks, L, TRIALS, SEED)
        print(f"L={L} done")

    print(f"\n--- TEXT-MODE (trials={TRIALS}) ---")
    hdr = f"{'L':>5} | {'hit%':>6} {'eff%':>6} {'avg':>5} {'med':>4} {'rec':>6} | {'hit%':>6} {'eff%':>6} {'avg':>5} {'med':>4} {'rec':>6}"
    print(hdr)
    print(f"{'':>5} | {'--- OLD (2M) ---':^30} | {'--- NEW (4.8M) ---':^30}")
    print('-' * 75)
    for L in LENGTHS:
        o = old_r[L]; n = new_r[L]
        oa = f"{o['avg_cand']:.0f}" if o['avg_cand'] else '-'
        na = f"{n['avg_cand']:.0f}" if n['avg_cand'] else '-'
        om = str(o['med_cand']) if o['med_cand'] else '-'
        nm = str(n['med_cand']) if n['med_cand'] else '-'
        print(f"{L:>5} | {o['hit_rate']*100:>5.1f}% {o['effective_pct']:>5.1f}% {oa:>5} {om:>4} {o['recall']:>6.4f} | {n['hit_rate']*100:>5.1f}% {n['effective_pct']:>5.1f}% {na:>5} {nm:>4} {n['recall']:>6.4f}")

    idx_old.close(); idx_new.close()

    out = {
        'mode': 'text',
        'strategy': 'isect_v1_canonical',
        'trials': TRIALS, 'seed': SEED,
        'results': {str(L): {'old': old_r[L], 'new': new_r[L]} for L in LENGTHS}
    }
    with open('data/bench_text_mode.json', 'w') as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved: data/bench_text_mode.json")

    print(f"\n--- SHA256 ---")
    for p in [GLYPH, OLD_L0, NEW_L0, 'data/l0_search']:
        print(f"  {sha256_file(p)}  {p}")

if __name__ == '__main__':
    main()
