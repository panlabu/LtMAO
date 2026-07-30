from io import BytesIO
from struct import unpack, pack, error as StructError

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

# modern: exact as above
modern_types = [*range(256)]
# legacy: did not have list2, every complex after list is down by 1
legacy_types = [i+1 if i > 128 else i for i in modern_types] 
# ancient: did not have file, complex is start at 18
ancient_types = [(128 if i == 18 else i + 111) if i > 17 else i for i in modern_types]

def flatten(binary):
    # init
    flat_fields = []
    flat_extend = flat_fields.extend
    list_types = {128, 129}
    embed_types = {130, 131}
    option_type = 133
    map_type = 134
    target_types = list_types | embed_types | {option_type, map_type}
    def flat_data(data_type, data):
        if data_type in list_types:
            value_type, values = data
            for value in values:
                flat_data(value_type, value)
        if data_type in embed_types:
            (_, _), fields = data
            flat_extend(fields)
            for field in fields:
                flat_data(field.data_type, field.data)
        if data_type == option_type:
            value_type, value = data
            if value is not None:
                flat_data(value_type, value)
        if data_type == map_type:
            key_type, value_type, pairs = data
            for key, value in pairs.items():
                flat_data(key_type, key)
                flat_data(value_type, value)
    # main
    for entry in binary.entries:
        flat_extend(entry.fields)
        for field in entry.fields:
            if field.data_type in target_types:
                flat_data(field.data_type, field.data)
    if binary.is_patch:
        for patch in binary.patches:
            if patch.data_type in target_types:
                flat_data(patch.data_type, patch.data)
    return flat_fields

def unhash(binary, lookup):
    # init
    if binary.flat_fields is None:
        binary.flat_fields = flatten(binary)
    hashed_types = {17, 18, 132}
    list_types = {128, 129}
    embed_types = {130, 131}
    option_type = 133
    map_type = 134
    target_types = hashed_types | list_types | embed_types | {option_type, map_type}
    def unhash_data(data_type, data):
        if data_type in hashed_types:
            return lookup(data, f'{data:08x}')
        if data_type in list_types:
            value_type, values = data
            return (value_type, [unhash_data(value_type, value) for value in values])
        if data_type in embed_types:
            (class_hash, _), fields = data
            if class_hash != 0:
                return ((class_hash, lookup(class_hash, f'{class_hash:08x}')), fields)
        if data_type == option_type:
            value_type, value = data
            if value is not None:
                return (value_type, unhash_data(value_type, value))
        if data_type == map_type:
            key_type, value_type, pairs = data
            return (
                key_type, 
                value_type, 
                {unhash_data(key_type, key): unhash_data(value_type, value) for key, value in pairs.items()}
            )
        return data
    # main 
    for entry in binary.entries:
        entry._hash = lookup(entry.hash, f'{entry.hash:08x}')
        entry._class_hash = lookup(entry.class_hash, f'{entry.class_hash:08x}')
    for field in binary.flat_fields:
        field._hash = lookup(field.hash, f'{field.hash:08x}')
        if field.data_type in target_types:
            field.data = unhash_data(field.data_type, field.data)
    if binary.is_patch:
        for patch in binary.patches:
            patch._hash = lookup(patch.hash, f'{patch.hash:08x}')
            if patch.data_type in target_types:
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


class Binary:
    __slots__ = ('signature', 'version', 'is_patch', 'links', 'entries', 'patches', 'flat_fields')
    def __init__(self, signature, version, is_patch, links, entries, patches):
        self.signature = signature
        self.version = version
        self.is_patch = is_patch
        self.links = links
        self.entries = entries
        self.patches = patches
        self.flat_fields = None

# read funcs
def read_none(bs): return None
def read_bool(bs): return bs.read(1)[0] != 0
def read_i8(bs): return b - 256 if (b:=bs.read(1)[0]) >= 128 else b
def read_u8(bs): return bs.read(1)[0]
def read_i16(bs): return int.from_bytes(bs.read(2), 'little', signed=True)
def read_u16(bs): return int.from_bytes(bs.read(2), 'little')
def read_i32(bs): return int.from_bytes(bs.read(4), 'little', signed=True)
def read_u32(bs): return int.from_bytes(bs.read(4), 'little')
def read_i64(bs): return int.from_bytes(bs.read(8), 'little', signed=True)
def read_u64(bs): return int.from_bytes(bs.read(8), 'little')
def read_f32(bs): return unpack('<f', bs.read(4))[0]
def read_vec2(bs): return unpack('<2f', bs.read(8))
def read_vec3(bs): return unpack('<3f', bs.read(12))
def read_vec4(bs): return unpack('<4f', bs.read(16))
def read_mtx44(bs): return unpack('<16f', bs.read(64))                          
def read_rgba(bs): return unpack('<4B', bs.read(4))
def read_string(bs): return bs.read(int.from_bytes(bs.read(2), 'little')).decode()
def read_hash(bs): return int.from_bytes(bs.read(4), 'little')
def read_file(bs): return int.from_bytes(bs.read(8), 'little')
def read_list(bs):
    value_type, value_count = unpack('<B4xI', bs.read(9))
    vt = bs.btypes[value_type]
    read_data_vt = read_data[vt]
    return (
        vt, 
        [read_data_vt(bs) for _ in range(value_count)
    ]
)
def read_embed(bs):
    class_hash = int.from_bytes(bs.read(4), 'little')
    if class_hash == 0:
        return ((class_hash, None), [])
    else:
        field_count, = unpack('<4xH', bs.read(6))
        return (
            (class_hash, None), 
            [
                Field(
                    field_hash, None,
                    dt:=bs.btypes[data_type],
                    read_data[dt](bs)
                )
                for _ in range(field_count)
                for field_hash, data_type in [unpack('<IB', bs.read(5))]
            ]
        )
def read_link(bs): return int.from_bytes(bs.read(4), 'little')
def read_option(bs):
    value_type, value_count = unpack('<2B', bs.read(2))
    return (
        vt:=bs.btypes[value_type], 
        None if value_count == 0 else read_data[vt](bs)
    )
def read_map(bs):
    key_type, value_type, pair_count = unpack('<2B4xI', bs.read(10))
    kt = bs.btypes[key_type]
    vt = bs.btypes[value_type]
    read_data_kt = read_data[kt]
    read_data_vt = read_data[vt]
    return (
        kt, vt, 
        {read_data_kt(bs): read_data_vt(bs) for _ in range(pair_count)}
    )
def read_flag(bs): return bs.read(1)[0]
# list 
def read_error(bs): raise ValueError
read_data = [
    read_none,
    read_bool,
    read_i8,
    read_u8,
    read_i16,
    read_u16,
    read_i32,
    read_u32,
    read_i64,
    read_u64,
    read_f32,
    read_vec2,
    read_vec3,
    read_vec4,
    read_mtx44,
    read_rgba,
    read_string,
    read_hash,
    read_file,
    *[read_error]*109, # pad
    read_list,
    read_list,
    read_embed,
    read_embed,
    read_link,
    read_option,
    read_map,
    read_flag,
    *[read_error]*120 # pad
]

def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # init 
        is_patch = False
        links = []
        patches = []
        def read_entries():
            return [
                Entry(
                    entry_hash, None, 
                    class_hashes[entry_id], None,
                    [
                        Field(
                            field_hash, None,
                            dt:=bs.btypes[data_type],
                            read_data[dt](bs)
                        )
                        for _ in range(field_count)
                        for field_hash, data_type in [unpack('<IB', bs.read(5))]
                    ]
                )
                for entry_id in range(entry_count)
                for entry_hash, field_count in [unpack('<4xIH', bs.read(10))]
            ]
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
        FallbackError = (IndexError, TypeError, ValueError, StructError, MemoryError)
        try:
            bs.btypes = modern_types
            # read as modern bin
            entries = read_entries()
        except FallbackError:
            try:
                bs.seek(entry_offset)
                bs.btypes = legacy_types
                # read as legacy bin
                entries = read_entries()
            except FallbackError:
                bs.seek(entry_offset)
                bs.btypes = ancient_types
                # read as ancient bin
                entries = read_entries()
        # patches
        if is_patch and version >= 3:
            patch_count = int.from_bytes(bs.read(4), 'little')
            patches = [
                Patch(
                    patch_hash, None, 
                    bs.read(int.from_bytes(bs.read(2), 'little')).decode(), 
                    dt:=bs.btypes[data_type],
                    read_data[dt](bs)
                )
                for i in range(patch_count)
                for patch_hash, data_type in [unpack('<I4xB', bs.read(9))]
            ]

    return Binary(
        signature, 
        version,
        is_patch,
        links,
        entries,
        patches
    )


# write funcs
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
def write_list_list2(data): 
    value_type, values = data
    write_data_vt = write_data[value_type]
    buffer = b''.join([
        write_data_vt(value) 
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
            pack(
                '<IB',
                field.hash,
                field.data_type
            ) + write_data[field.data_type](field.data)
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
    if value is None:
        return pack(
            '<2B', 
            value_type,
            0
        )
    return pack(
        '<2B',
        value_type,
        1
    ) + write_data[value_type](value)
def write_map(data): 
    key_type, value_type, pairs = data
    write_data_kt = write_data[key_type]
    write_data_vt = write_data[value_type]
    buffer = b''.join([
        write_data_kt(key) + write_data_vt(value)
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
# list
write_data = [
    write_none,
    write_bool,
    write_i8,
    write_u8,
    write_i16,
    write_u16,
    write_i32,
    write_u32,
    write_i64,
    write_u64,
    write_f32,
    write_vec2,
    write_vec3,
    write_vec4,
    write_mtx44,
    write_rgba,
    write_string,
    write_hash,
    write_file,
    *[write_none]*109, # pad
    write_list_list2,
    write_list_list2,
    write_pointer_embed,
    write_pointer_embed,
    write_link,
    write_option,
    write_map,
    write_flag
]
    
def write(binary, path=None):
    stream = BytesIO() if path is None else open(path, 'wb') 
    with stream as bs:
        # header
        if binary.is_patch:
            bs.write(pack('<4s2I', b'PTCH', 1, 0))
        bs.write(pack('<4sI', b'PROP', 3))
        # links
        bs.write(pack('<I', len(binary.links)))
        for link in binary.links:
            bs.write(pack('<H', len(b:=link.encode())) + b)
        # entries
        entry_count = len(binary.entries)
        bs.write(pack(
            f'<{entry_count+1}I', 
            entry_count, 
            *[entry.class_hash for entry in binary.entries]
        ))
        for entry in binary.entries:
            buffer = b''.join([
                pack(
                    '<IB',
                    field.hash,
                    field.data_type
                ) + write_data[field.data_type](field.data)
                for field in entry.fields
            ])
            bs.write(pack(
                '<2IH', 
                6+len(buffer),
                entry.hash, 
                len(entry.fields)
            ) + buffer)

        # patches
        if binary.is_patch:
            bs.write(pack('<I', len(binary.patches)))
            for patch in binary.patches:
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

# pyrf
indents = ['    ' * i for i in range(0, 32)]
equals= ['', ' = ']
def dump(binary, pyrf_file):
    string_type = 16
    list_types = {128, 129}
    embed_types = {130, 131}
    option_type = 133
    map_type = 134
    def dump_data(data_type, data, indent, inline, equal):
        # complex first
        if data_type in list_types:
            value_type, values = data
            res = [f'[{btype_names[value_type]}] = [' if equal else '[']
            if values:
                res.append('\n')
                res.extend([
                    f'{indents[indent+1]}{dump_data(value_type, value, indent+1, True, False)}\n'
                    for value in values
                ])
                res.append(f'{indents[indent]}]')
            else:
                res.append(']')
            return ''.join(res)
        elif data_type in embed_types:
            (class_hash, _class_hash), fields = data
            res = [f' = {_class_hash}(' if equal else f'{_class_hash}(']
            if fields:
                res.append('\n')
                res.extend([
                    f'{indents[indent+1]}{field._hash}: {btype_names[field.data_type]}{dump_data(field.data_type, field.data, indent+1, True, True)}\n'
                    for field in fields
                ])
                res.append(f'{indents[indent]})')
            else:
                res.append(')')
            return ''.join(res)
        elif data_type == option_type:
            value_type, value = data
            res = f'{dump_data(value_type, value, indent, True, False)}'
            if equal:
                res += f'[{btype_names[value_type]}] = '
            return res
        elif data_type == map_type:
            key_type, value_type, pairs = data
            res = [f'[{btype_names[key_type]},{btype_names[value_type]}] = {{' if equal else '{']
            if pairs:
                res.append('\n')
                res.extend([
                    f'{dump_data(key_type, key, indent+1, False, False)}: {dump_data(value_type, value, indent+1, True, False)}\n'
                    for key, value in pairs.items()
                ])
                res.append(f'{indents[indent]}}}')
            else:
                res.append('}')
            return ''.join(res)
        else:
            # basic 
            if data_type == string_type:                                            data = f'"{data}"'
            return f'{indents[0 if inline else indent]}{equals[equal]}{data}'

    with open(pyrf_file, 'w') as f:
        # header
        f.write(f'signature = {binary.signature}\n')
        # links
        res = ['links = [']
        if binary.links:
            res.append('\n')
            res.extend([
                f'{indents[1]}"{link}"\n'
                for link in binary.links
            ])
        res.append(']\n')
        f.write(''.join(res))
        # entries
        res = ['entries = {']
        if binary.entries:
            res.append('\n')
            for entry in binary.entries:
                res.append(f'{indents[1]}{entry._hash}: {entry._class_hash}(')
                if entry.fields:
                    res.append('\n')
                    res.extend([
                        f'{indents[2]}{field._hash}: {btype_names[field.data_type]}{dump_data(field.data_type, field.data, 2, True, True)}\n'
                        for field in entry.fields
                    ])
                    res.append(f'{indents[1]})\n')
                else:
                    res.append(')')
        res.append('}\n')
        f.write(''.join(res))

        # patches


