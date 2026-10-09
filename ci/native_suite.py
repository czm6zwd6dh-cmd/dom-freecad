"""Bounded synthetic native CAD qualification; never reads a real building model."""
import hashlib
import math
import os
from pathlib import Path
import runpy
import sys

ROOT = Path(os.environ['DOM_REPO_ROOT']).resolve()
OUT = ROOT / 'build/smoke'
VENDOR = ROOT / 'vendor/architect-engineer-spds'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def inspect_wall(doc, opening_width):
    wall = doc.getObject('Wall')
    opening = doc.getObject('WindowOpening')
    require(wall is not None and opening is not None, 'Missing native wall or window')
    require(wall.DataClass == 'SYNTHETIC_ONLY', 'Unexpected data classification')
    doc.recompute()
    expected = 4000 * 300 * 3000 - opening_width * 300 * 1200
    require(wall.Shape.isValid() and len(wall.Shape.Solids) == 1, 'Invalid solid')
    require(math.isclose(wall.Shape.Volume, expected, rel_tol=0, abs_tol=0.01), 'Net-volume mismatch')
    require(wall.Shape.common(opening.Shape).Volume <= 0.01, 'Required window void occupied')
    require(math.isclose(opening.Length.Value, opening_width, rel_tol=0, abs_tol=1e-7), 'Wrong opening width')
    for name, scale in [('Elevation', 0.05), ('TopProjection', 0.02)]:
        view = doc.getObject(name)
        require(view is not None and list(view.Source) == [wall], 'Broken TechDraw source')
        require(math.isclose(view.Scale, scale, rel_tol=0, abs_tol=1e-12), 'Wrong view scale')
    return {'wall_net_volume_mm3': wall.Shape.Volume,
            'expected_volume_mm3': expected, 'opening_width_mm': opening_width,
            'source_links': 'PASS', 'solid_and_void': 'PASS'}


def export_page(doc, destination):
    import FreeCADGui as Gui
    import TechDrawGui
    destination.mkdir(parents=True, exist_ok=True)
    page = doc.getObject('A3Sheet')
    require(page is not None, 'Missing native drawing page')
    # Restored TechDraw views may still expose their cached drawing. Mark the
    # native views dirty, recompute, and process the queued GUI/HLR completion
    # before export. The independent PDF test remains the acceptance condition.
    from PySide import QtCore
    page.KeepUpdated = True
    Gui.activeDocument().getObject(page.Name).show()
    for view in page.Views:
        view.touch()
    page.touch()
    doc.recompute()
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(1500, loop.quit)
    loop.exec_()
    for view in page.Views:
        view.requestPaint()
    Gui.updateGui()
    settle = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(500, settle.quit)
    settle.exec_()
    Gui.updateGui()
    TechDrawGui.exportPageAsPdf(page, str(destination / 'synthetic-page.pdf'))
    TechDrawGui.exportPageAsSvg(page, str(destination / 'synthetic-page.svg'))


def build():
    import FreeCAD as App
    import Part
    doc = App.newDocument('SyntheticWall')
    base = doc.addObject('Part::Box', 'WallBase')
    base.Length, base.Width, base.Height = 4000, 300, 3000
    opening = doc.addObject('Part::Box', 'WindowOpening')
    opening.Length, opening.Width, opening.Height = 1000, 500, 1200
    opening.Placement.Base = App.Vector(1500, -100, 900)
    wall = doc.addObject('Part::Cut', 'Wall')
    wall.Base, wall.Tool = base, opening
    wall.addProperty('App::PropertyString', 'DataClass', 'Provenance')
    wall.DataClass = 'SYNTHETIC_ONLY'
    page = doc.addObject('TechDraw::DrawPage', 'A3Sheet')
    template = doc.addObject('TechDraw::DrawSVGTemplate', 'PageTemplate')
    template.Template = str(ROOT / 'ci/a3-landscape.svg')
    page.Template = template
    for name, direction, x, y, scale in [
        ('Elevation', (0, -1, 0), 170, 143, 0.05),
        ('TopProjection', (0, 0, 1), 352, 220, 0.02)
    ]:
        view = doc.addObject('TechDraw::DrawViewPart', name)
        view.Source = [wall]
        page.addView(view)
        view.Direction = App.Vector(*direction)
        view.ScaleType = 'Custom'
        view.Scale = scale
        view.X, view.Y = x, y
    result = inspect_wall(doc, 1000)
    base.ViewObject.Visibility = False
    opening.ViewObject.Visibility = False
    export_page(doc, OUT)
    model = OUT / 'synthetic-wall.FCStd'
    doc.saveAs(str(model))
    Part.export([wall], str(OUT / 'synthetic-wall.step'))
    result.update(model_sha256=digest(model), exports=['FCStd', 'STEP', 'PDF', 'SVG'])
    App.closeDocument(doc.Name)
    return result


def reopen(phase):
    import FreeCAD as App
    import Part
    source = OUT / ('restored/synthetic-wall.FCStd' if phase == 'restore-reopen' else 'synthetic-wall.FCStd')
    before = digest(source)
    doc = App.openDocument(str(source))
    result = inspect_wall(doc, 1000)
    if phase == 'mutate':
        doc.getObject('WindowOpening').Length = 1200
        result = inspect_wall(doc, 1200)
        dest = OUT / 'mutated'
        export_page(doc, dest)
        doc.saveAs(str(dest / 'synthetic-wall.FCStd'))
        Part.export([doc.getObject('Wall')], str(dest / 'synthetic-wall.step'))
        result['mutated_model_sha256'] = digest(dest / 'synthetic-wall.FCStd')
        require(result['mutated_model_sha256'] != before, 'Mutation did not produce a new file')
    else:
        export_page(doc, OUT / ('restored-proof' if phase == 'restore-reopen' else 'cold'))
    App.closeDocument(doc.Name)
    require(digest(source) == before, 'Read-only source was modified')
    result.update(source_model_sha256=before, source_unchanged=True)
    return result


def native_tools():
    import FreeCAD as App
    import Part
    sys.path.insert(0, str(VENDOR / 'scripts'))
    import native_layers
    import native_audit
    runpy.run_path(str(VENDOR / 'tests/native_layers_test.py'), run_name='__main__')
    doc = App.newDocument('SyntheticLayerCutouts')
    tool = doc.addObject('Part::Box', 'SyntheticOpening')
    tool.Length, tool.Width, tool.Height = 500, 302, 1000
    tool.Placement.Base = App.Vector(750, -1, 1000)
    layers = [dict(material='synthetic-A', source='synthetic', role='facing', thickness=100),
              dict(material='synthetic-B', source='synthetic', role='core', thickness=200)]
    solids = native_layers.build(doc, 'QA', (0, 0, 0), 2000, 3000, layers, tool)
    count = len(doc.Objects)
    solids = native_layers.build(doc, 'QA', (0, 0, 0), 2000, 3000, layers, tool)
    require(len(doc.Objects) == count, 'Native builder is not idempotent')
    for obj, expected in zip(solids, [550000000, 1100000000]):
        require(math.isclose(obj.Shape.Volume, expected, rel_tol=0, abs_tol=0.01), 'Layer quantity mismatch')
    compound = doc.addObject('Part::Feature', 'ProbeCompound')
    compound.Shape = Part.makeCompound([o.Shape for o in solids])
    spec = {'volume_tolerance_mm3': 0.01, 'solids': [o.Name for o in solids],
            'void_probes': [dict(id='window', object=compound.Name,
                                box_mm=[750, -1, 1000, 500, 302, 1000], source='synthetic')]}
    clear = native_audit.inspect(doc, spec)
    require(clear['passed'], 'Empty synthetic window rejected')
    obstruction = Part.makeBox(100, 100, 100, App.Vector(800, 0, 1100))
    compound.Shape = Part.makeCompound([o.Shape for o in solids] + [obstruction])
    blocked = native_audit.inspect(doc, spec)
    require(not blocked['passed'] and any(f['code'] == 'REQUIRED_VOID_OCCUPIED' for f in blocked['findings']),
            'Deliberate obstruction was not detected')
    require(math.isclose(blocked['checks'][0]['overlap_mm3'], 1000000, rel_tol=0, abs_tol=0.01),
            'Wrong obstruction intersection volume')
    App.closeDocument(doc.Name)
    return {'upstream_version': '0.13.0', 'idempotent_layer_builder': 'PASS',
            'rectangular_layer_volume_check': 'PASS', 'empty_void_probe': clear,
            'deliberate_obstruction_rejected': blocked}


def run(phase):
    if phase == 'build':
        return build()
    if phase in {'cold-reopen', 'mutate', 'restore-reopen'}:
        return reopen(phase)
    if phase == 'native-tools':
        return native_tools()
    raise ValueError('Unapproved native phase')
