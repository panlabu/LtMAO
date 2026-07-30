from struct import unpack, iter_unpack, pack
from io import BytesIO

class StaticComponent:
    __slots__ = ('signature', 'version', 'flags', 'name', 'central', 'pivot', 'bounding_box', 'material', 'indices', 'positions', 'uvs', 'colors')

    def __init__(self, signature, version, flags, name, central, pivot, bounding_box, material, indices, positions, uvs, colors):
        self.signature = signature
        self.version = version
        self.flags = flags
        self.name = name
        self.central = central
        self.pivot = pivot
        self.bounding_box = bounding_box
        self.material = material
        self.indices = indices
        self.positions = positions
        self.uvs = uvs
        self.colors = colors

def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # init 
        major = None
        minor = None
        flags = 0
        name = ''
        pivot = None
        central = (0, 0, 0)
        bounding_box = None
        material = ''
        indices = []
        positions = []
        uvs = []
        colors = []
        signature = bs.read(13)
        if signature == b'[ObjectBegin]':
            # static component object
            # read line
            records = iter([line.split() for line in bs.read().decode().split('\n')])
            for record in records:
                if not record:
                    continue
                key = record[0]
                # various
                if key == 'Name=':
                    name = record[1]
                elif key == 'CentralPoint=':
                    central = (float(record[1]), float(record[2]), float(record[3]))
                elif key == 'PivotPoint=':
                    pivot = (float(record[1]), float(record[2]), float(record[3]))
                # vertex
                elif key == 'Verts=':
                    vertex_count = int(record[1])
                    positions = [
                        (float(x), float(y), float(z))
                        for _ in range(vertex_count)
                        for x, y, z in [next(records)]
                    ]
                # face
                elif key == 'Faces=':
                    face_count = int(record[1])
                    for _ in range(face_count):
                        rd = next(records)
                        a, b, c = int(rd[0]), int(rd[1]), int(rd[2])
                        if a == b or b == c or c == a:
                            continue
                        indices.extend((a, b, c))
                        material = rd[4]
                        # u v, u v, u v
                        uvs.extend((
                            (float(rd[5]), float(rd[6])),
                            (float(rd[7]), float(rd[8])),
                            (float(rd[9]), float(rd[10]))
                        ))
        elif signature.startswith(b'r3d2Mesh'):
            # static component binary
            # header
            bs.seek(8)
            major, minor = unpack('<HH', bs.read(4))
            if major not in {3, 2} and minor != 1:
                raise Exception(f'pyRitoFile: Error: Read SCB: Unsupported file version: {major}.{minor}')
            # various
            ud = unpack('<128s3I6f', bs.read(164))
            name = ud[0].rstrip(b'\x00').decode()
            vertex_count, face_count, flags = ud[1], ud[2], ud[3]
            bounding_box = (
                (ud[4], ud[5], ud[6]),
                (ud[7], ud[8], ud[9])
            )
            # vertex
            vertex_type = 0
            if major == 3 and minor == 2:
                vertex_type = int.from_bytes(bs.read(4), 'little')
            positions = [*iter_unpack('<3f', bs.read(vertex_count*12))]
            if vertex_type > 0:
                colors = [*iter_unpack('<4B', bs.read(vertex_count*4))]
            central = unpack('<3f', bs.read(12))
            # face
            for ud in iter_unpack('<3I64s6f', bs.read(face_count*100)):
                a, b, c = ud[0], ud[1], ud[2]
                if a == b or b == c or c == a:
                    continue
                indices.extend((a, b, c))
                material = ud[3].rstrip(b'\x00').decode()
                # u u u, v v v
                uvs.extend((
                    (ud[4], ud[7]),
                    (ud[5], ud[8]),
                    (ud[6], ud[9])
                ))
        else:
            raise Exception(f'pyRitoFile: Error: Read SCB: Wrong file signature: {signature}')

    return StaticComponent(
        signature,
        (major, minor), # version
        flags,
        name,
        central,
        pivot,
        bounding_box,
        material,
        indices,
        positions,
        uvs,
        colors
    )


def write(statcomp, path=None):
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        # init
        if statcomp.bounding_box == None:
            x_min, y_min, z_min = statcomp.positions[0]
            x_max, y_max, z_max = statcomp.positions[0]
            for x, y, z in statcomp.positions:
                if x > x_max: x_max = x
                if y > y_max: y_max = y
                if z > z_max: z_max = z
                if x < x_min: x_min = x
                if y < y_min: y_min = y
                if z < z_min: z_min = z
            statcomp.bounding_box = ((x_min, y_min, z_min), (x_max, y_max, z_max))
        vertex_type = 1 if statcomp.colors else 0
        # header
        bs.write(pack('<8sHH', b'r3d2Mesh', 3, 2))
        # various
        index_count = len(statcomp.indices)
        face_count = index_count // 3
        vertex_count = len(statcomp.positions)
        bs.write(pack(
            '<128s3I6fI',
            statcomp.name.encode(),
            vertex_count,
            face_count,
            statcomp.flags,
            *statcomp.bounding_box[0],
            *statcomp.bounding_box[1],
            vertex_type
        ))
        # positions
        bs.write(pack(
            f'<{vertex_count*3}f',
            *[v for p in statcomp.positions for v in p]
        ))
        # colors
        if vertex_type > 0:
            bs.write(pack(
                f'<{vertex_count*4}B',
                *[v for c in statcomp.colors for v in c]
            ))
        # central
        bs.write(pack('<3f', *statcomp.central))
        # faces 
        indices = statcomp.indices
        material = statcomp.material.encode()
        uvs = statcomp.uvs
        for index in range(0, index_count, 3):
            bs.write(pack(
                '<3I64s6f',
                indices[index],
                indices[index+1],
                indices[index+2],
                material,
                uvs[index][0],
                uvs[index+1][0],
                uvs[index+2][0],
                uvs[index][1],
                uvs[index+1][1],
                uvs[index+2][1]

            ))
        return stream.getvalue() if path is None else None
