from io import BytesIO
from struct import unpack, iter_unpack, pack
from .maths import hash_xxh3_64
import gzip
# not safe because external modules
try: 
    import pyzstd
except ImportError:
    print('Warning: pyRitoFile.wad failed to import pyzstd.')


sigmap = (
    (slice(13), {
        b'"use strict";': 'min.js',
        b'<!-- Elements': 'template.html',
        b'[ObjectBegin]': 'sco'
    }),
    (slice(8, 12), {
        b'WAVE': 'wav'
    }),
    (slice(10), {
        b'<template ': 'template.html',
        b'#MayaIcons': 'swatches',
        b'#PROP_text': 'py'
    }),
    (slice(9), {
        b'\x1bLuaQ\x00\x01\x04\x04': 'luabin',
        b'\x1bLuaQ\x00\x01\x04\x08': 'luabin64'
    }),
    (slice(8), {
        b'r3d2Mesh': 'scb',
        b'r3d2anmd': 'anm',
        b'r3d2canm': 'anm',
        b'r3d2sklt': 'skl',
        b'\x89PNG\r\n\x1a\n': 'png',
        b'PreloadB': 'preload',
        b'gimp xcf': 'xcf',
        b'Kaydara ': 'fbx'
    }),
    (slice(4, 8), {
        b'\xc3O\xfd"': 'skl'
    }),
    (slice(4), {
        b'OggS': 'ogg',
        b'\x00\x01\x00\x00': 'ttf',
        b'\x1aE\xdf\xa3': 'webm',
        b'true': 'ttf',
        b'OTTO': 'otf',
        b'DDS ': 'dds',
        b'<svg': 'svg',
        b'PROP': 'bin',
        b'PTCH': 'bin',
        b'BKHD': 'bnk',
        b'r3d2': 'wpk',
        b'3"\x11\x00': 'skn',
        b'\x02=\x00(': 'troybin',
        b'OEGM': 'mapgeo',
        b'TEX\x00': 'tex',
        b'8BPS': 'psd',
        b'BLEN': 'blend',
        b'FOR4': 'mb',
        b'FOR8': 'mb'
    }),
    (slice(3), {
        b'\xff\xd8\xff': 'jpg'
    }),
    (slice(2), {
        b'RW': 'wad',
        b'[\n': 'json',
        b'{\n': 'json'
    }),
)
exts = set([ext for sigpos, sigext in sigmap for ext in sigext.values()])

def guess_extension(header):
    for sigpos, sigext in sigmap:
        ext = sigext.get(header[sigpos])
        if ext is not None:
            return ext
    return None

def unhash(archive, lookup):
    for chunk in archive.chunks:
        chunk._hash = lookup(chunk.hash, f'{chunk.hash:016x}')
        if '.' in chunk._hash and chunk.extension is None:
            for ext in exts:
                if chunk._hash.endswith(ext):
                    chunk.extension = ext 
                    break

def read_data(chunk, bs):
    # read data and decompress
    bs.seek(chunk.offset)
    chunk_data = bs.read(chunk.compressed_size)
    if chunk.compression_type == 1:
        chunk_data = gzip.decompress(chunk_data)
    elif chunk.compression_type == 3:
        chunk_data = pyzstd.decompress(chunk_data)
     # no subchunk implemented yet
    elif chunk.compression_type == 4 and chunk_data[:4] == b'\x28\xb5\x2f\xfd':
        chunk_data = pyzstd.decompress(chunk_data)
    # guess extension
    if chunk.extension is None:
        chunk.extension = guess_extension(chunk_data[:20])
    return chunk_data

def write_data(chunk, bs, chunk_id, chunk_hash, chunk_data, previous_chunks=None):
    chunk.hash = chunk_hash
    chunk.compression_type = 0
    chunk.decompressed_size = len(chunk_data)
    if chunk.extension not in {'bnk', 'wpk'}:
        chunk_data = pyzstd.compress(chunk_data)
        chunk.compression_type = 3
    chunk.compressed_size = len(chunk_data)
    chunk.checksum = hash_xxh3_64(chunk_data)
    chunk.duplicated = False

    # check duplicated using previous_chunks: dict
    if previous_chunks is not None:
        key = (chunk.checksum, chunk.compressed_size, chunk.decompressed_size)
        if key not in previous_chunks:
            # chunk is unique, just add
            previous_chunks[key] = chunk
        else:
            # chunk is duped, copy offset
            chunk.duplicated = True
            chunk.offset = previous_chunks[key].offset
    # chunk is unique, save offset and write data
    if not chunk.duplicated:
        bs.seek(0, 2)
        chunk.offset = bs.tell()
        bs.write(chunk_data)
    # update chunk info
    bs.seek(272 + chunk_id * 32) # hack
    bs.write(pack(
        '<Q3IB?HQ',
        chunk_hash,
        chunk.offset,
        chunk.compressed_size,
        chunk.decompressed_size,
        chunk.compression_type,
        chunk.duplicated,
        0, # subchunk 
        chunk.checksum
    ))


class Chunk:
    __slots__ = ('hash', '_hash', 'offset', 'compressed_size', 'decompressed_size', 'compression_type', 'duplicated', 'checksum', 'extension')

    def __init__(self, hash, _hash, offset, compressed_size, decompressed_size, compression_type, duplicated, checksum, extension):
        self.hash = hash
        self._hash = _hash
        self.offset = offset
        self.compressed_size = compressed_size
        self.decompressed_size = decompressed_size
        self.compression_type = compression_type
        self.duplicated = duplicated
        self.checksum = checksum
        self.extension = extension

class Archive:
    __slots__ = ('signature', 'version', 'chunks')

    def __init__(self, signature, version, chunks):
        self.signature = signature
        self.version = version
        self.chunks = chunks


def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # header
        signature = bs.read(2)
        if signature != b'RW':
            raise Exception(f'pyRitoFile: Error: Read WAD: Wrong file signature: {signature}')
        major, minor = unpack('<BB', bs.read(2))
        if major > 3:
            raise Exception(f'pyRitoFile: Error: Read WAD: Unsupported file version: {major}.{minor}')
        if major == 1:
            bs.seek(4, 1)
        elif major == 2:
            bs.seek(96, 1)
        elif major == 3:
            bs.seek(264, 1)
        # chunks
        chunk_count = int.from_bytes(bs.read(4), 'little')
        chunks = [
            Chunk(
                hash, None,
                offset,
                compressed_size,
                decompressed_size,
                type & 15,
                # these values only in v2+, no check until i found a wad v1
                # no subchunk of v3.4 yet
                duplicated, 
                checksum,
                None
            )
            for hash, offset, compressed_size, decompressed_size, type, duplicated, checksum in iter_unpack('<Q3IB?2xQ', bs.read(chunk_count*32))
        ]
        
    return Archive(
        signature,
        (major, minor),
        chunks
    )

def write(archive, path=None):
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        # header
        bs.write(pack('<2sBB264s', b'RW', 3, 3, b''))
        # chunks
        bs.write(pack('<I', len(archive.chunks)))
        for chunk in archive.chunks:
            bs.write(pack(
                '<Q3IB?HQ',
                chunk.hash,
                chunk.offset,
                chunk.compressed_size,
                chunk.decompressed_size,
                chunk.compression_type,
                chunk.duplicated,
                0, # subchunk
                chunk.checksum
            ))
        return stream.getvalue() if path is None else None


def write_full(chunk_buffers, path=None):
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        # pad header and chunk info
        chunk_count = len(chunk_buffers)
        bs.write(pack(f'<{272+chunk_count*32}s', b''))
        # chunks data
        chunks = [None] * chunk_count
        previous_chunks = {}
        sound_ext = {'bnk', 'wpk'}
        for chunk_id, (chunk_hash, chunk_path) in enumerate(chunk_buffers):
            # create chunk
            if isinstance(chunk_path, bytes):
                chunk_data = chunk_path
            else:
                with open(chunk_path, 'rb') as f:
                    chunk_data = f.read()
            compression_type = 0
            decompressed_size = len(chunk_data)
            extension = guess_extension(chunk_data[:20])
            if extension not in sound_ext:
                chunk_data = pyzstd.compress(chunk_data)
                compression_type = 3
            compressed_size = len(chunk_data)
            checksum = hash_xxh3_64(chunk_data)
            # check duplicated using previous_chunks: dict
            key = (checksum, compressed_size, decompressed_size)
            if key not in previous_chunks:
                duplicated = False
                previous_chunks[key] = offset = bs.tell()
                bs.write(chunk_data)
            else:
                # chunk is duped, copy offset
                duplicated = True
                offset = previous_chunks[key]
            # add chunk
            chunks[chunk_id] = (
               chunk_hash, 
               offset, 
               compressed_size,
               decompressed_size,
               compression_type, 
               duplicated,
               checksum
            )

        # header
        bs.seek(0)
        bs.write(pack('<2sBB', b'RW', 3, 3))
        # chunks
        bs.seek(268)
        bs.write(pack('<I', chunk_count))
        for chunk_hash, offset, compressed_size, decompressed_size, compression_type, duplicated, checksum in chunks:
            bs.write(pack(
                '<Q3IB?HQ',
                chunk_hash,
                offset,
                compressed_size,
                decompressed_size,
                compression_type,
                duplicated,
                0, # subchunk
                checksum
            ))
        return stream.getvalue() if path is None else None

