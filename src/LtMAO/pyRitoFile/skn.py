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
    signature: str
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
    submeshes: list[Submesh] 
    indices: list[int] 
    vertices: list[Vertex] 

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
        signature, major, minor = unpack('<IHH', bs.read(8))
        if signature != 0x00112233:
            raise Exception(
                f'pyRitoFile: Error: Read SKN {path}: Wrong signature file: {hex(signature)}')
        if major not in (0, 2, 4) and minor != 1:
            raise Exception(
                f'pyRitoFile: Error: Read SKN {path}: Unsupported file version: {major}.{minor}')

        # rest of file
        if major == 0:
            index_count, vertex_count = unpack('<II', bs.read(8))
            # create a simple submesh for version
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
                    name.rstrip(b'\x00').decode(), # strip trailing null bytes 
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
                unpacked_floats = unpack('<10f', bs.read(40))
                bounding_box = (
                    unpacked_floats[0:2],
                    unpacked_floats[3:5]
                )
                bounding_sphere = (
                    unpacked_floats[6:8],
                    unpacked_floats[9]
                )

        # indices
        if index_count % 3 > 0:
            raise Exception(f'pyRitoFile: Error: Read SKN {path}: Indices length is not divisible by 3: {index_count}')
        indices = [
            index
            for a, b, c in iter_unpack('<3H', bs.read(index_count*2)) # read 3 indices as tuple
            for index in (a, b, c) # flatten tuple
            if a != b and b != c and c != a # only keep them if they are 3 distinct index that form a triangle
        ]

        # vertices
        vertices = [
            Vertex(
                # always: position, influences, weights, normal, uv
                unpacked_items[0:2],
                unpacked_items[3:6],
                unpacked_items[7:10],
                unpacked_items[11:13],
                unpacked_items[14:15],
                # depend: color, tangent
                unpacked_items[16:19] if vertex_type > 0 else None,
                unpacked_items[20:23] if vertex_type > 1 else None
            )
            for unpacked_items in iter_unpack(vertex_format, bs.read(vertex_size*vertex_count))
        ]

    return Skin(
        hex(signature),
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
    stream = BytesIO() if path == None else open(path, 'wb')
    with stream as bs:
        # header
        bs.write(pack('<IHH', 0x00112233, 1, 1))
        # submeshes
        bs.write(pack('<I', len(skin.submeshes)))
        bs.write(b''.join(
            pack('<64s4I',
                 submesh.name.encode(),
                 submesh.vertex_start,
                 submesh.vertex_count,
                 submesh.index_start,
                 submesh.index_count
            )
            for submesh in skin.submeshes
        ))
        # count
        bs.write(pack('<II', len(skin.indices), len(skin.vertices)))
        # indices 
        bs.write(pack(f'{len(skin.indices)}H', *skin.indices))
        # vertices
        bs.write(b''.join(
            pack('3f4B4f3f2f',
                 *vertex.position,
                 *vertex.influences,
                 *vertex.weights,
                 *vertex.normal,
                 *vertex.uv
            )
            for vertex in skin.vertices
        ))

    return stream.getvalue() if path == None else None
