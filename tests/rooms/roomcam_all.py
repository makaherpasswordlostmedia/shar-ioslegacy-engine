#!/usr/bin/env python3
"""Все записи PS2 по комнатам разом (стенд 2, 17.10): школа и прогулки ps2s_room.py (DMV, Moe's, Android's, Observatory, дом L4, комната Барта) +
дом и Kwik L1. Печатает долю кадров в допуске по комнате и общую. Данные: build/twins/o4 (дом, Kwik), build/twins/o4_s2 (остальное) в основном дереве,
пакеты рисования — наборы TEST28 (SHARTEST15) или build/.
  python3 tests/rooms/roomcam_all.py [old172]"""
import math, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import roomcam_twins as T
HOME = Path.home(); D = HOME / 'Downloads/shar-psp-sonnet-16b-w/build/test28/PSP/GAME/SHARTEST15'; O = HOME / 'Downloads/shar-psp/build/twins'
TR = ('trace', -20.0)
RUNS = [('SimpsonsHouse', D / 'interiors-l1-gfx.bin', O / 'o4/v17_house_cam/walk.tsv', 'walk'), ('KwikEMart', D / 'interiors-l1-gfx.bin', O / 'o4/v11_kwik_fwd/visit.tsv', 'visit'),
        ('SpringfieldElementary', D / 'interiors-l1-gfx.bin', O / 'o4/s2_school/visit.tsv', 'visit'), ('DMV', D / 'l2/interiors-l2-gfx.bin', O / 'o4_s2/room_DMV/trace.tsv', TR),
        ('Moes', D / 'l2/interiors-l2-gfx.bin', O / 'o4_s2/room_Moes/trace.tsv', TR), ('AndroidsDungeon', D / 'l3/interiors-l3-gfx.bin', O / 'o4_s2/room_AndroidsDungeon/trace.tsv', TR),
        ('Observatory', D / 'l3/interiors-l3-gfx.bin', O / 'o4_s2/room_Observatory/trace.tsv', TR), ('SimpsonsHouse', D / 'l4/interiors-l4-gfx.bin', O / 'o4_s2/room_SimpsonsHouse/trace.tsv', TR),
        ('BartRoom', D / 'l4/interiors-l4-gfx.bin', O / 'o4_s2/room_BartRoom/trace.tsv', TR)]
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''; host = T.build(0); tot = ok = 0; out = []
    for room, pkg, path, kind in RUNS:
        orig = T.original(path, kind); tsv = T.ROOT / 'build/rooms_cams/p.tsv'; tsv.write_text(''.join(f'{f} {x:.3f} {z:.3f}\n' for f, x, z, _, _ in orig))
        res = subprocess.run([str(host), str(pkg), room, str(tsv)] + ([mode] if mode else []), capture_output=True, text=True, check=True).stdout
        port = {int(l.split('\t')[0]): l.split('\t') for l in res.splitlines()}; g = b = 0
        for i, (f, x, z, e, d) in enumerate(orig):
            if any(math.dist(orig[j][3], orig[j - 1][3]) > .5 for j in range(max(1, i - 7), i + 1)): continue
            p = port.get(f)
            if not p: continue
            pe = [float(v) for v in p[2:5]]; pl = [float(v) for v in p[5:8]]; pd = [pl[k] - pe[k] for k in range(3)]; n = math.sqrt(sum(v * v for v in pd)) or 1.0
            ang = math.degrees(math.acos(max(-1, min(1, sum(a * c / n for a, c in zip(pd, d))))))
            g += 1; b += math.dist(e, pe) < T.EYE_TOL and ang < T.ANG_TOL
        out.append(f'{room[:8]}{"/L4" if "l4" in str(pkg) and room == "SimpsonsHouse" else ""} {b}/{g}'); tot += g; ok += b
    print(' · '.join(out), f'=> {ok}/{tot} {ok / tot:.1%}')
main()
