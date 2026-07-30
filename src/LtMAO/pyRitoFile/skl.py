from struct import unpack, iter_unpack, pack
from io import BytesIO
from functools import partial
from .maths import hash_elf, matrix4_multiply, matrix4_inverse, matrix4_decompose

class Joint:
    __slots__ = (
        'name', 'flags', 'parent', 'hash', 'radius', 'translate', 
        'scale', 'rotate', 'inversed_bind_translate', 'inversed_bind_scale', 
        'inversed_bind_rotate', 'transform'
    )

    def __init__(self, name, flags, parent, hash, radius, translate, scale, rotate, inversed_bind_translate, inversed_bind_scale, inversed_bind_rotate, transform):
        self.name = name
        self.flags = flags
        self.parent = parent
        self.hash = hash
        self.radius = radius
        self.translate = translate
        self.scale = scale
        self.rotate = rotate
        self.inversed_bind_translate = inversed_bind_translate
        self.inversed_bind_scale = inversed_bind_scale
        self.inversed_bind_rotate = inversed_bind_rotate
        self.transform = transform

class Skeleton:
    __slots__ = ('signature', 'version', 'joints', 'influences')

    def __init__(self, signature, version, joints, influences):
        self.signature = signature
        self.version = version
        self.joints = joints
        self.influences = influences


def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # read signature first to check legacy or not
        bs.seek(4)
        signature = bs.read(4)
        bs.seek(0)
        
        # starto
        if signature == b'\xc3O\xfd"':
            # new skl 
            # header
            signature, version = unpack('<4x4sI', bs.read(12))
            if version != 0:
                raise Exception(f'pyRitoFile: Error: Read SKL: Unsupported file version: {version}')
            # counts and offsets
            joint_count, influence_count, joints_offset, influences_offset = unpack('<2xHIi4xi32x', bs.read(52))
            # read joints
            if joints_offset > 0 and joint_count > 0:
                bs.seek(joints_offset)
                joints = [
                    Joint(
                        ud[24], # this is joint name offset at the moment
                        ud[0],
                        ud[1],
                        ud[2],
                        ud[3],
                        (ud[4], ud[5], ud[6]),
                        (ud[7], ud[8], ud[9]),
                        (ud[10], ud[11], ud[12], ud[13]),
                        (ud[14], ud[15], ud[16]),
                        (ud[17], ud[18], ud[19]),
                        (ud[20], ud[21], ud[22], ud[23]),
                        None 
                    )
                    for ud in iter_unpack('<H2xh2xI21fi', bs.read(100*joint_count))
                ]
                # read joint name with joint name offset
                for joint_id, joint in enumerate(joints):
                    bs.seek(joints_offset + 100 * joint_id + 96 + joint.name)
                    joint.name = b''.join(iter(partial(bs.read, 1), b'\x00')).decode()

            # influences
            if influences_offset > 0 and influence_count > 0:
                bs.seek(influences_offset)
                influences = unpack(f'<{influence_count}H', bs.read(influence_count*2))
        else:
            # old skl 
            # header
            signature = bs.read(8)
            if signature != b'r3d2sklt':
                raise Exception(f'pyRitoFile: Error: Read SKL: Wrong file signature: {signature}')
            version = int.from_bytes(bs.read(4), 'little')
            if version not in {1, 2}:
                raise Exception(f'pyRitoFile: Error: Read SKL: Unsupported file version: {version}')
            # joints
            joint_count, = unpack('<4xI', bs.read(8))
            joints = [
                Joint(
                    n:=ud[0].rstrip(b'\x00').decode(),
                    None,
                    ud[1],
                    hash_elf(n),
                    ud[2],
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    (
                        ud[3], ud[7], ud[11], 0.0,
                        ud[4], ud[8], ud[12], 0.0,
                        ud[5], ud[9], ud[13], 0.0,
                        ud[6], ud[10], ud[14], 1.0
                    )
                )
                for ud in iter_unpack('<32si13f', bs.read(88*joint_count))
            ]
                
            # transform decompose
            for joint_id, joint in enumerate(joints):
                transform = joint.transform if joint.parent == - 1 else matrix4_multiply(joint.transform, matrix4_inverse(joints[joint.parent].transform))

                joint.translate, joint.scale, joint.rotate = matrix4_decompose(transform)
                inversed_bind = matrix4_inverse(joint.transform)
                joint.inversed_bind_translate, joint.inversed_bind_scale, joint.inversed_bind_rotate = matrix4_decompose(inversed_bind)

            # influences
            if version == 1:
                influences = [*range(joint_count)]
            if version == 2:
                influence_count = int.from_bytes(bs.read(4), 'little')
                influences = unpack(f'<{influence_count}I', bs.read(influence_count*4))

        return Skeleton(
            signature,
            version,
            joints,
            influences
        )
        

def write(skeleton, path=None):
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        # pad
        bs.write(pack('<64s', b''))

        # joint
        joints_offset = bs.tell()
        for joint_id, joint in enumerate(skeleton.joints):
            bs.write(pack(
                '<H3hI21fi', 
                0, # flags
                joint_id, 
                joint.parent, 
                0, # pad
                joint.hash,
                joint.radius,
                *joint.translate,
                *joint.scale,
                *joint.rotate,
                *joint.inversed_bind_translate,
                *joint.inversed_bind_scale,
                *joint.inversed_bind_rotate,
                0 # name offset write later
            ))

        # joint hashes
        joint_hashes_offset = bs.tell()
        for joint_id, joint in sorted(enumerate(skeleton.joints), key=lambda x: x[1].hash):
            bs.write(pack('<2HI', joint_id, 0, joint.hash))

        # influences
        influences_offset = bs.tell()
        influence_count = len(skeleton.influences)
        bs.write(pack(f'<{influence_count}H', *skeleton.influences))

        # joint names
        joint_names_offset = bs.tell()
        for joint_id, joint in enumerate(skeleton.joints):
            name_offset = bs.tell()
            field_offset = joints_offset + (joint_id * 100) + 96   
            bs.seek(field_offset)
            bs.write(pack('<i', name_offset-field_offset))
            bs.seek(name_offset)
            bs.write(joint.name.encode() + b'\x00') # null terminated

        # go back write header
        file_size = bs.tell()
        bs.seek(0)
        bs.write(pack(
            '<I4sI2HI6i',
            file_size, b'\xc3O\xfd"', 
            0, 0, # verison, flags
            len(skeleton.joints), influence_count,
            joints_offset, joint_hashes_offset, influences_offset,
            0, 0, joint_names_offset # name, asset offset
        ))

        return stream.getvalue() if path is None else None
