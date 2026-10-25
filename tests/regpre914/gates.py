#!/usr/bin/env python3
# Б TEST57: ворота регионов уровня (хвост REGF/REG1/GAT1 в level.shr, как читает main_levels.h) -> json [{lv, i, c:[x,y,z], load}]
# использование: gates.py НАБОР_PSP_GAME_SHARTEST15 > gates.json
import struct, sys, json, os
def gates(path, lv):
    d = open(path, 'rb').read(); out = []
    at = -1; k = d.rfind(b'REGF')   # хвост REGF (смещение REG1) прямо перед PVS1 или в конце файла — как читает main_levels.h
    while k >= 0 and at < 0:
        a = struct.unpack_from('<I', d, k + 4)[0]
        if a + 32 <= len(d) and d[a:a + 4] == b'REG1': at = a
        k = d.rfind(b'REGF', 0, k)
    if at < 0: return out
    nreg, w, h = struct.unpack_from('<3I', d, at + 8)
    ver = struct.unpack_from('<I', d, at + 4)[0]
    mo = at + 32 + 16 * nreg; go = (mo + w * h * 2 + 15) & ~15
    if ver < 2 or d[go:go + 4] != b'GAT1': return out
    ng, npl = struct.unpack_from('<2I', d, go + 4)
    for i in range(ng):
        o = go + 16 + 68 * i
        c = struct.unpack_from('<3f', d, o); load = struct.unpack_from('<H', d, o + 60)[0]
        out.append({'lv': lv, 'i': i, 'c': [round(v, 1) for v in c], 'load': load})
    return out
if __name__ == '__main__':
    root = sys.argv[1]; res = []
    for lv in range(1, 8):
        p = os.path.join(root, 'level.shr' if lv == 1 else f'l{lv}/level.shr')
        if os.path.exists(p): res += gates(p, lv)
    json.dump(res, sys.stdout, ensure_ascii=False)
