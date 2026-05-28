# STRIDE v0 — Deterministic Corpus Analysis Toolkit

STRIDE v0 is a minimal, deterministic analysis toolkit for structured binary corpora.
It provides byte‑exact, reproducible inspection tools designed for transparent, measurable, and fully deterministic workflows.

This project revives and modernizes the original glyph‑v8 prototype, transforming it into a clean, well‑defined analysis engine focused on determinism and reproducibility.

---

## ✨ Key Principles

- Determinism — identical input always produces identical output
- Transparency — no heuristics, no randomness, no hidden state
- Reproducibility — stable algorithms, stable CLI, stable results
- Corpus‑centric design — operates directly on raw STRIDE containers
- Minimalism — small codebase, clear architecture, no external dependencies

---

## 📦 What STRIDE v0 Provides

STRIDE v0 performs four deterministic analyses on binary corpora:

1. **Byte Frequency** — global frequency distribution of all 256 byte values.
2. **Hotspots** — local entropy peaks across the corpus.
3. **Fingerprint** — rolling‑hash + bottom‑k MinHash content signature.
4. **HeaderSketch** — 64‑slot structural entropy sketch.

---

## 🚀 Try it in 30 seconds

\`\`\`bash
git clone https://github.com/yasha1971-coder/glyph-v8
cd glyph-v8
pip install -e .
stride --help
stride container-bytefreq enwik8.stridebin --top 10
\`\`\`

---

## 📊 Benchmark Results — STRIDE v0 (enwik8, 100MB)

**Hardware:** OVH EPYC server

| Module | Time | Output |
|--------|------|--------|
| ByteFreq | 1.97s | top byte: 0x20 space (13.52%) |
| Hotspots | 4.17s | max entropy: 5.685 (chunk 635) |
| HeaderSketch | 4.40s | 64-slot structural profile |
| Fingerprint | 71.6s | 128 MinHash values |
| **Total** | **~82s** | **full corpus analysis** |

SHA256-verified proof: [proof/enwik8_benchmark.txt](proof/enwik8_benchmark.txt)

---

## 📜 Project Lineage

- **ACEAPEX** — parallel LZ77 decode (9,903 MB/s, merged into lzbench)
- **GLYPH** — deterministic byte-exact retrieval (6,888× faster than grep)
- **STRIDE** — field-aware integer analysis for binary protocols

---

## 🧪 Tests

\`\`\`bash
pytest tests/
\`\`\`

---

## 📜 License

MIT License.
