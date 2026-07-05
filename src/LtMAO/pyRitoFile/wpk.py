from io import BytesIO
from struct import unpack, pack

class Wem:
    __slots__ = ('hash', 'offset', 'size')
    def __init__(self, hash, offset, size):
        self.hash = hash
        self.offset = offset
        self.size = size

class SoundPack:
    __slots__ = ('signature', 'version', 'wems')
    def __init__(self, signature, version, wems):
        self.signature = signature
        self.version = version
        self.wems = wems

def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # header
        signature = bs.read(4)
        if signature != b'r3d2':
            raise Exception(f'pyRitoFile: Error: Read WPK {path}: Wrong signature file: {signature}')
        version = int.from_bytes(bs.read(4), 'little')
        # info offset
        info_offset_count = int.from_bytes(bs.read(4), 'little')
        info_offsets = unpack(f'{info_offset_count}I', bs.read(4*info_offset_count))
        # wems
        wems = [
            (
                bs.seek(info_offset),
                ud:=unpack('<3I', bs.read(12)),
                Wem(
                    int(bs.read(ud[2]*2).decode('utf-16-le')[:-4]),
                    ud[0],
                    ud[1]
                )
            )[-1]
            for info_offset in info_offsets
            if info_offset > 0
        ]

    return SoundPack(
        signature,
        version,
        wems
    )

def write(soundpack, wem_datas, path=None):
    stream = BytesIO() if path is None else open(path, 'wb')
    with stream as bs:
        # header
        bs.write(pack('<4sI', b'r3d2', 1))
        # pad info offset
        wem_count = len(soundpack.wems)
        bs.write(pack('<I', wem_count))
        bs.seek(wem_count*4, 1)
        # wems
        info_offsets = [0] * wem_count
        for i, wem in enumerate(soundpack.wems):
            info_offsets[i] = bs.tell()
            bs.write(
                pack(
                    '<3I',
                    0, # pad data offset
                    len(wem_datas[i]),
                    len(b:=f'{wem.hash}.wem'.encode('utf-16-le'))
                ) + b
            )
        # wem datas
        for i, wem_data in enumerate(wem_datas):
            data_offset = bs.tell()
            bs.write(wem_data)
            # go back write data offset
            bs.seek(info_offsets[i])
            bs.write(pack('<I', data_offset))
            bs.seek(0, 2)
        # go back write info offsets
        bs.seek(12)
        bs.write(pack(f'<{wem_count}I', *info_offsets))
        
        return bs.getvalue() if path is None else None 

    
