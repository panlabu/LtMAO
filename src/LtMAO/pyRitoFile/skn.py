from io import BytesIO
from dataclasses import dataclass
from struct import unpack, iter_unpack, pack

@dataclass(slots=True)
class Vertex:
    position: tuple[float, float, float]
    influences: tuple[int, int, int, int]
    weights: tuple[float, float, float, float]
    normal: tuple[float, float, float]
    uv: tuple[float, float]
    color: tuple[int, int, int, int]
    tangent: tuple[float, float, float, float] 

@dataclass(slots=True)
class Submesh:
    name: str
    vertex_start: int
    vertex_count: int 
    index_start: int
    index_count: int 

@dataclass(slots=True)
class Skin:
    signature: bytes
    version: tuple[int, int] 
    flags: int
    bounding_box: tuple[
        tuple[float, float, float], # min
        tuple[float, float, float]  # max
    ]
    bounding_sphere: tuple[
        tuple[float, float, float], # central
        float # distance
    ] 
    vertex_type: int 
    vertex_size: int
    submeshes: tuple[Submesh, ...] 
    indices: tuple[int, ...] 
    vertices: tuple[Vertex, ...] 

def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # init some default values
        flags = None
        bouding_box = None
        bouding_sphere = None
        vertex_type = 0
        vertex_size = 52
        vertex_format = '3f4B4f3f2f'

        # header
        signature, major, minor = unpack('<4sHH', bs.read(8))
        if signature != b'3"\x11\x00':
            raise Exception(
                f'pyRitoFile: Error: Read SKN {path}: Wrong signature file: {signature}')
        if major not in {0, 2, 4} and minor != 1:
            raise Exception(
                f'pyRitoFile: Error: Read SKN {path}: Unsupported file version: {major}.{minor}')

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
            submesh_count, = unpack('<I', bs.read(4))
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
                flags, = unpack('<I', bs.read(4))

            index_count, vertex_count = unpack('<II', bs.read(8))
            # prepare vertex info
            if major == 4:
                vertex_size, vertex_type = unpack('<II', bs.read(8))
                if vertex_type > 0:
                    vertex_format += '4B'
                if vertex_type > 1:
                    vertex_format += '4f'
                if vertex_type > 2:
                    raise Exception(f'pyRitoFile: Error: Read SKN {path}: Unknown vertex_type: {vertex_type}')
                
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
            raise Exception(f'pyRitoFile: Error: Read SKN {path}: Indices length is not divisible by 3: {index_count}')
        indices = [
            index
            for a, b, c in iter_unpack('<3H', bs.read(index_count*2)) # read 3 indices as tuple
            if a != b and b != c and c != a # only keep them if they are 3 distinct index that form a triangle
            for index in (a, b, c) # flatten tuple
        ]

        # vertices
        vertices = [
            Vertex(
                # always: position, influences, weights, normal, uv
                (vd[0], vd[1], vd[2]),
                (vd[3], vd[4], vd[5], vd[6])
                (vd[7], vd[8], vd[9], vd[10])
                (vd[11], vd[12], vd[13])
                (vd[14], vd[15])
                # depend: color, tangent
                (vd[16], vd[17], vd[18]) if vertex_type > 0 else None,
                (vd[19], vd[20], vd[21]) if vertex_type > 1 else None
            )   
            for vd in iter_unpack(vertex_format, bs.read(vertex_size*vertex_count))
        ]

    return Skin(
        signature,
        (major, minor), #version
        flags, 
        bounding_box,
        bounding_sphere,
        vertex_type,
        vertex_size,
        submeshes,
        indices,
        vertices
    )


def write(skin, path=None):
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        # header
        bs.write(pack('<4sHH', b'\xc3O\xfd"', 4 if skin.version >= 4 else 1, 1))
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
        if skin.version >= 4:
            bs.write(pack('<I', skin.flags))
        # count
        bs.write(pack('<II', len(skin.indices), len(skin.vertices)))
        # vertex info
        if skin.version >= 4:
            bs.write(pack(
                '<2I10f',
                skin.vertex_size,
                skin.vertex_type,
                *[v for vec in skin.bounding_box for v in vec],
                *[v for v in skin.bounding_sphere[0]],
                skin.bounding_sphere[1]
            ))
        # indices 
        bs.write(pack(f'<{len(skin.indices)}H', *skin.indices))
        # vertices
        for vertex in skin.vertices:
            bs.write(pack(
                '<3f4B4f3f2f',
                *vertex.position,
                *vertex.influences,
                *vertex.weights,
                *vertex.normal,
                *vertex.uv
            ))
            if skin.vertex_type > 0:
                bs.write(pack('<4B', *vertex.color))
                if skin.vertex_type > 1:
                    bs.write(pack('<4f', *vertex.tangent))

    return stream.getvalue() if path is None else None
