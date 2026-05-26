# STRIDE v0 — Deterministic Field‑Aware Integer Analyzer

STRIDE v0 is a deterministic, field‑aware integer **analysis and modeling tool** revived from the abandoned glyph‑v8 prototype.  
It profiles integer fields in binary protocols, builds per‑field entropy models, and forms the foundation for a future STRIDE codec (planned for v1).

This version does **not** include an encoder/decoder.  
It focuses entirely on deterministic corpus analysis.

---

## Features (v0)

### Profiling Layer
- Parse binary corpus  
- Detect integer fields  
- Build per‑field histograms  
- Estimate entropy  

### Modeling Layer
- Select best codec model (Delta, Rice, Elias, Dictionary)  
- Build entropy model  
- Generate `model.json`  

### Container Analysis Tools
- `container-bytefreq` — byte frequency distribution  
- `container-hotspots` — entropy hotspots  
- `container-fingerprint` — rolling fingerprint  
- `container-headersketch` — header entropy sketch  
- `container-compare` — compare two STRIDE containers  

---

## Benchmark Status (May 2026)

STRIDE v0 is a **minimal deterministic analyzer**.  
It does not include an encoder/decoder yet.  
As a result, **no real compression ratios can be produced at this stage**.

Expected ratios (6–8× vs zstd on integer‑heavy data) are **theoretical expectations derived from entropy modeling**, not measured compression results.

The encoder/decoder will be introduced in **STRIDE v1**.

---

## Roadmap

### STRIDE v1 (planned)
- Deterministic encoder  
- Deterministic decoder  
- Full benchmark suite (STRIDE vs zstd vs LZ4)  
- Streaming mode  
- MessagePack and Thrift adapters  
- Visualization of field distributions  

---

## Project Lineage

STRIDE is the third primitive in a family:

- **ACEAPEX** — parallel LZ77 decode  
- **GLYPH** — deterministic byte‑exact retrieval  
- **STRIDE** — field‑aware integer analysis  

---

## License
MIT
