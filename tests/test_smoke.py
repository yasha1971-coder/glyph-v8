from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GLYPH = ROOT / "stride" / "configs" / ".." / ".." / "STRIDE_core_dummy.glyph"

def test_import():
    import stride  # noqa

