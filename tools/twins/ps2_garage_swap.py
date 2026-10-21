#!/usr/bin/env python3
"""Клон ISO: старт L1 пешком у выезда гаража АЭС (локатор m4_homer_start, PS2 x -84,63 z 300,67 = порт z -300,67).
Правка m0sdi.mfk в RCF: SetMissionResetPlayerOutCar("level1_homer_start",...) -> m4_*; зоны как у миссии 4; без начальной прогулки.
python3 -I tools/twins/ps2_garage_swap.py → build/ps2stend/iso/garage.iso"""
import subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ps2_car_swap as S
S.OUT.mkdir(parents=True, exist_ok=True); dst = S.OUT / 'garage.iso'
if dst.exists(): dst.unlink()
subprocess.run(['cp', '-c', str(S.SRC), str(dst)], check=True)
f = open(dst, 'r+b'); rel = 'scripts/missions/level01/m0sdi.mfk'; d = (S.GAME / rel).read_bytes()
for old, new in ((b'SetMissionResetPlayerOutCar("level1_homer_start", "level1_carstart");', b'SetMissionResetPlayerOutCar("m4_homer_start", "m4_carstart");'),
                 (b'SetDynaLoadData("l1z1.p3d;l1r1.p3d;l1r7.p3d;");', b'SetDynaLoadData("l1r4a.p3d;l1z6.p3d;l1r6.p3d;");'),
                 (b'SetInitialWalk("level1_homer_walkto");', b'')):
    assert d.count(old) == 1, old; d = d.replace(old, new)
S.patch(f, rel, d); f.close(); print(dst)
