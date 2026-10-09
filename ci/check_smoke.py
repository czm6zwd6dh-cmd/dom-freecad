#!/usr/bin/env python3
"""Check synthetic FreeCAD reports and exports; NOT an SPDS or real-house check."""
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import fitz

root = Path(sys.argv[1] if len(sys.argv) > 1 else "build/smoke")
report = json.loads((root / "report.json").read_text(encoding="utf-8"))
assert report["status"] == "PASS", report
assert report["version"] == "1.1.4", report
expected = 4000 * 300 * 3000 - 1000 * 300 * 1200
assert math.isclose(float(report["wall_net_volume_mm3"]), expected, abs_tol=0.01)
assert report["source"] == "SYNTHETIC_ONLY"
for name in ("synthetic-wall.FCStd", "synthetic-wall.step", "synthetic-page.pdf", "synthetic-page.svg"):
    assert (root / name).is_file(), f"Missing {name}"
    assert (root / name).stat().st_size > 100, f"Empty {name}"
assert ET.parse(root / "synthetic-page.svg").getroot().tag.endswith("svg")
with fitz.open(root / "synthetic-page.pdf") as document:
    assert len(document) == 1
    page = document[0]
    width, height = (page.rect.width, page.rect.height)
    assert abs(width - 420 * 72 / 25.4) < 2, (width, height)
    assert abs(height - 297 * 72 / 25.4) < 2, (width, height)
    assert len(page.get_drawings()) > 0, "PDF contains no vector linework"
    page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False).save(str(root / "preview.png"))
print("SYNTHETIC CAD PASS: wall geometry, FCStd, STEP, A3 vector PDF, SVG")
print("Review preview.png manually; drawing completeness, scale fidelity and SPDS NOT proven.")
