import json, os, shutil, traceback
import requests, pyzstd
from . import pyRitoFile

local_dir = './pref/mandown'
cache_dir = f'{local_dir}/cache'
loaded_file = f'{local_dir}/loaded.json'
version_file = f'{local_dir}/version'

loaded = {}

def parse(region, patch):
    session = requests.Session()
    print(f'mandown: Getting info: {region}/{patch}')
    # download manifest
    tget = session.get(f'https://raw.githubusercontent.com/Morilli/riot-manifests/master/LoL/{region}/windows/lol-game-client/{patch}')
    tget.raise_for_status()
    remote_file = tget.text
    local_file = os.path.join(cache_dir, remote_file.rsplit('/', 1)[-1])
    if not os.path.exists(local_file):
        mget = session.get(remote_file, stream=True)
        mget.raise_for_status()
        print(f'mandown: Downloading: {local_file}')
        with open(local_file, 'wb') as f:
            for chunk in mget.iter_content(1024**2):
                f.write(chunk)
    # parse manifest
    print(f'mandown: Parsing: {local_file}')
    manifest = pyRitoFile.manifest.read(local_file)
    # file infos
    dirs = {dir.id: dir for dir in manifest.dirs}
    cached_dirs = {}
    def get_path(item):
        if item.parent == item.id:
            return item.name
        parent_id = item.parent
        if parent_id not in cached_dirs:
            cached_dirs[parent_id] = get_path(dirs[parent_id])
        return f'{cached_dirs[parent_id]}/{item.name}'
    file_infos = {file.id: (file, get_path(file).lstrip('/')) for file in manifest.files}
    # chunk infos
    chunk_infos = {}
    for bundle in manifest.bundles:
        chunk_offset = 0
        for chunk in bundle.chunks:
            chunk_infos[chunk.id] = (chunk, chunk_offset, bundle.id)
            chunk_offset += chunk.compressed_size

    return (file_infos, chunk_infos)

def download(parsed, file_ids, output_dir):
    # init
    file_infos, chunk_infos = parsed
    bundles_dir = f'{cache_dir}/bundles'
    os.makedirs(bundles_dir, exist_ok=True)
    decompress = pyzstd.decompress
    bundle_base = 'https://lol.dyn.riotcdn.net/channels/public/bundles'
    session = requests.Session()
    stream_size = 1024 ** 2
    for file_id in file_ids:
        file, file_path = file_infos[file_id]
        local_file = f'{output_dir}/{file_path}'
        os.makedirs(os.path.dirname(local_file), exist_ok=True)
        print(f'mandown: Extracting: {local_file}')
        with open(local_file, 'wb') as lf:
            for chunk_id in file.chunk_ids:
                chunk, chunk_offset, bundle_id = chunk_infos[chunk_id]
                # download bundle 
                bundle_name = f'{bundle_id:016X}.bundle'
                local_bundle = f'{bundles_dir}/{bundle_name}'
                if not os.path.exists(local_bundle):
                    remote_bundle = f'{bundle_base}/{bundle_name}'
                    for _ in range(5):
                        try:
                            bget = session.get(remote_bundle, stream=True)
                            bget.raise_for_status()
                            print(f'mandown: Downloading: {local_bundle}')
                            local_bundle_tmp = f'{local_bundle}.tmp'
                            with open(local_bundle_tmp, 'wb') as f:
                                for content in bget.iter_content(stream_size):
                                    f.write(content)
                            os.rename(local_bundle_tmp, local_bundle)
                            break
                        except Exception as e:
                            print(f'mandown: Error: Download bundle {local_bundle}: {e}\nTrying again...')
                    else:
                        raise Exception(f'mandown: Error: Download bundle {local_bundle} failed, too many attemps.')
                # write chunk data from bundle
                with open(local_bundle, 'rb') as bf:
                    bf.seek(chunk_offset)
                    lf.write(decompress(bf.read(chunk.compressed_size)))
    print(f'mandown: Fininshed download {len(file_ids)} files at {output_dir}.')
    # delete cache only if we succed, otherwise we can re use cache again.
    shutil.rmtree(bundles_dir)

def init(region_combobox):
    os.makedirs(local_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)
    # sync 
    need_local = True
    session = requests.Session()
    try:
        # local version
        local_version = None
        if os.path.exists(version_file):
            with open(version_file, 'r', encoding='utf-8') as f:
                local_version = f.read()
        # remote version
        vget = session.get('https://api.github.com/repos/Morilli/riot-manifests/commits?ref=master')
        vget.raise_for_status()
        remote_version = vget.json()[0]['sha']
        # if new version 
        if local_version != remote_version:
            # regions and patches
            rget = session.get('https://api.github.com/repos/Morilli/riot-manifests/contents/LoL?ref=master')
            rget.raise_for_status()
            for r in rget.json():
                region = r['name']
                pget = session.get(f'https://api.github.com/repos/Morilli/riot-manifests/contents/LoL/{region}/windows/lol-game-client?ref=master')
                pget.raise_for_status()
                loaded[region] = [p['name'] for p in pget.json()]
            # save loaded
            with open(loaded_file, 'w', encoding='utf-8') as f:
                json.dump(loaded, f, indent=4, ensure_ascii=False)
            # save version
            with open(version_file, 'w', encoding='utf-8') as f:
                f.write(remote_version)
            # dont need to read local loaded anymore
            need_local = False
        print(f'mandown: Finish: Sync regions and patches.')
    except Exception as e:
        print(f'mandown: Error: Sync remote: {e}')
    # read local loaded
    if need_local:
        try:
            with open(loaded_file, 'r', encoding='utf-8') as f:
                loaded.update(json.load(f))
        except Exception as e:                                     
            print(f'mandown: Error: Read local: {e}')
    # qt 
    if region_combobox:
        region_combobox.addItems(loaded.keys())
