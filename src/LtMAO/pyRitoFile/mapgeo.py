from io import BytesIO
from struct import unpack, iter_unpack, pack

class PlanarReflector:
    __slots__ = ('transform', 'plane', 'normal')

    def __init__(self, transform, plane, normal):
        self.transform = transform
        self.plane = plane
        self.normal = normal

class Bucket:
    __slots__ = (
        'max_stickout_x', 'max_stickout_z',
        'start_index', 'base_vertex',
        'inside_face_count', 'sticking_out_face_count'
    )

    def __init__(self, max_stickout_x, max_stickout_z, start_index, base_vertex, inside_face_count, sticking_out_face_count):
        self.max_stickout_x = max_stickout_x
        self.max_stickout_z = max_stickout_z
        self.start_index = start_index
        self.base_vertex = base_vertex
        self.inside_face_count = inside_face_count
        self.sticking_out_face_count = sticking_out_face_count
    

class BucketGrid:
    __slots__ = (
        'controller_hash', 'unknown_hash',
        'min_x', 'min_z', 'max_x', 'max_z', 'max_stickout_x', 'max_stickout_z', 'bucket_size_x', 'bucket_size_z',
        'is_disabled', 'flags',
        'vertices', 'indices', 'buckets',
        'face_layers'
    )

    def __init__(self, controller_hash, unknown_hash, min_x, min_z, max_x, max_z, max_stickout_x, max_stickout_z, bucket_size_x, bucket_size_z, is_disabled, flags, vertices, indices, buckets, face_layers):
        self.controller_hash = controller_hash
        self.unknown_hash = unknown_hash
        self.min_x = min_x
        self.min_z = min_z
        self.max_x = max_x
        self.max_z = max_z
        self.max_stickout_x = max_stickout_x
        self.max_stickout_z = max_stickout_z
        self.bucket_size_x = bucket_size_x
        self.bucket_size_z = bucket_size_z
        self.is_disabled = is_disabled
        self.flags = flags
        self.vertices = vertices
        self.indices = indices
        self.buckets = buckets
        self.face_layers = face_layers
    

class Submesh:
    __slots__ = ('hash', 'name', 'index_start', 'index_count', 'min_vertex', 'max_vertex')
    def __init__(self, hash, name, index_start, index_count, min_vertex, max_vertex):
        self.hash = hash
        self.name = name
        self.index_start = index_start
        self.index_count = index_count
        self.min_vertex = min_vertex
        self.max_vertex = max_vertex
    


class Model:
    __slots__ = (
        'name', 'vertices', 'indices', 'submeshes', 'layer', 'unknown_hash', 'controller_hash', 'bounding_box', 
        'transform', 'quality', 'disable_backface_culling', 'is_bush', 'render', 
        'point_light', 'light_probe', 'baked_light', 'stationary_light', 'baked_paint', 'texture_overrides'
    )

    def __init__(self, name, vertices, indices, submeshes, layer, unknown_hash, controller_hash, bounding_box, transform, quality, disable_backface_culling, is_bush, render, point_light, light_probe, baked_light, stationary_light, baked_paint, texture_overrides):
        self.name = name
        self.vertices = vertices
        self.indices = indices
        self.submeshes = submeshes
        self.layer = layer
        self.unknown_hash = unknown_hash
        self.controller_hash = controller_hash
        self.bounding_box = bounding_box
        self.transform = transform
        self.quality = quality
        self.disable_backface_culling = disable_backface_culling
        self.is_bush = is_bush
        self.render = render
        self.point_light = point_light
        self.light_probe = light_probe
        self.baked_light = baked_light
        self.stationary_light = stationary_light
        self.baked_paint = baked_paint
        self.texture_overrides = texture_overrides

element_names = {
    0: 'Position',
    1: 'Blend Weight',
    2: 'Normal',
    3: 'Fog Coordinate',
    4: 'Primary Color',
    5: 'Secondary Color',
    6: 'Blend Index',
    7: 'Texcoord 0',
    8: 'Texcoord 1',
    9: 'Texcoord 2',
    10: 'Texcoord 3',
    11: 'Texcoord 4',
    12: 'Texcoord 5',
    13: 'Texcoord 6',
    14: 'Texcoord 7',
    15: 'Tangent'

}

format_names = {
    0: 'X Float32',
    1: 'XY Float32',
    2: 'XYZ Float32',
    3: 'XYZW Float32',
    4: 'BGRA Int8',
    5: 'ZYXW Int8',
    6: 'RGBA Int8',
    7: 'XY Float16',
    8: 'XYZ Float16',
    9: 'XYZW Float16'

}

usage_names = {
    0: 'Static',
    1: 'Dynamic',
    2: 'Stream'
}

format_py = {
    0: 'f',
    1: '2f',
    2: '3f',
    3: '4f',
    4: '4B',
    5: '4B',
    6: '4B',
    7: '2e',
    8: '3e2x', # pad 2 byte for no reason
    9: '4e'
}
format_count = {
    0: 1,
    1: 2,
    2: 3,
    3: 4,
    4: 4,
    5: 4,
    6: 4,
    7: 2,
    8: 3,
    9: 4
}

class MapGeometry:
    __slots__ = ('signature', 'version', 'samplers', 'shader_texture_overrides', 'models', 'bucket_grids', 'planar_reflectors')
    def __init__(self, signature, version, samplers, shader_texture_overrides, models, bucket_grids, planar_reflectors):
        self.signature = signature
        self.version = version
        self.samplers = samplers
        self.shader_texture_overrides = shader_texture_overrides
        self.models = models
        self.bucket_grids = bucket_grids
        self.planar_reflectors = planar_reflectors

def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # header
        signature, version = unpack('<4sI', bs.read(8))
        if signature != b'OEGM':
            raise Exception(f'pyRitoFile: Error: Read MAPGEO: Wrong signature file: {signature}')
        if version not in {5, 6, 7, 9, 11, 12, 13, 14, 15, 17, 18}:
            raise Exception(f'pyRitoFile: Error: Read MAPGEO: Unsupported file version: {version}')

        # 6-: use separate point light
        use_separate_point_lights = (version <= 6) and (bs.read(1)[0] != 0)

        # 17+: shader texture overrides
        # 9+: 1st sampler
        # 11+: 2nd sampler
        shader_texture_overrides = []
        samplers = ['', '']
        if version >= 17:
            shader_texture_overrides = [
                (index, bs.read(path_length).decode()) 
                for _ in range(int.from_bytes(bs.read(4), 'little'))
                for index, path_length in [unpack('<II', bs.read(8))]
            ]
        else:
            if version >= 9:
                samplers[0] = bs.read(int.from_bytes(bs.read(4), 'little')).decode()
                if version >= 11:
                    samplers[1] = bs.read(int.from_bytes(bs.read(4), 'little')).decode()

        # vertex descriptions
        vertex_description_count = int.from_bytes(bs.read(4), 'little')
        vertex_descriptions = [None] * vertex_description_count 
        for vd_id in range(vertex_description_count):
            usage, element_count = unpack('<2I', bs.read(8))
            vertex_descriptions[vd_id] = (
                usage,
                [*iter_unpack('<2I', bs.read(element_count*8))] # list[(name, format),...]
            )
            bs.seek(120 - element_count*8, 1) # pad empty, each desc size is 128

        # vertex buffers 
        vertex_buffer_count = int.from_bytes(bs.read(4), 'little')
        vertex_buffers = [None] * vertex_buffer_count
        for vb_id in range(vertex_buffer_count):
            # 13+: 1 byte layer
            if version >= 13: bs.seek(1, 1) 
            vertex_buffers[vb_id] = bs.read(int.from_bytes(bs.read(4), 'little'))

        # index buffers
        index_buffer_count = int.from_bytes(bs.read(4), 'little')
        index_buffers = [None] * index_buffer_count
        for ib_id in range(index_buffer_count):
            if version >= 13: bs.seek(1, 1)
            index_buffers[vb_id] = bs.read(int.from_bytes(bs.read(4), 'little'))
    
        # init to unpack vertices
        unpacked_vertices = {}
        fmt_py = format_py
        fmt_count = format_count
        # models
        model_count = int.from_bytes(bs.read(4), 'little')
        models = [None] * model_count
        for model_id in range(model_count):
            # init
            unknown_hash = 0
            controller_hash = 0
            disable_backface_culling = False
            layer = 0
            is_bush = False
            render = 0
            point_light = None
            light_probe = None
            stationary_light = ('', 0, 0, 0, 0)
            baked_paint = ('', 0, 0, 0, 0)
            texture_overrides = ([], 0, 0, 0, 0)

            # name
            name = f'MapGeo_Instance_{model_id}' if version >= 12 else bs.read(int.from_bytes(bs.read(4), 'little')).decode()

            # vertices
            vertices = {}
            vertex_count, vertex_buffer_count, vertex_description_start_id = unpack('<3I', bs.read(12))
            vertex_buffer_ids = unpack(f'<{vertex_buffer_count}I', bs.read(vertex_buffer_count*4))
            # unpack vertex buffer into python data types
            for i, vertex_buffer_id in enumerate(vertex_buffer_ids):
                usage, elements = vertex_descriptions[vertex_description_start_id+i]
                if vertex_buffer_id not in unpacked_vertices:
                    vertex_format = ''.join([fmt_py[format] for _, format in elements])
                    stride = 0
                    slices = [
                        (name, stride, stride:=stride+fmt_count[format])
                        for name, format in elements
                    ]
                    # unpack vertex buffer into flat vertex element tuple
                    unpacked_items = unpack(f'<{vertex_format*vertex_count}', vertex_buffers[vertex_buffer_id])
                    # use stride to extract individual component
                    unpacked_components = [unpacked_items[offset::stride] for offset in range(stride)]
                    # use slice to merge component back to element
                    unpacked_vertices[vertex_buffer_id] = {
                        name: [*zip(*unpacked_components[s1:s2])]
                        for name, s1, s2 in slices
                    }
                # set vertex data
                vertices.update(unpacked_vertices[vertex_buffer_id])

            # indices
            index_count, index_buffer_id = unpack('<2I', bs.read(8))
            indices = unpack(f'<{index_count}H', index_buffers[index_buffer_id])

            # 13+: layer is up here
            if version >= 13:
                layer = bs.read(1)[0]

            # 18+: unknown hash
            if version >= 18:
                unknown_hash = int.from_bytes(bs.read(4), 'little')

            # 15+: controller hash
            if version >= 15:
                controller_hash = int.from_bytes(bs.read(4), 'little')

            # submeshes
            submesh_count = int.from_bytes(bs.read(4), 'little')
            submeshes = [
                Submesh(
                    submesh_hash, 
                    bs.read(name_length).decode(),
                    # index start, count and min, max vertex
                    *unpack('<4I', bs.read(16))
                )
                for _ in range(submesh_count)
                for submesh_hash, name_length in [unpack('<II', bs.read(8))]
            ]

            # not 5: backface culling
            if version != 5:
                disable_backface_culling = bs.read(1)[0] != 0

            # bounding box, transform, quality
            ud = unpack('<22fB', bs.read(89))
            bounding_box = (
                (ud[0], ud[1], ud[2]), # min
                (ud[3], ud[4], ud[5]) # max
            )
            transform = ud[6:22]
            quality = ud[22]

            # 7+ to 12-: layer is down here
            if 7 <= version <= 12:
                layer = bs.read(1)[0]
            
            if version >= 11:
                if version >= 14:
                    # 14: is_bush
                    is_bush = bs.read(1)[0] != 0
                # 11+: render
                render = int.from_bytes(bs.read(2), 'little') if version >= 15 else bs.read(1)[0]

            # 6-: point light
            if version <= 6 and use_separate_point_lights:
                point_light = unpack('<3f', bs.read(12))

            # 7-: light probe
            if version <= 7:
                # light probe - 27 floats, 9 for each RGB channel
                fd = unpack('<27f', bs.read(108))
                light_probe = (fd[0:9], fd[9:18], fd[18:27])

            # channels
            # baked light
            baked_light = (
                # texture
                bs.read(int.from_bytes(bs.read(4), 'little')).decode(), 
                # (scale_x, scale_y, offset_x, offset_y)
                *unpack('<4f', bs.read(16))
            )
            if version >= 9:
                # 9+: stationary light
                stationary_light = (
                    bs.read(int.from_bytes(bs.read(4), 'little')).decode(),
                    *unpack('<4f', bs.read(16))
                )
                # 12+: baked paint
                # 17+: texture overrides
                if version >= 12:
                    if version >= 17:
                        texture_overrides = (
                            [
                                (index, bs.read(path_length).decode())
                                for _ in range(int.from_bytes(bs.read(4), 'little'))
                                for index, path_length in [unpack('<2I', bs.read(8))]
                            ],
                            *unpack('<4f', bs.read(16))
                        )
                    else:
                        baked_paint = (
                            bs.read(int.from_bytes(bs.read(4), 'little')).decode(),
                            *unpack('<4f', bs.read(16))
                        )
            models[model_id] = Model(
                name,
                vertices,
                indices,
                submeshes,
                layer,
                unknown_hash,
                controller_hash,
                bounding_box,
                transform,
                quality,
                disable_backface_culling,
                is_bush,
                render,
                point_light,
                light_probe,
                baked_light,
                stationary_light,
                baked_paint,
                texture_overrides
            )

        # modded file with no bucket grid, planar reflector: stop reading
        # (exported by lemon3d/lol_maya)
        bucket_grids = []
        planar_reflectors = []
        current = bs.tell()
        bs.seek(0, 2)
        end = bs.tell()
        if current == end:
            return MapGeometry(
                signature,
                version,
                samplers,
                shader_texture_overrides,
                models,
                bucket_grids,
                planar_reflectors
            )
        bs.seek(current)

        # bucket grids
        # 15+: multi bucket grids
        bucket_grid_count = int.from_bytes(bs.read(4), 'little') if version >= 15 else 1
        bucket_grids = [None] * bucket_grid_count
        for bucket_grid_id in range(bucket_grid_count):
            # init
            controller_hash = 0
            unknown_hash = 0
            vertices = []
            indices = []
            buckets = []
            face_layers = []
            # 15+: controller hash
            if version >= 15:
                controller_hash = int.from_bytes(bs.read(4), 'little')
            # 18+: unknown hash
            if version >= 18:
                unknown_hash = int.from_bytes(bs.read(4), 'little')
            ud = unpack('<8fH?B2I', bs.read(44))
            bucket_count = ud[8]
            is_disabled = ud[9]
            flags = ud[10]
            vertex_count = ud[11]
            index_count = ud[12]
            if not is_disabled:
                vertices = [*iter_unpack('<3f', bs.read(vertex_count*12))]
                indices = unpack(f'<{index_count}H', bs.read(index_count*2))
                buckets = [
                    [Bucket(*ud) for ud in iter_unpack('<2f2I2H', bs.read(bucket_count*20))]
                    for _ in range(bucket_count)

                ]
                if flags > 0:
                    face_layers = unpack(f'<{(face_count:=index_count//3)}B', bs.read(face_count))
            bucket_grids[bucket_grid_id] = BucketGrid(
                controller_hash,
                unknown_hash, 
                *ud[0:8],
                is_disabled,
                flags,
                vertices,
                indices,
                buckets,
                face_layers
            )

        if version >= 13:
            planar_reflector_count = int.from_bytes(bs.read(4), 'little')
            planar_reflectors = [
                PlanarReflector(
                    fd[0:16],
                    ((fd[16], fd[17], fd[18]), (fd[19], fd[20], fd[21])),
                    (fd[22], fd[23], fd[24])
                )
                for fd in iter_unpack('<25f', bs.read(planar_reflector_count*100))
            ]

        return MapGeometry(
            signature,
            version,
            samplers,
            shader_texture_overrides,
            models,
            bucket_grids,
            planar_reflectors
        )
       

def write(mapgeo, path=None, version=18, float16=False):
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        # init
        fmt_py = format_py
        position_element = 0
        normal_element = 2
        primary_color_element = 4
        texcoord_element = {7, 14} 
        texcoord5_element = 12
        xyz_float32 = 2
        bgra_int8 = 4
        normal_format = 8 if float16 else 2
        texcoord_format = 7 if float16 else 1
        # force write version 18 or 13
        version = 18 if version >= 18 else 13
        # build vertex descriptions, vertex buffers, index buffers
        model_count = len(mapgeo.models)
        vertex_descriptions = [None] * model_count
        vertex_buffers = [None] * model_count
        index_buffers = [None] * model_count
        vertex_counts = [None] * model_count
        for model_id, model in enumerate(mapgeo.models):
            # vertex description 
            elements = {}
            for name in model.vertices.keys():
                if name == position_element:
                    elements[name] = xyz_float32
                elif name == normal_element:
                    elements[name] = normal_format
                elif name == primary_color_element:
                    elements[name] = bgra_int8
                elif name in texcoord_element:
                    elements[name] = texcoord_format
            if model.is_bush:
                elements[texcoord5_element] = xyz_float32
            elements_list = list(elements.items())
            vertex_descriptions[model_id] = (0, elements_list)
            # vertex buffer 
            vertex_format = ''.join([fmt_py[format] for _, format in elements_list])
            vertex_count = len(next(iter(model.vertices.values())))
            vertex_buffers[model_id] = (
                model.layer,
                pack(
                    f'<{vertex_format*vertex_count}', 
                    *[
                        value
                        for element_values in zip(*[model.vertices[name] for name in elements])
                        for element_value in element_values
                        for value in element_value
                    ]
                )
            )
            vertex_counts[model_id] = vertex_count

            # index buffer
            index_buffers[model_id] = (
                model.layer,
                pack(f'<{len(model.indices)}H', *model.indices)
            )
                
        # header
        bs.write(pack('<4sI', b'OEGM', version))
        # sampler and shader texture overrides
        if version > 13:
            bs.write(pack('<I', len(mapgeo.shader_texture_overrides)))
            for index, path in mapgeo.shader_texture_overrides:
                bs.write(pack(f'<2I', index, len(p:=path.encode())) + p)
        else:
            for sampler in mapgeo.samplers:
                bs.write(pack(f'<I', len(p:=sampler.encode())) + p)
        # vertex descriptions
        bs.write(pack('<I', len(vertex_descriptions)))
        for usage, elements in vertex_descriptions:
            bs.write(pack('<2I', usage, len(elements)))
            bs.write(pack('<120s', b''.join([pack('<2I', name, format) for name, format in elements])))
        # vertex buffers
        bs.write(pack('<I', len(vertex_buffers)))
        for layer, vertex_buffer in vertex_buffers:
            bs.write(pack('<BI', layer, len(vertex_buffer)))
            bs.write(vertex_buffer)
        # index buffers
        bs.write(pack('<I', len(index_buffers)))
        for layer, index_buffer in index_buffers:
            bs.write(pack('<BI', layer, len(index_buffer)))
            bs.write(index_buffer)
        # models
        bs.write(pack('<I', len(mapgeo.models)))
        for model_id, model in enumerate(mapgeo.models):
            # vertices, indices
            bs.write(pack(
                '<6I', 
                vertex_counts[model_id],
                1, # vertex buffer count
                model_id, # vertex description id
                model_id, # vertex buffer id
                len(model.indices), # index count
                model_id, # index buffer id
            ))
            # layer
            bs.write(pack('<B', model.layer))
            # unknown and controller hash
            if version > 13:
                bs.write(pack('<2I', model.unknown_hash, model.controller_hash))
            # submeshes
            bs.write(pack('<I', len(model.submeshes)))
            for submesh in model.submeshes:
                bs.write(pack('<2I', submesh.hash, len(n:=submesh.name.encode())) + n)
                bs.write(pack('<4I', submesh.index_start, submesh.index_count, submesh.min_vertex, submesh.max_vertex))
            # disable backface culling, bounding box, transform, quality
            bs.write(pack(
                '<?22fB', 
                model.disable_backface_culling,
                *model.bounding_box[0],
                *model.bounding_box[1],
                *model.transform,
                31 # all quality
            ))
            # is bush, render
            if version > 13:
                bs.write(pack('<?H', model.is_bush, model.render))
            else:
                bs.write(pack('<B', model.render))
            # baked light
            bs.write(pack('<I', len(p:=model.baked_light[0].encode())) + p)
            bs.write(pack('<4f', *model.baked_light[1:]))
            # stationary light
            bs.write(pack('<I', len(p:=model.stationary_light[0].encode())) + p)
            bs.write(pack('<4f', *model.stationary_light[1:]))
            # baked paint / texture override
            if version > 13:
                bs.write(pack('<I', len(model.texture_overrides[0])))
                for index, path in model.texture_overrides[0]:
                    bs.write(pack(f'<2I', index, len(p:=path.encode())) + p)
                bs.write(pack('<4f', *model.texture_overrides[1:]))
            else:
                bs.write(pack('<I', len(p:=model.baked_paint[0].encode())) + p)
                bs.write(pack('<4f', *model.baked_paint[1:]))
        # bucket grids
        if version > 13:
            bs.write(pack('<I', len(mapgeo.bucket_grids)))
            bucket_grids = mapgeo.bucket_grids
        else:
            bucket_grids = mapgeo.bucket_grids[:1]
        for bucket_grid in bucket_grids:
            # controller and unknown hash
            if version > 13:
                bs.write(pack('<2I', bucket_grid.controller_hash, bucket_grid.unknown_hash))
            index_count = len(bucket_grid.indices)
            bs.write(pack(
                '<8fH?B2I',
                bucket_grid.min_x,
                bucket_grid.min_z,
                bucket_grid.max_x,
                bucket_grid.max_z,
                bucket_grid.max_stickout_x,
                bucket_grid.max_stickout_z,
                bucket_grid.bucket_size_x,
                bucket_grid.bucket_size_z,
                len(bucket_grid.buckets),
                bucket_grid.is_disabled,
                bucket_grid.flags,
                len(bucket_grid.vertices),
                index_count
            ))
            if not bucket_grid.is_disabled:
                bs.write(pack(
                    f'<{len(bucket_grid.vertices)*3}f',
                    *[
                        value 
                        for vertex in bucket_grid.vertices
                        for value in vertex
                    ]
                ))
                bs.write(pack(f'<{index_count}H', *bucket_grid.indices))
                for bucket_row in bucket_grid.buckets:
                    for bucket in bucket_row:
                        bs.write(pack(
                            '<2f2I2H', 
                            bucket.max_stickout_x,
                            bucket.max_stickout_z,
                            bucket.start_index,
                            bucket.base_vertex,
                            bucket.inside_face_count,
                            bucket.sticking_out_face_count
                        ))
                if bucket_grid.flags > 0:
                    bs.write(pack(f'<{index_count//3}B', *bucket_grid.face_layers))
        # planar reflectors
        bs.write(pack('<I', len(mapgeo.planar_reflectors)))
        for planar_reflector in mapgeo.planar_reflectors:
            bs.write(pack(
                '<25f',
                *planar_reflector.transform,
                *planar_reflector.plane[0],
                *planar_reflector.plane[1],
                *planar_reflector.normal
            ))

        return stream.getvalue() if path is None else None

