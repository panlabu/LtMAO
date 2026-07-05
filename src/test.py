import cProfile, pstats
from LtMAO import hash_helper, lepath

def test():
    print(lepath.abs('D:/'))
    
def db(func):
    with cProfile.Profile() as profile:
        func()
    stats = pstats.Stats(profile)
    stats.sort_stats(pstats.SortKey.TIME)
    stats.print_stats(20)

test()