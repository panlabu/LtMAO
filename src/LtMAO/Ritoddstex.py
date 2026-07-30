from struct import unpack
from io import BytesIO
from math import ceil
from . import pyRitoFile

mask_to_index = {
    0x000000ff: 0,
    0x0000ff00: 1,
    0x00ff0000: 2,
    0xff000000: 3
}

def dds2tex(dds_path):
    if isinstance(dds_path, bytes):
        stream = BytesIO(dds_path)
        tex_path = None
    else:
        stream = open(dds_path, 'rb')
        tex_path = dds_path.removesuffix('.dds') + '.tex'
    # dds 
    with stream as bs:
        signature = bs.read(4)
        if signature != b'DDS ':
            raise Exception(f'Ritoddstex: Error: dds2tex: Wrong signature file: {signature}')
        (dwSize, dwFlags, dwHeight, dwWidth, dwPitchOrLinearSize, dwDepth, dwMipMapCount, *dwReserved1, dwSize2, dwFlags2, dwFourCC, dwRGBBitCount, dwRBitMask, dwGBitMask, dwBBitMask, dwABitMask, dwCaps, dwCaps2, dwCaps3, dwCaps4, dwReserved2) = unpack('<20I4s10I', bs.read(124))
        dds_data = bs.read()
    # tex
    # format and other stuffs
    if dwFourCC == b'DXT1':
        format = 10
        block_size = 4
        block_bytes = 8
    elif dwFourCC == b'DXT5':
        format = 12
        block_size = 4
        block_bytes = 16
    elif dwFlags2 & 0x00000041 == 0x00000041:
        format = 20
        block_size = 1
        block_bytes = 4
        # do some check and convert data to bgra 
        if dwRGBBitCount != 32:
            raise Exception(f'Ritoddstex: Error: dds2tex: dwRGBBitCount is expected 32, not {dwRGBBitCount}.')
        if dwBBitMask != 0x000000ff or dwGBitMask != 0x0000ff00 or dwRBitMask != 0x00ff0000 or dwABitMask != 0xff000000:
            rgba_indices = (
                mask_to_index.get(dwRBitMask),
                mask_to_index.get(dwGBitMask),
                mask_to_index.get(dwBBitMask),
                mask_to_index.get(dwABitMask)
            )
            if None in rgba_indices:
                raise Exception(f'Ritoddstex: Error: dds2tex: bitmask data invalid. Can not convert to BGRA output format.')
            r_index, g_index, b_index, a_index = rgba_indices
            bgra_data = bytearray(len(dds_data))
            bgra_data[0::4] = dds_data[b_index::4]
            bgra_data[1::4] = dds_data[g_index::4]
            bgra_data[2::4] = dds_data[r_index::4]
            bgra_data[3::4] = dds_data[a_index::4]
            dds_data = bytes(bgra_data)
    elif dwFourCC == b'DX10': 
        dxgiFormat, resourceDimension, miscFlag, arraySize, miscFlags2 = unpack('<5I', bs.read(20))
        if dxgiFormat == 13:
            format = 21
            block_size = 1
            block_bytes = 8
        elif dxgiFormat == 84:
            format = 14
            block_size = 4
            block_bytes = 16
        elif dxgiFormat == 99:
            format = 13
            block_size = 4
            block_bytes = 16
        else:
            raise Exception(f'Ritoddstex: Error: Unsupported DX10 extended format: {dxgiFormat}')
    else:
        raise Exception(f'Ritoddstex: Error: dds2tex: Unsupported format: {dwFourCC}')
    # mipmaps
    has_mipmaps = False
    if dwMipMapCount > 1: # 1 also mean no mipmaps
        expected_dwMipMapCount = max(dwWidth, dwHeight).bit_length()
        if dwMipMapCount != expected_dwMipMapCount:
            raise Exception(f'Ritoddstex: Error: dds2tex: Wrong DDS mipmap count: {dwMipMapCount}, expected: {expected_dwMipMapCount}')
        has_mipmaps = True
    # data
    if has_mipmaps:
        tex_data = b''
        left = 0
        for i in range(dwMipMapCount):
            right = left + block_bytes * ceil(max(dwWidth >> i, 1) / block_size) * ceil(max(dwHeight >> i, 1) / block_size)
            tex_data = dds_data[left:right] + tex_data
            left = right
    else:
        tex_data = dds_data
        
    return pyRitoFile.tex.write(
        pyRitoFile.tex.Texture(
            None, dwWidth, dwHeight,
            format, 0, has_mipmaps,
            tex_data
        ),
        tex_path
    )

def tex2dds(tex_path):
    # tex
    tex = pyRitoFile.tex.read(tex_path)
    # dds 
    dwSize = 124
    dwFlags = 0x00001007
    dwHeight = tex.height
    dwWidth = tex.width
    dwPitchOrLinearSize = 0
    dwDepth = 0
    dwMipMapCount= 0
    dwReserved1 = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    dwSize2 = 32
    dwFlags2 = 0
    dwFourCC = b''
    dwRGBBitCount = 0
    dwRBitMask = 0
    dwGBitMask = 0
    dwBBitMask = 0
    dwABitMask = 0
    dwCaps = 0x00001000
    dwCaps2 = 0
    dwCaps3 = 0
    dwCaps4 = 0
    dwReserved2 = 0
    # format
    if tex.format == 10:
        dwFourCC = b'DXT1'
        dwFlags2 = 0x00000004
        block_size = 4
        block_bytes = 8
    elif tex.format == 12:
        dwFourCC = b'DXT5'
        dwFlags2 = 0x00000004
        block_size = 4
        block_bytes = 16
    elif tex.format == 13:
        dwFourCC = b'DX10'
        dwFlags2 = 0x00000004
        dxgiFormat = 99 
        resourceDimension = 3
        miscFlag = 0
        arraySize = 1
        miscFlags2 = 1
        block_size = 4
        block_bytes = 16
    elif tex.format == 14:
        dwFourCC = b'DX10'
        dwFlags2 = 0x00000004
        dxgiFormat = 84
        resourceDimension = 3
        miscFlag = 0
        arraySize = 1
        miscFlags2 = 1
        block_size = 4
        block_bytes = 16
    elif tex.format == 21:
        dwFourCC = b'DX10'
        dwFlags2 = 0x00000004
        dxgiFormat = 13
        resourceDimension = 3
        miscFlag = 0
        arraySize = 1
        miscFlags2 = 1
        block_size = 1
        block_bytes = 8
    elif tex.format == 20:
        dwFlags2 = 0x00000041
        dwRGBBitCount = 32
        dwBBitMask = 0x000000ff
        dwGBitMask = 0x0000ff00
        dwRBitMask = 0x00ff0000
        dwABitMask = 0xff000000
        block_size = 1
        block_bytes = 4
    else:
        raise Exception(f'Ritoddstex: Error: tex2dds: Unsupported format: {tex.format}')
    # mipmaps and data
    if tex.has_mipmaps:
        dwFlags |= 0x00020000
        dwCaps |= 0x00400008
        dwMipMapCount = max(dwWidth, dwHeight).bit_length()
        dds_data = b''
        left = 0
        for i in reversed(range(dwMipMapCount)):
            right = left + block_bytes * ceil(max(dwWidth >> i, 1) / block_size) * ceil(max(dwHeight >> i, 1) / block_size)
            dds_data = tex.data[left:right] + dds_data
            left = right
    else:
        dds_data = tex.data
    # write
    if isinstance(tex_path, bytes):
        dds_path = None
        stream = BytesIO()
    else:
        dds_path = tex_path.removesuffix('.tex') + '.dds'
        stream = open(dds_path, 'wb')
    with stream as bs:
        # hearer
        bs.write(pack(
            '<4s20I4s10I',
            b'DDS ',
            dwSize,
            dwFlags,
            dwHeight,
            dwWidth,
            dwPitchOrLinearSize,
            dwDepth,
            dwMipMapCount,
            *dwReserved1,
            dwSize2,
            dwFlags2,
            dwFourCC,
            dwRGBBitCount,
            dwRBitMask,
            dwGBitMask,
            dwBBitMask,
            dwABitMask,
            dwCaps,
            dwCaps2,
            dwCaps3,
            dwCaps4,
            dwReserved2
        ))
        # dx10
        if dwFourCC == b'DX10':
            bs.write(pack(
                '<5I',
                dxgiFormat,
                resourceDimension,
                miscFlag,
                arraySize,
                miscFlags2
            ))
        # data
        bs.write(dds_data)
        return stream.getvalue() if dds_path is None else None
