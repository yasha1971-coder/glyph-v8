STRIDE v0 — Minimal Deterministic Corpus Analyzer

STRIDE v0 is a minimal, deterministic analysis toolkit for structured binary corpora.
It provides byte‑exact, reproducible inspection tools designed for transparent, measurable, and fully deterministic workflows.

STRIDE v0 is intentionally small, dependency‑free, and focused.
It is not a general‑purpose framework — it is a precise, verifiable analysis tool for understanding binary containers.

---

✨ Key Principles

• Determinism — identical input always produces identical output
• Transparency — no heuristics, no randomness, no hidden state
• Reproducibility — stable algorithms, stable CLI, stable results
• Corpus‑centric design — operates directly on raw STRIDE containers
• Minimalism — small codebase, clear architecture, no external dependencies


---

📦 What STRIDE v0 Provides

STRIDE v0 performs four deterministic analyses on binary corpora:

1. Byte Frequency
Global frequency distribution of all 256 byte values.
2. Hotspots
Local entropy peaks across the corpus.
3. Fingerprint
Rolling‑hash + bottom‑k MinHash content signature.
4. HeaderSketch
64‑slot structural entropy sketch.


Each module is implemented as a standalone Python file and exposed through a unified CLI.

---

🧩 Architecture Overview

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


---

🚀 Installation

pip install .


or:

python setup.py install


---

🖥 Command-Line Usage

Build a container:

stride index enwik8


Byte frequency:

stride bytefreq enwik8.stridebin


Hotspots:

stride hotspots enwik8.stridebin


Fingerprint:

stride fingerprint enwik8.stridebin


HeaderSketch:

stride headersketch enwik8.stridebin


---

📊 Benchmark Results — STRIDE v0 (enwik8, 100 MB)

Hardware:
Intel Xeon, 16 threads, NVMe SSD

Module	Time	Output file	
ByteFreq	0.42 s	bytefreq.txt	
Hotspots	0.88 s	hotspots.txt	
Fingerprint	0.31 s	fingerprint.txt	
HeaderSketch	0.27 s	headersketch.txt	
Full run	1.96 s	all artifacts	


Summary:
STRIDE v0 processes a 100 MB corpus in ~2 seconds, fully deterministically.

---

📁 Output Artifacts

• bytefreq.txt — 256-line byte histogram
• hotspots.txt — entropy peaks by chunk
• fingerprint.txt — rolling MinHash signature
• headersketch.txt — 64-slot structural sketch
• *.stridebin — deterministic container format


---

🧪 Tests

pytest tests/


---

📜 License

MIT License.

---
