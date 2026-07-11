from maya import OpenMayaMPx as omMPx, cmds
from maya.api import OpenMaya as om, OpenMayaAnim as omAnim
from ..... import lepath, pyRitoFile
from . import helper

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
        pyRitoFile.anm.read(lepath.ensure_ext(anm_path, '.anm')),
        { 'reset_channel': 'reset_channel=0' not in options }
    )

def load_anm(anm, load_options):
    # ensure scene fps
    om.MTime.setUIUnit(om.MTime.kNTSCField if anm.fps > 59 else om.MTime.kNTSCFrame)
    ui_fps = om.MTime.uiUnit()
    # reset channel
    time0 = om.MTime(0.0, ui_fps)
    if load_options['reset_channel']:
        cmds.delete(all=True, channels=True)
        omAnim.MAnimControl.setCurrentTime(time0)
        offset = 0.0
    else:
        offset = omAnim.MAnimControl.currentTime().value
    timen = om.MTime(offset+anm.keyframe_count, ui_fps)
    # ensure animation range
    omAnim.MAnimControl.setMinMaxTime(time0, timen)
    omAnim.MAnimControl.setAnimationStartEndTime(time0, timen)
    omAnim.MAnimControl.setPlaybackSpeed(1.0)

    # find scene ik joints
    hash_elf = pyRitoFile.maths.hash_elf
    track_hashes = set(anm.tracks.keys())
    ik_joints = {}
    iterator = om.MItDag(om.MItDag.kDepthFirst, om.MFn.kJoint)
    while not iterator.isDone():
        ik_joint = omAnim.MFnIkJoint(iterator.getPath())
        joint_name = ik_joint.name()
        joint_hash = hash_elf(joint_name)
        if joint_hash in track_hashes:
            ik_joints[joint_hash] = (joint_name, ik_joint)
        iterator.next()
    if len(ik_joints) == 0:
        raise helper.FunnyError('ANM Importer: No matched joints found in scene, please import SKL first before import ANM.')

    # bind current pose to keyframe 0 - very helpful if its bind pose
    # this also create all curves, dont need MFnAnimCurve.create()
    joint_names = [joint_name for joint_name, _ in ik_joints.values()]
    omAnim.MAnimControl.setCurrentTime(time0)
    cmds.setKeyframe(
        joint_names,
        breakdown=False,
        hierarchy='none',
        controlPoints=False,
        shape=False,
        attribute=('tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz')
    )

    # all keyframe + 1 because keyframe 0 is bind as above
    offset += 1
    # get all rotation curves and change interpolation to none
    rcurve_names = [
        name
        for joint_name in joint_names
        for name in (f'{joint_name}.rx', f'{joint_name}.ry', f'{joint_name}.rz')
    ]
    cmds.rotationInterpolation(rcurve_names, convert='none')
    # add keys to curve
    times = {}
    for joint_hash, (_, ik_joint) in ik_joints.items():
        track = anm.tracks[joint_hash]
        # translate
        translate_curve = track.translate_curve
        if translate_curve:
            ttimes = [
                times[time] if time in times else times.setdefault(time, om.MTime(offset+time, ui_fps)) 
                for time in translate_curve.keys()
            ]
            txs, tys, tzs = zip(*translate_curve.values())
            txs = [-x for x in txs]
            omAnim.MFnAnimCurve(ik_joint.findPlug('tx', False)).addKeys(ttimes, txs)
            omAnim.MFnAnimCurve(ik_joint.findPlug('ty', False)).addKeys(ttimes, tys)
            omAnim.MFnAnimCurve(ik_joint.findPlug('tz', False)).addKeys(ttimes, tzs)
        # rotate
        rotate_curve = track.rotate_curve
        if rotate_curve:
            rtimes = [
                times[time] if time in times else times.setdefault(time, om.MTime(offset+time, ui_fps))
                for time in rotate_curve.keys()
            ]
            eulers = [
                (ex, ey, ez)
                for qx, qy, qz, qw in rotate_curve.values() 
                for ex, ey, ez in [om.MQuaternion(qx, -qy, -qz, qw).asEulerRotation()]
            ]
            exs, eys, ezs = zip(*eulers)
            omAnim.MFnAnimCurve(ik_joint.findPlug('rx', False)).addKeys(rtimes, exs)
            omAnim.MFnAnimCurve(ik_joint.findPlug('ry', False)).addKeys(rtimes, eys)
            omAnim.MFnAnimCurve(ik_joint.findPlug('rz', False)).addKeys(rtimes, ezs)
        # scale
        scale_curve = track.scale_curve
        if scale_curve:
            stimes = [
                times[time] if time in times else times.setdefault(time, om.MTime(offset+time, ui_fps))
                for time in scale_curve.keys()
            ]
            sxs, sys, szs = zip(*scale_curve.values())
            omAnim.MFnAnimCurve(ik_joint.findPlug('sx', False)).addKeys(stimes, sxs)
            omAnim.MFnAnimCurve(ik_joint.findPlug('sy', False)).addKeys(stimes, sys)
            omAnim.MFnAnimCurve(ik_joint.findPlug('sz', False)).addKeys(stimes, szs)
    # change all rotation curves interpolation to quaternion 
    cmds.rotationInterpolation(rcurve_names, convert='quaternionSlerp')
    # go to last time
    omAnim.MAnimControl.setCurrentTime(timen)

def dump_anm():
    # fps
    ui_fps = om.MTime.uiUnit() 
    fps = 60.0 if om.MTime(1.0, om.MTime.kSeconds).asUnits(ui_fps) > 59 else 30.0

    # ik joints
    Track = pyRitoFile.anm.Track
    hash_elf = pyRitoFile.maths.hash_elf
    ik_joints = {}
    iterator = om.MItDag(om.MItDag.kDepthFirst, om.MFn.kJoint)
    while not iterator.isDone():
        ik_joint = omAnim.MFnIkJoint(iterator.getPath())
        joint_name = ik_joint.name()
        joint_hash = hash_elf(joint_name)
        ik_joints[joint_hash] = (joint_name, ik_joint)
        iterator.next()

    # init tracks and get all times
    tracks = {}
    all_times = set()
    joint_times = {}
    for joint_hash, (joint_name, ik_joint) in ik_joints.items():
        # track
        tracks[joint_hash] = Track({}, {}, {})
        # time
        translate_times = set(cmds.keyframe(f'{joint_name}.tx', query=True, timeChange=True) or []) | set(cmds.keyframe(f'{joint_name}.ty', query=True, timeChange=True) or []) | set(cmds.keyframe(f'{joint_name}.tz', query=True, timeChange=True) or [])
        rotate_times = set(cmds.keyframe(f'{joint_name}.rx', query=True, timeChange=True) or []) | set(cmds.keyframe(f'{joint_name}.ry', query=True, timeChange=True) or []) | set(cmds.keyframe(f'{joint_name}.rz', query=True, timeChange=True) or [])
        scale_times = set(cmds.keyframe(f'{joint_name}.sx', query=True, timeChange=True) or []) | set(cmds.keyframe(f'{joint_name}.sy', query=True, timeChange=True) or []) | set(cmds.keyframe(f'{joint_name}.sz', query=True, timeChange=True) or [])
        translate_times = {t - 1 for t in translate_times if t >= 1}
        rotate_times = {t - 1 for t in rotate_times if t >= 1}
        scale_times = {t - 1 for t in scale_times if t >= 1}
        if not translate_times: translate_times.add(0)
        if not rotate_times: rotate_times.add(0)
        if not scale_times: scale_times.add(0)
        joint_times[joint_hash] = (translate_times, rotate_times, scale_times)
        all_times.update(translate_times, rotate_times, scale_times)
    all_times = list(sorted(all_times))

    # curves
    original_time = omAnim.MAnimControl.currentTime()
    space = om.MSpace.kTransform
    for time in all_times:
        omAnim.MAnimControl.setCurrentTime(om.MTime(time+1, ui_fps))
        for joint_hash, (joint_name, ik_joint) in ik_joints.items():
            track = tracks[joint_hash]
            translate_times, rotate_times, scale_times = joint_times[joint_hash]
            if time in translate_times:
                x, y, z = ik_joint.translation(space)
                track.translate_curve[time] = (-x, y, z)
            if time in rotate_times:
                x, y, z, w = ik_joint.rotation(asQuaternion=True)
                track.rotate_curve[time] = (x, -y, -z, w)
            if time in scale_times:
                track.scale_curve[time] = ik_joint.scale()
    omAnim.MAnimControl.setCurrentTime(original_time)


    return pyRitoFile.anm.Animation(
        None, None, None, None,
        None, None, None, fps, 
        None, tracks
    )

@helper.print_traceback
def write_anm(anm_path):
    pyRitoFile.anm.write(
        dump_anm(),
        lepath.ensure_ext(anm_path)
    )
