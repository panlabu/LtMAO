from io import BytesIO
from struct import unpack, pack

btype_names = {
    # basic
    0: 'none',
    1: 'bool',
    2: 'i8',
    3: 'u8',
    4: 'i16',
    5: 'u16',
    6: 'i32',
    7: 'u32',
    8: 'i64',
    9: 'u64',
    10: 'f32',
    11: 'vec2',
    12: 'vec3',
    13: 'vec4',
    14: 'mtx44',
    15: 'rgba',
    16: 'string',
    17: 'hash',
    18: 'file',
    # complex
    128: 'list',
    129: 'list2',
    130: 'pointer',
    131: 'embed',
    132: 'link',
    133: 'option',
    134: 'map',
    135: 'flag'
}

    

def is_hex(s):
    if len(s) != 8: return False
    try: 
        int(s, 16)
        return True
    except:
        return False

def unhash(bin, hashtable):
    hashed_types = {17, 18, 132}
    list_types = {128, 129}
    embed_types = {130, 131}
    option_type = 133
    map_type = 134
    get = hashtable.get

    def unhash_data(data_type, data):
        if data_type in hashed_types:
            return get(data, f'{data:08x}')
        if data_type in list_types:
            value_type, values = data
            return (value_type, [unhash_data(value_type, value) for value in values])
        if data_type in embed_types:
            (class_hash, _class_hash), fields = data
            return ((class_hash, get(class_hash, f'{class_hash:08x}')), [] if class_hash == 0 else [unhash_field(field) for field in fields])
        if data_type == option_type:
            value_type, value = data
            return (value_type, None if value is None else unhash_data(value_type, value))
        if data_type == map_type:
            key_type, value_type, pairs = data
            return (
                key_type, 
                value_type, 
                {unhash_data(key_type, key): unhash_data(value_type, value) for key, value in pairs.items()}
            )
        return data

    def unhash_field(field):
        field._hash = get(field.hash, f'{field.hash:08x}')
        field.data = unhash_data(field.data_type, field.data)
        return field

    for entry in bin.entries:
        entry._hash = get(entry.hash, f'{entry.hash:08x}')
        entry._class_hash = get(entry.class_hash, f'{entry.class_hash:08x}')
        entry.data = [unhash_field(field) for field in entry.fields]
    if bin.is_patch:
        for patch in bin.patches:
            patch._hash = get(patch.hash, f'{patch.hash:08x}')
            patch.data = unhash_data(patch.data_type, patch.data)


class Field:
    __slots__ = ('hash', '_hash', 'data_type', 'data')
    def __init__(self, hash, _hash, data_type, data):
        self.hash = hash
        self._hash = _hash
        self.data_type = data_type
        self.data = data


class Entry:
    __slots__ = ('hash', '_hash', 'class_hash', '_class_hash', 'fields')
    def __init__(self, hash, _hash, class_hash, _class_hash, fields):
        self.hash = hash
        self._hash = _hash
        self.class_hash = class_hash
        self._class_hash = _class_hash
        self.fields = fields


class Patch:
    __slots__ = ('hash', '_hash', 'path', 'data_type', 'data')
    def __init__(self, hash, _hash, path, data_type, data):
        self.hash = hash
        self._hash = _hash
        self.path = path
        self.data_type = data_type
        self.data = data


class Bin:
    __slots__ = ('signature', 'version', 'is_patch', 'links', 'entries', 'patches')
    def __init__(self, signature, version, is_patch, links, entries, patches):
        self.signature = signature
        self.version = version
        self.is_patch = is_patch
        self.links = links
        self.entries = entries
        self.patches = patches


def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # init stuff to read
        is_patch = False
        links = []
        patches = []
        legacy = False
        # some func
        def fix_type(btype): return btype+1 if legacy and btype > 128 else btype
        # basic
        def read_none(): return None
        def read_bool(): return bs.read(1)[0] != 0
        def read_i8(): return b - 256 if (b:=bs.read(1)[0]) >= 128 else b
        def read_u8(): return bs.read(1)[0]
        def read_i16(): return int.from_bytes(bs.read(2), 'little', signed=True)
        def read_u16(): return int.from_bytes(bs.read(2), 'little')
        def read_i32(): return int.from_bytes(bs.read(4), 'little', signed=True)
        def read_u32(): return int.from_bytes(bs.read(4), 'little')
        def read_i64(): return int.from_bytes(bs.read(8), 'little', signed=True)
        def read_u64(): return int.from_bytes(bs.read(8), 'little')
        def read_f32(): return unpack('<f', bs.read(4))[0]
        def read_vec2(): return unpack('<2f', bs.read(8))
        def read_vec3(): return unpack('<3f', bs.read(12))
        def read_vec4(): return unpack('<4f', bs.read(16))
        def read_mtx44(): return unpack('<16f', bs.read(64))                          
        def read_rgba(): return unpack('<4B', bs.read(4))
        def read_string(): return bs.read(int.from_bytes(bs.read(2), 'little')).decode()
        def read_hash(): return int.from_bytes(bs.read(4), 'little')
        def read_file(): return int.from_bytes(bs.read(8), 'little')
        # complex
        def read_list_list2():
            value_type, value_count = unpack('<B4xI', bs.read(9))
            return (
                vt:=fix_type(value_type), 
                [read_data[vt]() for _ in range(value_count)
            ]
        )
        def read_pointer_embed():
            class_hash = int.from_bytes(bs.read(4), 'little')
            if class_hash == 0:
                return ((class_hash, None), [])
            else:
                field_count, = unpack('<4xH', bs.read(6))
                return (
                    (class_hash, None), 
                    [read_field() for _ in range(field_count)]
                )
        def read_link(): return int.from_bytes(bs.read(4), 'little')
        def read_option():
            value_type, value_count = unpack('<2B', bs.read(2))
            return (
                vt:=fix_type(value_type), 
                None if value_count == 0 else read_data[vt]()
            )
        def read_map():
            key_type, value_type, pair_count = unpack('<2B4xI', bs.read(10))
            return (
                kt:=fix_type(key_type), 
                vt:=fix_type(value_type), 
                {read_data[kt](): read_data[vt]() for _ in range(pair_count)}
            )
        def read_flag(): return bs.read(1)[0]
        # map read
        read_data = {
            0: read_none,
            1: read_bool,
            2: read_i8,
            3: read_u8,
            4: read_i16,
            5: read_u16,
            6: read_i32,
            7: read_u32,
            8: read_i64,
            9: read_u64,
            10: read_f32,
            11: read_vec2,
            12: read_vec3,
            13: read_vec4,
            14: read_mtx44,
            15: read_rgba,
            16: read_string,
            17: read_hash,
            18: read_file,
            128: read_list_list2,
            129: read_list_list2,
            130: read_pointer_embed,
            131: read_pointer_embed,
            132: read_link,
            133: read_option,
            134: read_map,
            135: read_flag
        }
        # field
        def read_field():
            hash, data_type = unpack('<IB', bs.read(5))
            return Field(
                hash, None, 
                dt:=fix_type(data_type), 
                read_data[dt]()
            )
        # header
        signature = bs.read(4)
        if signature not in {b'PROP', b'PTCH'}:
            raise Exception(f'pyRitoFile: Error: Read BIN {path}: Wrong file signature: {signature}')
        if signature == b'PTCH':
            is_patch = True
            bs.seek(8, 1)  # patch header
            if bs.read(4) != b'PROP':
                raise Exception(f'pyRitoFile: Error: Read BIN {path}: Missing PROP after PTCH signature.')
        version, = unpack('<I', bs.read(4))
        if version not in {1, 2, 3}:
            raise Exception(f'pyRitoFile: Error: Read BIN {path}: Unsupported file version: {version}')
        # links
        if version >= 2:
            link_count = int.from_bytes(bs.read(4), 'little')
            links = [
                bs.read(int.from_bytes(bs.read(2), 'little')).decode()
                for i in range(link_count) 
            ]
        # entries
        entry_count = int.from_bytes(bs.read(4), 'little')
        class_hashes = unpack(f'<{entry_count}I', bs.read(entry_count*4))
        entry_offset = bs.tell()
        try:
            # try read as new bin
            entries = [
                Entry(
                    hash, None, 
                    class_hashes[entry_id], None,
                    [read_field() for i in range(field_count)]
                )
                for entry_id in range(entry_count)
                for hash, field_count in [unpack('<4xIH', bs.read(10))]
            ]
        except ValueError:
            # legacy bin, fall back
            bs.seek(entry_offset)
            legacy = True
            entries = [
                Entry(
                    hash, None, 
                    class_hashes[entry_id], None,
                    [read_field() for i in range(field_count)]
                )
                for entry_id in range(entry_count)
                for hash, field_count in [unpack('<4xIH', bs.read(10))]
            ]
        except Exception as e:
            raise e
        # patches
        if is_patch and version >= 3:
            patch_count = int.from_bytes(bs.read(4), 'little')
            patches = [
                Patch(
                    hash, None, 
                    bs.read(int.from_bytes(bs.read(2), 'little')).decode(), 
                    dt:=fix_type(data_type),
                    read_data[dt]()
                )
                for i in range(patch_count)
                for hash, data_type in [unpack('<I4xB', bs.read(9))]
            ]

    return Bin(
        signature, 
        version,
        is_patch,
        links,
        entries,
        patches
    )
    
def write(bin, path=None):
    stream = BytesIO() if path is None else open(path, 'wb') 
    with stream as bs:
        # init
        # basic
        def write_none(data): return b''
        def write_bool(data): return pack('<?', data)
        def write_i8(data): return pack('<b', data)
        def write_u8(data): return pack('<B', data)
        def write_i16(data): return pack('<h', data)
        def write_u16(data): return pack('<H', data)
        def write_i32(data): return pack('<i', data)
        def write_u32(data): return pack('<I', data)
        def write_i64(data): return pack('<q', data)
        def write_u64(data): return pack('<Q', data)
        def write_f32(data): return pack('<f', data)
        def write_vec2(data): return pack('<2f', *data)
        def write_vec3(data): return pack('<3f', *data)
        def write_vec4(data): return pack('<4f', *data)
        def write_mtx44(data): return pack('<16f', *data)
        def write_rgba(data): return pack('<4B', *data)
        def write_string(data): return pack('<H', len(b:=data.encode())) + b
        def write_hash(data): return pack('<I', data)
        def write_file(data): return pack('<Q', data)
        # complex
        def write_list_list2(data): 
            value_type, values = data
            buffer = b''.join([
                write_data[value_type](value) 
                for value in values
            ])
            return pack(
                '<B2I',
                value_type,
                9+len(buffer),
                len(values)
            ) + buffer
        def write_pointer_embed(data): 
            (class_hash, _class_hashh), fields = data
            if class_hash == 0:
                return pack('<I', class_hash)
            else:
                buffer = b''.join([
                    write_field(field)
                    for field in fields
                ])
                return pack(
                    '<2IH',
                    class_hash,
                    10+len(buffer),
                    len(fields)
                ) + buffer
        def write_link(data): return pack('<I', data)
        def write_option(data): 
            value_type, value = data
            return pack(
                '<2B',
                value_type,
                0 if value is None else 1
            ) + (b'' if value is None else write_data[value_type](value))
        def write_map(data): 
            key_type, value_type, pairs = data
            buffer = b''.join([
                write_data[key_type](key) + write_data[value_type](value)
                for key, value in pairs.items()
            ])
            return pack(
                '<2B2I',
                key_type,
                value_type,
                10+len(buffer),
                len(pairs)
            ) + buffer
        def write_flag(data): return pack('B', data)
        # map write 
        write_data = {
            0: write_none,
            1: write_bool,
            2: write_i8,
            3: write_u8,
            4: write_i16,
            5: write_u16,
            6: write_i32,
            7: write_u32,
            8: write_i64,
            9: write_u64,
            10: write_f32,
            11: write_vec2,
            12: write_vec3,
            13: write_vec4,
            14: write_mtx44,
            15: write_rgba,
            16: write_string,
            17: write_hash,
            18: write_file,
            128: write_list_list2,
            129: write_list_list2,
            130: write_pointer_embed,
            131: write_pointer_embed,
            132: write_link,
            133: write_option,
            134: write_map,
            135: write_flag
        }
        # field
        def write_field(field):
            return pack(
                '<IB', 
                field.hash, 
                field.data_type
            ) + write_data[field.data_type](field.data)
        # header
        if bin.is_patch:
            bs.write(pack('<4s2I', b'PTCH', 1, 0))
        bs.write(pack('<4sI', b'PROP', 3))
        # links
        bs.write(pack('<I', len(bin.links)))
        for link in bin.links:
            bs.write(pack('<H', len(b:=link.encode())) + b)
        # entries
        entry_count = len(bin.entries)
        bs.write(pack(
            f'<{entry_count+1}I', 
            entry_count, 
            *[entry.class_hash for entry in bin.entries]
        ))
        for entry in bin.entries:
            buffer = b''.join([
                write_field(field) 
                for field in entry.fields
            ])
            bs.write(pack(
                '<2IH', 
                6+len(buffer),
                entry.hash, 
                len(entry.fields)
            ) + buffer)

        # patches
        if bin.is_patch:
            bs.write(pack('<I', len(bin.patches)))
            for patch in bin.patches:
                path_buffer = path.encode()
                buffer = write_data[patch.data_type](patch.data)
                bs.write(pack(
                    '<2IBH',
                    patch.hash,
                    3+(lp:=len(path_buffer))+len(buffer),
                    patch.data_type,
                    lp
                ) + path_buffer + buffer)
        return stream.getvalue() if path is None else None

