import cProfile, pstats

def test():
    from LtMAO import wad_tool
    wad_tool.pack('D:/Lulu.wad', 'D:/a.wad.client')
    #no_skin.full('D:/Game/DATA/FINAL/Champions', 'D:/')
    
def db(func):
    with cProfile.Profile() as profile:
        func()
    stats = pstats.Stats(profile)
    stats.sort_stats(pstats.SortKey.TIME)
    stats.print_stats(20)

if __name__ == '__main__':
    test()