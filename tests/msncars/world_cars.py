"""Правка Роба 268 (04.10: «у ракетной машины стоит машина, которую не видно — въехал в пустоту и разбил»): у каждой машины мира
(viewer/worldcars.h) есть модель в пакете msncars уровня — иначе движок ставит её твёрдой и невидимой (строка MCRNONE в журнале).
python3 tests/msncars/world_cars.py [ПАКЕТ_L1 ...] -> 0 = PASS. Красный: пакет до правки (без rocke_v) обязан упасть"""
import struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / 'tools'))
import msncar_export as M

def names(pack):
    d = Path(pack).read_bytes(); h = struct.unpack('<8I', d[:32])
    return {d[h[4] + i * 176:h[4] + i * 176 + 16].split(b'\0')[0].decode().lower() for i in range(h[3])}

if __name__ == '__main__':
    packs = sys.argv[1:] or [str(ROOT / 'build/msncars-l1.shr')]; bad = []
    for p in packs:
        lv = 1 if p.endswith('l1.shr') else int(Path(p).stem.split('-l')[-1])
        have = names(p); need = [n for l, n in M.world_cars() if l == lv]
        miss = [n for n in need if n.lower() not in have]
        print(f'{p}: машин мира {len(need)}, без модели: {", ".join(miss) or "нет"}'); bad += miss
    print('PASS' if not bad else 'FAIL'); sys.exit(1 if bad else 0)
