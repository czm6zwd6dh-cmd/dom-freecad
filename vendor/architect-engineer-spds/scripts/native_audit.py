"""FreeCAD-only geometric assertions. Caller must source and bound every probe.

Probes check positive-volume overlaps only, not surface contact, strength or all
unobserved openings. A passing sample does not prove the entire void envelope.
"""
def inspect(document, spec):
    import Part
    findings=[];checks=[]
    tolerance=spec['volume_tolerance_mm3']
    if tolerance<0:raise ValueError('negative tolerance')
    for name in spec.get('solids',[]):
        o=document.getObject(name)
        if o is None or not hasattr(o,'Shape'):
            findings.append({'object':name,'code':'MISSING_SHAPE'});continue
        if not o.Shape.isValid() or not o.Shape.Solids:
            findings.append({'object':name,'code':'INVALID_OR_NON_SOLID'})
    for p in spec.get('void_probes',[]):
        if not p.get('source'):raise ValueError('probe source required')
        box=p['box_mm'];o=document.getObject(p['object'])
        if len(box)!=6 or any(v<=0 for v in box[3:]):raise ValueError('invalid probe box')
        if o is None or not hasattr(o,'Shape'):
            findings.append({'object':p['object'],'code':'MISSING_SHAPE'});continue
        import FreeCAD
        tool=Part.makeBox(*box[3:],FreeCAD.Vector(*box[:3]))
        overlap=o.Shape.common(tool).Volume
        checks.append({'id':p['id'],'overlap_mm3':overlap,'tolerance_mm3':tolerance})
        if overlap>tolerance:findings.append({'object':p['object'],'probe':p['id'],'code':'REQUIRED_VOID_OCCUPIED'})
    if not checks and not spec.get('solids'):raise ValueError('empty geometric audit')
    return {'checks':checks,'findings':findings,'passed':not findings,'construction_ready':False}
