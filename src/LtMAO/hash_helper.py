try: 
    import requests
except ImportError: 
    print('Warning: hash_helper failed to import requests.')
import os, json, traceback, threading, shutil
from . import lepath, pyRitoFile, stash

hashes_dir = './pref/hashes'
cdtb_dir = f'{hashes_dir}/cdtb'
extracted_dir = f'{hashes_dir}/extracted'
etag_file = f'{hashes_dir}/etags.json'

# b = bin
# w = wad / width
# h = hashes
# sl = slice
# fh = filehash
bw = 8
bsl1 = slice(bw)
bsl2 = slice(bw+1, -1)
bfhs = (
    (f'{cdtb_dir}/hashes.binentries.txt', bsl1, bsl2, bw),
    (f'{cdtb_dir}/hashes.binhashes.txt', bsl1, bsl2, bw),
    (f'{cdtb_dir}/hashes.bintypes.txt', bsl1, bsl2, bw),
    (f'{cdtb_dir}/hashes.binfields.txt', bsl1, bsl2, bw),
    (f'{extracted_dir}/hashes.binentries.txt', bsl1, bsl2, bw),
    (f'{extracted_dir}/hashes.binhashes.txt', bsl1, bsl2, bw)
)
ww = 16
wsl1 = slice(ww)
wsl2 = slice(ww+1, -1)
wfhs = (
    (f'{cdtb_dir}/hashes.game.txt', wsl1, wsl2, ww),
    (f'{cdtb_dir}/hashes.lcu.txt', wsl1, wsl2, ww),
    (f'{extracted_dir}/hashes.game.txt', wsl1, wsl2, ww)
)

# simple read write
def read_hash(h, fh, sl1, sl2):
    i = int
    with open(fh, 'a+', encoding='ascii') as f:
        f.seek(0)
        for line in f:
            h[i(line[sl1], 16)] = line[sl2]

def write_hash(h, fh, w):
    with open(fh, 'w') as f:
        for k, v in sorted(h.items(), key=lambda x: x[1]):
            f.write(f'{k:0{w}x} {v}\n')

# into hashes
hashes = {}

def read_hashes(b, w):
    fhs = []
    if b: fhs += bfhs
    if w: fhs += wfhs
    h = hashes
    i = int
    for fh, sl1, sl2, _ in fhs:
        with open(fh, 'a+', encoding='ascii') as f:
            f.seek(0)
            for line in f:
                h[i(line[sl1], 16)] = line[sl2]

free_hashes = hashes.clear
lookup = hashes.get

# size related
def human_size(nbytes):
    if nbytes < 1024:
        return f"{nbytes} B"  
    if nbytes < 1048576:        
        return f"{f'{nbytes/1024:.2f}'.rstrip('0').rstrip('.')} KB"
    if nbytes < 1073741824:      
        return f"{f'{nbytes/1048576:.2f}'.rstrip('0').rstrip('.')} MB"
    return f"{f'{nbytes/1073741824:.2f}'.rstrip('0').rstrip('.')} GB"

def total_size(path): return human_size(sum(map(lepath.getsize, lepath.walk(path))))

def sync_hashes():
    # init 
    etags = {}
    cdtb_remote = 'https://raw.communitydragon.org/data/hashes/lol'
    rfhs = (
        f'{cdtb_remote}/hashes.binentries.txt',
        f'{cdtb_remote}/hashes.binhashes.txt',
        f'{cdtb_remote}/hashes.bintypes.txt',
        f'{cdtb_remote}/hashes.binfields.txt',
        f'{cdtb_remote}/hashes.game.txt',
        f'{cdtb_remote}/hashes.lcu.txt'
    )
    cfhs = (bfhs[0], bfhs[1], bfhs[2], bfhs[3], wfhs[0], wfhs[1])
    lfhs = [fh for fh, _, _, _ in cfhs]
    def sync_hash(lfh, rfh):
        try:
            get = requests.get(rfh, stream=True)
            get.raise_for_status()
            letag = etags.get(rfh, None)
            retag = get.headers['Etag']
            if not lepath.exists(lfh) or letag is None or letag != retag:
                print(f'hash_helper: Downloading: {rfh}')
                etags[rfh] = retag
                with open(lfh, 'wb') as f:
                    for chunk in get.iter_content(1024**2):
                        f.write(chunk)
        except Exception as e:
            print(f'hash_helper: Error: Sync hash: {rfh}: {e}')
            print(traceback.format_exc())

    # read etags
    if lepath.exists(etag_file):
        with open(etag_file, 'r') as f:
            etags = json.load(f)
    # sync
    ts = [
        threading.Thread(target=sync_hash, args=(lfh, rfh,), daemon=True)
        for lfh, rfh in zip(lfhs, rfhs)
    ]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    print(f'hash_helper: Finish: Sync all hashes.')
    # write etags
    with open(etag_file, 'w') as f:
        json.dump(etags, f, indent=4)

# hasher
class Hasher(dict):
    def __init__(self, hash_func):
        super().__init__()
        self.hash_func = hash_func

    def __missing__(self, key):
        value = self.hash_func(key)
        self[key] = value
        return value

bin_hasher = Hasher(pyRitoFile.maths.hash_fnv1a)
wad_hasher = Hasher(pyRitoFile.maths.hash_xxh64)

# extract hashes
def extract_hashes(*file_paths):
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
    efhs = (bfhs[4], bfhs[5], wfhs[2])
    binhashes = {}
    binentries = {}
    game = {}
    hs = (binentries, binhashes, game)
    string_type = 16
    list_types = {128, 129}
    option_type = 133
    map_type = 134
    target_types = {string_type, option_type, map_type} | list_types 
    read_skn = pyRitoFile.skn.read
    read_skl = pyRitoFile.skl.read
    read_bin = pyRitoFile.bin.read
    flatten = pyRitoFile.bin.flatten
    read_wad = pyRitoFile.wad.read
    read_data = pyRitoFile.wad.read_data
    target_get = {
        bin_hasher['VfxSystemDefinitionData']: bin_hasher['particlePath'],
        bin_hasher['StaticMaterialDef']: bin_hasher['name']
    }.get

    # extract func
    def extract_skn(path):
        try:
            for submesh in read_skn(path).submeshes:
                binhashes[bin_hasher[submesh.name]] = submesh.name
        except Exception as e:
            print(f'hash_helper: Error: {e}')
            print(traceback.format_exc())

    def extract_skl(path):
        try:
            for joint in read_skl(path).joints:
                binhashes[bin_hasher[joint.name]] = joint.name
        except Exception as e:
            print(f'hash_helper: Error: {e}')
            print(traceback.format_exc())

    def extract_bin(path):
        def extract_data(data_type, data):
            if data_type == string_type:
                data = data.lower()
                if data.startswith(prefixes):
                    game[wad_hasher[data]] = data
                    if data.endswith('.dds'):
                        dirname, basename = lepath.split(data)
                        data2x = lepath.join(dirname, f'2x_{basename}')
                        data4x = lepath.join(dirname, f'4x_{basename}')
                        game[wad_hasher[data2x]] = data2x
                        game[wad_hasher[data4x]] = data4x
                    elif data.endswith('.bin'):
                        datapy = lepath.ext(data, '.bin', '.py')
                        game[wad_hasher[datapy]] = datapy
            elif data_type in list_types:
                value_type, values = data
                for value in values:
                    extract_data(value_type, value)
            elif data_type == option_type:
                value_type, value = data
                if value is not None:
                    extract_data(value_type, value)
            elif data_type == map_type:
                key_type, value_type, pairs = data
                for key, value in pairs.items():
                    extract_data(key_type, key)
                    extract_data(value_type, value)
    
        try:
            bin = read_bin(path)
            if bin.flat_fields is None:
                bin.flat_fields = flatten(bin)
            for link in bin.links:
                extract_data(string_type, link) # treat as string   
            for entry in bin.entries:
                target_field = target_get(entry.class_hash)
                if target_field is not None:
                    for field in entry.fields:
                        if field.hash == target_field: 
                            binentries[entry.hash] = field.data
                            break
            for field in bin.flat_fields:
                if field.data_type in target_types:
                    extract_data(field.data_type, field.data)
        except Exception as e:
            print(f'hash_helper: Error: {e}')
            print(traceback.format_exc())
            
    def extract_wad(path):
        wad = read_wad(path)
        with open(path, 'rb') as bs:
            for chunk in wad.chunks:
                chunk_data = read_data(chunk, bs)
                if chunk.extension == 'skn':
                    extract_skn(chunk_data)
                elif chunk.extension == 'skl':
                    extract_skl(chunk_data)
                elif chunk.extension == 'bin':
                    extract_bin(chunk_data)
        
    # read extracted hashes
    for h, (fh, sl1, sl2, _) in zip(hs, efhs):
        read_hash(h, fh, sl1, sl2)
    # extract hashes
    for file_path in file_paths:
        print(f'hash_helper: Extracting: {file_path}')
        if file_path.endswith('.wad.client'):
            extract_wad(file_path)
        elif file_path.endswith('.skn'):
            extract_skn(file_path)
        elif file_path.endswith('.skl'):
            extract_skl(file_path)
        elif file_path.endswith('.bin'):
            extract_bin(file_path)
    # write extracted hashes
    for h, (fh, _, _, w) in zip(hs, efhs):
        write_hash(h, fh, w)
        print(f'hash_helper: Finish: Extract: {fh}')

def clear_extracted():
    shutil.rmtree(lepath.abs(extracted_dir))
    os.makedirs(extracted_dir, exist_ok=True)
    print(f'hash_helper: Finish: Clear: {extracted_dir}')

def apply_paths(_cdtb_dir, _extracted_dir):
    global cdtb_dir, extracted_dir, bfhs, wfhs
    cdtb_dir = _cdtb_dir
    extracted_dir = _extracted_dir
    bfhs = (
        (f'{cdtb_dir}/hashes.binentries.txt', bsl1, bsl2, bw),
        (f'{cdtb_dir}/hashes.binhashes.txt', bsl1, bsl2, bw),
        (f'{cdtb_dir}/hashes.bintypes.txt', bsl1, bsl2, bw),
        (f'{cdtb_dir}/hashes.binfields.txt', bsl1, bsl2, bw),
        (f'{extracted_dir}/hashes.binentries.txt', bsl1, bsl2, bw),
        (f'{extracted_dir}/hashes.binhashes.txt', bsl1, bsl2, bw)
    )
    wfhs = (
        (f'{cdtb_dir}/hashes.game.txt', wsl1, wsl2, ww),
        (f'{cdtb_dir}/hashes.lcu.txt', wsl1, wsl2, ww),
        (f'{extracted_dir}/hashes.game.txt', wsl1, wsl2, ww)
    )

def init():
    apply_paths(
        stash.fetch('hash_helper.cdtb_dir', cdtb_dir),
        stash.fetch('hash_helper.extracted_dir', extracted_dir)
    )
    os.makedirs(cdtb_dir, exist_ok=True)
    os.makedirs(extracted_dir, exist_ok=True)
