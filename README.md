# STRIDE v0 — Minimal Corpus Analysis Engine

STRIDE v0 is a minimal, deterministic, byte‑level corpus analysis tool.
It operates on STRIDE v0 containers and provides global and local
statistical analysis, structural profiling, and corpus comparison.

This version intentionally does NOT include indexing or search.
It is a pure analyzer.

---

## Features

### 1. Container Reader
- Validates STRIDE v0 container format
- Reads header, chunk size, and chunk table
- Iterates over raw chunks efficiently
- Zero external dependencies

### 2. Byte Frequency Analysis
stride container-bytefreq 
Outputs:
- total bytes processed
- top N most frequent bytes
- percentage distribution

### 3. Entropy Hotspots
stride container-hotspots 
Computes Shannon entropy per chunk and reports:
- lowest‑entropy chunks
- structural irregularities
- local anomalies in the corpus

### 4. MinHash Fingerprint
Computes Shannon entropy per chunk and reports:
- lowest‑entropy chunks
- structural irregularities
- local anomalies in the corpus

### 4. MinHash Fingerprint
stride container-fingerprint 
Generates a deterministic fingerprint using:
- rolling hash (window=32)
- bottom‑k MinHash (k=128)

Used for:
- similarity detection
- corpus identity
- clustering

### 5. HeaderSketch (Structural Profile)
stride container-headersketch 
Produces a normalized 64‑element vector representing:
- entropy distribution across the corpus
- structural “shape” of the dataset

### 6. Corpus Comparison
stride container-compare A B
Computes:
- Jaccard similarity of fingerprints
- L2 distance between HeaderSketch vectors
- combined similarity score

---

## Example Output (enwik8.stridebin)

### ByteFreq
- space: 13.52%
- e: 8.00%
- t: 6.15%
- a: 5.71%
- i: 5.22%
- o: 5.17%

## Benchmark Results — STRIDE v0 Analysis (enwik8, 100 MB)

STRIDE v0 performs deterministic corpus analysis.  
Below are real results obtained from running the STRIDE v0 analyzers on `enwik8.stridebin` (100,000,000 bytes).

### 1. Byte Frequency (Top 20)
The most common byte is `0x20` (space), appearing **13.5198%** of the time.

Other high‑frequency bytes:
- `0x65` ('e') — 8.0012%
- `0x74` ('t') — 6.1549%
- `0x61` ('a') — 5.7120%
- `0x69` ('i') — 5.2276%
- `0x6F` ('o') — 5.1761%

### 2. Entropy Hotspots
Highest‑entropy chunks:
- Chunk `0x000010CDD5159219` — **5.685 bits**
- Chunk `0x000010E433AB9296` — 5.609 bits
- Chunk `0x00001117B455E36F` — 5.533 bits

### 3. Rolling Fingerprint
STRIDE produces a deterministic 128‑bit rolling fingerprint across the corpus.

### 4. HeaderSketch (64‑bucket entropy map)
Selected buckets:
- Bucket 15 — **0.57358**
- Bucket 33 — **0.66261**
- Bucket 48 — **0.66045**
- Bucket 41 — **0.60471**

These results demonstrate STRIDE v0’s ability to analyze structured binary data and prepare the foundation for STRIDE v1 encoding.

Matches known English Zipf distribution.

### Hotspots
Lowest‑entropy chunks around:
- 5.34–5.68 bits

### Fingerprint
128 stable MinHash values (hex).

### HeaderSketch
64 normalized entropy samples (0.06–0.66 range).

---

## Status

STRIDE v0 is **complete**.

It includes:
- container reader
- bytefreq
- hotspots
- fingerprint
- headersketch
- compare
- full CLI

It does NOT include:
- container packer
- indexer
- search engine

These belong to STRIDE v1+.

---

## Requirements

- Python 3.8+
- No external libraries

---

## Quick Start

stride container-bytefreq enwik8.stridebin
stride container-hotspots enwik8.stridebin
stride container-fingerprint enwik8.stridebin
stride container-headersketch enwik8.stridebin
stride container-compare enwik8.stridebin enwik8.stridebin

## License

MIT
