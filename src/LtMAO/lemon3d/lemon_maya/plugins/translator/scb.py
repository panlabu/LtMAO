from maya import OpenMayaMPx as omMPx, cmds
from maya.api import OpenMaya as om, OpenMayaAnim as omAnim
from ..... import pyRitoFile
from . import helper
import os.path

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

@helper.print_traceback
def read_sco(scb_path):
    load_scb(
        scb:=pyRitoFile.scb.read(scb_path:=helper.ensure_ext(scb_path, '.sco')),
        { 'scb_name': scb.name if scb.name else helper.extract_name(scb_path) }
    )

@helper.print_traceback
def read_scb(scb_path):
    load_scb(
        scb:=pyRitoFile.scb.read(scb_path:=helper.ensure_ext(scb_path, '.scb')),
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


def dump_scb(dump_options):
    mesh_dagpath = dump_options['selected_mesh']
    mesh = om.MFnMesh(mesh_dagpath)

    # check holes
    if len(mesh.getHoles()) > 0:
        raise helper.FunnyError(f'SCB Exporter: {mesh.name()} has holes.')

    # name and central
    mesh_name = mesh.name()
    mesh_transform = om.MFnTransform(mesh.parent(0))
    cx, cy, cz = mesh_transform.translation(om.MSpace.kTransform)
    central = (-cx, cy, cz)

    vertex_count = mesh.numVertices
    # positions
    positions = [(-x, y, z) for x, y, z, _ in mesh.getFloatPoints()]
    # uv
    us, vs = mesh.getUVs()
    us = tuple(us)
    vs = tuple(vs)
    uv_count = len(us)
    vertex_id_counts, vertex_ids = mesh.getVertices()
    _, uv_ids = mesh.getAssignedUVs()
    vertex_ids = tuple(vertex_ids)
    uv_ids = tuple(uv_ids)
    # init
    uv_id_map = [None] * vertex_count
    indices = []
    uvs = []
    add_idx = indices.append
    add_uv = uvs.append
    # triangle
    triangle_counts, triangle_vertices = mesh.getTriangles()
    triangle_vertices = tuple(triangle_vertices)
    left_t = 0
    left_v = 0
    for vertex_id_count, triangle_count in zip(vertex_id_counts, triangle_counts):
        right_v = left_v + vertex_id_count
        right_t = left_t + triangle_count * 3
        # local face vertex id to uv id map
        for i in range(left_v, right_v):
            uv_id_map[vertex_ids[i]] = uv_ids[i]
        # dump triangle vertex ids
        for vertex_id in triangle_vertices[left_t:right_t]:
            uv_id = uv_id_map[vertex_id]
            if uv_id is None or uv_id < 0 or uv_id >= uv_count:
                raise helper.FunnyError(f'SKN Exporter: UV id is missing or out of bounds. Please check if all UVs of {mesh.name()} are in first UV set.')
            add_idx(vertex_id)
            add_uv((
                us[uv_id],
                1.0 - vs[uv_id]
            ))
        left_v = right_v
        left_t = right_t

    # bounding box
    bbox = mesh.boundingBox
    x_min, y_min, z_min, _ = bbox.min
    x_max, y_max, z_max, _ = bbox.max

    return pyRitoFile.scb.StaticComponent(
        None, None, 2, mesh_name, 
        central, None, 
        ((-x_min, y_min, z_min), (-x_max, y_max, z_max)), 'lambert1', 
        indices, positions, uvs, []
    )

@helper.print_traceback
def write_scb(scb_path):
    # selected dagpath
    selections = om.MGlobal.getActiveSelectionList()
    iterator = om.MItSelectionList(selections, om.MFn.kMesh)
    if iterator.isDone():
        raise helper.FunnyError(f'SCB Exporter: Please select a mesh to export.')
    selected_dagpath = iterator.getDagPath()
    iterator.next()
    if not iterator.isDone():
        raise helper.FunnyError(f'SCB Exporter: Please select only one mesh to export.')
    # write scb
    scb_path = helper.ensure_ext(scb_path, '.scb')
    pyRitoFile.scb.write(
        dump_scb({ 'selected_mesh': selected_dagpath }),
        scb_path
    )
