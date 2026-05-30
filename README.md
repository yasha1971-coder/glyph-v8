# STRIDE v0 — Deterministic Corpus Analysis Toolkit

STRIDE v0 is a minimal, deterministic analysis toolkit for structured binary corpora.
It provides byte‑exact, reproducible inspection tools designed for transparent, measurable, and fully deterministic workflows.

This project revives and modernizes the original glyph‑v8 prototype, transforming it into a clean, well‑defined analysis engine focused on determinism and reproducibility.

-----

## ✨ Key Principles

- Determinism — identical input always produces identical output
- Transparency — no heuristics, no randomness, no hidden state
- Reproducibility — stable algorithms, stable CLI, stable results
- Corpus‑centric design — operates directly on raw STRIDE containers
- Minimalism — small codebase, clear architecture, no external dependencies

-----

## 📦 What STRIDE v0 Provides

STRIDE v0 performs four deterministic analyses on binary corpora:

1. **Byte Frequency** — global frequency distribution of all 256 byte values.
1. **Hotspots** — local entropy peaks across the corpus.
1. **Fingerprint** — rolling‑hash + bottom‑k MinHash content signature.
1. **HeaderSketch** — 64‑slot structural entropy sketch.

Each module is implemented as a standalone Python file and exposed through a unified CLI.

-----

## 🧩 Architecture Overview

```
stride/
 ├── cli.py                     # Unified command-line interface
 ├── build_enwik8_container.py  # Container builder
 ├── container_reader.py        # Binary container reader
 ├── container_bytefreq.py      # Byte-frequency analysis
 ├── container_hotspots.py      # Entropy hotspot analysis
 ├── container_fingerprint.py   # Rolling fingerprint
 ├── container_headersketch.py  # Structural header sketch
 ├── glyph_pack.py              # Artifact packer
 ├── glyph_store.py             # Artifact storage
 └── configs/
      └── eval_matrix.json      # Analysis configuration
```

-----

## 🚀 Installation

```bash
pip install -e .
```

-----

## 🖥 Try it in 30 seconds

```bash
git clone https://github.com/yasha1971-coder/glyph-v8
cd glyph-v8
pip install -e .
stride --help
```

Build a container and run analysis:

```bash
stride index enwik8
stride container-bytefreq enwik8.stridebin --top 10
stride container-hotspots enwik8.stridebin --top 5
stride container-fingerprint enwik8.stridebin --k 128 --window 32
stride container-headersketch enwik8.stridebin --size 64
```

-----

## 📊 Benchmark Results — STRIDE v0 (enwik8, 100MB)

**Hardware:** OVH EPYC server

|Module      |Time    |Output                                           |
|------------|--------|-------------------------------------------------|
|ByteFreq    |1.97s   |256-byte histogram, top byte: 0x20 space (13.52%)|
|Hotspots    |4.17s   |Max entropy: 5.685 (chunk 635)                   |
|HeaderSketch|4.40s   |64-slot structural profile                       |
|Fingerprint |71.6s   |128 MinHash values *(known: O(n·k) rolling hash)*|
|**Total**   |**~82s**|**Full corpus analysis**                         |

SHA256-verified proof: <proof/enwik8_benchmark.txt>

-----

## 📁 Output Artifacts

- `bytefreq.txt` — 256-line byte histogram
- `hotspots.txt` — entropy peaks by chunk
- `fingerprint.txt` — rolling MinHash signature
- `headersketch.txt` — 64-slot structural sketch
- `*.stridebin` — deterministic container format

-----

## 🧪 Tests

```bash
pytest tests/
```

-----

## 📜 Project Lineage

STRIDE is the third primitive in a deterministic systems family:

- **ACEAPEX** — parallel LZ77 decode (9,903 MB/s, merged into lzbench)
- **GLYPH** — deterministic byte-exact retrieval (6,888× faster than grep)
- **STRIDE** — field-aware integer analysis for binary protocols

Same philosophy: deterministic, exact, measurable.

-----

## 📜 License

MIT License.