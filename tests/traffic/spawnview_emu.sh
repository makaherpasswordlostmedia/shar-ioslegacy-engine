#!/bin/bash
# Гейт правки 328 в эмуляторе (безголовый PPSSPP, без звука): езда по полосам уровня 1 (маршруты из traffic.shr,
# tests/traffic/spawnview_route.py; на каждый — goto = сброс трафика, потом автопилот по точкам 17 м/с), строки движка
# TRFSPAWN (flag trflog): каждая рождённая машина трафика — расстояние и угол от камеры кадра, в пирамиде кадра ли (ближе
# дальности рисования машин). Два прогона одного EBOOT: прежнее рождение («flag trfspawnold 1», обязано дать рождения в кадре)
# и новое (обязано дать 0). Плотность — строки TRF (cars, drawn) в среднем.
#   tests/traffic/spawnview_emu.sh [EBOOT.PBP]      (по умолчанию viewer/build/EBOOT.PBP)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
EB="${1:-$ROOT/viewer/build/EBOOT.PBP}"; DATA="${SCEN_ROOT:-$HOME/Downloads/shar-psp}"
SCEN="${SCEN_PY:-$HOME/.claude/skills/shar-level-polish/scripts/scen.py}"; T="${TMPDIR:-/tmp}/spawnview_emu.$$"; mkdir -p "$T"
python3 tests/traffic/spawnview_route.py "$DATA/build/levels/l1/traffic.shr" 4 328 > "$T/routes.txt"
{ echo "flag trflog"; echo "flag trfspawnold 1"; cat "$T/routes.txt"; } > "$T/old.txt"
{ echo "flag trflog"; cat "$T/routes.txt"; } > "$T/new.txt"
TAG=${SV_TAG:-sv328}
SCEN_EBOOT="$EB" SCEN_HOME="$T/home_old" python3 "$SCEN" ${TAG}_old "$T/old.txt" > "$T/old.log" 2>&1 &
SCEN_EBOOT="$EB" SCEN_HOME="$T/home_new" python3 "$SCEN" ${TAG}_new "$T/new.txt" > "$T/new.log" 2>&1 &
wait
python3 - "$T" <<'PY'
import sys, re
from pathlib import Path
T = Path(sys.argv[1]); res = {}
for k in ('old', 'new'):
    d = re.search(r'^dir (\S+)', (T / f'{k}.log').read_text(), re.M)
    log = (Path(d.group(1)) / 'smoke.txt').read_text().splitlines() if d else []
    sp, trf, scene = [], [], None
    for l in log:
        p = l.split()
        if not p: continue
        if p[0] == 'SCENE': scene = p[1]
        kv = dict(x.split('=', 1) for x in p[1:] if '=' in x)
        if p[0] == 'TRFSPAWN': sp.append((scene, kv))
        if p[0] == 'TRF' and scene and scene.startswith('drive'): trf.append(kv)
    drive = [s for s in sp if s[0] and s[0].startswith('drive')]
    vis = [(s, kv) for s, kv in drive if kv['inframe'] == '1']
    near = [kv for s, kv in vis if float(kv['d']) < 60]
    cars = sum(float(r['cars']) for r in trf) / max(1, len(trf)); drawn = sum(float(r['drawn']) for r in trf) / max(1, len(trf))
    res[k] = dict(n=len(drive), vis=len(vis), near=len(near), cars=cars, drawn=drawn, rows=len(trf), ok=bool(log))
    print(f'  {k}: smoke {"ok" if log else "MISSING"}, drive TRF rows {len(trf)}, spawns {len(drive)}, in frame {len(vis)} (<60 m {len(near)}), cars {cars:.2f}, drawn {drawn:.2f}')
    for s, kv in vis[:12]: print(f'      {s} t={kv["t"]} d={kv["d"]} ang={kv["ang"]} dp={kv["dp"]}')
o, n = res['old'], res['new']
red = o['ok'] and o['vis'] > 0; green = n['ok'] and n['vis'] == 0 and n['n'] > 0
dens = n['ok'] and o['ok'] and n['cars'] >= .8 * o['cars']
print(f'GATE spawnview emu: old in-frame {o["vis"]} ({"RED as it must be" if red else "NOT RED"}), new in-frame {n["vis"]} ({"GREEN" if green else "RED"}), '
      f'cars {n["cars"]:.2f} vs {o["cars"]:.2f} ({"ok" if dens else "DROP"}) -> {"PASS" if red and green and dens else "FAIL"}')
sys.exit(0 if red and green and dens else 1)
PY
