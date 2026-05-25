# GLYPH-CORE v9.1 — OVH Mirror Manifest

## Base
- Upgraded from: `glyph_core_v9.0_ovh_mirror.tar.gz`
- Upgrade date: 2026-02-25
- Patch: headersketch hit-path reorder (HS_REORDER_MIN=16) + tail lab tool
- Improvement: L=48 tail events 26 → 11 at threshold=5 (58% reduction), 0 at threshold=100

## Architecture

### Data Layer
- `data/benchmark.glyph` — 6104 independently zlib-compressed chunks (16KB uncompressed each)
- Chunk offset table: `data/benchmark.glyph.idx.json` (built at runtime if missing)

### Index Stack (from broadest to narrowest)
| Index | File | Size | Parameters |
|-------|------|------|------------|
| L0 primary | `data/benchmark.glyph.l0` | 22 MB | q=8, B+C layers |
| L0 extended | `data/indexes/benchmark_5M_df1.glyph.l0` | 65 MB | B=4.8M, df_min=1 |
| Fingerprint w40 | `data/benchmark.glyph.fingerprints.bin` | 12 MB | q=8 w=40 bloom=16384 k=11 |
| Fingerprint w24 | `data/benchmark.glyph.fingerprints_w24.bin` | 12 MB | q=8 w=24 bloom=16384 k=11 |
| Hotspots | `data/benchmark.glyph.hotspots.bin` | 23 MB | q=8 w=40 max_df=4096 |
| HeaderSketch | `data/benchmark.glyph.headersketch.bin` | 24 MB | sketch=4096B q=8 k=1 |

### Query Pipeline
```
query → L0 minimizers → B/C anchor lookup → intersection/union
      → confidence reorder (isect+1000, union+200, freq+10..3)
      → [miss path] hotspots + bloom scan_all_scored
      → [hit path]  bloom filter_candidates_fast
      → [tail]      headersketch rescue reorder #1 (q_mins ≤ 2, df/nc ≥ 0.6)
      → fast_cap overflow rescue reorder #2 (len(cs) > fast_cap_this)
      → verify: fast → miss_cs → miss_exhaust
```

### Adaptive Fast Cap (v9.0)
- `len(cs) > 4096` → `fast_cap_this = 2048`
- `len(cs) <= 4096` → `fast_cap_this = 256`
- Single source: `compute_fast_cap()` function
- Constants: `FAST_CAP=256`, `FAST_CAP_SWITCH=4096`, `FAST_CAP_BIG=2048`

### Headersketch Hit-Path Reorder (v9.1 new)
- Headersketch reorder now applied on ALL paths (hit + miss) when `len(cs) > HS_REORDER_MIN` (default: 16)
- Previously only triggered on miss-path tail detection and fast_cap overflow
- Result: L=48 tail events reduced 58% (26 → 11 at threshold=5)

### Tail Observability (v9.0 new)
Events logged to JSONL when `decompress_count > tail_threshold`:
- `found_via`: fast / miss_cs / miss_exhaust
- `verify_steps`, `rank_in_cs`, `rank_full_cs`
- `cs_considered_len`, `fast_cap_this`
- Safety assertions enforce invariants inline

### Correctness Invariants
- `e2e_hit_rate = 1.0` (all queries found)
- `verify_miss = 0` (no false negatives)
- `candidate_fn = 0` (no candidate false negatives)
- `bloom_fn = 0` (no bloom false negatives)
- `found_via=fast` => `verify_steps == rank_in_cs + 1` and `rank_in_cs >= 0`
- `found_via=miss_cs` => `fast_cap_triggered=1` and `rank_in_cs==-1`
- `found_via=miss_exhaust` => `rank_full_cs==-1`

## Commands

### Quick start (one command)
```bash
bash scripts/ovh_quickstart.sh
```

### Smoke test only (~2 min)
```bash
bash scripts/ovh_quickstart.sh --smoke-only
```

### Regression gate
```bash
bash tests/test_tail_regression.sh
```

### Full evaluation with tail logging
```bash
TAIL_LOG=1 bash scripts/run_full_eval.sh
```

### Tail event analysis
```bash
python3 tools_tail_events_summary.py --trials 2000 data/bench_runs/<timestamp>
```

### Invariant check
```bash
python3 tools_check_tail_invariants.py data/bench_runs/<timestamp>
```

## File Inventory
```
bench_text_mode.py              — benchmark driver + verify + tail logging
glyph_store.py                  — chunk access with LRU cache
build_l0v2.py                   — L0V2 binary index builder (replaces tools/l0_build)
glyph_pack.py                   — raw file → GLYPH1 archive packer
glyph_make_index.py             — JSON offset index (.idx.json) for GlyphStore
glyph_make_fingerprint.py       — FingerprintIndex (bloom per-chunk)
glyph_make_hotspots.py          — HotspotsIndex (minimizer→chunks), CLI: --glyph
glyph_make_headersketch.py      — HeaderSketchIndex (content-bloom)
full_scan_baseline.py           — brute-force baseline search
triage_gate.py                  — correctness triage tool
tools_check_tail_invariants.py  — standalone invariant checker
tools_tail_events_summary.py    — tail event aggregation
tools_tail_lab.py               — tail analysis laboratory (causes, distributions, worst events)
tests/test_tail_regression.sh   — regression gate (golden test)
scripts/ovh_quickstart.sh       — one-command setup+eval
scripts/run_full_eval.sh        — full evaluation harness
scripts/build_all_indexes.sh    — index builder
scripts/summary_eval.py         — result summarizer
configs/eval_matrix.json        — evaluation parameters
build_manifest.json             — SHA256 integrity manifest
VERSION                         — version metadata
```

## New Corpus Pipeline

To index and benchmark a new corpus (any raw binary file):

```bash
# 1. Pack raw file → GLYPH1 archive
python3 glyph_pack.py --input corpus.bin --output data/corpus.glyph

# 2. Build L0V2 binary index (NOT glyph_make_index.py — that makes JSON)
python3 build_l0v2.py --glyph data/corpus.glyph --out data/corpus.glyph.l0

# 3. Build fingerprints (w40 + w24)
python3 glyph_make_fingerprint.py data/corpus.glyph \
    --w 40 --q 8 --bloom-bits 16384 --k 11 \
    --out-bin data/corpus.glyph.fingerprints.bin --verify
python3 glyph_make_fingerprint.py data/corpus.glyph \
    --w 24 --q 8 --bloom-bits 16384 --k 11 \
    --out-bin data/corpus.glyph.fingerprints_w24.bin --verify

# 4. Build hotspots (use --glyph, NOT positional)
python3 glyph_make_hotspots.py --glyph data/corpus.glyph \
    --q 8 --w 40 --max-df 4096 --out data/corpus.glyph.hotspots.bin

# 5. Build headersketch
python3 glyph_make_headersketch.py data/corpus.glyph \
    --out-bin data/corpus.glyph.headersketch.bin

# 6. Build JSON offset index (optional, for GlyphStore)
python3 glyph_make_index.py data/corpus.glyph

# 7. Run full_stack bench
python3 bench_text_mode.py \
    --glyph data/corpus.glyph \
    --new data/corpus.glyph.l0 \
    --bloom data/corpus.glyph.fingerprints.bin \
    --bloom-miss data/corpus.glyph.fingerprints_w24.bin \
    --hotspots data/corpus.glyph.hotspots.bin \
    --headersketch data/corpus.glyph.headersketch.bin \
    --e2e-verify --skip-old --trials 2000 --seed 1
```

## Requirements
- Python 3.8+
- No external packages (stdlib only)
- ~300 MB disk space
- No GPU needed
- Works offline
