import json, os, zlib
from collections import OrderedDict

class GlyphStore:
    def __init__(self, glyph_path, index_path, cache_size=256):
        self.glyph_path = glyph_path
        self.index_path = index_path
        self.cache_size = int(cache_size)
        self._cache = OrderedDict()

        self.cache_hit = 0
        self.cache_miss = 0

        with open(index_path, "r") as f:
            idx = json.load(f)

        self.chunks = idx["chunks"]
        self.num_chunks = int(idx["num_chunks"])
        self.usizes = [c.get("usize") for c in self.chunks]

        self.f = open(glyph_path, "rb")

    def close(self):
        try:
            self.f.close()
        except Exception:
            pass

    def reset_stats(self):
        self.cache_hit = 0
        self.cache_miss = 0

    def stats(self):
        total = self.cache_hit + self.cache_miss
        return {
            "cache_hit": self.cache_hit,
            "cache_miss": self.cache_miss,
            "cache_hit_rate": round(self.cache_hit / total, 4) if total else None,
        }

    def get(self, i: int) -> bytes:
        i = int(i)
        if i in self._cache:
            self.cache_hit += 1
            self._cache.move_to_end(i)
            return self._cache[i]

        self.cache_miss += 1

        rec = self.chunks[i]
        off = rec["off"]
        csize = rec["csize"]

        self.f.seek(off)
        comp = self.f.read(csize)
        raw = zlib.decompress(comp)

        self._cache[i] = raw
        self._cache.move_to_end(i)

        if len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)

        return raw

    def prefetch(self, ids):
        try:
            ids_sorted = sorted(set(int(x) for x in ids))
        except Exception:
            ids_sorted = list(ids)
        for i in ids_sorted:
            if 0 <= i < self.num_chunks:
                self.get(i)
