import struct

MAGIC = b"STRIDE01"

class StrideContainer:
    def __init__(self, path: str):
        self.path = path
        with open(path, "rb") as f:
            magic = f.read(8)
            if magic != MAGIC:
                raise ValueError(f"Bad magic: {magic!r}")
            self.corpus_size = struct.unpack("<Q", f.read(8))[0]
            self.chunk_size = struct.unpack("<Q", f.read(8))[0]
            self.data_offset = f.tell()

    def iter_chunks(self):
        with open(self.path, "rb") as f:
            f.seek(self.data_offset)
            remaining = self.corpus_size
            while remaining > 0:
                to_read = min(self.chunk_size, remaining)
                chunk = f.read(to_read)
                if not chunk:
                    break
                yield chunk
                remaining -= len(chunk)
