from io import BytesIO
from struct import unpack, pack
from math import ceil

format_names = {
    1: 'etc1',
    2: 'etc2_eac',
    3: 'etc2',
    10: 'dxt1',
    12: 'dxt5',
    13: 'bc7',
    14: 'bc5',
    20: 'bgra8',
    21: 'rgba16'
}


class Texture:
    __slots__ = (
        'signature', 'width', 'height', 'format', 
        'resource_type', 'has_mipmaps', 'data'
    )

    def __init__(self, signature, width, height, format, resource_type, has_mipmaps, data):
        self.signature = signature
        self.width = width
        self.height = height
        self.format = format
        self.resource_type = resource_type
        self.has_mipmaps = has_mipmaps
        self.data = data


def read(path):
    stream = BytesIO(path) if isinstance(path, bytes) else open(path, 'rb')
    with stream as bs:
        # header
        signature = bs.read(4)
        if signature != b'TEX\x00':
            raise Exception(
                f'pyRitoFile: Error: Read TEX {path}: Wrong file signature: {signature}')
        width, height, format, resource_type,  has_mipmaps = unpack('<2Hx2B?', bs.read(8))
        data = bs.read()

        return Texture(
            signature, 
            width,
            height,
            format,
            resource_type,
            has_mipmaps,
            data
        )
    
def write(texture, path):
    stream = BytesIO() if path is None else open(path, 'wb') 
    with stream as bs:
        # header
        bs.write(pack(
            '<4s2H3B?',
            b'TEX\x00',
            texture.width, texture.height,
            1, texture.format, texture.resource_type,
            texture.has_mipmaps
        ))
        bs.write(texture.data)
