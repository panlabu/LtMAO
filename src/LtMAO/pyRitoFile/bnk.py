from io import BytesIO
from struct import unpack, iter_unpack, pack

object_type_names = {
    1: 'Settings',
    2: 'Sound',
    3: 'Action',
    4: 'Event',
    5: 'Random/Sequence Container',
    6: 'Switch Container',
    7: 'Actor-Mixer',
    8: 'Audio Bus',
    9: 'Blend Container',
    10: 'Music Segment',
    11: 'Music Track',
    12: 'Music Switch Container',
    13: 'Music Playlist Container',
    14: 'Attenuation',
    15: 'Dialogue Event',
    16: 'Motion Bus',
    17: 'Motion FX',
    18: 'Effect',
    19: 'Auxiliary Bus',
    20: 'Bus',
    21: 'Modulator',
    22: 'Acoustic Texture'
}

class Object:
    # hirc
    __slots__ = ('id', 'type', 'size', 'data')
    def __init__(self, id, type, size, data):
        self.id = id
        self.type = type
        self.size = size
        self.data = data

class Wem:
    # didx
    __slots__ = ('hash', 'offset', 'size')
    def __init__(self, hash, offset, size):
        self.hash = hash
        self.offset = offset
        self.size = size

class BankHeader:
    __slots__ = ('version', 'id')
    def __init__(self, version, id):
        self.version = version
        self.id = id

class DataIndex:
    __slots__ = ('wems',)
    def __init__(self, wems):
        self.wems = wems

class Data:
    __slots__ = ('start_offset',)
    def __init__(self, start_offset):
        self.start_offset = start_offset

class Hierarchy:
    __slots__ = ('objects',)
    def __init__(self, objects):
        self.objects = objects

class SoundBank:
    __slots__ = ('bkhd', 'didx', 'data', 'hirc')

    def __init__(self, bkhd, didx, data, hirc):
        self.bkhd = bkhd
        self.didx = didx
        self.data = data
        self.hirc = hirc

def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # init
        bkhd = None
        didx = None
        data = None
        hirc = None
        # skip func
        def skip_fx():
            bs.seek(1, 1)
            fx_count = bs.read(1)[0]
            if fx_count > 0:
                bs.seek(1 + fx_count * (7 if bkhd.version <= 145 else 6), 1)
            if bkhd.version > 136:
                bs.seek(1, 1)
                bs.seek(bs.read(1)[0] * 6, 1)
            if 89 < bkhd.version <= 145: 
                bs.seek(1, 1)
        def skip_init_params():
            bs.seek(bs.read(1)[0] * 5, 1)
            bs.seek(bs.read(1)[0] * 9, 1)
        def skip_pos_params():
            pos_bits = bs.read(1)[0]
            has_pos = pos_bits & 1
            has_3d = False
            has_automation = False
            if has_pos:
                if bkhd.version <= 89:
                    has_2d = bs.read(1)[0] != 0
                    has_3d = bs.read(1)[0] != 0
                    if has_2d: bs.seek(1, 1)
                else:
                    has_3d = pos_bits & 2
            if has_pos and has_3d:
                if bkhd.version <= 89:
                    has_automation = (bs.read(1)[0] & 3) != 1
                    bs.seek(8, 1)
                else:
                    has_automation = (pos_bits >> 5) & 3
                    bs.seek(1, 1)
            if has_automation:
                bs.seek(9 if bkhd.version <= 89 else 5, 1)
                bs.seek(16 * int.from_bytes(bs.read(4), 'little'), 1)
                bs.seek((16 if bkhd.version <= 89 else 20) * int.from_bytes(bs.read(4), 'little'), 1)
            elif bkhd.version <= 89:
                bs.seek(1, 1)
        def skip_aux():
            has_aux = (bs.read(1)[0] >> 3) & 1
            if has_aux: bs.seek(16, 1)
            if bkhd.version > 135: bs.seek(4, 1)
        def skip_state_groups():
            bs.seek(6, 1)
            bs.seek(3 * bs.read(1)[0], 1)
            for i in range(bs.read(1)[0]):
                bs.seek(5, 1)
                bs.seek(8 * bs.read(1)[0], 1)
        def skip_rtpc():
            for i in range(int.from_bytes(bs.read(2), 'little')):
                bs.seek(13 if bkhd.version <= 89 else 12, 1)
                bs.seek(12 * int.from_bytes(bs.read(2), 'little'), 1)
        def skip_base_params():
            skip_fx()
            bus_id, parent_id = unpack('<2I', bs.read(8))
            bs.seek(2 if bkhd.version <= 89 else 1, 1)
            skip_init_params()
            skip_pos_params()
            skip_aux()
            skip_state_groups()
            skip_rtpc()
            return bus_id, parent_id
        def skip_clip_automation():
            for i in range(int.from_bytes(bs.read(4), 'little')):
                bs.seek(8, 1)
                bs.seek(12 * int.from_bytes(bs.read(4), 'little'), 1)
        # read hirc object
        sound = 2
        action = 3
        event = 4
        ranseq_container = 5
        switch_container = 6
        mseglist_container = {10, 13}
        music_track = 11
        mswitch_container = 12
        def read_object():
            type, size, id = unpack('<B2I', bs.read(9))
            offset = bs.tell()-4 # 4 byte id
            obj = Object(id, type, size, None)
            if type == sound:
                bs.seek(4, 1)
                stream_type = int.from_bytes(bs.read(4), 'little') if bkhd.version == 88 else bs.read(1)[0]
                wem_hash, source_id = unpack('<2I', bs.read(8))
                bs.seek(7 if bkhd.version == 88 else 8, 1)
                object_id = int.from_bytes(bs.read(4), 'little')
                obj.data = (stream_type, wem_hash, source_id, object_id)
            elif type == action:
                switch_group_id, switch_id, object_id = None, None, None
                scope, action_type = unpack('<2B', bs.read(2))
                if action_type == 25:
                    bs.seek(5, 1)
                    skip_init_params()
                    switch_group_id, switch_id = unpack('<2I', bs.read(8))
                else:
                    object_id = int.from_bytes(bs.read(4), 'little')
                obj.data = (scope, action_type, switch_group_id, switch_id, object_id)

            elif type == event:
                action_count = int.from_bytes(bs.read(4), 'little') if bkhd.version == 58 else bs.read(1)[0]
                action_ids = unpack(f'<{action_count}I', bs.read(action_count*4))
                obj.data = action_ids

            elif type == ranseq_container:
                _, switch_container_id = skip_base_params()
                sound_count, = unpack('<24xI', bs.read(28))
                sound_ids = unpack(f'<{sound_count}I', bs.read(sound_count*4))
                obj.data = (switch_container_id, sound_ids)

            elif type == switch_container:
                _, parent_id = skip_base_params()
                group_type = bs.read(1)[0]
                if bkhd.version <= 89: bs.seek(3, 1)
                group_id, child_count = unpack('<I5xI', bs.read(13))
                child_ids = unpack(f'<{child_count}I', bs.read(child_count*4))
                obj.data = (group_type, group_id, child_ids)

            elif type in mseglist_container:
                bs.seek(1, 1)
                music_switch_id, sound_id = skip_base_params()
                music_track_count = int.from_bytes(bs.read(4), 'little')
                music_track_ids = unpack(f'<{music_track_count}I', bs.read(music_track_count*4))
                obj.data = (music_switch_id, sound_id, music_track_ids)

            elif type == music_track:
                has_switch_ids, switch_group_id, switch_ids = False, None, None
                bs.seek(1, 1)
                bs.seek(14 * int.from_bytes(bs.read(4), 'little'), 1)
                playlist_count = int.from_bytes(bs.read(4), 'little')
                playlist_buffer = bs.read(playlist_count*44)
                track_count = int.from_bytes(bs.read(4), 'little')
                wem_hashes = [0] * track_count
                for track_id, wem_hash in iter_unpack('<2I36x', playlist_buffer):
                    wem_hashes[track_id] = wem_hash
                bs.seek(4, 1)
                skip_clip_automation()
                _, parent_id = skip_base_params()
                if bs.read(1)[0] == 3:
                    has_switch_ids = True
                    switch_group_id, = unpack('<xI8x', bs.read(13))
                    switch_ids = unpack(f'<{track_count}I', bs.read(track_count*4))
                obj.data = (wem_hashes, parent_id, has_switch_ids, switch_group_id, switch_ids)

            elif type == mswitch_container:
                bs.seek(1, 1)
                _, parent_id = skip_base_params()
                child_count = int.from_bytes(bs.read(4), 'little')
                child_ids = unpack(f'<{child_count}I', bs.read(child_count*4))
                bs.seek(23, 1)
                bs.seek(24 * int.from_bytes(bs.read(4), 'little'), 1)
                rule_count = int.from_bytes(bs.read(4), 'little')
                for _ in range(rule_count):
                    bs.seek(4 * int.from_bytes(bs.read(4), 'little'), 1)
                    bs.seek(4 * int.from_bytes(bs.read(4), 'little'), 1)
                    bs.seek(45 if bkhd.version <= 132 else 47, 1)
                    if bs.read(1)[0] > 0: bs.seek(30, 1)
                param_count, = unpack('<xI', bs.read(5))
                param_group_ids = unpack(f'<{param_count}I', bs.read(param_count*4))
                param_group_types = unpack(f'<{param_count}B', bs.read(param_count))
                tree_size, = unpack('<Ix', bs.read(5))
                node_count = tree_size // 12
                nodes = [*iter_unpack('<3I', bs.read(node_count*12))]
                obj.data = (parent_id, child_ids, param_group_ids, param_group_types, nodes)

            unread = size - bs.tell() + offset
            if unread < 0:
                raise Exception(f'pyRitoFile: Error: Read BNK {path}: Wrong size with object type: {type}')
            if unread > 0: bs.seek(unread, 1)
            return obj

         
        # get file size
        bs.seek(0, 2)
        end = bs.tell()
        bs.seek(0)
        # main
        while bs.tell() < end:
            # sections
            signature, size = unpack('<4sI', bs.read(8))
            if signature == b'BKHD':
                bkhd = BankHeader(*unpack('<2I', bs.read(8)))
                bs.seek(size-8, 1)
            elif signature == b'DIDX':
                didx = DataIndex([
                    Wem(*ud)
                    for ud in iter_unpack('<3I', bs.read(size))
                ])
            elif signature == b'DATA':
                data = Data(bs.tell())
                bs.seek(size, 1)
            elif signature == b'HIRC':
                hirc = Hierarchy([
                    read_object()
                    for _ in range(int.from_bytes(bs.read(4), 'little'))
                ])
            else:
                # unknown
                bs.seek(size, 1)


        return SoundBank(
            bkhd,
            didx, 
            data,
            hirc
        )
    
def write(soundbank, wem_datas, path=None):
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        # bkhd
        bs.write(pack(
            '<4s3I24s', 
            b'BKHD', 
            32, 134, 0,
            # unknown 24 bytes
            b'>]p\x17\x00\x00\x00\x00\xfa\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        ))

        # didx
        wem_count = len(soundbank.didx.wems)
        bs.write(pack('<4sI', b'DIDX', wem_count*12))
        data_size = 0
        info_offsets = [0] * wem_count
        for i, wem in enumerate(soundbank.didx.wems):
            info_offsets[i] = bs.tell()+4
            wem_size = len(wem_datas[i])
            bs.write(pack('<3I', wem.hash, 0, wem_size))
            data_size += wem_size

        # data
        bs.write(pack('<4sI', b'DATA', data_size))
        start_offset = bs.tell()
        for i, wem_data in enumerate(wem_datas):
            data_offset = bs.tell()
            bs.write(wem_data)
            # go back write info
            bs.seek(info_offsets[i])
            bs.write(pack('<I', data_offset-start_offset))
            bs.seek(0, 2)

        return bs.getvalue() if path is None else None

