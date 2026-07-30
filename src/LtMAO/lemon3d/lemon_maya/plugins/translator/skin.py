from maya import OpenMayaMPx as omMPx, cmds
from maya.api import OpenMaya as om, OpenMayaAnim as omAnim
from ..... import pyRitoFile
from . import helper
import os.path

class sknImporter(omMPx.MPxFileTranslator):
    name = 'League of Legends: SKN'
    extension = 'skn'
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
        read_skn(file.fullName())
        return True

class sklImporter(omMPx.MPxFileTranslator):
    name = 'League of Legends: SKL'
    extension = 'skl'
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
        read_skl(file.fullName())
        return True

class skinExporter(omMPx.MPxFileTranslator):
    name = 'League of Legends: SKN & SKL Export'
    extension = 'skn'
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
        write_skn(file.fullName())
        return True

class sklExporter(omMPx.MPxFileTranslator):
    name = 'League of Legends: SKL Export'
    extension = 'skl'
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
        write_skl(file.fullName())
        return True

@helper.print_traceback
def read_skl(skl_path):
    # ensure path
    skl_path = helper.ensure_ext(skl_path, '.skl')
    skl_name = helper.extract_name(skl_path)
    # group transform
    group_transform_name = f'group_{skl_name}'
    try:
        selections = om.MSelectionList()
        selections.add(group_transform_name)
        group_transform = om.MFnTransform(selections.getDagPath(0))
    except RuntimeError:
        group_transform = om.MFnTransform()
        group_transform.create()
        group_transform.setName(group_transform_name)
    # load skl
    load_skl(
        pyRitoFile.skl.read(skl_path), 
        { 'group_transform': group_transform }
    )

def load_skl(skl, load_options):
    # init
    joint_count = len(skl.joints)
    ik_joints = [None] * joint_count
    selections = om.MSelectionList()
    joint_fn = om.MFn.kJoint
    space = om.MSpace.kTransform
    num_attr = om.MFnNumericAttribute()
    group_transform = load_options['group_transform']

    # create ik joints 
    for joint_id, joint in enumerate(skl.joints):
        try:
            # find existed
            selections.add(joint.name)
            dagpath = selections.getDagPath(0)
            if dagpath.node().hasFn(joint_fn):
                ik_joint = omAnim.MFnIkJoint(dagpath)
            else:
                raise RuntimeError
        except RuntimeError:
            # create new
            ik_joint = omAnim.MFnIkJoint()
            ik_joint.create()
            ik_joint.setName(joint.name)
        ik_joints[joint_id] = ik_joint
        selections.clear()

    # set ik joint data
    for joint_id, (ik_joint, joint) in enumerate(zip(ik_joints, skl.joints)):
        # parent
        if joint.parent > -1:
            ik_joints[joint.parent].addChild(ik_joint.object())
        else:
            group_transform.addChild(ik_joint.object())
        # transform
        tx, ty, tz = joint.translate
        rx, ry, rz, rw = joint.rotate
        ik_joint.setTranslation(om.MVector(-tx, ty, tz), space)
        ik_joint.setRotation(om.MQuaternion(rx, -ry, -rz, rw), space)
        ik_joint.setScale(joint.scale)
        # custom attribute
        if ik_joint.hasAttribute('riotID'):
            plug = ik_joint.findPlug('riotID', False)
            plug.setInt(joint_id)
        else:
            rid = num_attr.create(
                'riotID',
                'rid',
                om.MFnNumericData.kInt,
                joint_id
            )
            num_attr.setMin(0)
            num_attr.setMax(65535)
            ik_joint.addAttribute(rid)


def dump_skl(dump_options):
    selected_dagpath = dump_options['selected_group']
    
    # init
    Joint = pyRitoFile.skl.Joint
    hash_elf = pyRitoFile.maths.hash_elf
    scene_joints = []
    ik_joints = {}
    space = om.MSpace.kTransform

    # dump joints
    iterator = om.MItDag()
    iterator.reset(selected_dagpath, om.MItDag.kDepthFirst, om.MFn.kJoint)
    while not iterator.isDone():
        # init
        joint_dagpath = iterator.getPath()
        ik_joint = omAnim.MFnIkJoint(joint_dagpath)
        name = ik_joint.name()
        ik_joints[name] = ik_joint
        transform = om.MTransformationMatrix(ik_joint.transformationMatrix())
        tx, ty, tz = transform.translation(space)
        qx, qy, qz, qw = transform.rotation(asQuaternion=True)
        inversed_bind_transform = om.MTransformationMatrix(joint_dagpath.inclusiveMatrixInverse())
        ibtx, ibty, ibtz = inversed_bind_transform.translation(space)
        ibqx, ibqy, ibqz, ibqw = inversed_bind_transform.rotation(asQuaternion=True)
        # add joints
        scene_joints.append(Joint(
            name,
            None,
            -1,
            hash_elf(name),
            2.1,
            (-tx, ty, tz),
            (qx, -qy, -qz, qw),
            transform.scale(space),
            (-ibtx, ibty, ibtz),
            (ibqx, -ibqy, -ibqz, ibqw),
            inversed_bind_transform.scale(space),
            None
        ))
        iterator.next()

    # sort joints
    riot_skl = dump_options['riot_skl']
    if riot_skl is not None:
        # sort joints with riot skl
        print('SKL Exporter: Found riot.skl, sorting joints...')
        # init
        sj_map = {sj.name.lower(): sj for sj in scene_joints}
        # find riot joints in scene joints
        joints = [
            Joint(
                rj.name, None, -1, hash_elf(rj.name), 2.1,
                (0, 0, 0), (0, 0, 0, 1), (0, 0, 0),
                (0, 0, 0), (0, 0, 0, 1), (0, 0, 0),
                None
            ) if (sj:=sj_map.pop(rj.name.lower(), None)) is None else sj
            for rj in riot_skl.joints
        ]
        joints.extend(sj_map.values())
    else:
        # sort joint with attribute
        print('SKL Exporter: Sorting joints...')
        # init
        assigned_joints = {}
        new_joints = []
        # find riotID attribute
        for sj in scene_joints:
            ik_joint = ik_joints.get(sj.name)
            if ik_joint.hasAttribute('riotID'):
                rid = ik_joint.findPlug('riotID', False).asInt()
                if rid not in assigned_joints:
                    assigned_joints[rid] = sj
                    continue
            new_joints.append(sj)
        # add new
        joints = [assigned_joints[joint_id] for joint_id in sorted(assigned_joints)]
        joints.extend(new_joints)

    # parent
    joint_ids = {joint.name: joint_id for joint_id, joint in enumerate(joints)}
    for joint in joints:
        ik_joint = ik_joints.get(joint.name)
        if ik_joint is not None and ik_joint.parentCount() > 0:
            parent = ik_joint.parent(0)
            joint.parent = joint_ids.get(om.MFnDependencyNode(parent).name(), -1)
        else:
            joint.parent = -1

    return pyRitoFile.skl.Skeleton(
        None, 
        None,
        joints, 
        [] # influences are built inside skn dump
    )

@helper.print_traceback
def write_skl(skl_path):
    # selected group
    selections = om.MGlobal.getActiveSelectionList()
    if selections.isEmpty():
        raise helper.FunnyError('SKL Exporter: Please select a group to export.')
    iterator = om.MItSelectionList(selections, om.MFn.kTransform)
    if iterator.isDone():
        raise helper.FunnyError('SKL Exporter: Please select a group to export.')
    selected_dagpath = iterator.getDagPath()
    iterator.next()
    if not iterator.isDone():
        raise helper.FunnyError('SKL Exporter: Please select only one group to export.')
    # dump and write skl
    skl_path = helper.ensure_ext(skl_path, '.skl')
    pyRitoFile.skl.write(
        dump_skl({
            'selected_group': selected_dagpath,
            'riot_skl': pyRitoFile.skl.read(rsp) if os.path.exists(rsp:=helper.prefix('riot_', skl_path)) else None
        }),
        skl_path
    )

@helper.print_traceback
def read_skn(skn_path):
    # ensure path
    skn_path = helper.ensure_ext(skn_path, '.skn')
    skl_path = skn_path.removesuffix('.skn') + '.skl'
    skn_name = helper.extract_name(skn_path)
    # group transform
    group_transform = om.MFnTransform()
    group_transform.create()
    group_transform.setName(f'group_{skn_name}')
    # read and load skl
    load_options = {
        'group_transform': group_transform,
        'skn_name': skn_name,
        'skl': None
    }
    if os.path.exists(skl_path):
        load_options['skl'] = skl = pyRitoFile.skl.read(skl_path)
        load_skl(skl, load_options)
    # read and load skn
    load_skn(
        pyRitoFile.skn.read(skn_path),
        load_options
    )


def load_skn(skn, load_options):
    # init
    group_transform = load_options.get('group_transform')
    skn_name = load_options.get('skn_name')
    skl = load_options.get('skl')
    # material related
    selections = om.MSelectionList()
    selections.add('renderPartition')
    selections.add('defaultShaderList1')
    render_partition = om.MFnDependencyNode(selections.getDependNode(0))
    shader_list = om.MFnDependencyNode(selections.getDependNode(1))
    render_partition_sets = render_partition.findPlug('sets', False)
    shader_list_shaders = shader_list.findPlug('shaders', False)
    dg_modifier = om.MDGModifier()
    # binding related
    if skl is not None:
        joint_names_set = {joint.name for joint in skl.joints}
        influence_names = [skl.joints[influence].name for influence in skl.influences]
        influence_count = len(influence_names)
        components = om.MFnSingleIndexedComponent()
        vertex_components = components.create(om.MFn.kMeshVertComponent)
    # create mesh for each submesh
    for submesh in skn.submeshes:
        # lower submesh name if match any joint
        submesh_name = submesh.name.lower() if skl is not None and submesh.name in joint_names_set else submesh.name

        # mesh transform
        mesh_transform = om.MFnTransform()
        mesh_transform.create(group_transform.object())
        mesh_transform.setName(f'mesh_{submesh_name}')

        # mesh shape 
        vertex_slice = slice(submesh.vertex_start, submesh.vertex_start+submesh.vertex_count)
        submesh_positions = om.MFloatPointArray([(-x, y, z) for x, y, z in skn.vertices[0][vertex_slice]])
        index_slice = slice(submesh.index_start, submesh.index_start+submesh.index_count)
        vids = skn.indices[index_slice]
        min_vid = min(vids)
        submesh_indices = om.MIntArray([vid - min_vid for vid in vids])
        face_sizes = om.MIntArray(len(submesh_indices) // 3, 3)
        mesh = om.MFnMesh()
        mesh_object = mesh.create(
            submesh_positions, 
            face_sizes, 
            submesh_indices, 
            parent=mesh_transform.object()
        )
        mesh.setName(f'{skn_name}_{submesh_name}_Shape')
        mesh_name = mesh.name()
        
        # uvs
        submesh_us, submesh_vs = zip(*skn.vertices[4][vertex_slice])
        submesh_vs = [1-v for v in submesh_vs]
        mesh.setUVs(submesh_us, submesh_vs)
        mesh.assignUVs(face_sizes, submesh_indices)

        # materials
        # create lambert and shading engine then get dependency node
        lambert = dg_modifier.createNode('lambert')
        shading_engine = dg_modifier.createNode('shadingEngine')
        dg_modifier.renameNode(lambert, submesh_name)
        dg_modifier.renameNode(shading_engine, f'{submesh_name}_SG')
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

        if skl is not None:
            # bind mesh and get skincluster
            cmds.skinCluster(
                mesh_name,
                influence_names,
                name=f'{mesh_name}_skinCluster',
                toSelectedBones=True,
                maximumInfluences=4,
                bindMethod=0,
                dropoffRate=0.1
            )
            skin_cluster = omAnim.MFnSkinCluster(om.MItDependencyGraph(mesh_object, om.MFn.kSkinClusterFilter, om.MItDependencyGraph.kUpstream).currentNode())
            skin_cluster_name = skin_cluster.name()

            # init 
            submesh_influence_ids = skn.vertices[1][vertex_slice]
            submesh_weights = skn.vertices[2][vertex_slice]
            vertex_count = submesh.vertex_count
            components.setCompleteData(vertex_count)
            flat_weights = [0.0] * (influence_count * vertex_count)
            # convert skeleton influence ids to mesh influence ids
            source_influence_ids = {
                om.MFnDependencyNode(influence_dagpath.node()).name(): skin_cluster.indexForInfluenceObject(influence_dagpath)
                for influence_dagpath in skin_cluster.influenceObjects()
            }
            converted_influence_ids = [
                source_influence_ids[influence_name]
                for influence_name in influence_names
            ]
    
            # populate flat weights
            for vertex_id, (inf_ids, ws) in enumerate(zip(submesh_influence_ids, submesh_weights)):
                offset = vertex_id * influence_count
                for inf_id, w in zip(inf_ids, ws):
                    if w > 0:
                        flat_weights[offset+inf_id] = w    
            flat_weights = om.MDoubleArray(flat_weights)
            # set weights
            skin_cluster.setWeights(
                mesh.getPath(),
                vertex_components,
                om.MIntArray(converted_influence_ids),
                flat_weights,
                normalize=True
            )

    dg_modifier.doIt()

@helper.print_traceback
def write_skn(skn_path):
    # selected group
    selections = om.MGlobal.getActiveSelectionList()
    if selections.isEmpty():
        raise helper.FunnyError('SKN Exporter: Please select a group to export.')
    iterator = om.MItSelectionList(selections, om.MFn.kTransform)
    if iterator.isDone():
        raise helper.FunnyError('SKN Exporter: Please select a group to export.')
    selected_dagpath = iterator.getDagPath()
    iterator.next()
    if not iterator.isDone():
        raise helper.FunnyError('SKN Exporter: Please select only one group to export.')
    # init
    skn_path = helper.ensure_ext(skn_path, '.skn')
    skl_path = skn_path.removesuffix('.skn') + '.skl'
    dump_options = {
        'selected_group': selected_dagpath,
        'riot_skl': pyRitoFile.skl.read(rsp) if os.path.exists(rsp:=helper.prefix('riot_', skl_path)) else None,
    }
    # dump and write skin
    skl = dump_skl(dump_options)
    pyRitoFile.skn.write(
        dump_skn(skl, dump_options),
        skn_path
    )
    pyRitoFile.skl.write(skl, skl_path)


    
def dump_skn(skl, dump_options):
    # init
    components = om.MFnSingleIndexedComponent()
    vertex_component = components.create(om.MFn.kMeshVertComponent)
    sc_iterator = om.MItDependencyGraph()
    joint_count = len(skl.joints)
    joint_ids = {joint.name: joint_id for joint_id, joint in enumerate(skl.joints)}
    influences = set()
    combined_vertices = {}
    combined_indices = {}

    def dump_mesh(mesh):
        # check skinned mesh
        sc_iterator.resetTo(mesh.object(), om.MFn.kSkinClusterFilter, om.MItDependencyGraph.kUpstream)
        if sc_iterator.isDone():
            raise helper.FunnyError(f'SKN Exporter: No skin_cluster on {mesh.name()}, make sure the mesh is bound.')
        skin_cluster = omAnim.MFnSkinCluster(sc_iterator.currentNode())

        # check holes
        if len(mesh.getHoles()) > 0:
            raise helper.FunnyError(f'SKN Exporter: {mesh.name()} has holes.')

        # get material faces and init submesh data
        shading_engines, material_faces = mesh.getConnectedShaders(0)
        material_faces = tuple(material_faces)
        material_count = len(shading_engines)
        if material_count == 0:
            raise helper.FunnyError(f'SKN Exporter: {mesh.name()} has no material assigned.')
        submesh_vertices = [None] * material_count
        submesh_indices = [None] * material_count
        cached_lookups = [None] * material_count
        for material_id, shading_engine in enumerate(shading_engines):
            # get material name
            surface_shader = om.MFnDependencyNode(shading_engine).findPlug('surfaceShader', False)
            plugs = surface_shader.connectedTo(True, False)
            name = om.MFnDependencyNode(plugs[0].node()).name()
            # local submesh data
            vertices = [[], [], [], [], []]
            submesh_vertices[material_id] = vertices
            indices = []
            submesh_indices[material_id] = indices
            # global combined data map
            combined_vertices.setdefault(name, []).append(vertices)
            combined_indices.setdefault(name, []).append(indices)
            # cached relevant pointers per material 
            cached_lookups[material_id] = (
                vertices[0].append, 
                vertices[1].append, 
                vertices[2].append,
                vertices[3].append, 
                vertices[4].append,
                indices.append,  
                {} # uniques
            )

        vertex_count = mesh.numVertices
        # get points
        positions = tuple(mesh.getFloatPoints())
        # get flat weights 
        components.setCompleteData(vertex_count)
        flat_weights, influence_count = skin_cluster.getWeights(mesh.getPath(), vertex_component)
        flat_weights = tuple(flat_weights)
        # convert mesh influence ids to skeleton influences (joint ids) for now
        converted_influences = [None] * influence_count
        influence_dagpaths = skin_cluster.influenceObjects()
        for influence_id, influence_dagpath in enumerate(influence_dagpaths):
            influence_name = om.MFnDependencyNode(influence_dagpath.node()).name()
            influence = joint_ids.get(influence_name)
            if influence is None:
                raise helper.FunnyError(f'SKN Exporter: {influence_name} is not inside selected group. Please move all bound joints into skin group.')
            converted_influences[influence_id] = influence
        # get normals
        normals = tuple(mesh.getVertexNormals(False))

        # cached vertex attributes except uv
        cached_vertices = [None] * vertex_count
        for vertex_id, ((px, py, pz, _), (nx, ny, nz)) in enumerate(zip(positions, normals)):
            # influences (joint ids) and weights
            left = vertex_id * influence_count
            right = left + influence_count
            active = [
                (w, inf)
                for w, inf in zip(flat_weights[left:right], converted_influences)
                if w > 0.001
            ]
            active.sort(reverse=True)
            active_count = len(active)
            if active_count == 0:
                raise helper.FunnyError(f'SKN Exporter: Vertex {vertex_id} on {mesh.name()} has no skin weights assigned.')
            if active_count < 4:
                active.extend([(0.0, active[0][1])] * (4 - active_count))
            (w0, w1, w2, w3), infs = zip(*active[:4])
            # flip position and normal, normalize weight
            cached_vertices[vertex_id] = (
                (-px, py, pz),
                infs,
                (w0/s, w1/s, w2/s, w3/s) if (s:=w0+w1+w2+w3) > 0 else (w0, w1, w2, w3), 
                (nx, -ny, -nz)
            )
            # add to skeleton influences (joint ids)
            influences.update(infs)

        # get uv
        us, vs = mesh.getUVs()
        us = tuple(us)
        vs = tuple(vs)
        uv_count = len(us)
        vertex_id_counts, vertex_ids = mesh.getVertices()
        _, uv_ids = mesh.getAssignedUVs()
        vertex_ids = tuple(vertex_ids)
        uv_ids = tuple(uv_ids)
        # get unique uvs: one vertex can have multiple uv on multiple face
        unique_uv_ids = {}
        left = 0
        for face_id, count in enumerate(vertex_id_counts):
            right = left + count
            for vertex_id, uv_id in zip(vertex_ids[left:right], uv_ids[left:right]):
                unique_uv_ids[(face_id, vertex_id)] = uv_id
            left = right

        # loop triangle: dump unique uv vertices and triangulated indices
        triangle_counts, triangle_vertices = mesh.getTriangles()
        triangle_vertices = tuple(triangle_vertices)
        left = 0
        for face_id, triangle_count in enumerate(triangle_counts):
            # init
            material_id = material_faces[face_id]
            if material_id == -1:
                raise helper.FunnyError(f'SKN Exporter: {mesh.name()} has faces with no material assigned.')
            add_pos, add_inf, add_w, add_nor, add_uv, add_idx, uniques = cached_lookups[material_id]
            right = left + triangle_count * 3
            # loop flat triangle vertices
            for vertex_id in triangle_vertices[left:right]:
                # get uv id
                uv_id = unique_uv_ids.get((face_id, vertex_id))
                if uv_id is None or uv_id < 0 or uv_id >= uv_count:
                    raise helper.FunnyError(f'SKN Exporter: UV id is missing or out of bounds. Please check if all UVs of {mesh.name()} are in first UV set.')
                # check and dump vertex if unique uv id
                key = (vertex_id, uv_id)
                if key not in uniques:
                    uniques[key] = len(uniques)
                    # extract cached vertex attribute
                    position, infs, weights, normal = cached_vertices[vertex_id]
                    # uv
                    uv = (us[uv_id], 1-vs[uv_id])
                    # add to submesh data
                    add_pos(position)
                    add_inf(infs)
                    add_w(weights)
                    add_nor(normal)
                    add_uv(uv)
                # add mapped index
                add_idx(uniques[key])
            left = right

    # find mesh, dump, then combine data
    selected_dagpath = dump_options['selected_group']
    iterator = om.MItDag()
    iterator.reset(selected_dagpath, om.MItDag.kBreadthFirst, om.MFn.kMesh)
    if iterator.isDone():
        raise helper.FunnyError( f'SKN Exporter: No mesh found under selected group.')
    while not iterator.isDone():
        mesh = om.MFnMesh(iterator.currentItem())
        if not mesh.isIntermediateObject:
            dump_mesh(mesh)
        iterator.next()

    # build influences (joint ids)
    skl.influences = influences = sorted(influences)
    influence_count = len(influences)
    if influence_count > 256:
        raise helper.FunnyError(f'SKN Exporter: Too many influences found: {influence_count}, max allowed: 256 influences.')
    converted_influence_ids = [None] * joint_count
    # convert influence (joint id) to influence id map
    for influence_id, influence in enumerate(influences):
        converted_influence_ids[influence] = influence_id

    # build skin
    Submesh = pyRitoFile.skn.Submesh
    submeshes = [None] * len(combined_indices)
    index_start = 0
    vertex_start = 0
    vertices = {
        0: [], # position
        1: [], # influence_ids
        2: [], # weights
        3: [], # normal
        4: [] # uv
    }
    indices = []
    for submesh_index, name in enumerate(combined_indices):
        vertex_count = 0
        index_count = 0
        for part_vertices, part_indices in zip(combined_vertices[name], combined_indices[name]):
            for attribute_id, attribute_data in enumerate(part_vertices):
                if attribute_id != 1:
                    vertices[attribute_id].extend(attribute_data)
                else:
                    # convert influences (joint ids) to influence_ids
                    vertices[1].extend([
                        (
                            converted_influence_ids[inf0],
                            converted_influence_ids[inf1],
                            converted_influence_ids[inf2],
                            converted_influence_ids[inf3]
                        )
                        for inf0, inf1, inf2, inf3 in attribute_data
                    ])

            offset = vertex_start + vertex_count
            indices.extend([index + offset for index in part_indices])
            vertex_count += len(part_vertices[0])
            index_count += len(part_indices)

        submeshes[submesh_index] = Submesh(
            name,
            index_start,
            vertex_start,
            index_count,
            vertex_count
        )

        index_start += index_count
        vertex_start += vertex_count

    # check limit vertices
    vertex_count = len(vertices[0])
    if vertex_count > 65536:
        raise helper.FunnyError(f'SKN Exporter: Too many vertices found: {vertex_count}, max allowed: 65536 vertices.')

    # check limit submeshes
    submesh_count = len(submeshes)
    if submesh_count > 32:
        raise helper.FunnyError(f'SKN Exporter: Too many materials assigned: {submesh_count}, max allowed: 32 materials.')

    return pyRitoFile.skn.Skin(
        None, (1, 1),
        None, None, None,
        submeshes, indices, vertices
    )
