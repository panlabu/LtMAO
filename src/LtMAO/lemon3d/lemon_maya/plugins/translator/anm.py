from maya import OpenMayaMPx as omMPx, cmds
from maya.api import OpenMaya as om, OpenMayaAnim as omAnim
from ..... import pyRitoFile
from . import helper
import os.path

class anmImporter(omMPx.MPxFileTranslator):
    name = 'League of Legends: ANM'
    extension = 'anm'
    pixmap = ''
    options_script = 'ANMImporterOptions'
    options_string = 'reset_channel=1'

    @classmethod
    def creator(cls):
        return omMPx.asMPxPtr(cls())

    def __init__(self):
        omMPx.MPxFileTranslator.__init__(self)

    def haveReadMethod(self):
        return True
    
    def defaultExtension(self):
        return self.extension

    def filter(self):
        return f'*.{self.extension}'
    
    def identifyFile(self, file, buffer, size):
        if file.fullName().lower().endswith(f'.{self.extension}'):
            return omMPx.MPxFileTranslator.kIsMyFileType
        return omMPx.MPxFileTranslator.kNotMyFileType

    def reader(self, file, options, access):
        read_anm(file.fullName(), options)
        return True

class anmExporter(omMPx.MPxFileTranslator):
    name = 'League of Legends: ANM Export'
    extension = 'anm'
    pixmap = ''
    options_script = ''
    options_string = ''

    @classmethod
    def creator(cls):
        return omMPx.asMPxPtr(cls())

    def __init__(self):
        omMPx.MPxFileTranslator.__init__(self)
    
    def haveWriteMethod(self):
        return True

    def defaultExtension(self):
        return self.extension

    def filter(self):
        return f'*.{self.extension}'
    
    def identifyFile(self, file, buffer, size):
        if file.fullName().lower().endswith(f'.{self.extension}'):
            return omMPx.MPxFileTranslator.kIsMyFileType
        return omMPx.MPxFileTranslator.kNotMyFileType

    def writer(self, file, options, access):
        write_anm(file.fullName())
        return True

@helper.print_traceback
def read_anm(anm_path, options):
    load_anm(
        pyRitoFile.anm.read(helper.ensure_ext(anm_path, '.anm')),
        { 'reset_channel': 'reset_channel=0' not in options }
    )

def load_anm(anm, load_options):
    # find scene curves
    hash_elf = pyRitoFile.maths.hash_elf
    createAnimCurve = omAnim.MAnimUtil.createAnimCurve
    joint_hashes = set(anm.joint_hashes)
    curves = {}
    joint_names = []
    dg_modifier = om.MDGModifier()
    iterator = om.MItDag(om.MItDag.kDepthFirst, om.MFn.kJoint)
    while not iterator.isDone():
        ik_joint = omAnim.MFnIkJoint(iterator.getPath())
        joint_name = ik_joint.name()
        joint_hash = hash_elf(joint_name)
        if joint_hash in joint_hashes:
            curves[joint_hash] = (
                createAnimCurve(ik_joint.findPlug('tx', False)),
                createAnimCurve(ik_joint.findPlug('ty', False)),
                createAnimCurve(ik_joint.findPlug('tz', False)),
                createAnimCurve(ik_joint.findPlug('rx', False)),
                createAnimCurve(ik_joint.findPlug('ry', False)),
                createAnimCurve(ik_joint.findPlug('rz', False)),
                createAnimCurve(ik_joint.findPlug('sx', False)),
                createAnimCurve(ik_joint.findPlug('sy', False)),
                createAnimCurve(ik_joint.findPlug('sz', False))
            )
            joint_names.append(joint_name)
        iterator.next()
    if len(joint_names) == 0:
        raise helper.FunnyError('ANM Importer: No matched joints found in scene, please import SKL first before import ANM.')
    dg_modifier.doIt()

    # fps
    om.MTime.setUIUnit(om.MTime.kNTSCField if anm.fps > 59.0 else om.MTime.kNTSCFrame)
    ui_fps = om.MTime.uiUnit()

    # times and timeline
    if load_options['reset_channel']:
        cmds.delete(joint_names, channels=True)
        offset = 0.0
    else:
        offset = omAnim.MAnimControl.animationEndTime().value + 1.0
    times = {keyframe: om.MTime(offset + keyframe, ui_fps) for keyframe in anm.keyframes}
    time_start = om.MTime(0.0, ui_fps)
    time_end = times[anm.keyframes[-1]]
    omAnim.MAnimControl.setMinMaxTime(time_start, time_end)
    omAnim.MAnimControl.setAnimationStartEndTime(time_start, time_end)
    omAnim.MAnimControl.setPlaybackSpeed(1.0)

    # rotation curves interpolation to none
    rcurve_names = [
        name
        for joint_name in joint_names
        for name in (f'{joint_name}.rx', f'{joint_name}.ry', f'{joint_name}.rz')
    ]
    cmds.rotationInterpolation(rcurve_names, convert='none')

    # add keys to curves
    translate_curves = anm.translate_curves
    rotate_curves = anm.rotate_curves
    scale_curves = anm.scale_curves
    for joint_hash, (tx, ty, tz, rx, ry, rz, sx, sy, sz) in curves.items():
        # translate
        translate_curve = translate_curves[joint_hash]
        if translate_curve:
            ttimes = [times[time] for time in translate_curve]
            txs, tys, tzs = zip(*translate_curve.values())
            txs = [-x for x in txs]
            omAnim.MFnAnimCurve(tx).addKeys(ttimes, txs)
            omAnim.MFnAnimCurve(ty).addKeys(ttimes, tys)
            omAnim.MFnAnimCurve(tz).addKeys(ttimes, tzs)
        # rotate
        rotate_curve = rotate_curves[joint_hash]
        if rotate_curve:
            rtimes = [times[time] for time in rotate_curve]
            eulers = [
                (ex, ey, ez)
                for qx, qy, qz, qw in rotate_curve.values() 
                for ex, ey, ez in [om.MQuaternion(qx, -qy, -qz, qw).asEulerRotation()]
            ]
            exs, eys, ezs = zip(*eulers)
            omAnim.MFnAnimCurve(rx).addKeys(rtimes, exs)
            omAnim.MFnAnimCurve(ry).addKeys(rtimes, eys)
            omAnim.MFnAnimCurve(rz).addKeys(rtimes, ezs)
        # scale
        scale_curve = scale_curves[joint_hash]
        if scale_curve:
            stimes = [times[time] for time in scale_curve]
            sxs, sys, szs = zip(*scale_curve.values())
            omAnim.MFnAnimCurve(sx).addKeys(stimes, sxs)
            omAnim.MFnAnimCurve(sy).addKeys(stimes, sys)
            omAnim.MFnAnimCurve(sz).addKeys(stimes, szs)

    # rotation curves interpolation to quaternion 
    cmds.rotationInterpolation(rcurve_names, convert='quaternionSlerp')

def dump_anm():
    # fps
    ui_fps = om.MTime.uiUnit() 
    fps = 60.0 if om.MTime(1.0, om.MTime.kSeconds).asUnits(ui_fps) > 59.0 else 30.0

    # joint hashes
    hash_elf = pyRitoFile.maths.hash_elf
    ik_joints = {}
    iterator = om.MItDag(om.MItDag.kDepthFirst, om.MFn.kJoint)
    while not iterator.isDone():
        ik_joint = omAnim.MFnIkJoint(iterator.getPath())
        joint_name = ik_joint.name()
        joint_hash = hash_elf(joint_name)
        ik_joints[joint_hash] = ik_joint
        iterator.next()
    joint_hashes = [*ik_joints]

    # keyframes 
    start = round(omAnim.MAnimControl.animationStartTime().value)
    end = round(omAnim.MAnimControl.animationEndTime().value)
    keyframe_count = end - start + 1
    keyframes = tuple(range(keyframe_count))

    # curves
    space = om.MSpace.kTransform
    translate_curves = {}
    rotate_curves = {}
    scale_curves = {}
    for joint_hash in joint_hashes:
        translate_curves[joint_hash] = {}
        rotate_curves[joint_hash] = {}
        scale_curves[joint_hash] = {}
    time_return = omAnim.MAnimControl.currentTime()
    for keyframe in keyframes:
        omAnim.MAnimControl.setCurrentTime(om.MTime(start+keyframe, ui_fps))
        for joint_hash, ik_joint in ik_joints.items():
            # translate
            tx, ty, tz = ik_joint.translation(space)
            translate_curves[joint_hash][keyframe] = (-tx, ty, tz)
            # rotate
            qx, qy, qz, qw = ik_joint.rotation(asQuaternion=True)
            rotate_curves[joint_hash][keyframe] = (qx, -qy, -qz, qw)
            # scale
            scale_curves[joint_hash][keyframe] = ik_joint.scale()
    omAnim.MAnimControl.setCurrentTime(time_return)

    return pyRitoFile.anm.Animation(
        None, None, None, None,
        fps, keyframes, joint_hashes,
        translate_curves, rotate_curves, scale_curves
    )

@helper.print_traceback
def write_anm(anm_path):
    pyRitoFile.anm.write(
        dump_anm(),
        helper.ensure_ext(anm_path, '.anm')
    )
