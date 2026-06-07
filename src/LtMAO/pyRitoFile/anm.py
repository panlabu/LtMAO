from struct import unpack, iter_unpack, pack
from io import BytesIO
from .maths import hash_elf, vector3_lerp, quaternion_decompress, quaternion_compress, quaternion_slerp


class Track:
    __slots__ = ('translate_curve', 'rotate_curve', 'scale_curve')
    
    def __init__(self, translate_curve, rotate_curve, scale_curve):
        self.translate_curve = translate_curve
        self.rotate_curve = rotate_curve
        self.scale_curve = scale_curve

class Animation:
    __slots__ = (
        'signature', 'file_size', 'version', 'format_token', 
        'flags1', 'flags2', 'keyframe_count', 'fps', 
        'error_metrics', 'tracks'
    )
    
    def __init__(self, signature, file_size, version, format_token, flags1, flags2, keyframe_count, fps, error_metrics, tracks):
        self.signature = signature
        self.file_size = file_size
        self.version = version
        self.format_token = format_token
        self.flags1 = flags1
        self.flags2 = flags2
        self.keyframe_count = keyframe_count
        self.fps = fps
        self.error_metrics = error_metrics
        self.tracks = tracks


def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # header
        signature = bs.read(8)
        version = int.from_bytes(bs.read(4), 'little')

        if signature == b'r3d2canm':
            # compressed
            # header
            file_size, format_token, flags1, track_count, compressed_buffer_count, keytime_max, fps = unpack('<5I4x2f', bs.read(32))
            # error metrics and translate, scale min max
            fd = unpack('<18f', bs.read(72))
            error_metrics = (
                (fd[0], fd[1]),
                (fd[2], fd[3]),
                (fd[4], fd[5])
            )
            tx_min, ty_min, tz_min, tx_max, ty_max, tz_max, sx_min, sy_min, sz_min, sx_max, sy_max, sz_max = fd[6:18]
            # offsets
            compressed_buffers_offset, joint_hashes_offset = unpack('<i4xi', bs.read(12))
            # joint hashes and init tracks
            bs.seek(joint_hashes_offset + 12)
            joint_hashes = unpack(f'<{track_count}I', bs.read(track_count*4))
            tracks = { 
                joint_hash: Track({}, {}, {}) 
                for joint_hash in joint_hashes
            }
            # some calculation 
            keyframe_count = keytime_max * fps + 1
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
            bs.seek(compressed_buffers_offset + 12)
            for compressed_time, compressed_bits, compressed_transform in iter_unpack('<HH6s', bs.read(compressed_buffer_count*10)):
                # decompress keytime and convert to keyframe
                keyframe = compressed_time * keytime_factor
                # extract joint hash and transform type
                joint_hash = joint_hashes[compressed_bits & 16383]
                transform_type = compressed_bits >> 14
                track = tracks[joint_hash]
                if transform_type == 0:
                    track.rotate_curve[keyframe] = quaternion_decompress(compressed_transform)
                # decompress vectors
                elif transform_type == 1:
                    cx, cy, cz = unpack('<HHH', compressed_transform)
                    track.translate_curve[keyframe] = (
                        cx * tx_factor + tx_min,
                        cy * ty_factor + ty_min,
                        cz * tz_factor + tz_min
                    )
                elif transform_type == 2:
                    cx, cy, cz = unpack('<HHH', compressed_transform)
                    track.scale_curve[keyframe] = (
                        cx * sx_factor + sx_min,
                        cy * sy_factor + sy_min,
                        cz * sz_factor + sz_min
                    )
                else:
                    raise Exception(f'pyRitoFile: Error: Read ANM: Unknown transform_type: {transform_type}.')
        elif signature == b'r3d2anmd':
            if version == 5:
                # uncompressed v5
                # header 
                file_size, format_token, flags1, flags2, track_count, keyframe_count, frame_time = unpack('<6If', bs.read(28))
                fps = 1 / frame_time
                # offsets 
                joint_hashes_offset, vecs_offset, quats_offset, buffers_offset = unpack('<i8x3i', bs.read(24))
                vec_count = (quats_offset - vecs_offset) // 12
                quat_count = (joint_hashes_offset - quats_offset) // 6
                # joint hashes and init tracks
                bs.seek(joint_hashes_offset + 12)
                joint_hashes = unpack(f'<{track_count}I', bs.read(track_count*4))                
                tracks = {
                    joint_hash: Track({}, {}, {})
                    for joint_hash in joint_hashes
                }
                # vecs
                bs.seek(vecs_offset + 12)
                vec_bank = [*iter_unpack('<3f', bs.read(vec_count*12))]
                # quats
                bs.seek(quats_offset + 12)
                quat_bank = [
                    quaternion_decompress(quat_bytes)
                    for quat_bytes, in iter_unpack('<6s', bs.read(quat_count*6))
                ]
                # buffers 
                # = keyframe * [track_count * [(tid, sid, rid),...]]
                bs.seek(buffers_offset + 12)
                for buffer_index, (tid, sid, rid) in enumerate(iter_unpack('<3H', bs.read(keyframe_count*track_count*6))):
                    # 1d array index to 2d array using integer divide and module on column count
                    keyframe = buffer_index // track_count
                    track = tracks[joint_hashes[buffer_index % track_count]]
                    track.translate_curve[keyframe] = vec_bank[tid]
                    track.scale_curve[keyframe] = vec_bank[sid]
                    track.rotate_curve[keyframe] = quat_bank[rid]
            elif version == 4:
                # v4
                # headers
                file_size, format_token, flags1, flags2, track_count, keyframe_count, frame_time = unpack('<6If', bs.read(28))
                fps = 1 / frame_time
                # offsets
                vecs_offset, quats_offset, buffers_offset = unpack('<12x3i', bs.read(24))
                vec_count = (quats_offset - vecs_offset) // 12
                quat_count = (buffers_offset - quats_offset) // 16
                # vecs
                bs.seek(vecs_offset + 12)
                vec_bank = [*iter_unpack('<3f', bs.read(vec_count*12))]
                # quats
                bs.seek(quats_offset + 12)
                quat_bank = [*iter_unpack('<4f', bs.read(quat_count*16))]
                # buffers
                # = keyframe * [track_count * [(joint_hash, tid, sid, rid),...]] 
                tracks = {}
                bs.seek(buffers_offset + 12)
                for buffer_index, (joint_hash, tid, sid, rid) in enumerate(iter_unpack('<I3i2x', bs.read(keyframe_count*track_count*18))):
                    keyframe = buffer_index // track_count
                    if joint_hash not in tracks:
                        tracks[joint_hash] = Track({}, {}, {})
                    track = tracks[joint_hash]
                    track.translate_curve[keyframe] = vec_bank[tid]
                    track.scale_curve[keyframe] = vec_bank[sid]
                    track.rotate_curve[keyframe] = quat_bank[rid]
            elif version == 3:
                # legacy
                # header
                track_count, keyframe_count, fps = unpack('<4x3I', bs.read(16))
                # buffers
                # = [joint_name, keyframe * [(rotate, translate),...]]
                tracks = {}
                for joint_name, *unpacked_floats in iter_unpack(f'<32s4x{keyframe_count*7}f', bs.read((36+keyframe_count*28)*track_count)):
                    tracks[hash_elf(joint_name.rstrip(b'\x00').decode())] = track = Track({}, {}, {})
                    for i in range(0, len(unpacked_floats), 7):
                        # each 7 floats is translate and rotate at one keyframe
                        keyframe = i // 7
                        track.rotate_curve[keyframe] = unpacked_floats[i:i+4]
                        track.translate_curve[keyframe] = unpacked_floats[i+4:i+7]
                        track.scale_curve[keyframe] = (1.0, 1.0, 1.0)
            else:
                raise Exception(f'pyRitoFile: Error: Read ANM: Unsupported file version: {version}')
        else:
            raise Exception(f'pyRitoFile: Error: Read ANM: Wrong signature file: {signature}') 
            
    return Animation(
        signature,
        file_size,
        version,
        format_token,
        flags1,
        flags2,
        keyframe_count,
        fps,
        error_metrics,
        tracks
    )


def write(animation, path=None):
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        # generate transform at all integer frames using interpolation then build vec bank, quat bank and buffers
        vec_bank = {}
        vec_id = 0
        quat_bank = {}
        quat_id = 0
        keyframe_count = round(animation.keyframe_count)
        track_count = len(animation.tracks)
        buffers = track_count * keyframe_count * [None]
        for track_id, (join_hash, track) in enumerate(animation.tracks.items()):
            t_keyframes = sorted(track.translate_curve.keys())
            r_keyframes = sorted(track.rotate_curve.keys())
            s_keyframes = sorted(track.scale_curve.keys())
            t_keyframe_count = len(t_keyframes)
            r_keyframe_count = len(r_keyframes)
            s_keyframe_count = len(s_keyframes)
            t_near = r_near = s_near = 0
            for keyframe in range(keyframe_count):
                # translate
                while t_near < t_keyframe_count and keyframe > t_keyframes[t_near]:
                    t_near += 1
                if t_near == 0:
                    translate = track.translate_curve[t_keyframes[0]]
                elif t_near < t_keyframe_count:
                    left, right = t_keyframes[t_near-1], t_keyframes[t_near]
                    translate = vector3_lerp(
                        track.translate_curve[left],
                        track.translate_curve[right],
                        (keyframe - left) / (right - left)
                    )
                else:
                    translate = track.translate_curve[t_keyframes[-1]]
                tid = vec_bank.setdefault(translate, vec_id)
                if tid == vec_id:
                    vec_id += 1
                # scale
                while s_near < s_keyframe_count and keyframe > s_keyframes[s_near]:
                    s_near += 1
                if s_near == 0:
                    scale = track.scale_curve[s_keyframes[0]]
                elif s_near < s_keyframe_count:
                    left, right = s_keyframes[s_near-1], s_keyframes[s_near]
                    scale = vector3_lerp(
                        track.scale_curve[left],
                        track.scale_curve[right],
                        (keyframe - left) / (right - left)
                    )
                else:
                    scale = track.scale_curve[s_keyframes[-1]]
                sid = vec_bank.setdefault(scale, vec_id)
                if sid == vec_id:
                    vec_id += 1
                # rorate
                while r_near < r_keyframe_count and keyframe > r_keyframes[r_near]:
                    r_near += 1
                if r_near == 0:
                    rotate = track.rotate_curve[r_keyframes[0]]
                elif r_near < r_keyframe_count:
                    left, right = r_keyframes[r_near-1], r_keyframes[r_near]
                    rotate = quaternion_slerp(
                        track.rotate_curve[left],
                        track.rotate_curve[right],
                        (keyframe - left) / (right - left)
                    )
                else:
                    rotate = track.rotate_curve[r_keyframes[-1]]
                rid = quat_bank.setdefault(rotate, quat_id)
                if rid == quat_id:
                    quat_id += 1

                # build buffers 
                buffers[keyframe * track_count + track_id] = pack('<3H', tid, sid, rid)

        vec_count = len(vec_bank)
        if vec_count > 65535:
            raise Exception(f'pyRitoFile: Error: Write ANM: Animation size is too big, vector bank size: {vec_count} exceed 65535.')
        quat_count = len(quat_bank)
        if quat_count > 65535:
            raise Exception(f'pyRitoFile: Error: Write ANM: Animation size is too big, quaternion bank size: {quat_count} exceed 65535.')
        # header and offsets
        bs.write(
            pack(
                '<8s7If9i', 
                b'r3d2anmd', 
                5, # version
                0, 0, 0, 0, # file_size, format_token, flags1, flags2
                track_count,
                keyframe_count,
                1 / animation.fps, # frame_time
                0, 0, 0, 0, 0, 0, # offsets
                0, 0, 0, # pad 12 bytes
            )
        )
        # write order: vecs -> quats -> joint_hashes -> buffers
        # vecs
        vecs_offset = bs.tell()
        for vec in vec_bank:
            bs.write(pack('<3f', *vec))
        # quats
        quats_offset = bs.tell()
        for quat in quat_bank:
            bs.write(pack('<6s', quaternion_decompress(quat)))
        # joint hashes
        joint_hashes_offset = bs.tell()
        bs.write(pack(f'<{track_count}I', *track))
        # buffers   
        buffers_offset = bs.tell()
        for buffer in buffers:
            bs.write(buffer)
        # offsets
        bs.seek(40)
        bs.write(pack(
            '<6i',
            joint_hashes_offset-12,
            0,
            0,
            vecs_offset-12,
            quats_offset-12,
            buffers_offset-12,
        ))
        # file size
        file_size = bs.tell()
        bs.seek(12) 
        bs.write(pack('<I', file_size))
        return stream.getvalue() if path is None else None
