import sys,re
L=[l for l in open(sys.argv[1],errors='ignore') if l.startswith('LOADACC')]
def g(l,k): return int(float(re.search(k+r'=(\d+)',l).group(1)))
late=sum(int(re.search(r'late=(\d+)/',l).group(1)) for l in L); ld=sum(g(l,'ld') for l in L); slow=sum(g(l,'slow') for l in L)
print('сек',len(L),'клеток',ld,'кадров с недогрузом',late,'медленных >100мс',slow,'худшая задержка мс',max(g(l,'latmax') for l in L),'макс очередь',max(g(l,'q') for l in L),'макс cand',max(g(l,'cand') for l in L))
