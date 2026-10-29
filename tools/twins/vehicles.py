# Близнецы · В18: машины в памяти оригинала по метке класса (три указателя на таблицы за 80, 48 и 16 байт до матрицы: 0x47ac58, 0x484778, 0x484030 —
# общие у машины игрока 0xa21870 и полицейской 0xa257e0). Машины трафика (минивэн) этой меткой НЕ находятся: у них свой класс.
#   python3 tools/twins/vehicles.py СНИМОК.p2s …
import sys, struct, math, re
sys.path.insert(0,'/Users/USER/Downloads/shar-psp/tools/ps2ref'); import dig
def vehicles(snap):
    ee=bytes(dig.load_ee(snap)); out=[]
    for m in re.finditer(re.escape(struct.pack('<I',0x47ac58)), ee):
        a=m.start()
        if a%4 or a+0x80>len(ee): continue
        if struct.unpack_from('<I',ee,a+32)[0]!=0x484778 or struct.unpack_from('<I',ee,a+64)[0]!=0x484030: continue
        mat=a+80; f=struct.unpack_from('<16f',ee,mat); v=struct.unpack_from('<3f',ee,mat+0x40)
        name=''
        out.append(dict(addr=mat, pos=f[12:15], vel=v, speed=math.hypot(v[0],v[2])))
    return out
if __name__=='__main__':
    for snap in sys.argv[1:]:
        vs=vehicles(snap); print(snap.split('/')[-2:], 'машин-объектов', len(vs))
        for v in sorted(vs, key=lambda v: math.hypot(v['pos'][0]-215, v['pos'][2]+170)):
            d=math.hypot(v['pos'][0]-215, v['pos'][2]+170)
            print(f"  {v['addr']:#09x} ({v['pos'][0]:8.1f},{v['pos'][1]:6.1f},{v['pos'][2]:8.1f}) d={d:6.1f} v={v['speed']:5.1f}")
