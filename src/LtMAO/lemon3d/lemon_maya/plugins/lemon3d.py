import traceback, sys
from maya import OpenMayaMPx as omMPx

def print_traceback(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            print(traceback.format_exc())
            raise
    return wrapper

@print_traceback
def register(mobject):
    ltmao_dir = omMPx.MFnPlugin(mobject, 'panlabu', '0.0.0').loadPath().replace('\\', '/').replace('/src/LtMAO/lemon3d/lemon_maya/plugins', '')
    # pythonpath can be overrided by windows environment variables
    # when that happend, maya.env pythonpath get ignored
    # so this part check and add ltmao paths to pythonpath
    pythonpaths = [f'{ltmao_dir}/src', f'{ltmao_dir}/cpy/Lib/site-packages']
    sys.path.extend([p for p in pythonpaths if p not in sys.path])
    # read ltmao version file and create plugin
    try:
        with open(f'{ltmao_dir}/version', 'r') as f:
            version = f.read()
    except:
        version = 'unknown'
    plugin = omMPx.MFnPlugin(mobject, 'panlabu', version)
    # register translators
    from LtMAO.lemon3d.lemon_maya.plugins.translator import skin#, anm, scb, mapgeo
    translators = (
        skin.sknImporter, skin.skinExporter, skin.sklImporter, skin.sklExporter,
        #anm.anmImporter, anm.anmExporter,
        #scb.scbImporter, scb.scoImporter, scb.scbExporter,
        #mapgeo.mapgeoImporter, mapgeo.mapgeoExporter
    )
    for translator in translators:
        plugin.registerFileTranslator(
            translator.name, 
            translator.pixmap, 
            translator.creator,
            translator.options_script,
            translator.options_string,
            False
        )

@print_traceback
def deregister(mobject):
    plugin = omMPx.MFnPlugin(mobject)
    from LtMAO.lemon3d.lemon_maya.plugins.translator import skin#, anm, scb, mapgeo
    translators = (
        skin.sknImporter, skin.skinExporter, skin.sklImporter, skin.sklExporter,
        #anm.anmImporter, anm.anmExporter,
        #scb.scbImporter, scb.scoImporter, scb.scbExporter,
        #mapgeo.mapgeoImporter, mapgeo.mapgeoExporter
    )
    for translator in translators:
        plugin.deregisterFileTranslator(translator.name)

def initializePlugin(mobject):
    register(mobject)

def uninitializePlugin(mobject):
    deregister(mobject)
