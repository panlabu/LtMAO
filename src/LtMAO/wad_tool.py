from . import lepath, pyRitoFile
import os, json

def unpack(wad_file, raw_dir, lookup, filter=None):
    print(f'wad_tool: Start:  Unpack WAD: {wad_file}')
    # read wad
    wad = pyRitoFile.wad.read(wad_file)
    pyRitoFile.wad.unhash(wad, lookup)
    # filter chunks
    target_chunks = [chunk for chunk in wad.chunks if filter is None or chunk._hash in filter]
    # create dirs
    file_paths = {}
    dirnames = set()
    for chunk in target_chunks:
        dirname, basename = lepath.split(lepath.join(raw_dir, chunk._hash))
        file_paths[chunk.hash] = (dirname, basename)
        os.makedirs(dirname, exist_ok=True)
        dirnames.add(dirname)
    # extract files
    is_hex = pyRitoFile.wad.is_hex
    read_data = pyRitoFile.wad.read_data
    hashed_files = {}
    with open(wad_file, 'rb') as bs:
        for chunk in target_chunks:
            # read chunk data 
            chunk_data = read_data(chunk, bs)
            dirname, basename = file_paths[chunk.hash]
            # try add extension to hashed file
            if is_hex(chunk._hash) and chunk.extension is not None:
                basename +=  f'.{chunk.extension}'
            file_path = lepath.join(dirname, basename)
            # long basename or match existed dirname
            if len(basename) > 255 or file_path in dirnames:
                basename = f'{chunk.hash:016x}.{chunk.extension}' if chunk.extension is not None else f'{chunk.hash:016x}'
                file_path =  lepath.join(raw_dir, basename)
                hashed_files[basename] = chunk._hash
            # write out chunk data to file
            with open(file_path, 'wb') as f:
                f.write(chunk_data)
    # remove empty dirs
    for root, dirs, files in os.walk(raw_dir, topdown=False):
        if len(os.listdir(root)) == 0:
            os.rmdir(root)
    # write hashed bins json
    if len(hashed_files) > 0:
        with open(lepath.join(raw_dir, 'hashed_files.json'), 'w+', encoding='utf-8') as f:
            json.dump(hashed_files, f, indent=4, ensure_ascii=False)


def pack(raw_dir, wad_file):
    print(f'wad_tool: Start:  Pack WAD: {raw_dir}')
    # create wad first with only infos
    chunk_datas = []
    chunk_hashes = []
    for root, dirs, files in os.walk(raw_dir):
        for file in files:
            # skip hashed bins json
            if file == 'hashed_files.json':
                continue
            # prepare chunk datas
            file_path = lepath.join(root, file)
            chunk_datas.append(file_path)

            # check hashed files
            # hashed files are in root of the directory
            # and also be a valid hexadecimal int file name
            basename = os.path.basename(file)
            relative_path = lepath.rel(file_path, raw_dir)
            if pyRitoFile.wad.WADHasher.is_hash(basename.split('.')[0]) and relative_path == basename:
                file_path = basename.split('.')[0]
                chunk_hashes.append(file_path)
            else:
                chunk_hashes.append(lepath.rel(file_path, raw_dir))
    # write wad
    wad = pyRitoFile.wad.WAD()
    wad.chunks = [pyRitoFile.wad.WADChunk.default()
                  for id in range(len(chunk_hashes))]
    wad.write(wad_file)
    # write wad chunk
    with pyRitoFile.stream.BytesStream.updater(wad_file) as bs:
        for id, chunk in enumerate(wad.chunks):
            with open(chunk_datas[id], 'rb') as f:
                chunk_data = f.read()
            chunk.write_data(bs, id, chunk_hashes[id], chunk_data, previous_chunks=wad.chunks[:id])
            chunk.free_data()
            print(f'wad_tool: Finish: Pack: {chunk.hash}')

