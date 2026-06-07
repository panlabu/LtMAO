from io import BytesIO
from struct import unpack, pack

format_names = {
    1: 'etc1',
    2: 'etc2_eac',
    3: 'ect2',
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
    stream = BytesIO(path) if path is None else open(path, 'rb')
    with stream as bs:
        # header
        signature = bs.read(4)
        if signature != b'TEX\x00':
            raise Exception(
                f'pyRitoFile: Error: Read TEX {path}: Wrong file signature: {signature}')
        width, height, format, resource_type,  has_mipmaps = unpack('<2Hx2B?', bs.read(8))
        # data
        if has_mipmaps:
            block_size = 4 if format in {10, 12, 13, 14} else 1
            if format == 20:
                bytes_per_block = 4
            elif format in {10, 21}:
                bytes_per_block = 8
            else:
                bytes_per_block = 16
            mipmap_count = max(width, height).bit_length()
            data = []
            for i in reversed(range(mipmap_count)):
                current_width = max(width // (1 << i), 1)
                current_height = max(height // (1 << i), 1)
                block_width = (current_width + block_size - 1) // block_size
                block_height = (current_height + block_size - 1) // block_size
                current_size = bytes_per_block * block_width * block_height
                data.append(bs.read(current_size))
        else:
            data = [bs.read(-1)]

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
        for block_data in texture.data:
            bs.write(block_data)
