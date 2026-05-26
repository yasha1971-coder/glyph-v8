import struct
from pathlib import Path

MAGIC = b"STRIDE01"
CHUNK_SIZE = 65536  # 64 KB

def build_container(corpus_path: str, out_path: str) -> None:
    corpus = Path(corpus_path).read_bytes()
    corpus_size = len(corpus)

    with open(out_path, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<Q", corpus_size))
        f.write(struct.pack("<Q", CHUNK_SIZE))
        f.write(corpus)

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", dest="out", required=True)
    args = p.parse_args()

    build_container(args.inp, args.out)
