import cProfile, pstats
from LtMAO import hash_helper, lepath, pyRitoFile

def test():
    skn = pyRitoFile.skn.read('D:/durian_petholder.skn')
    skl = pyRitoFile.skl.read('D:/durian_petholder.skl')
    for joint in skl.joints:
        print(joint.name)
    
def db(func):
    with cProfile.Profile() as profile:
        func()
    stats = pstats.Stats(profile)
    stats.sort_stats(pstats.SortKey.TIME)
    stats.print_stats(20)

test()