#!/usr/bin/env python3
"""Клон hop_to_L<K>.iso (Стенд3) со стартом героя уровня K сразу в своей машине: в levelKK/m1sdi.mfk
SetMissionResetPlayerOutCar(..., "levelK_carstart") -> SetMissionResetPlayerInCar("levelK_carstart"), SetInitialWalk убран.
python3 -I tools/twins/ps2s_lv_incar.py K → build/ps2stend/iso/lv<K>_incar.iso"""
import re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ps2_car_swap as S
HOPDIR = Path('/Users/USER/Downloads/shar-psp/build/twins/ps2stend3_iso')
def main(k):
    src = HOPDIR / f'hop_to_L{k}.iso'; dst = S.OUT / f'lv{k}_incar.iso'; S.OUT.mkdir(parents=True, exist_ok=True)
    if dst.exists(): dst.unlink()
    subprocess.run(['cp', '-c', str(src), str(dst)], check=True)
    rel = f'scripts/missions/level0{k}/m1sdi.mfk'; d = (S.GAME / rel).read_bytes()
    m = re.search(rb'SetMissionResetPlayerOutCar\("[^"]*",\s*"(level%d_carstart)"\);' % k, d); assert m, 'нет OutCar'
    d = d[:m.start()] + b'SetMissionResetPlayerInCar("' + m.group(1) + b'");' + d[m.end():]
    d = re.sub(rb'SetInitialWalk\([^)]*\);', lambda x: b'//' + b' ' * (len(x.group(0)) - 2), d)
    f = open(dst, 'r+b'); S.patch(f, rel, d); f.close(); print(dst)
if __name__ == '__main__': main(int(sys.argv[1]))
