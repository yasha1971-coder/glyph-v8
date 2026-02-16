# Glyph v8 (L0 index + search)

This repo contains:
- `tools/l0_build` — builds L0 index from `.glyph`
- `tools/l0_search` — search (intersect strategy)
- `bench_text_mode.py` — TEXT-mode benchmark (queries from decompressed glyph chunks)
- `proof/` — benchmark output + SHA256SUMS

Large binary artifacts (`benchmark.glyph`, `.l0`) are provided via GitHub Releases.
Glyph v8 is not the first system to search compressed data.

But it is a simple, practical implementation of:
chunked compression + minimizer indexing + partial decompression.

Designed for:
- logs
- source code
- large text archives

A lightweight foundation for building searchable compressed storage.
