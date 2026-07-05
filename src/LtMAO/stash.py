import os, json, traceback
from . import lepath

s = {}
pref_dir = './pref'
stash_file = f'{pref_dir}/stash.json'

fetch = s.get
store = s.__setitem__

def load():
    try: 
        with open(stash_file, 'r', encoding='utf-8') as f:
            s.update(json.load(f))
    except Exception as e:
        print(f'stash: Error: Load {stash_file}: {e}')
        print(traceback.format_exc())

def save():
    with open(stash_file, 'w', encoding='utf-8') as f:
        json.dump(s, f, indent=4, ensure_ascii=False)

def init():
    os.makedirs(pref_dir, exist_ok=True)
    if not lepath.exists(stash_file):
        with open(stash_file, 'w') as f:
            f.write('{}')
    load()
