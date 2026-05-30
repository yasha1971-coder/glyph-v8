import struct
from pathlib import Path

MAGIC = b"STRIDE01"
HEADER_SIZE = 24  # 8 magic + 8 corpus_size + 8 chunk_size

def write_container(input_path: str, output_path: str, chunk_size: int = 65536):
    input_path = Path(input_path)
    output_path = Path(output_path)

    corpus_size = input_path.stat().st_size

    with open(input_path, "rb") as fin, open(output_path, "wb") as fout:
        fout.write(MAGIC)
        fout.write(struct.pack("<Q", corpus_size))
        fout.write(struct.pack("<Q", chunk_size))

        remaining = corpus_size
        while remaining > 0:
            to_read = min(chunk_size, remaining)
            chunk = fin.read(to_read)
            if not chunk:
                break
            fout.write(chunk)
            remaining -= len(chunk)

    return {
        "input": str(input_path),
        "output": str(output_path),
        "corpus_size": corpus_size,
        "chunk_size": chunk_size,
        "chunks": (corpus_size + chunk_size - 1) // chunk_size,
    }

if __name__ == "__main__":
    import argparse, json
    ap = argparse.ArgumentParser(description="Write STRIDE01 container from raw file")
    ap.add_argument("input", help="Raw input file")
    ap.add_argument("output", help="Output .stridebin file")
    ap.add_argument("--chunk-size", type=int, default=65536)
    args = ap.parse_args()
    result = write_container(args.input, args.output, args.chunk_size)
    print(json.dumps(result, indent=2))
