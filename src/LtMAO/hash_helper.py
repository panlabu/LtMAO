try: 
    import requests
except: 
    print('Warning: hash_helper failed to import requests.')
import os, json, traceback, threading, shutil
from . import lepath, pyRitoFile, setting

hashtable = {}
local_dir = r'.\pref\hashes'
local_cdtb = rf'{local_dir}\cdtb'
local_extracted = rf'{local_dir}\extracted'

bsl1, bsl2 = slice(8), slice(9, -1)
bfilehashes = (
    (rf'{local_cdtb}\hashes.binentries.txt', bsl1, bsl2),
    (rf'{local_cdtb}\hashes.binhashes.txt', bsl1, bsl2),
    (rf'{local_cdtb}\hashes.bintypes.txt', bsl1, bsl2),
    (rf'{local_cdtb}\hashes.binfields.txt', bsl1, bsl2),
    (rf'{local_extracted}\hashes.binentries.txt', bsl1, bsl2),
    (rf'{local_extracted}\hashes.binhashes.txt', bsl1, bsl2)
)
wsl1, wsl2 = slice(16), slice(17, -1)
wfilehashes = (
    (rf'{local_cdtb}\hashes.game.txt', wsl1, wsl2),
    (rf'{local_cdtb}\hashes.lcu.txt', wsl1, wsl2),
    (rf'{local_extracted}\hashes.game.txt', wsl1, wsl2)
)

def read_hash(hashes, fh, sl1, sl2):
    if lepath.exists(fh):
        i = int
        with open(fh, 'r', encoding='ascii') as f:
            for line in f:
                hashes[i(line[sl1], 16)] = line[sl2]

def write_hash(hashes, fh, fmhex):
    with open(fh, 'w+') as f:
        for k, v in sorted(hashes.items(), key=lambda x: x[1]):
            f.write(f'{k:0{fmhex}x} {v}\n')

def read_hashes(read_bin, read_wad):
    fhs = []
    h = hashtable
    i = int
    if read_bin:
        fhs += bfilehashes
    if read_wad:
        fhs += wfilehashes
    for fh, sl1, sl2 in fhs:
        if lepath.exists(fh):
            with open(fh, 'r', encoding='ascii') as f:
                for line in f:
                    h[i(line[sl1], 16)] = line[sl2]

def free_hashes():
    global hashtable
    hashtable = {}

def humansize(nbytes):
    if nbytes < 1024:
        return f"{nbytes} B"  
    if nbytes < 1048576:        
        return f"{f'{nbytes/1024:.2f}'.rstrip('0').rstrip('.')} KB"
    if nbytes < 1073741824:      
        return f"{f'{nbytes/1048576:.2f}'.rstrip('0').rstrip('.')} MB"
    return f"{f'{nbytes/1073741824:.2f}'.rstrip('0').rstrip('.')} GB"

def total_size(path):
    return humansize(sum(map(lepath.getsize, lepath.walk(path, lambda f: f))))

local_etag = rf'{local_dir}\etags.json'
local_filehashes = (
    rf'{local_cdtb}\hashes.binentries.txt',
    rf'{local_cdtb}\hashes.binhashes.txt',
    rf'{local_cdtb}\hashes.bintypes.txt',
    rf'{local_cdtb}\hashes.binfields.txt',
    rf'{local_cdtb}\hashes.game.txt',
    rf'{local_cdtb}\hashes.lcu.txt'
)
remote_cdtb = 'https://raw.communitydragon.org/data/hashes/lol'
remote_filehashes = (
    rf'{remote_cdtb}/hashes.binentries.txt',
    rf'{remote_cdtb}/hashes.binhashes.txt',
    rf'{remote_cdtb}/hashes.bintypes.txt',
    rf'{remote_cdtb}/hashes.binfields.txt',
    rf'{remote_cdtb}/hashes.game.txt',
    rf'{remote_cdtb}/hashes.lcu.txt'
)

def sync_hashes():
    def sync_hash(lfh, rfh):
        try:
            get = requests.get(rfh, stream=True)
            get.raise_for_status()
            letag = etags.get(rfh, None)
            retag = get.headers['Etag']
            if not lepath.exists(lfh) or letag == None or letag != retag:
                print(f'hash_helper: Downloading: {rfh}')
                etags[rfh] = retag
                with open(lfh, 'wb') as f:
                    for chunk in get.iter_content(1024**2):
                        f.write(chunk)
        except Exception as e:
            print(f'hash_helper: Error: Sync hash: {rfh}: {e}')
            print(traceback.format_exc())

    # read etags
    etags = {}
    if lepath.exists(local_etag):
        with open(local_etag, 'r') as f:
            etags = json.load(f)
    # sync
    ts = [
        threading.Thread(target=sync_hash, args=(lfh, rfh,), daemon=True)
        for lfh, rfh in zip(local_filehashes, remote_filehashes)
    ]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(f'hash_helper: Finish: Sync all hashes.')
    # write etags
    with open(local_etag, 'w+') as f:
        json.dump(etags, f, indent=4)

class BinHashes(dict):
    def __getitem__(self, key):
        if key in self:
            return super().__getitem__(key)
        else:
            value = pyRitoFile.maths.hash_fnv1a(key)
            super().__setitem__(key, value)
            return value
bin_hashes = BinHashes()
        
class WadHashes(dict):
    def __getitem__(self, key):
        if key in self:
            return super().__getitem__(key)
        else:
            value = pyRitoFile.maths.hash_xxh64(key)
            super().__setitem__(key, value)
            return value
wad_hashes = WadHashes()

def extract(*file_paths):
    # init
    prefixes = (
        'assets/', 
        'clientstates/',
        'data/',
        'levels/',
        'maps/',
        'uiautoatlas/',
        'ux/'
    )
    ehashes = (
        ({}, rf'{local_extracted}\hashes.binentries.txt', bsl1, bsl2, 8),
        ({}, rf'{local_extracted}\hashes.binhashes.txt', bsl1, bsl2, 8),
        ({}, rf'{local_extracted}\hashes.game.txt', wsl1, wsl2, 16)
    )
    binentries_txt = ehashes[0][0]
    binhashes_txt = ehashes[1][0]
    game_txt = ehashes[2][0]
    string_type = 16
    list_types = {128, 129}
    embed_types = {130, 131}
    option_type = 133
    map_type = 134
    read_data = pyRitoFile.wad.read_data
    # extract func
    def extract_skn(path):
        try:
            skn = pyRitoFile.skn.read(path)
            for submesh in skn.submeshes:
                binhashes_txt[bin_hashes[submesh.name]] = submesh.name
        except Exception as e:
            print(f'hash_helper: Error: {e}')
            print(traceback.format_exc())

    def extract_skl(path):
        try:
            skl = pyRitoFile.skl.read(path)
            for joint in skl.joints:
                binhashes_txt[bin_hashes[joint.name]] = joint.name
        except Exception as e:
            print(f'hash_helper: Error: {e}')
            print(traceback.format_exc())

    def extract_bin(path):
        def extract_data(data_type, data):
            if data_type == string_type:
                data = data.lower()
                if data.startswith(prefixes):
                    game_txt[wad_hashes[data]] = data
                if data.endswith('.dds'):
                    dirname, basename = lepath.split(data)
                    data2x = f'{dirname}/2x_{basename}'
                    data4x = f'{dirname}/4x_{basename}'
                    game_txt[wad_hashes[data2x]] = data2x
                    game_txt[wad_hashes[data4x]] = data4x
                elif data.endswith('.bin'):
                    datapy = lepath.ext(data, '.bin', '.py')
                    game_txt[wad_hashes[datapy]] = datapy
            elif data_type in list_types:
                value_type, values = data
                for value in values:
                    extract_data(value_type, value)
            elif data_type in embed_types:
                (class_hash, _class_hash), fields = data
                for field in fields:
                    extract_field(field)
            elif data_type == option_type:
                value_type, value = data
                if value is not None:
                    extract_data(value_type, value)
            elif data_type == map_type:
                key_type, value_type, pairs = data
                for key, value in pairs.items():
                    extract_data(key_type, key)
                    extract_data(value_type, value)
    
        def extract_field(field):
            extract_data(field.data_type, field.data)

        try:
            bin = pyRitoFile.bin.read(path)
            for entry in bin.entries:
                # map some specific entry
                target_field = None
                if entry.class_hash == bin_hashes['VfxSystemDefinitionData']:
                    target_field = bin_hashes['particlePath']
                elif entry.class_hash == bin_hashes['StaticMaterialDef']:
                    target_field = bin_hashes['name']
                for field in entry.fields:
                    if target_field and field.hash == target_field:
                        binentries_txt[entry.class_hash] = field.data
                    extract_field(field)
            for link in bin.links:
                extract_data(string_type, link) # treat as string
        except Exception as e:
            print(f'hash_helper: Error: {e}')
            print(traceback.format_exc())
            
    def extract_wad(path):
        wad = pyRitoFile.wad.read(path)
        with open(path, 'rb') as bs:
            for chunk in wad.chunks:
                chunk_data = read_data(chunk, bs)
                if chunk.extension == 'skn':
                    extract_skn(chunk_data)
                elif chunk.extension == 'skl':
                    extract_skl(chunk_data)
                elif chunk.extension == 'bin':
                    extract_bin(chunk_data)
        
    # read existed extract hash
    for hashes, filehash, sl1, sl2, fmhex in ehashes:
        read_hash(hashes, filehash, sl1, sl2)
    # extract hashes
    for file_path in file_paths:
        print(f'hash_helper: Finish: Extracting: {filehash}')
        if file_path.endswith('.wad.client'):
            extract_wad(file_path)
        elif file_path.endswith('.skn'):
            extract_skn(file_path)
        elif file_path.endswith('.skl'):
            extract_skl(file_path)
        elif file_path.endswith('.bin'):
            extract_bin(file_path)
    # write out extracted hashes 
    for hashes, filehash, sl1, sl2, fmhex in ehashes:
        write_hash(hashes, filehash, fmhex)
        print(f'hash_helper: Finish: Extract: {filehash}')

def clear_extracted():
    shutil.rmtree(lepath.abs(local_extracted))
    os.makedirs(local_extracted, exist_ok=True)
    print(f'hash_helper: Finish: Clear: {local_extracted}')

def apply_basedir(local_cdtb, local_extracted):
    global bfilehashes, wfilehashes, local_filehashes
    bfilehashes = (
        (rf'{local_cdtb}\hashes.binentries.txt', bsl1, bsl2),
        (rf'{local_cdtb}\hashes.binhashes.txt', bsl1, bsl2),
        (rf'{local_cdtb}\hashes.bintypes.txt', bsl1, bsl2),
        (rf'{local_cdtb}\hashes.binfields.txt', bsl1, bsl2),
        (rf'{local_extracted}\hashes.binentries.txt', bsl1, bsl2),
        (rf'{local_extracted}\hashes.binhashes.txt', bsl1, bsl2)
    )
    wfilehashes = (
        (rf'{local_cdtb}\hashes.game.txt', wsl1, wsl2),
        (rf'{local_cdtb}\hashes.lcu.txt', wsl1, wsl2),
        (rf'{local_extracted}\hashes.game.txt', wsl1, wsl2)
    )
    local_filehashes = (
        rf'{local_cdtb}\hashes.binentries.txt',
        rf'{local_cdtb}\hashes.binhashes.txt',
        rf'{local_cdtb}\hashes.bintypes.txt',
        rf'{local_cdtb}\hashes.binfields.txt',
        rf'{local_cdtb}\hashes.game.txt',
        rf'{local_cdtb}\hashes.lcu.txt'
    )

def init():
    global local_cdtb, local_extracted
    local_cdtb = setting.get('hash_helper.local_cdtb', local_cdtb)
    local_extracted = setting.get('hash_helper.local_extracted', local_extracted)
    apply_basedir(local_cdtb, local_extracted)
    # ensure folder
    os.makedirs(local_cdtb, exist_ok=True)
    os.makedirs(local_extracted, exist_ok=True)
