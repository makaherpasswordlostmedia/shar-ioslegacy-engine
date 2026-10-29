#!/usr/bin/env python3
"""Клон hop-образа, где стартовая миссия уровня сажает игрока в машину у нужного локатора (оригинал и hop_to_LK не трогаются).
python3 -I tools/twins/ps2_spawn.py K ЛОКАТОР [КУСКИ_МИРА 'l3z3.p3d;l3r3.p3d;l3z4.p3d;'] [BASE.iso]   → build/ps2stend3/iso/spawn_L<K>_<ЛОКАТОР>.iso
Строка SetMissionResetPlayerOutCar(...) первой миссии заменяется на SetMissionResetPlayerInCar("ЛОКАТОР"); размер файла не меняется (добивка пробелами)."""
import re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ps2_car_swap as S
import ps2_level_hop as H

def main(k, loc, dyna=None, base=None):
    foot = None
    if ',' in loc: foot, loc = loc.split(',', 1)   # 'пешеход,машина' -> SetMissionResetPlayerOutCar(пешеход, машина)
    base = Path(base) if base else Path(f'/Users/USER/Downloads/shar-psp/build/twins/ps2stend3_iso/hop_to_L{k}.iso')
    dst = H.OUT / f'spawn_L{k}_{(foot + "_") if foot else ""}{loc}.iso'
    if dst.exists(): dst.unlink()
    subprocess.run(['cp', '-c', str(base), str(dst)], check=True)
    rel = f'scripts/missions/level0{k}/{H.FIRST[k]}.mfk'
    d = (S.GAME / rel).read_bytes().decode('latin-1')
    n, c = re.subn(r'SetMissionReset\w+\([^)]*\);', (f'SetMissionResetPlayerOutCar("{foot}","{loc}");' if foot else f'SetMissionResetPlayerInCar("{loc}");'), d, count=1)
    assert c == 1, 'нет строки SetMissionReset*'
    if dyna:   # куски мира с локатором (как в AddTeleportDest level.mfk)
        n, c = re.subn(r'SetDynaLoadData\("[^"]*"\);', f'SetDynaLoadData("{dyna}");', n, count=1); assert c == 1
    n = re.sub(r'SetInitialWalk\("[^"]*"\);', '', n)   # стартовая автоходьба мешает управлению
    new = n.encode('latin-1'); old = d.encode('latin-1')
    assert len(new) <= len(old)
    f = open(dst, 'r+b'); S.patch(f, rel, new + b' ' * (len(old) - len(new))); f.close(); print(dst)

if __name__ == '__main__': main(int(sys.argv[1]), sys.argv[2], *(sys.argv[3:5]))
