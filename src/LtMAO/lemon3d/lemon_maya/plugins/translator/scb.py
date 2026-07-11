from maya import OpenMayaMPx as omMPx, cmds
from maya.api import OpenMaya as om, OpenMayaAnim as omAnim
from ..... import lepath, pyRitoFile
from . import helper

class scoImporter(omMPx.MPxFileTranslator):
    name = 'League of Legends: SCO'
    extension = 'sco'
    pixmap = ''
    options_script = ''
    options_string = ''

    @classmethod
    def creator(cls):
        return omMPx.asMPxPtr(cls())

    def __init__(self):
        omMPx.MPxFileTranslator.__init__(self)

    def haveReadMethod(self):
        return True

    def defaultExtension(self):
        return self.extension

    def filter(self):
        return f'*.{self.extension}'
    
    def identifyFile(self, file, buffer, size):
        if file.fullName().lower().endswith(f'.{self.extension}'):
            return omMPx.MPxFileTranslator.kIsMyFileType
        return omMPx.MPxFileTranslator.kNotMyFileType

    def reader(self, file, options, access):
        read_sco(file.fullName())
        return True  

class scbImporter(omMPx.MPxFileTranslator):
    name = 'League of Legends: SCB'
    extension = 'scb'
    pixmap = ''
    options_script = ''
    options_string = ''

    @classmethod
    def creator(cls):
        return omMPx.asMPxPtr(cls())

    def __init__(self):
        omMPx.MPxFileTranslator.__init__(self)

    def haveReadMethod(self):
        return True

    def defaultExtension(self):
        return self.extension

    def filter(self):
        return f'*.{self.extension}'
    
    def identifyFile(self, file, buffer, size):
        if file.fullName().lower().endswith(f'.{self.extension}'):
            return omMPx.MPxFileTranslator.kIsMyFileType
        return omMPx.MPxFileTranslator.kNotMyFileType

    def reader(self, file, options, access):
        read_scb(file.fullName())
        return True  

class scbExporter(omMPx.MPxFileTranslator):
    name = 'League of Legends: SCB Export'
    extension = 'scb'
    pixmap = ''
    options_script = ''
    options_string = ''

    @classmethod
    def creator(cls):
        return omMPx.asMPxPtr(cls())

    def __init__(self):
        omMPx.MPxFileTranslator.__init__(self)
    
    def haveWriteMethod(self):
        return True

    def defaultExtension(self):
        return self.extension

    def filter(self):
        return f'*.{self.extension}'
    
    def identifyFile(self, file, buffer, size):
        if file.fullName().lower().endswith(f'.{self.extension}'):
            return omMPx.MPxFileTranslator.kIsMyFileType
        return omMPx.MPxFileTranslator.kNotMyFileType

    def writer(self, file, options, access):
        return True
    """
        def write_cmd(file, options, access):
            # check selected
            selections = MSelectionList()
            MGlobal.getActiveSelectionList(selections)
            iterator = MItSelectionList(selections, MFn.kMesh)
            if iterator.isDone():
                raise helper.FunnyError(
                    f'SO Exporter: Please select a mesh to export.')
            mesh_dagpath = MDagPath()
            iterator.getDagPath(mesh_dagpath)
            iterator.next()
            if not iterator.isDone():
                raise helper.FunnyError(
                    f'SO Exporter: Please select only one mesh to export.')
            selected_mesh = MFnMesh(mesh_dagpath)
            # export options
            scb_path = helper.ensure_path_extension(file.expandedFullName(), self.extension)
            so = pyRitoFile.so.SO()
            dump_options = {
                'selected_mesh': selected_mesh,
                'scb_flags': pyRitoFile.so.SOFlag.HasVcp if 'HasVcp' in options else pyRitoFile.so.SOFlag.HasLocalOriginLocatorAndPivot
            }
            SO.scene_dump(so, dump_options)
            helper.mirrorX(so=so)
            so.write_scb(scb_path)
            return True

        return helper.try_cmd(lambda: write_cmd(file, options, access))"""

@helper.print_traceback
def read_sco(scb_path):
    load_scb(
        scb:=pyRitoFile.scb.read(scb_path:=lepath.ensure_ext(scb_path, '.sco')),
        { 'scb_name': scb.name if scb.name else helper.extract_name(scb_path) }
    )

@helper.print_traceback
def read_scb(scb_path):
    load_scb(
        scb:=pyRitoFile.scb.read(scb_path:=lepath.ensure_ext(scb_path, '.scb')),
        { 'scb_name': scb.name if scb.name else helper.extract_name(scb_path) }
    )

def load_scb(scb, load_options):
    scb_name = load_options['scb_name']

    # mesh transform
    mesh_transform = om.MFnTransform()
    mesh_transform.create()
    mesh_transform.setName(f'mesh_{scb_name}')
    cx, cy, cz = scb.central
    mesh_transform.setTranslation(om.MVector(-cx, cy, cz), om.MSpace.kTransform)

    # mesh shape 
    index_count = len(scb.indices)
    positions = om.MFloatPointArray([(-x, y, z) for x, y, z in scb.positions])
    face_sizes = om.MIntArray(index_count // 3, 3)
    indices = om.MIntArray(scb.indices)
    mesh = om.MFnMesh()
    mesh.create(
        positions, 
        face_sizes, 
        indices, 
        parent=mesh_transform.object()
    )
    mesh.setName(f'{scb_name}_Shape')

    # uvs
    us, vs = zip(*scb.uvs)
    vs = [1-v for v in vs]
    uv_indices = om.MIntArray(range(index_count))
    mesh.setUVs(us, vs)
    mesh.assignUVs(face_sizes, uv_indices)


    # materials
    dg_modifier = om.MDGModifier()
    material_name = scb.material
    selections = om.MSelectionList()
    selections.add('renderPartition')
    selections.add('defaultShaderList1')
    render_partition = om.MFnDependencyNode(selections.getDependNode(0))
    shader_list = om.MFnDependencyNode(selections.getDependNode(1))
    render_partition_sets = render_partition.findPlug('sets', False)
    shader_list_shaders = shader_list.findPlug('shaders', False)
    # create lambert and shading engine then get dependency node
    lambert = dg_modifier.createNode('lambert')
    shading_engine = dg_modifier.createNode('shadingEngine')
    dg_modifier.renameNode(lambert, material_name)
    dg_modifier.renameNode(shading_engine, f'{material_name}_SG')
    lambert = om.MFnDependencyNode(lambert)
    shading_engine = om.MFnDependencyNode(shading_engine)
    # link lambert.message to defaultShaderList1.shaders[n]
    dg_modifier.connect(
        lambert.findPlug('message', False),
        shader_list_shaders.elementByLogicalIndex(shader_list_shaders.evaluateNumElements())
    )
    # link shadingEngine.partition to renderPartition.sets[n]
    dg_modifier.connect(
        shading_engine.findPlug('partition', False), 
        render_partition_sets.elementByLogicalIndex(render_partition_sets.evaluateNumElements())
    )
    # link lambert.outColor to shadingEngine.surfaceShader
    dg_modifier.connect(
        lambert.findPlug('outColor', False),
        shading_engine.findPlug('surfaceShader', False)
    )
    # link mesh.instObjGroups[0] to shadingEninge.dagSetMembers[n]
    shading_engine_dagSetMembers = shading_engine.findPlug('dagSetMembers', False)
    dg_modifier.connect(
        mesh.findPlug('instObjGroups', False).elementByLogicalIndex(0), 
        shading_engine_dagSetMembers.elementByLogicalIndex(shading_engine_dagSetMembers.evaluateNumElements())
    )
    # do it
    dg_modifier.doIt()

    #mesh.updateSurface()

"""
def dump_scb(scb, dump_options):
    mesh = dump_options['selected_mesh']
    mesh_dagpath = MDagPath()
    mesh.getPath(mesh_dagpath)

    # get name
    so.name = mesh.name()

    # central point: translation of mesh
    transform = MFnTransform(mesh.parent(0))
    central_translation = transform.getTranslation(MSpace.kTransform)
    so.central = pyRitoFile.structs.Vector(
        central_translation.x, central_translation.y, central_translation.z)

    # check hole
    hole_info = MIntArray()
    hole_vertex = MIntArray()
    mesh.getHoles(hole_info, hole_vertex)
    if hole_info.length() > 0:
        raise helper.FunnyError(f'SO Expoter ({mesh.name()}): Mesh contains holes.')

    # SCO only: find pivot joint through skin cluster
    iterator = MItDependencyGraph(
        mesh.object(), MFn.kSkinClusterFilter, MItDependencyGraph.kUpstream)
    if not iterator.isDone():
        skin_cluster = MFnSkinCluster(iterator.currentItem())
        influences_dagpath = MDagPathArray()
        influence_count = skin_cluster.influenceObjects(
            influences_dagpath)
        if influence_count > 1:
            raise helper.FunnyError(
                f'SO Expoter ({mesh.name()}): More than 1 joint bound with this mesh, can not determine which one is pivot joint.')
        ik_joint = MFnTransform(influences_dagpath[0])
        joint_translation = ik_joint.getTranslation(MSpace.kTransform)
        so.pivot = pyRitoFile.structs.Vector(
            so.central.x - joint_translation.x,
            so.central.y - joint_translation.y,
            so.central.z - joint_translation.z
        )

    # dumb vertices
    vertex_count = mesh.numVertices()
    points = MFloatPointArray()
    mesh.getPoints(points, MSpace.kWorld)
    so.positions = [pyRitoFile.structs.Vector(points[i].x, points[i].y, points[i].z)
                        for i in range(vertex_count)]
    so.indices = []
    so.uvs = []
    # dump uvs outside loop
    u_values = MFloatArray()
    v_values = MFloatArray()
    mesh.getUVs(u_values, v_values)
    # iterator on faces
    # to dump face indices and UVs
    # extra checking
    bad_faces = MIntArray()  # invalid triangulation face
    bad_faces2 = MIntArray()  # no UV face
    iterator = MItMeshPolygon(mesh_dagpath)
    iterator.reset()
    while not iterator.isDone():
        face_index = iterator.index()

        # check valid triangulation
        if not iterator.hasValidTriangulation():
            if face_index not in bad_faces:
                bad_faces.append(face_index)
        # check if face has no UVs
        if not iterator.hasUVs():
            if face_index not in bad_faces2:
                bad_faces2.append(face_index)

        # get triangulated face indices
        points = MPointArray()
        indices = MIntArray()
        iterator.getTriangles(points, indices)
        face_index_count = indices.length()
        # get face vertices
        map_indices = {}
        vertices = MIntArray()
        iterator.getVertices(vertices)
        face_vertex_count = vertices.length()
        # map face indices by uv_index
        for i in range(face_vertex_count):
            util = MScriptUtil()
            ptr = util.asIntPtr()
            iterator.getUVIndex(i, ptr)
            uv_index = util.getInt(ptr)
            map_indices[vertices[i]] = uv_index
        # dump indices and uvs
        for i in range(face_index_count):
            index = indices[i]
            so.indices.append(index)
            uv_index = map_indices[index]
            so.uvs.append(pyRitoFile.structs.Vector(
                u_values[uv_index],
                1.0 - v_values[uv_index]
            ))
        iterator.next()
    if bad_faces.length() > 0:
        component = MFnSingleIndexedComponent()
        face_component = component.create(
            MFn.kMeshPolygonComponent)
        component.addElements(bad_faces)
        selections = MSelectionList()
        selections.add(mesh_dagpath, face_component)
        MGlobal.selectCommand(selections)
        raise helper.FunnyError(
            f'SO Expoter ({mesh.name()}): Mesh contains {bad_faces.length()} invalid triangulation faces, those faces will be selected in scene.\nBonus: If there is nothing selected (or they are invisible) after this error message, consider to delete history, that might fix the problem.')
    if bad_faces2.length() > 0:
        component = MFnSingleIndexedComponent()
        face_component = component.create(
            MFn.kMeshPolygonComponent)
        component.addElements(bad_faces2)
        selections = MSelectionList()
        selections.add(mesh_dagpath, face_component)
        MGlobal.selectCommand(selections)
        raise helper.FunnyError(
            f'SO Expoter ({mesh.name()}): Mesh contains {bad_faces2.length()} faces have no UVs assigned, or, those faces UVs are not in current UV set, those faces will be selected in scene.\nBonus: If there is nothing selected (or they are invisible) after this error message, consider to delete history, that might fix the problem.')

    # get shader
    instance = mesh_dagpath.instanceNumber() if mesh_dagpath.isInstanced() else 0
    shaders = MObjectArray()
    face_shader = MIntArray()
    mesh.getConnectedShaders(instance, shaders, face_shader)
    if shaders.length() > 1:
        raise helper.FunnyError(
            f'SO Expoter ({mesh.name()}): More than 1 material assigned to this mesh.')
    # material name
    if shaders.length() > 0:
        ss = MFnDependencyNode(
            shaders[0]).findPlug('surfaceShader')
        plugs = MPlugArray()
        ss.connectedTo(plugs, True, False)
        material = MFnDependencyNode(plugs[0].node())
        so.material = material.name()
        if len(so.material) > 64:
            raise helper.FunnyError(
                f'SO Expoter ({mesh.name()}): Material name is too long: {so.material} with {len(so.material)} chars, max allowed: 64 chars.')
    else:
        # its only allow 1 material anyway
        so.material = 'standardSurface69'
    
    # set flags
    so.flags = pyRitoFile.so.SOFlag.HasLocalOriginLocatorAndPivot
    if 'scb_flags' in dump_options:
        so.flags = dump_options['scb_flags']
"""