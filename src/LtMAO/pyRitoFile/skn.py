from io import BytesIO
from struct import unpack, iter_unpack, pack

attribute_names = {
    0: 'Position',
    1: 'Influence IDs',
    2: 'Weights',
    3: 'Normal',
    4: 'Texcoord',
    5: 'Color',
    6: 'Tangent'
}

class Submesh:
    __slots__ = ('name', 'vertex_start', 'vertex_count', 'index_start', 'index_count')

    def __init__(self, name, vertex_start, vertex_count, index_start, index_count):
        self.name = name
        self.vertex_start = vertex_start
        self.vertex_count = vertex_count
        self.index_start = index_start
        self.index_count = index_count

class Skin:
    __slots__ = ('signature', 'version', 'flags', 'bounding_box', 'bounding_sphere', 'submeshes', 'indices', 'vertices')

    def __init__(self, signature, version, flags, bounding_box, bounding_sphere, submeshes, indices, vertices):
        self.signature = signature
        self.version = version
        self.flags = flags
        self.bounding_box = bounding_box
        self.bounding_sphere = bounding_sphere
        self.submeshes = submeshes
        self.indices = indices
        self.vertices = vertices

def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # init some default values
        flags = None
        bounding_box = None
        bounding_sphere = None
        vertex_type = 0
        vertex_format = '<3f4B4f3f2f'
        vertex_size = 52

        # header
        signature, major, minor = unpack('<4sHH', bs.read(8))
        if signature != b'3"\x11\x00':
            raise Exception(
                f'pyRitoFile: Error: Read SKN: Wrong signature file: {signature}')
        if major not in {0, 2, 4} and minor != 1:
            raise Exception(
                f'pyRitoFile: Error: Read SKN: Unsupported file version: {major}.{minor}')
        # rest of file
        if major == 0:
            index_count, vertex_count = unpack('<II', bs.read(8))
            # create a simple submesh for version 0
            submeshes = [
                Submesh(
                    'Base', 
                    0,
                    vertex_count,
                    0,
                    index_count
                )
            ]
        else:
            # submeshes
            submesh_count = int.from_bytes(bs.read(4), 'little')
            submeshes = [
                Submesh(
                    name.rstrip(b'\x00').decode(),
                    vertex_start,
                    vertex_count,
                    index_start,
                    index_count
                )
                for name, vertex_start, vertex_count, index_start, index_count in iter_unpack('<64s4I', bs.read(submesh_count*80))
            ]

            if major == 4:
                flags = int.from_bytes(bs.read(4), 'little') 

            index_count, vertex_count = unpack('<II', bs.read(8))
            # prepare vertex info
            if major == 4:
                _, vertex_type = unpack('<II', bs.read(8))
                if vertex_type > 0:
                    vertex_format += '4B'
                    vertex_size += 4
                if vertex_type > 1:
                    vertex_format += '4f'
                    vertex_size += 16
                if vertex_type > 2:
                    raise Exception(f'pyRitoFile: Error: Read SKN: Unknown vertex_type: {vertex_type}')
                
                # read bounding 
                fd = unpack('<10f', bs.read(40))
                bounding_box = (
                    (fd[0], fd[1], fd[2]),
                    (fd[3], fd[4], fd[5])
                )
                bounding_sphere = (
                    (fd[6], fd[7], fd[8]),
                    fd[9]
                )


        # indices
        if index_count % 3 > 0:
            raise Exception(f'pyRitoFile: Error: Read SKN: Indices length is not divisible by 3: {index_count}')
        indices = []
        faces = [*iter_unpack('<3H', bs.read(index_count*2))]
        for submesh in submeshes:
            face_start = submesh.index_start // 3
            face_count = submesh.index_count // 3
            submesh_indices = [
                index
                for a, b, c in faces[face_start:face_start+face_count]
                if a != b and b != c and c != a
                for index in (a, b, c)
            ]
            submesh.index_start = len(indices)
            submesh.index_count = len(submesh_indices)
            indices.extend(submesh_indices)

        # vertices 
        ud = [*iter_unpack(vertex_format, bs.read(vertex_size*vertex_count))]
        vertices = [
            [vd[0:3] for vd in ud], # positions
            [vd[3:7] for vd in ud], # influence_ids
            [vd[7:11] for vd in ud], # weights
            [vd[11:14] for vd in ud], # normals
            [vd[14:16] for vd in ud], # uvs
            [], # colors
            [], # tangents
        ]
        if vertex_type > 0:
            vertices[5] = [vd[16:20] for vd in ud] 
            if vertex_type > 1:
                vertices[6] = [vd[20:24] for vd in ud] 

    return Skin(
        signature,
        (major, minor), #version
        flags, 
        bounding_box,
        bounding_sphere,
        submeshes,
        indices,
        vertices
    )


def write(skin, path=None):
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        major, minor = skin.version
        # header
        bs.write(pack('<4sHH', b'3"\x11\x00', 4 if major >= 4 else 1, 1))
        # submeshes
        bs.write(pack('<I', len(skin.submeshes)))
        for submesh in skin.submeshes:
            bs.write(pack(
                '<64s4I',
                submesh.name.encode(),
                submesh.vertex_start,
                submesh.vertex_count,
                submesh.index_start,
                submesh.index_count
            ))
        # flags
        if major >= 4:
            bs.write(pack('<I', skin.flags))
        # count
        index_count = len(skin.indices)
        vertex_count = len(skin.vertices[0])
        bs.write(pack('<II', index_count, vertex_count))
        # vertex info
        vertex_type = 0
        vertex_format = '3f4B4f3f2f'
        vertex_size = 52
        if major >= 4:
            if skin.vertices[5]:
                vertex_type = 1
                vertex_format += '4B'
                vertex_size += 4
                if skin.vertices[6]:
                    vertex_type = 2
                    vertex_format += '4f'
                    vertex_size += 16
            bs.write(pack(
                '<2I10f',
                vertex_size,
                vertex_type,
                *skin.bounding_box[0],
                *skin.bounding_box[1],
                *skin.bounding_sphere[0],
                skin.bounding_sphere[1]
            ))
        # indices 
        bs.write(pack(f'<{index_count}H', *skin.indices))
        # vertices
        bs.write(pack(
            f'<{vertex_format*vertex_count}',
            *[
                component
                for vertex in zip(*skin.vertices[0:5+vertex_type])
                for attribute in vertex
                for component in attribute
            ]
        ))

        return stream.getvalue() if path is None else None
