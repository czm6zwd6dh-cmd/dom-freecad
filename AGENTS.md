# Instructions for CAD development agents

This repository is PUBLIC. It must contain **only generic software, documentation,
and synthetic test fixtures**. Never upload or log any actual R1 / Дом house plan,
address, scan, photograph, measured dimensions, HVAC details, floor layouts,
FCStd model, DXF, PDF, STEP or backup. Private source material must be handled
in separate private storage and workflows. Avoid directly passing secrets to
untrusted forks or public CI.

## Validate changes

1. Run `python ci/privacy_guard.py` in a Git checkout.
2. Keep the FreeCAD version and checksum pinned in `ci/freecad-lock.json`.
3. Examine GitHub Actions for actual successful native runs: a green Python
   syntax test alone is insufficient.
4. Review the exported synthetic drawing visually. Confirm no clipping,
   geometry/size mismatch, or missing text.
5. Treat test fixtures as **synthetic only**. Do not apply them to R1.
6. Production model correctness, linked dimension updates, engineering
   calculations and regulatory documentation need separate validation.

Never declare the real building design safe for construction based solely on
this repository's synthetic CI results.
