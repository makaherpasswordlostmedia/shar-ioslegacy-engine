#!/usr/bin/env python3
"""Клон ISO с другим персонажем и его машиной на L1 (оригинал game/Hit and Run.iso не трогается: cp -c).
Правятся level.mfk и leveli.mfk внутри RCF: famil_v -> <имя>_v; в leveli.mfk AddCharacter("homer","homer") -> имя персонажа.
python3 -I tools/twins/ps2_char_swap.py marge [машина]   → build/ps2stend/iso/<имя>_<машина>.iso (путь печатается)
Машина по умолчанию <имя>_v; чужая машина: marge bart_v"""
import subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ps2_car_swap as S

def main(ch, car):
    assert (S.GAME / f'art/chars/{ch}_m.p3d').exists(), ch
    assert (S.GAME / f'art/cars/{car}.p3d').exists() and (S.GAME / f'scripts/cars/{car}.con').exists(), car
    S.OUT.mkdir(parents=True, exist_ok=True); dst = S.OUT / f'{ch}_{car}.iso'
    if dst.exists(): dst.unlink()
    subprocess.run(['cp', '-c', str(S.SRC), str(dst)], check=True)
    f = open(dst, 'r+b')
    for rel in ('scripts/missions/level01/level.mfk', 'scripts/missions/level01/leveli.mfk'):
        d = (S.GAME / rel).read_bytes(); d = d.replace(b'famil_v', car.encode())
        if rel.endswith('leveli.mfk'):
            old = b'AddCharacter("homer","homer");'; assert d.count(old) == 1
            d = d.replace(old, f'AddCharacter("{ch}","{ch}");'.encode())
        S.patch(f, rel, d)
    # старт сразу в машине: как m0i.mfk (SetMissionResetPlayerInCar), вместо выхода из дома в m0sdi.mfk
    rel = 'scripts/missions/level01/m0sdi.mfk'; d = (S.GAME / rel).read_bytes()
    old = b'SetMissionResetPlayerOutCar("level1_homer_start", "level1_carstart");'; assert d.count(old) == 1
    S.patch(f, rel, d.replace(old, b'SetMissionResetPlayerInCar("level1_carstart");'))
    f.close(); print(dst)

if __name__ == '__main__': main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else f'{sys.argv[1]}_v')
