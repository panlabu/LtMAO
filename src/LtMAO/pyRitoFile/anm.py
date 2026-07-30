from struct import unpack, iter_unpack, pack
from io import BytesIO
from .maths import hash_elf, vector3_lerp, quaternion_decompress, quaternion_compress, quaternion_slerp

class Animation:
    __slots__ = (
        'signature', 'version', 'flags1', 'flags2', 'fps', 'keyframes', 'joint_hashes', 'translate_curves', 'rotate_curves', 'scale_curves'
    )
    
    def __init__(self, signature, version, flags1, flags2, fps, keyframes, joint_hashes, translate_curves, rotate_curves, scale_curves):
        self.signature = signature
        self.version = version
        self.flags1 = flags1
        self.flags2 = flags2
        self.fps = fps
        self.keyframes = keyframes
        self.joint_hashes = joint_hashes
        self.translate_curves = translate_curves
        self.rotate_curves = rotate_curves
        self.scale_curves = scale_curves


def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # init
        flags1 = None
        flags2 = None
        # header
        signature = bs.read(8)
        version = int.from_bytes(bs.read(4), 'little')

        if signature == b'r3d2canm':
            # compressed
            # header
            flags1, joint_hash_count, compressed_buffer_count, keytime_max, fps, tx_min, ty_min, tz_min, tx_max, ty_max, tz_max, sx_min, sy_min, sz_min, sx_max, sy_max, sz_max, compressed_buffers_offset, joint_hashes_offset = unpack('<8x3Ix2f24x12fi4xi', bs.read(116))
            # joint hashes
            bs.seek(joint_hashes_offset + 12)
            joint_hashes = unpack(f'<{joint_hash_count}I', bs.read(joint_hash_count*4))
            # curves 
            translate_curves = {}
            rotate_curves = {}
            scale_curves = {}
            for joint_hash in joint_hashes:
                translate_curves[joint_hash] = {}
                rotate_curves[joint_hash] = {}
                scale_curves[joint_hash] = {}
            # factors
            keytime_factor = keytime_max * fps / 65535.0
            tx_factor = (tx_max - tx_min) / 65535.0
            ty_factor = (ty_max - ty_min) / 65535.0
            tz_factor = (tz_max - tz_min) / 65535.0
            sx_factor = (sx_max - sx_min) / 65535.0
            sy_factor = (sy_max - sy_min) / 65535.0
            sz_factor = (sz_max - sz_min) / 65535.0
            # compressed buffers
            # each buffer contains:
            #    compressed keytime
            #    compressed bits that contains joint hash index and transform type
            #    compressed transform
            keyframes = set()
            bs.seek(compressed_buffers_offset + 12)
            compressed_buffers = []
            for compressed_time, compressed_bits, compressed_transform in iter_unpack('<2H6s', bs.read(compressed_buffer_count*10)):
                # decompress keytime and convert to keyframe
                keyframe = compressed_time * keytime_factor
                keyframes.add(keyframe)
                # extract joint hash and transform type
                joint_hash = joint_hashes[compressed_bits & 16383]
                transform_type = compressed_bits >> 14
                if transform_type == 0:
                    rotate_curves[joint_hash][keyframe] = quaternion_decompress(compressed_transform)
                    compressed_buffers.append((keyframe, joint_hash, transform_type, rotate_curves[joint_hash][keyframe]))
                # decompress vectors
                elif transform_type == 1:
                    cx, cy, cz = unpack('<3H', compressed_transform)
                    translate_curves[joint_hash][keyframe] = (
                        cx * tx_factor + tx_min,
                        cy * ty_factor + ty_min,
                        cz * tz_factor + tz_min
                    )
                    compressed_buffers.append((keyframe, joint_hash, transform_type, translate_curves[joint_hash][keyframe]))
                elif transform_type == 2:
                    cx, cy, cz = unpack('<3H', compressed_transform)
                    scale_curves[joint_hash][keyframe] = (
                        cx * sx_factor + sx_min,
                        cy * sy_factor + sy_min,
                        cz * sz_factor + sz_min
                    )
                    compressed_buffers.append((keyframe, joint_hash, transform_type, scale_curves[joint_hash][keyframe]))

                else:
                    raise Exception(f'pyRitoFile: Error: Read ANM: Unknown transform_type: {transform_type}.')
            # ensure order
            keyframes = sorted(keyframes)
            for joint_hash in joint_hashes:
                translate_curves[joint_hash] = { keyframe: value for keyframe, value in sorted(translate_curves[joint_hash].items()) }
                rotate_curves[joint_hash] = { keyframe: value for keyframe, value in sorted(rotate_curves[joint_hash].items()) }
                scale_curves[joint_hash] = { keyframe: value for keyframe, value in sorted(scale_curves[joint_hash].items()) }
        elif signature == b'r3d2anmd':
            if version == 5:
                # uncompressed v5
                # header 
                flags1, flags2, joint_hash_count, keyframe_count, frame_time, joint_hashes_offset, vecs_offset, quats_offset, buffers_offset = unpack('<8x4Ifi8x3i', bs.read(52))
                fps = 1 / frame_time
                keyframes = [*range(keyframe_count)]
                vec_size = quats_offset - vecs_offset
                quat_size = joint_hashes_offset - quats_offset
                # vecs
                bs.seek(vecs_offset + 12)
                vec_bank = [*iter_unpack('<3f', bs.read(vec_size))]
                # quats
                bs.seek(quats_offset + 12)
                quat_bank = [
                    quaternion_decompress(quat_bytes)
                    for quat_bytes, in iter_unpack('<6s', bs.read(quat_size))
                ]
                # joint hashes 
                bs.seek(joint_hashes_offset + 12)
                joint_hashes = unpack(f'<{joint_hash_count}I', bs.read(joint_hash_count*4))                
                # curves
                translate_curves = {}
                rotate_curves = {}
                scale_curves = {}
                for joint_hash in joint_hashes:
                    translate_curves[joint_hash] = {}
                    rotate_curves[joint_hash] = {}
                    scale_curves[joint_hash] = {}
                # buffers = keyframe * joint_hash * (tid, sid, rid)
                bs.seek(buffers_offset + 12)
                for buffer_index, (tid, sid, rid) in enumerate(iter_unpack('<3H', bs.read(keyframe_count*joint_hash_count*6))):
                    # 1d to 2d: divide and module on column count
                    keyframe = buffer_index // joint_hash_count
                    joint_hash = joint_hashes[buffer_index % joint_hash_count]
                    translate_curves[joint_hash][keyframe] = vec_bank[tid]
                    scale_curves[joint_hash][keyframe] = vec_bank[sid]
                    rotate_curves[joint_hash][keyframe] = quat_bank[rid]
            elif version == 4:
                # v4
                # headers
                flags1, flags2, joint_hash_count, keyframe_count, frame_time, vecs_offset, quats_offset, buffers_offset = unpack('<8x4If12x3i', bs.read(52))
                fps = 1 / frame_time
                keyframes = [*range(keyframe_count)]
                vec_size = quats_offset - vecs_offset
                quat_size = buffers_offset - quats_offset
                # vecs
                bs.seek(vecs_offset + 12)
                vec_bank = [*iter_unpack('<3f', bs.read(vec_size))]
                # quats
                bs.seek(quats_offset + 12)
                quat_bank = [*iter_unpack('<4f', bs.read(quat_size))]
                # buffers = keyframe * (joint_hash, tid, sid, rid) 
                bs.seek(buffers_offset + 12)
                joint_hashes = set()
                translate_curves = {}
                rotate_curves = {}
                scale_curves = {}
                for buffer_index, (joint_hash, tid, sid, rid) in enumerate(iter_unpack('<I3H2x', bs.read(keyframe_count*joint_hash_count*12))):
                    keyframe = buffer_index // joint_hash_count
                    if joint_hash not in joint_hashes:
                        joint_hashes.add(joint_hash)
                        translate_curves[joint_hash] = {}
                        rotate_curves[joint_hash] = {}
                        scale_curves[joint_hash] = {}
                    translate_curves[joint_hash][keyframe] = vec_bank[tid]
                    scale_curves[joint_hash][keyframe] = vec_bank[sid]
                    rotate_curves[joint_hash][keyframe] = quat_bank[rid]
                joint_hashes = tuple(joint_hashes)
            elif version == 3:
                # legacy
                # header
                joint_hash_count, keyframe_count, fps = unpack('<4x3I', bs.read(16))
                keyframes = [*range(keyframe_count)]
                joint_hashes = []
                translate_curves = {}
                rotate_curves = {}
                scale_curves = {}
                # buffers = joint_name, keyframe * (rotate, translate)
                for joint_name, *unpacked_floats in iter_unpack(f'<32s4x{keyframe_count*7}f', bs.read((36+keyframe_count*28)*joint_hash_count)):
                    # curves
                    joint_hash = hash_elf(joint_name.rstrip(b'\x00').decode())
                    joint_hashes.append(joint_hash)
                    translate_curves[joint_hash] = {}
                    rotate_curves[joint_hash] = {}
                    scale_curves[joint_hash] = {}
                    for i in range(0, len(unpacked_floats), 7):
                        # each 7 floats is translate and rotate at one keyframe
                        keyframe = i // 7
                        rotate_curves[joint_hash][keyframe] = unpacked_floats[i:i+4]
                        translate_curves[joint_hash][keyframe] = unpacked_floats[i+4:i+7]
                        scale_curves[joint_hash][keyframe] = (1.0, 1.0, 1.0)
            else:
                raise Exception(f'pyRitoFile: Error: Read ANM: Unsupported file version: {version}')
        else:
            raise Exception(f'pyRitoFile: Error: Read ANM: Wrong signature file: {signature}') 
            
    return Animation(
        signature,
        version,
        flags1,
        flags2,
        fps,
        keyframes, 
        joint_hashes,
        translate_curves,
        rotate_curves,
        scale_curves
    )


def write(animation, path=None):
    keyframes = animation.keyframes
    if not keyframes:
        raise Exception('pyRitoFile: Error: Write ANM: Zero keyframes.')
    keyframe_count = round(keyframes[-1]) + 1
    joint_hashes = animation.joint_hashes
    joint_hash_count = len(joint_hashes)
    translate_curves = animation.translate_curves
    rotate_curves = animation.rotate_curves
    scale_curves = animation.scale_curves
    # init
    # generate transform at all integer frames using interpolation then build vec bank, quat bank and buffers
    vec_bank = {}
    vec_id = 0
    quat_bank = {}
    quat_id = 0
    buffers = [None] * (joint_hash_count * keyframe_count)
    for joint_index, joint_hash in enumerate(joint_hashes):
        translate_curve = translate_curves[joint_hash]
        rotate_curve = rotate_curves[joint_hash]
        scale_curve = scale_curves[joint_hash]
        translate_keyframes = sorted(translate_curve)
        rotate_keyframes = sorted(rotate_curve)
        scale_keyframes = sorted(scale_curve)
        translate_keyframe_count = len(translate_keyframes)
        rotate_keyframe_count = len(rotate_keyframes)
        scale_keyframe_count = len(scale_keyframes)
        translate_near = rotate_near = scale_near = 0
        for keyframe in range(keyframe_count):
            # translate
            translate = translate_curve.get(keyframe)
            if translate is None:
                while translate_near < translate_keyframe_count and keyframe > translate_keyframes[translate_near]:
                    translate_near += 1
                if translate_near == 0:
                    translate = translate_curve[translate_keyframes[0]]
                elif translate_near < translate_keyframe_count:
                    left = translate_keyframes[translate_near-1]
                    right = translate_keyframes[translate_near]
                    translate = vector3_lerp(
                        translate_curve[left],
                        translate_curve[right],
                        (keyframe - left) / (right - left)
                    )
                else:
                    translate = translate_curve[translate_keyframes[-1]]
            tid = vec_bank.get(translate)
            if tid is None:
                vec_bank[translate] = tid = vec_id
                vec_id += 1
            # scale
            scale = scale_curve.get(keyframe)
            if scale is None:
                while scale_near < scale_keyframe_count and keyframe > scale_keyframes[scale_near]:
                    scale_near += 1
                if scale_near == 0:
                    scale = scale_curve[scale_keyframes[0]]
                elif scale_near < scale_keyframe_count:
                    left = scale_keyframes[scale_near-1] 
                    right = scale_keyframes[scale_near]
                    scale = vector3_lerp(
                        scale_curve[left],
                        scale_curve[right],
                        (keyframe - left) / (right - left)
                    )
                else:
                    scale = scale_curve[scale_keyframes[-1]]
            sid = vec_bank.get(scale)
            if sid is None:
                vec_bank[scale] = sid = vec_id
                vec_id += 1
            # rotate
            rotate = rotate_curve.get(keyframe)
            if rotate is None:
                while rotate_near < rotate_keyframe_count and keyframe > rotate_keyframes[rotate_near]:
                    rotate_near += 1
                if rotate_near == 0:
                    rotate = rotate_curve[rotate_keyframes[0]]
                elif rotate_near < rotate_keyframe_count:
                    left = rotate_keyframes[rotate_near-1]
                    right = rotate_keyframes[rotate_near]
                    rotate = quaternion_slerp(
                        rotate_curve[left],
                        rotate_curve[right],
                        (keyframe - left) / (right - left)
                    )
                else:
                    rotate = rotate_curve[rotate_keyframes[-1]]
            rid = quat_bank.get(rotate)
            if rid is None:
                quat_bank[rotate] = rid = quat_id
                quat_id += 1
            # build buffers 
            buffers[keyframe * joint_hash_count + joint_index] = pack('<3H', tid, sid, rid)
    # check limit
    vec_count = len(vec_bank)
    if vec_count > 65536:
        raise Exception(f'pyRitoFile: Error: Write ANM: Animation is too dense, vector bank size: {vec_count} exceed 65536.')
    quat_count = len(quat_bank)
    if quat_count > 65536:
        raise Exception(f'pyRitoFile: Error: Write ANM: Animation is too dense, quaternion bank size: {quat_count} exceed 65536.')
    # write
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        # pad 
        bs.write(pack('<64s', b''))
        # vecs
        vecs_offset = bs.tell()
        for vec in vec_bank:
            bs.write(pack('<3f', *vec))
        # quats
        quats_offset = bs.tell()
        for quat in quat_bank:
            bs.write(quaternion_compress(quat))
        # joint hashes
        joint_hashes_offset = bs.tell()
        bs.write(pack(f'<{joint_hash_count}I', *joint_hashes))
        # buffers   
        buffers_offset = bs.tell()
        for buffer in buffers:
            bs.write(buffer)
        # go back write header
        file_size = bs.tell()
        bs.write(pack(
            '<8s7If6i', 
            b'r3d2anmd', 5, # version
            file_size, 0, 0, 0, # format_token, flags1, flags2
            joint_hash_count, keyframe_count,
            1 / animation.fps, # frame_time
            joint_hashes_offset-12, 
            0, 
            0, 
            vecs_offset-12, 
            quats_offset-12, 
            buffers_offset-12,
        ))
        return stream.getvalue() if path is None else None

