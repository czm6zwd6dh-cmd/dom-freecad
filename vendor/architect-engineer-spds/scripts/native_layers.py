"""FreeCAD rectangular multilayer wall primitive. No project-private defaults."""
def build(document,prefix,origin,length,height,layers,void_tool=None):
    import FreeCAD as A
    if length<=0 or height<=0 or not layers:raise ValueError('positive dimensions and layers required')
    for layer in layers:
        if not layer.get('material') or not layer.get('source') or not layer.get('role') or layer.get('thickness',0)<=0:
            raise ValueError('each layer requires material/source/role/positive thickness')
    names=[prefix+'Base'+str(i) for i in range(len(layers))]+[prefix+'Layer'+str(i) for i in range(len(layers))]
    # Idempotency by explicit identity; fail on incompatible existing object.
    def obtain(kind,name):
        o=document.getObject(name)
        if o and o.TypeId!=kind:raise ValueError('incompatible existing object '+name)
        return o or document.addObject(kind,name)
    result=[];offset=0
    for i,layer in enumerate(layers):
        b=obtain('Part::Box',prefix+'Base'+str(i));b.Length=length;b.Width=layer['thickness'];b.Height=height;b.Placement.Base=A.Vector(origin[0],origin[1]+offset,origin[2])
        if void_tool:
            o=obtain('Part::Cut',prefix+'Layer'+str(i));o.Base=b;o.Tool=void_tool
        else:o=b
        for k,v in [('MaterialID',layer['material']),('LayerRole',layer['role']),('MaterialSource',layer['source']),('ReferenceFace','outer_y'),('LayerStatus',layer.get('status','DOCUMENTARY'))]:
            if k not in o.PropertiesList:o.addProperty('App::PropertyString',k,'Provenance')
            setattr(o,k,v)
        result.append(o);offset+=layer['thickness']
    document.recompute()
    for o in result:
        if o.Shape.isNull() or not o.Shape.isValid():raise ValueError('invalid layer '+o.Name)
    return result
