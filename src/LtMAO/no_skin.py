import json, os, zipfile, shutil, time
from concurrent.futures import ProcessPoolExecutor
from . import hash_helper, pyRitoFile

local_dir = './pref/no_skin'
skips_file = f'{local_dir}/SKIPS.json'
skips = {}
meta = {
    'Name': 'NO SKIN',
    'Author': 'panlabu',
    'Version': '1.0',
    'Description': ''
}

def load_skips():
    if os.path.exists(skips_file):
        with open(skips_file, 'r', encoding='utf-8') as f:
            skips.update(json.load(f))
    else:
        skips.update({
            "_comment_general": [
                "Key starts with _ mean comment. What you put in here determine which characters and skins wont become skin0.bin (get skipped).",
                "example: azirsoldier: all mean all skinx.bin of azisoldier wont become skin0.bin."
            ],
            "_azirsoldier": "crash some game for no reason",
            "azirsoldier": "all",
            "_mel": "invisible particles",
            "mel": "all",
            "_aniviaiceblock": "some walls are invisible",
            "aniviaiceblock": "all",
            "_ekko": "true damage ekko become transparent",
            "ekko": [
                "skin19.bin",
                "skin20.bin",
                "skin21.bin",
                "skin22.bin",
                "skin23.bin",
                "skin24.bin",
                "skin25.bin",
                "skin26.bin",
                "skin27.bin"
            ],
            "_threshlantern": "crash some game for no reason",
            "threshlantern": [
                "skin11.bin"
            ]
        })


def save_skips():
    with open(skips_file, 'w', encoding='utf-8') as f:
        json.dump(skips, f, indent=4, ensure_ascii=False)
    print(f'no_skin: Finish: Write {skips_file}')

def get_skips():
    return json.dumps(skips, indent=4)

def set_skips(text):
    try:
        skips.clear()
        skips.update(json.loads(text))
    except Exception as e:
        raise Exception(f'no_skin: Error: Set skips: {e}')

def lite(skin0_file, skinx_files):
    # rebuild hashes
    print('no_skin: Start: Rebuild hashes.')
    h = {}
    for fh, sl1, sl2, _ in hash_helper.bfhs:
        if 'binentries' in fh:
            hash_helper.read_hash(h, sl1, sl2)
    skin0_hashes = set()
    skinx_hashes = set()
    for key, value in h.items():
        if value.startswith('Characters/') and not value.endswith('/Root') and '/Skins/' in value:
            if value.endswith('/Skin0'):
                skin0_hashes.add(key)
            else:
                skinx_hashes.add(key)
    h.clear()
    # read bins
    print('no_skin: Start: Read BINs.')
    skin0_bin = pyRitoFile.bin.read(skin0_file)
    skinx_bins = [pyRitoFile.bin.read(skinx_file) for skinx_file in skinx_files]
    # init
    bin_hasher = hash_helper.bin_hasher
    hSkinCharacterDataProperties = bin_hasher['SkinCharacterDataProperties']
    hResourceResolver = bin_hasher['ResourceResolver']
    hmResourceResolver = bin_hasher['mResourceResolver']
    # skin0 bin
    base_SkinCharacterDataProperties = None
    base_ResourceResolver = None
    base_mResourceResolver = None
    for entry in skin0_bin.entries:
        if entry.class_hash == hSkinCharacterDataProperties:
            base_SkinCharacterDataProperties = entry
            for field in entry.fields:
                if field.hash == hmResourceResolver:
                    base_mResourceResolver = field
                    break
            if base_ResourceResolver:
                break
        elif entry.class_hash == hResourceResolver:
            base_ResourceResolver = entry
            if base_SkinCharacterDataProperties:
                break
    if base_SkinCharacterDataProperties is None or base_SkinCharacterDataProperties.hash not in skin0_hashes:
        raise Exception(f'no_skin: Error: Swap skin: {skin0_file} is not a skin0.bin.')
    # skinx bins
    for skinx_file, skinx_bin in zip(skinx_files, skinx_bins):
        skin_SkinCharacterDataProperties_hash = None
        skin_ResourceResolver_hash = None
        for entry in skinx_bin.entries:
            if entry.class_hash == hSkinCharacterDataProperties:
                skin_SkinCharacterDataProperties_hash = entry.hash
                for field in entry.fields:
                    if field.hash == hmResourceResolver:
                        skin_ResourceResolver_hash = field.data
                        break
                break
        if skin_SkinCharacterDataProperties_hash not in skinx_hashes:
            print(f'no_skin: Error: Swap skin: {skinx_file} is not a skinX.bin.')
            continue
        # swap
        base_SkinCharacterDataProperties.hash = skin_SkinCharacterDataProperties_hash
        if base_ResourceResolver is not None:
            base_ResourceResolver.hash = base_mResourceResolver.data = skin_ResourceResolver_hash
        # write 
        pyRitoFile.bin.write(skin0_bin, skinx_file)
    print(f'no_skin: Finish: Swap {len(skinx_files)} skinX as skin0.')

def full_wad(wad_file, h, skips):
    # swap
    read_bin = pyRitoFile.bin.read
    write_bin = pyRitoFile.bin.write
    read_data = pyRitoFile.wad.read_data
    bin_hasher = hash_helper.bin_hasher
    hSkinCharacterDataProperties = bin_hasher['SkinCharacterDataProperties']
    hResourceResolver = bin_hasher['ResourceResolver']
    hmResourceResolver = bin_hasher['mResourceResolver']
    chunk_buffers = []
    skin0_bins = {}  # base bin at character
    skinx_bins = {}  # skin bins at character
    # read
    wad = pyRitoFile.wad.read(wad_file)
    pyRitoFile.wad.unhash(wad, h.get)
    with open(wad_file, 'rb') as bs:
        for chunk in wad.chunks:
            if chunk.extension == 'bin':
                # chunk._hash = 'data/characters/{character}/skins/{skinx}'
                parts = chunk._hash.split('/', 4)
                character = parts[2]
                skinx = parts[4]
                # skip?
                if character in skips:
                    if skips[character] == 'all' or skinx in skips[character]:
                        continue
                # read chunk
                chunk_data = read_data(chunk, bs)
                bin = read_bin(chunk_data)
                # if skin0 bin: save the bin to write later
                # if skinx bin: save the bin and chunk hash to swap
                if 'skin0.bin' in chunk._hash:
                    skin0_bins[character] = bin
                else:
                    if character not in skinx_bins:
                        skinx_bins[character] = []
                    skinx_bins[character].append((chunk.hash, bin))
    # swap skins 
    for character in skin0_bins:
        # there is character that only has skin0.bin, skip them
        if character not in skinx_bins:
            continue
        # skin0 bin
        skin0_bin = skin0_bins[character]
        base_SkinCharacterDataProperties = None
        base_ResourceResolver = None
        base_mResourceResolver = None
        for entry in skin0_bin.entries:
            if entry.class_hash == hSkinCharacterDataProperties:
                base_SkinCharacterDataProperties = entry
                for field in entry.fields:
                    if field.hash == hmResourceResolver:
                        base_mResourceResolver = field
                        break
                if base_ResourceResolver:
                    break
            elif entry.class_hash == hResourceResolver:
                base_ResourceResolver = entry
                if base_SkinCharacterDataProperties:
                    break
        # skinx bin
        for chunk_hash, skinx_bin in skinx_bins[character]:
            skin_SkinCharacterDataProperties_hash = None
            skin_ResourceResolver_hash = None
            for entry in skinx_bin.entries:
                if entry.class_hash == hSkinCharacterDataProperties:
                    skin_SkinCharacterDataProperties_hash = entry.hash
                    for field in entry.fields:
                        if field.hash == hmResourceResolver:
                            skin_ResourceResolver_hash = field.data
                            break
                    break
            # swap
            base_SkinCharacterDataProperties.hash = skin_SkinCharacterDataProperties_hash
            if base_ResourceResolver is not None:
                base_ResourceResolver.hash = base_mResourceResolver.data = skin_ResourceResolver_hash
            # add chunk
            chunk_buffers.append((chunk_hash, write_bin(skin0_bin)))
        print(f'no_skin: Finish: {character}: Swap {len(skinx_bins[character])} skins.')
    return chunk_buffers

def full(champions_dir, output_dir):
    start_time = time.time()
    print('no_skin: Start: Filter wads and rebuild hashes.')
    # filter wads
    files = os.listdir(champions_dir)
    wad_files = [
        os.path.join(champions_dir, file)
        for file in files
        if file.endswith('.wad.client') and '_' not in file
    ]
    if not wad_files:
        raise Exception('no_skin: Error: Invalid Champions folder?')
    # rebuilds hashes
    h = {}
    for fh, sl1, sl2, _ in hash_helper.wfhs:
        if 'game' in fh:
            hash_helper.read_hash(h, fh, sl1, sl2)
    h = {
        k: v
        for k, v in h.items()
        if v.endswith('.bin') and not v.endswith('root.bin') and v.startswith('data/characters/') and '/skins/' in v 
    }
    # swap
    print('no_skin: Start: Swap characters.')
    chunk_buffers = []
    with ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(full_wad, wad_file, h, skips)
            for wad_file in wad_files
        ]
        for future in futures:
            chunk_buffers.extend(future.result())
    # create fantome
    fantome_file = os.path.join(
        output_dir,
        f'{meta["Name"]} V{meta["Version"]} by {meta["Author"]}.fantome'
    )
    with zipfile.ZipFile(fantome_file, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr('META/info.json', json.dumps(meta, indent=4, ensure_ascii=False))
        z.writestr('WAD/Zyra.wad.client', pyRitoFile.wad.write_full(chunk_buffers))
    end_time = time.time()
    print(f'no_skin: Finish: Create Fantome: {fantome_file} with {end_time-start_time:.2f} seconds')

def init():
    # ensure folder
    os.makedirs(local_dir, exist_ok=True)
    load_skips()
