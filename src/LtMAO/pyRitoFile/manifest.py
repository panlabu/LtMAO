from io import BytesIO
from struct import unpack, unpack_from

# not safe because external modules
try: 
    import pyzstd
except ImportError:
    print('Warning: pyRitoFile.manifest failed to import pyzstd.')

class BundleChunk:
    __slots__ = ('id', 'compressed_size', 'decompressed_size')
    
    def __init__(self, id, compressed_size, decompressed_size):
        self.id = id
        self.compressed_size = compressed_size
        self.decompressed_size = decompressed_size

class Bundle:
    __slots__ = ('id', 'chunks')
    
    def __init__(self, id, chunks):
        self.id = id
        self.chunks = chunks

class File:
    __slots__ = ('id', 'parent', 'name', 'chunk_ids')
    
    def __init__(self, id, parent, name, chunk_ids):
        self.id = id
        self.parent = parent
        self.name = name
        self.chunk_ids = chunk_ids

class Directory:
    __slots__ = ('id', 'parent', 'name')
    
    def __init__(self, id, parent, name):
        self.id = id
        self.parent = parent
        self.name = name

class Manifest:
    __slots__ = ('signature', 'version', 'flags', 'manifest_id', 'bundles', 'files', 'dirs')

    def __init__(self, signature, version, flags, manifest_id, bundles, files, dirs):
        self.signature = signature
        self.version = version
        self.flags = flags
        self.manifest_id = manifest_id
        self.bundles = bundles
        self.files = files
        self.dirs = dirs

def get_pointer(buffer, table_offset, vtable_offset):
    vtable_start = table_offset - unpack_from('<i', buffer, table_offset)[0]
    vtable_size, = unpack_from('<H', buffer, vtable_start)
    if vtable_offset < vtable_size:
        offset = unpack_from('<H', buffer, vtable_start + vtable_offset)[0]
        if offset != 0:
            return table_offset + offset
    return 0

def read_str(buffer, pointer):
    if not pointer: return None
    offset = pointer + unpack_from('<I', buffer, pointer)[0]
    count, = unpack_from('<I', buffer, offset)
    return buffer[offset+4:offset+4+count].decode('utf-8') if count else ''

def read_u32(buffer, pointer):
    return unpack_from('<I', buffer, pointer)[0] if pointer else 0

def read_u64(buffer, pointer):
    return unpack_from('<Q', buffer, pointer)[0] if pointer else 0

def read_u64s(buffer, pointer):
    if not pointer: return ()
    offset = pointer + unpack_from('<I', buffer, pointer)[0]
    count, = unpack_from('<I', buffer, offset)
    return unpack_from(f'<{count}Q', buffer, offset+4) if count else ()

def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # header
        signature = bs.read(4)
        if signature != b'RMAN':
            raise Exception(f'pyRitoFile: Error: Read MANIFEST {path}: Wrong signature file: {signature}')
        major, minor = unpack('<BB', bs.read(2))
        if major != 2:
            raise Exception(f'pyRitoFile: Error: Read MANIFEST {path}: Unsupported file version: {major}.{minor}')
        
        # some numbers
        flags, buffer_offset, compressed_size, manifest_id, decompressed_size = unpack('<HIIQI', bs.read(22))

        # buffer and root offset
        bs.seek(buffer_offset)
        buffer = pyzstd.decompress(bs.read(compressed_size))
        root_offset, = unpack_from('<I', buffer, 0)

        # bundles
        bundles = []
        bundles_pointer = get_pointer(buffer, root_offset, 4)
        if bundles_pointer:
            bundles_offset = bundles_pointer + unpack_from('<I', buffer, bundles_pointer)[0]
            bundle_count, = unpack_from('<I', buffer, bundles_offset)
            for bundle_index in range(bundle_count):
                bundle_pointer = bundles_offset + 4 + (bundle_index * 4)
                bundle_offset = bundle_pointer + unpack_from('<I', buffer, bundle_pointer)[0]
                bundle_id = read_u64(buffer, get_pointer(buffer, bundle_offset, 4))
                # bundle chunks
                chunks = []
                chunks_pointer = get_pointer(buffer, bundle_offset, 6)
                if chunks_pointer:
                    chunks_offset = chunks_pointer + unpack_from('<I', buffer, chunks_pointer)[0]
                    chunk_count, = unpack_from('<I', buffer, chunks_offset)
                    for chunk_index in range(chunk_count):
                        chunk_pointer = chunks_offset + 4 + (chunk_index * 4)
                        chunk_offset = chunk_pointer + unpack_from('<I', buffer, chunk_pointer)[0]
                        chunks.append(BundleChunk(
                            read_u64(buffer, get_pointer(buffer, chunk_offset, 4)),
                            read_u32(buffer, get_pointer(buffer, chunk_offset, 6)),
                            read_u32(buffer, get_pointer(buffer, chunk_offset, 8))
                        ))
                bundles.append(Bundle(bundle_id, tuple(chunks)))

        # files
        files = []
        files_pointer = get_pointer(buffer, root_offset, 8)
        if files_pointer:
            files_offset = files_pointer + unpack_from('<I', buffer, files_pointer)[0]
            file_count, = unpack_from('<I', buffer, files_offset)
            for file_index in range(file_count):
                file_pointer = files_offset + 4 + (file_index * 4)
                file_offset = file_pointer + unpack_from('<I', buffer, file_pointer)[0]
                files.append(File(
                    read_u64(buffer, get_pointer(buffer, file_offset, 4)),
                    read_u64(buffer, get_pointer(buffer, file_offset, 6)),
                    read_str(buffer, get_pointer(buffer, file_offset, 10)),
                    read_u64s(buffer, get_pointer(buffer, file_offset, 18))
                ))

        # dirs 
        dirs = []
        dirs_pointer = get_pointer(buffer, root_offset, 10)
        if dirs_pointer:
            dirs_offset = dirs_pointer + unpack_from('<I', buffer, dirs_pointer)[0]
            dir_count, = unpack_from('<I', buffer, dirs_offset)
            for dir_index in range(dir_count):
                dir_pointer = dirs_offset + 4 + (dir_index * 4)
                dir_offset = dir_pointer + unpack_from('<I', buffer, dir_pointer)[0]
                dirs.append(Directory(
                    read_u64(buffer, get_pointer(buffer, dir_offset, 4)),
                    read_u64(buffer, get_pointer(buffer, dir_offset, 6)),
                    read_str(buffer, get_pointer(buffer, dir_offset, 8))
                ))

    return Manifest(
        signature,
        (major, minor), # version
        flags,
        manifest_id,
        bundles,
        files, 
        dirs
    )
    
