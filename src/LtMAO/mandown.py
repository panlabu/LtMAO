import requests, json, os, shutil
import pyzstd
from . import lepath, pyRitoFile

local_dir = r'.\pref\mandown'
cache_dir = rf'{local_dir}\cache'
loaded_file = rf'{local_dir}\loaded.json'
version_file = rf'{local_dir}\version'

loaded = {}

def get_version():
    get = requests.get('https://api.github.com/repos/Morilli/riot-manifests/commits?ref=master')
    get.raise_for_status()
    return get.json()[0]['sha']
    
def get_regions():
    get = requests.get('https://api.github.com/repos/Morilli/riot-manifests/contents/LoL?ref=master')
    get.raise_for_status()
    return [r['name'] for r in get.json()]

def get_patches(region):
    get = requests.get(f'https://api.github.com/repos/Morilli/riot-manifests/contents/LoL/{region}/windows/lol-game-client?ref=master')
    get.raise_for_status()
    return [p['name'] for p in get.json()]

def get_manifest_url(region, patch):
    get = requests.get(f'https://raw.githubusercontent.com/Morilli/riot-manifests/master/LoL/{region}/windows/lol-game-client/{patch}')
    get.raise_for_status()
    return get.text

class Mandown:
    def __init__(self, region, patch):
        print(f'mandown: Getting info: {region} {patch}')
        # download manifest
        remote_file = get_manifest_url(region, patch)
        local_file = lepath.join(cache_dir, remote_file.split('/')[-1])
        if not lepath.exists(local_file):
            get = requests.get(remote_file, stream=True)
            get.raise_for_status()
            print(f'mandown: Downloading: {local_file}')
            chunk_size = 1024**2
            with open(local_file, 'wb') as f:
                for chunk in get.iter_content(chunk_size):
                    f.write(chunk)
        # read downloaded manifest
        print(f'mandown: Parsing: {local_file}')
        manifest = pyRitoFile.manifest.read(local_file)
        # getting info
        self.dirs = [manifest.body.Dirs(i) for i in range(manifest.body.DirsLength())]
        self.files = [manifest.body.Files(i) for i in range(manifest.body.FilesLength())]
        def get_fullname(item):
            if isinstance(item, pyRitoFile.manifest.File):
                dir_id = item.DirId()
                return get_fullname(next((dir for dir in self.dirs if dir.Id() == dir_id), None)) + rf'\{item.Name().decode()}'
            parent_id = item.Parent()
            if parent_id == item.Id():
                return item.Name().decode()
            return get_fullname(next((dir for dir in self.dirs if dir.Id() == parent_id), None)) + rf'\{item.Name().decode()}'
        # why we map with a list of tuple but not variable of object
        # well we use flatbuffers module and its so bad, that why
        self.dir_dict = {
            dir.Id(): (dir.Name().decode(), dir.Parent())
            for dir in self.dirs
        }
        self.file_dict = {
            file.Id(): (file.Name().decode(), file.DirId(), get_fullname(file).lstrip('\\'), [file.ChunkIds(i) for i in range(file.ChunkIdsLength())])
            for file in self.files
        }
        self.chunk_dict = {}
        for i in range(manifest.body.BundlesLength()):
            bundle = manifest.body.Bundles(i)
            chunk_offset = 0
            for j in range(bundle.ChunksLength()):
                chunk = bundle.Chunks(j)
                chunk_size = chunk.CompressedSize()
                self.chunk_dict[chunk.Id()] = (bundle.Id(), chunk_offset, chunk_size)
                chunk_offset += chunk_size

    def download(self, file_ids, output_dir):
        def try_download_bundle(local_bundle, remote_bundle, try_count):
            # this function first downlaod a bundle
            # if fail, redownload bundle again
            # until fail 5 times, remove the local bundle and raise error 
            if try_count == 5:
                if lepath.exists(local_bundle):
                    os.remove(local_bundle)
                print(f'mandown: Error: Download bundle {local_bundle} failed, too many attemps.')
            try:
                get = requests.get(remote_bundle, stream=True)
                get.raise_for_status()
                print(f'mandown: Downloading: {local_bundle}')
                with open(local_bundle, 'wb') as f:
                    for content in get.iter_content(1024**2):
                        f.write(content)
            except Exception as e:
                print(f'mandown: Error: Download bundle {local_bundle}: {e}')
                if lepath.exists(local_bundle):
                    os.remove(local_bundle) 
                try_download_bundle(local_bundle, remote_bundle, try_count+1)


        decompress = pyzstd.decompress
        bundle_base = 'https://lol.dyn.riotcdn.net/channels/public/bundles'
        for file_id in file_ids:
            local_file = rf'{output_dir}\{self.file_dict[file_id][2]}'
            os.makedirs(os.path.dirname(local_file), exist_ok=True)
            print(f'mandown: Extracting: {local_file}')
            with open(local_file, 'wb') as lf:
                for chunk_id in self.file_dict[file_id][3]:
                    # download bundle if need
                    bundle_name = f'{self.chunk_dict[chunk_id][0]:016X}.bundle'
                    local_bundle = rf'{cache_dir}\bundles\{bundle_name}'
                    if not lepath.exists(local_bundle):
                        try_download_bundle(local_bundle, f'{bundle_base}/{bundle_name}', 0)
                    # read chunk data then write
                    with open(local_bundle, 'rb') as bf:
                        bf.seek(self.chunk_dict[chunk_id][1])
                        lf.write(decompress(bf.read(self.chunk_dict[chunk_id][2])))
        print(f'mandown: Fininshed download {len(file_ids)} files at {output_dir}.')
        # delete cache only if we succed, otherwise we can re use cache again.
        shutil.rmtree(rf'{cache_dir}\bundles')

def init(region_combobox):
    os.makedirs(local_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)

    global loaded    
    need_local = True
    try:
        # read local and remote
        local_commit = None
        if lepath.exists(version_file):
            with open(version_file, 'r', encoding='utf-8') as f:
                local_commit = f.read()
        remote_commit = get_version()
        # if remote is a new 
        if local_commit != remote_commit:
            # save remote as local
            with open(version_file, 'w+', encoding='utf-8') as f:
                f.write(remote_commit)
            # get regions and patches
            regions = get_regions()
            loaded = { r: get_patches(r) for r in regions }
            # save loaded to a file
            with open(loaded_file, 'w+', encoding='utf-8') as f:
                json.dump(loaded, f, indent=4, ensure_ascii=False)
            # dont need to read local loaded anymore
            need_local = False
    except Exception as e:
        print(f'mandown: Error: Sync remote: {e}')
    # read local loaded
    if need_local:
        try:
            with open(loaded_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
        except Exception as e:                                     
            print(f'mandown: Error: Read local: {e}')

    region_combobox.addItems(loaded.keys())
