from maya import cmds
from maya.api import OpenMaya as om
import traceback, random, os.path

from cProfile import Profile

def print_traceback(func):
    def wrapper(*args, **kwargs):
        try:
            #with Profile() as pr:
            func(*args, **kwargs)
            #    pr.print_stats('time')
        except:
            print(traceback.format_exc())
            raise
    return wrapper

def ensure_ext(path, ext):
    if not path.endswith(ext):
        path += ext
    return path

def get_option_key_name(key):
    return 'lemon3d_'+key

def extract_name(path):
    name = os.path.split(path)[1].split('.')[0]
    if name[0].isdigit(): 
        name = 'l_' + name
    return name

"""
def mirrorX(skn=None, skl=None, anm=None, so=None, mapgeo=None):
    if mapgeo != None:
        for model in mapgeo.models:
            # flip matrix 
            matrix = MMatrix()
            MScriptUtil.createMatrixFromList([value for value in model.matrix], matrix)
            translate, rotate, scale = MayaTransformMatrix.decompose(MTransformationMatrix(matrix), MSpace.kWorld)
            translate.x = -translate.x
            rotate.y = -rotate.y
            rotate.z = -rotate.z
            matrix = MayaTransformMatrix.compose(translate, rotate, scale, MSpace.kWorld).asMatrix()
            model.matrix = pyRitoFile.structs.Matrix4(*[matrix(i, j) for i in range(4) for j in range(4)]) 
            # flip vertex
            for vertex in model.vertices:
                if pyRitoFile.mapgeo.MAPGEOVertexElementName.Position in vertex.value:
                    position = vertex.value[pyRitoFile.mapgeo.MAPGEOVertexElementName.Position]
                    position.x = -position.x
                if pyRitoFile.mapgeo.MAPGEOVertexElementName.Texcoord5 in vertex.value:
                    bush_vertex_animation = vertex.value[pyRitoFile.mapgeo.MAPGEOVertexElementName.Texcoord5]
                    bush_vertex_animation.x = -bush_vertex_animation.x
                if pyRitoFile.mapgeo.MAPGEOVertexElementName.Normal in vertex.value:
                    normal = vertex.value[pyRitoFile.mapgeo.MAPGEOVertexElementName.Normal]
                    normal.y = -normal.y
                    normal.z = -normal.z
"""

# error dialog
class FunnyError(Exception):
    ok_response = [
        'UwU', '<(\")', 'ok boomer', 'funny man', 'jesus', 'bruh', 'bro', 'please', 'man',
        'stop', 'get some help', 'haha', 'lmao', 'ay yo', 'SUS', 'sOcIEtY.', 'yeah', 'whatever',
        'gurl', 'fck', 'im ded', '(~`u`)~', 't(^u^t)', '(>w<)', 'xdd', 'cluegi', 'kappachungusdeluxe',
        'cap', 'L', 'W', 'cooked', 'bet', 'mid', 'sheesh', 'ur delulu'
    ]
    def __init__(self, text):
        cmds.confirmDialog(
            title=(t:=text.split(':', 1))[0],
            message=t[1:],
            button=(b:=random.choice(FunnyError.ok_response)),
            icon='critical',
            defaultButton=b
        )
