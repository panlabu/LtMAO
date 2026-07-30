from . import hash_helper, pyRitoFile

def find_mMaskDataMap(bin):
    bin_hasher = hash_helper.bin_hasher
    for entry in bin.entries:
        if entry.class_hash == bin_hasher['animationGraphData']:
            for field in entry.fields:
                if field.hash == bin_hasher['mMaskDataMap']:
                    return field
    raise Exception('mask_viewer: Error: mMaskDataMap not found, not Animation BIN?')

def get_weights(bin):
    mask_data = {}
    mMaskDataMap = find_mMaskDataMap(bin)
    _, _, pairs = mMaskDataMap.data
    for mask_name, MaskData in pairs.items():
        _, fields = MaskData.data
        for field in fields:
            if field.hash == bin_hasher['mWeightList']:
                _, values = field.data
                mask_data[mask_name] = values
    return mask_data


def set_weights(bin, mask_data):
    mMaskDataMap = find_mMaskDataMap(bin)
    _, _, pairs = mMaskDataMap.data
    for mask_name, MaskData in pairs.items():
        _, fields = MaskData.data
        for field in fields:
            if field.hash == bin_hasher['mWeightList']:
                value_type, values = field.data
                field.data = (value_type, mask_data[mask_name])
