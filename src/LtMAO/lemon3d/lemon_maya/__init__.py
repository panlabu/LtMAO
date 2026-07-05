
def install_plugin(pref_dir):
    # init
    import posixpath
    env_file = f'{pref_dir}/Maya.env'
    lemon_dir = posixpath.abspath('./src/LtMAO/lemon3d/lemon_maya')
    ltmao_dir = posixpath.abspath('.')
    envs = {}
    # read
    with open(env_file, 'a+', encoding='utf-8') as f:
        f.seek(0)
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, values = line.split('=', 1)
                envs[key.strip()] = values.strip().rstrip(';').split(';')
    # add ltmao and lemon3d to maya envs  
    paths = {
        'MAYA_PLUG_IN_PATH': [f'{lemon_dir}/plugins'],
        'MAYA_SHELF_PATH': [f'{lemon_dir}/prefs/shelves'],
        'XBMLANGPATH': [f'{lemon_dir}/prefs/icons'],
        'MAYA_SCRIPT_PATH': [f'{lemon_dir}/scripts'],
        'PYTHONPATH': [f'{ltmao_dir}/src', f'{ltmao_dir}/cpy/Lib/site-packages']
    }
    for key, values in paths.items():
        if key not in envs:
            envs[key] = values
        else:
            for value in values:
                if value not in envs[key]:
                    envs[key].append(value)
    # write
    with open(env_file, 'w', encoding='utf-8') as f:
        for key, values in envs.items():
            f.write(f'{key}={";".join(values)}\n')
    print(f'lemon_maya: Finish: Install plugin at: {pref_dir}')
    
