import cProfile, pstats
from LtMAO import hash_helper

def test():
    hash_helper.extract('D:/Map11.wad.client')
    
def db(func):
    with cProfile.Profile() as profile:
        func()
    stats = pstats.Stats(profile)
    stats.sort_stats(pstats.SortKey.TIME)
    stats.print_stats(20)

db(test)