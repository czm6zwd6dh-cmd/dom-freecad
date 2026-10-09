"""Run inside FreeCAD Python (e.g. freecadcmd), not system Python."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import FreeCAD as A
from native_layers import build
d=A.newDocument('SyntheticLayers')
layers=[{'material':'synthetic-A','source':'synthetic','role':'facing','thickness':100},{'material':'synthetic-B','source':'synthetic','role':'core','thickness':200}]
result=build(d,'Test',(0,0,0),2000,3000,layers);n=len(d.Objects)
assert abs(sum(o.Shape.Volume for o in result)-1.8e9)<.001
result=build(d,'Test',(0,0,0),2000,3000,layers)
assert len(d.Objects)==n
try:build(d,'Bad',(0,0,0),2000,3000,[{'thickness':500}])
except ValueError:pass
else:raise AssertionError('unknown material was accepted')
A.closeDocument(d.Name)
print('SYNTHETIC_RECTANGULAR_LAYERS_PASS')
