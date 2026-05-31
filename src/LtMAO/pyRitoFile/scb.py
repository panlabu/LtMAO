from dataclasses import dataclass
from struct import unpack, iter_unpack, pack
from io import BytesIO

@dataclass(slots=True)
class SceneObject:
    signature: bytes
    version: tuple[int, int]
    flags: int
    name: str
    central: tuple[float, float, float]
    pivot: tuple[float, float, float]
    bounding_box: tuple[
        tuple[float, float, float],
        tuple[float, float, float]
    ]
    material: str
    vertex_type: int
    indices: tuple[int, ...]
    positions: tuple[tuple[float, float, float], ...]
    uvs: tuple[tuple[float, float], ...]
    colors: tuple[tuple[int, int, int, int], ...]


def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open('rb', path)
    with stream as bs:
        # init some value
        vertex_type = 0
        indices = []
        positions = []
        uvs = []

        signature = bs.read(8)
        if signature == b'[ObjectB':
            # sco
            # header
            signature += bs.read(6)[:-1]
            # read each line
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
                        for i in range(vertex_count)
                        for x, y, z in (next(records),)
                    ]
                # face
                elif key == 'Faces=':
                    face_count = int(record[1])
                    for i in range(face_count):
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
        elif signature == b'r3d2Mesh':
            # scb
            # header
            major, minor = unpack('<HH', bs.read(4))
            if major not in {3, 2} and minor != 1:
                raise Exception(f'pyRitoFile: Error: Read SCB {path}: Unsupported file version: {major}.{minor}')
            # various
            ud = unpack('<128s3I6f', bs.read(164))
            name = ud[0].rstrip(b'\x00').decode()
            vertex_count, face_count, flags = ud[1], ud[2], ud[3]
            bounding_box = (
                (ud[4], ud[5], ud[6]),
                (ud[7], ud[8], ud[9])
            )
            # vertex
            if major == 3 and minor == 2:
                vertex_type, = unpack('<I', bs.read(4))
            positions = [*iter_unpack('<3f', bs.read(vertex_count*12))]
            if vertex_type >= 1:
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
            raise Exception(f'pyRitoFile: Error: Read SCB {path}: Wrong file signature: {signature}')

    return SceneObject(
        signature,
        (major, minor), # version
        flags,
        name,
        central,
        pivot,
        bounding_box,
        material,
        vertex_type,
        indices,
        positions,
        uvs,
        colors
    )


def write(scene_object, path=None):
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        # header
        bs.write(pack('<8sHH', b'r3d2Mesh', 3, 2))
        # various
        face_count = len(scene_object.indices) // 3
        bs.write(pack(
            '<128s3I6fI',
            scene_object.name,
            face_count,
            len(scene_object.positions),
            scene_object.flags,
            0, 0, 0, 0, 0, 0, # bouding box later
            scene_object.vertex_type
        ))

        # positions 
        x_min, y_min, z_min = scene_object.positions[0]
        x_max, y_max, z_max = scene_object.positions[0]
        for x, y, z in scene_object.positions:
            if x > x_max: x_max = x
            if y > y_max: y_max = y
            if z > z_max: z_max = z
            if x < x_min: x_min = x
            if y < y_min: y_min = y
            if z < z_min: z_min = z
            bs.write(pack('<3f', x, y, z))
        # central
        bs.write(pack('<3f', *scene_object.central))
        # faces 
        indices = scene_object.indices
        material = scene_object.material.encode()
        uvs = scene_object.uvs
        for i in range(face_count):
            index = i * 3
            bs.write(pack(
                '3I64s6f',
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
        # bounding box
        bs.seek(152)
        bs.write(pack('<6f', x_min, y_min, z_min, x_max, y_max, z_max))

    return stream.getvalue() if path is None else None
