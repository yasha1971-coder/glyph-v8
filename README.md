STRIDE v0 — Minimal Deterministic Corpus Analyzer

███████╗████████╗██████╗ ██╗██████╗ ███████╗
██╔════╝╚══██╔══╝██╔══██╗██║██╔══██╗██╔════╝
███████╗   ██║   ██████╔╝██║██║  ██║█████╗  
╚════██║   ██║   ██╔══██╗██║██║  ██║██╔══╝  
███████║   ██║   ██║  ██║██║██████╔╝███████╗
╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚═════╝ ╚══════╝
Minimal Deterministic Corpus Analyzer


STRIDE v0 is a minimal, deterministic analysis toolkit for STRIDE containers.
It provides byte‑exact, reproducible corpus inspection tools designed for low‑level structural analysis, benchmarking, and research workflows.

STRIDE v0 is intentionally small, transparent, and dependency‑free.
It is not a general‑purpose framework — it is a precise, verifiable toolset for understanding STRIDE‑encoded corpora.

---

Design Goals

• Determinism — identical input always produces identical output
• Minimalism — no external dependencies, no hidden state
• Transparency — simple, readable Python implementation
• Reproducibility — stable algorithms and stable CLI
• Corpus‑centric — tools operate directly on STRIDE containers


---

Features

• bytefreq — global byte‑frequency statistics
• hotspots — per‑chunk entropy analysis
• fingerprint — rolling‑hash + bottom‑k MinHash corpus fingerprint
• headersketch — 64‑element structural entropy sketch
• compare — corpus similarity (fingerprint Jaccard + sketch L2)
• full CLI — complete command‑line interface for all analysis tools


---

Source Layout

./stride_v0/
    README.md
    stride/
        bytefreq.py
        hotspots.py
        fingerprint.py
        headersketch.py
        compare.py
        cli.py


---

CLI Usage

Byte frequency

stride bytefreq corpus.stridebin


Hotspots (entropy map)

stride hotspots corpus.stridebin


Fingerprint (MinHash)

stride fingerprint corpus.stridebin


Header sketch

stride headersketch corpus.stridebin


Corpus comparison

stride compare corpus_A.stridebin corpus_B.stridebin


---

Example Output

Bytefreq

{
  "00": 123456,
  "01": 98765,
  "02": 54321,
  ...
}


Hotspots

chunk_0001: entropy=7.92
chunk_0002: entropy=7.88
chunk_0003: entropy=7.91
...


Compare

fingerprint_jaccard: 0.873
headersketch_l2: 0.042
similarity_score: 0.912


---

Limitations (Intentional)

STRIDE v0 is a minimal prototype, not a full analysis suite.

• No visualization tools
• No parallel processing
• No fuzzy matching
• No semantic analysis
• No compression or encoding logic


Its purpose is clarity, not completeness.

---

Roadmap

v0.x (current)

• Minimal deterministic analyzers
• Stable CLI
• Reproducible algorithms


v1.0 (planned)

• Unified output schema
• Optional JSON output
• Chunk‑level structural diff
• Multi‑corpus comparison
• Performance improvements


---

Release

Initial public pre‑release:https://github.com/yasha1971-coder/glyph-v8/releases/tag/v0.1.0

---

License

MIT License — see LICENSE file.

---

Acknowledgements

STRIDE v0 is part of a broader research effort exploring deterministic corpus analysis and field‑aware encoding strategies.

---
