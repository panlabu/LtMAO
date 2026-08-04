from . import pyRitoFile
import os, os.path, json

def unpack(wad_file, raw_dir, lookup, filters=None):
    # init
    is_xxh64_hex = pyRitoFile.maths.is_xxh64_hex
    read_data = pyRitoFile.wad.read_data
    print(f'wad_tool: Start: Unpack WAD: {wad_file}')
    # read and unhash wad
    wad = pyRitoFile.wad.read(wad_file)
    pyRitoFile.wad.unhash(wad, lookup)
    # filter chunks
    target_chunks = [chunk for chunk in wad.chunks if filters is None or chunk._hash in filters]
    # get basename dirname of each file
    files = [None] * len(target_chunks)
    dirs = set()
    for chunk_id, chunk in enumerate(target_chunks):
        dirname, basename = os.path.split(os.path.join(raw_dir, chunk._hash))
        files[chunk_id] = (dirname, basename)
        dirs.add(dirname)
    # create dirs
    for dirname in dirs:
        os.makedirs(dirname, exist_ok=True)
    # extract files
    hashed_files = {}
    with open(wad_file, 'rb') as bs:
        for chunk_id, chunk in enumerate(target_chunks):
            # read chunk data to get chunk.extension
            chunk_data = read_data(chunk, bs)
            dirname, basename = files[chunk_id]
            # add extension to hashed file
            if is_xxh64_hex(chunk._hash) is not None and chunk.extension is not None:
                basename +=  f'.{chunk.extension}'
            file = os.path.join(dirname, basename)
            # long basename or match existed dir
            if len(basename) > 255 or os.path.isdir(file):
                basename = f'{chunk.hash:016x}.{chunk.extension}' if chunk.extension is not None else f'{chunk.hash:016x}'
                file =  os.path.join(raw_dir, basename)
                hashed_files[basename] = chunk._hash
            # write chunk data to file
            with open(file, 'wb') as f:
                f.write(chunk_data)
    # remove empty dirs
    for root, dirs, files in os.walk(raw_dir, topdown=False):
        for dir in dirs:
            try:
                os.rmdir(os.path.join(root, dir))
            except OSError:
                pass
    # write hashed bins json
    if len(hashed_files) > 0:
        with open(os.path.join(raw_dir, 'hashed_files.json'), 'w', encoding='utf-8') as f:
            json.dump(hashed_files, f, indent=4, ensure_ascii=False)

def pack(raw_dir, wad_file):
    # init 
    is_xxh64_hex = pyRitoFile.maths.is_xxh64_hex
    hash_xxh64 = pyRitoFile.maths.hash_xxh64
    print(f'wad_tool: Start: Pack WAD: {raw_dir}')
    # chunk hashes = [(hash of rel_file, file to read data later)]
    chunk_buffers = [
        # if rel_file is hex.ext, convert hex to int 
        (h, f) if (h:=is_xxh64_hex((rf:=os.path.relpath(f, raw_dir)).split('.', 1)[0])) is not None
        # otherwise, hash_xxh64(rel_file)
        else (hash_xxh64(rf.replace('\\', '/')), f)
        # loop files
        for root, dirs, files in os.walk(raw_dir)
        for file in files
        # filter out hashed_files.json
        if not (f:=os.path.join(root, file)).endswith('hashed_files.json')
    ]
    # write wad
    pyRitoFile.wad.write_full(chunk_buffers, wad_file)
