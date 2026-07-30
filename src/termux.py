import os, os.path

# ensure this script always work with ltmao dir
os.chdir('/storage/emulated/0/ltmao')

# test uvee
def tu():
    from LtMAO import uvee
    uvee.uvee('akshan_base_w_geometryburst01.scb')
    uvee.uvee('akshan_base.skn')

tu()

# test mandown
def tmd():
    from LtMAO import mandown
    mandown.init(None)
    file_infos, chunk_infos = mandown.parse('VN2', '16.15.7987775.txt')
    for file_id, (file, _) in file_infos.items():
        if file.name == 'Akshan.wad.client':
            break
    mandown.download((file_infos, chunk_infos), [file_id], '.')

# test wt
def twt():
    from LtMAO import hash_helper, wad_tool, pyRitoFile
    hash_helper.read_hashes(False, True)
    wad = pyRitoFile.wad.read('Akshan.wad.client')
    pyRitoFile.wad.unhash(wad, hash_helper.lookup)
    fs = [chunk._hash for chunk in wad.chunks if chunk._hash.endswith(('.skn', '.scb'))]
    wad_tool.unpack('Akshan.wad.client', 'Akshan.wad', hash_helper.lookup, fs)


# hash_helper test
def thh():
    from LtMAO import hash_helper
    hash_helper.init()
    hash_helper.sync_hashes()

# test pyrf
def tpyrf():
    from LtMAO import pyRitoFile, hash_helper
    hash_helper.read_hashes(True, True)
    a = pyRitoFile.bin.read('skin0.bin')
    pyRitoFile.bin.unhash(a, hash_helper.lookup)
    pyRitoFile.bin.dump(a, 'skin0.py')

# test skl
def tskl():
    from LtMAO import pyRitoFile
    s = pyRitoFile.skl.read('jhin.skl')
    for j in s.joints:
        print(j.name, j.hash)
    print()
    pyRitoFile.skl.write(s, 'b.skl')
    b = pyRitoFile.skl.read('b.skl')
    for j in b.joints:
        print(j.name, j.hash)

