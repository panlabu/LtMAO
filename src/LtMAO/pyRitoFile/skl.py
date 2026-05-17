from dataclasses import dataclass
from struct import unpack, iter_unpack, pack
from io import BytesIO
from .helper import hash_elf, matrix_multiply, matrix_inverse, matrix_decompose

@dataclass(slots=True)
class Joint:
    name: str
    flags: int
    id: int
    parent: int
    hash: int
    radius: float
    translate: tuple[float, float, float]
    rotate: tuple[float, float, float, float]
    scale: tuple[float, float, float]
    inversed_bind_translate: tuple[float, float, float]
    inversed_bind_rotate: tuple[float, float, float, float]
    inversed_bind_scale: tuple[float, float, float]
    transform: tuple[float, ...]

class Skeleton:
    file_size: int
    signature: str
    version: int
    flags: int
    name: str
    asset: str
    joints: list[Joint]
    influences: list[int]

def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # init some data
        file_size = None                                       
        flags = None                                           
        name = None
        asset = None

        # read signature first to check legacy or not
        bs.seek(4)
        signature, = unpack('<I', bs.read(4))
        bs.seek(0)
        
        # starto
        if signature == 0x22FD4FC3:
            # new skl 
            # header
            file_size, signature, version = unpack('<3I', bs.read(12))
            if version != 0:
                raise Exception(f'pyRitoFile: Error: Read SKL {path}: Unsupported file version: {version}')
            # flags, counts and offsets
            flags, joint_count, influence_count, joints_offset, influences_offset, name_offset, asset_offset = unpack('<HHIi4xiii24x', bs.read(52))
            # read joints
            if joints_offset > 0 and joint_count > 0:
                bs.seek(joints_offset)
                joints = [
                    Joint(
                        unpacked_items[25], # this is joint name offset at the moment
                        unpacked_items[0],
                        unpacked_items[1],
                        unpacked_items[2],
                        unpacked_items[3],
                        unpacked_items[4],
                        unpacked_items[5:7],
                        unpacked_items[8:10],
                        unpacked_items[11:14],
                        unpacked_items[15:17],
                        unpacked_items[18:20],
                        unpacked_items[21:24],
                        None 
                    )
                    for unpacked_items in iter_unpack('<Hhh2xI21fi', bs.read(100*joint_count))
                ]
                # read joint name with joint name asset
                for joint_id, joint in enumerate(joints):
                    bs.seek(100*(joint_id+1)+60+joint.name)
                    joint.name = b''.join(iter(lambda: bs.read(1), b'\x00')).decode()

            # influences
            if influences_offset > 0 and influence_count > 0:
                bs.seek(influences_offset)
                influences = unpack(f'<{influence_count}h', influence_count*2)
            # name and asset 
            if name_offset > 0:
                bs.seek(name_offset)
                name = b''.join(iter(lambda: bs.read(1), b'\x00')).decode()
            if asset_offset > 0:
                bs.seek(asset_offset)
                asset = b''.join(iter(lambda: bs.read(1), b'\x00')).decode()
        else:
            # old skl 
            # header
            signature = bs.read(8).decode()
            if signature != 'r3d2sklt':
                raise Exception(f'pyRitoFile: Error: Read SKL {path}: Wrong file signature: {signature}')
            version, = unpack('<I', bs.read(4))
            if version not in (1, 2):
                raise Exception(f'pyRitoFile: Error: Read SKL {path}: Unsupported file version: {version}')
            # joints
            skeleton_id, joint_count = unpack('<II', bs.read(8))
            joints = [
                Joint(
                    unpacked_items[0].rstrip(b'\x00').decode(),
                    None,
                    joint_id,
                    unpacked_items[1],
                    None,
                    unpacked_items[2],
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    (
                        unpacked_items[3],
                        unpacked_items[7],
                        unpacked_items[11],
                        0.0,
                        unpacked_items[4],
                        unpacked_items[8],
                        unpacked_items[12],
                        0.0,
                        unpacked_items[5],
                        unpacked_items[9],
                        unpacked_items[13],
                        0.0,
                        unpacked_items[6],
                        unpacked_items[10],
                        unpacked_items[14],
                        1.0
                    )
                )
                for joint_id, unpacked_items in enumerate(iter_unpack('<32si13f', bs.read(88*joint_count)))
            ]
                
            # joint hash and transform decompose
            for joint_id, joint in enumerate(joints):
                joint.hash = hash_elf(joint.name)
                transform = joint.transform if joint.parent == - 1 else matrix_multiply(joint.transform, matrix_inverse(joints[joint.parent].transform))

                joint.translate, joint.rotate, joint.scale = matrix_decompose(transform)
                inversed_bind = matrix_inverse(joint.transform)
                joint.inversed_bind_translate, joint.inversed_bind_rotate, joint.inversed_bind_scale = matrix_decompose(inversed_bind)

            # influences
            if version == 1:
                influences = tuple(range(joint_count))
            if version == 2:
                influence_count, = unpack('<I', bs.read(4))
                influences = unpack(f'<{influence_count}I', bs.read(influence_count*4))

        return Skeleton(
            file_size, 
            signature,
            version,
            flags,
            name,
            asset,
            joints,
            influences
        )
        

def write(skeleton, path=None):
    stream = BytesIO() if path == None else open(path, 'wb')
    with stream as bs:
        # header
        bs.write(pack('<3I', 0, 0x22FD4FC3,0))

        # flags, counts and offsets
        joint_count = len(skeleton.joints)
        joints_offset = 64
        joint_indices_offset = joints_offset + joint_count * 100
        influences_offset = joint_indices_offset + joint_count * 8
        joint_names_offset = influences_offset + joint_count * 2
        bs.write(pack(
            '<HHI6i5I', 
            0, joint_count, joint_count,  # flags, joint and influence count
            joints_offset, joint_indices_offset, influences_offset, 0, 0, joint_names_offset, # offsets
            0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF # pad 20 bytes
        ))

        # write joint names
        joint_name_offsets = [None] * joint_count
        bs.seek(joint_names_offset)
        for joint_id, joint in enumerate(skeleton.joints):
            joint_name_offsets[joint_id] = bs.tell()
            bs.write(joint.name.encode() + b'\x00') # null terminated
        
        # write join
        bs.seek(joints_offset)
        for joint_id, joint in enumerate(skeleton.joints):
            bs.write(pack(
                '<HhhhI21fi', 
                0, # flags
                joint_id, 
                joint.parent, 
                0, # pad
                joint.hash,
                joint.radius,
                *joint.translate,
                *joint.rotate,
                *joint.scale
                *joint.inversed_bind_translate,
                *joint.inversed_bind_rotate,
                *joint.inversed_bind_scale,
                joint_name_offsets[joint_id] - bs.tell()
            ))

        # influences
        bs.seek(influences_offset)
        bs.write(pack(f'<{joint_count}H', *range(joint_count)))

        # joint indices
        bs.seek(joint_indices_offset)
        bs.write(b''.join(
            pack('<HHI', joint_id, 0, joint.hash)
            for joint_id, joint in enumerate(skeleton.joints)
        ))

        # file size
        file_size = bs.tell()
        bs.seek(0)
        bs.write(pack('<I', file_size))

    return stream.getvalue() if path == None else None
