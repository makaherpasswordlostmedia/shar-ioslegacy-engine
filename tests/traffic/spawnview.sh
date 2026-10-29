#!/bin/bash
# Гейт правки 328 на Маке (tests/traffic/spawnview.c): езда по дорогам всех 7 уровней (18 мин на уровень: скорость x1; x1,5;
# x2 трафика, сбросы и переносы игрока), машины трафика, рождённые в кадре ближе дальности рисования машин (сфера кузова в
# пирамиде кадра 62° x 16:9), — прежнее правило (trfSpawnOld = 1) обязано дать их больше нуля (красный контроль), новое — ноль
# на каждом уровне, в том числе при сбросе и переносе. Плотность нового против прежнего: машин в кадре и ближе 60 м от игрока
# на каждом уровне не меньше 85%, в среднем по уровням не меньше 90%.
#   tests/traffic/spawnview.sh [папка уровней]      (по умолчанию build/levels: l<N>/level.shr, l<N>/traffic.shr)
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
L="${1:-build/levels}"; B=${TMPDIR:-/tmp}/spawnview.$$
cc -std=c11 -O2 -Wall -Wno-unused-function -DSKIN_HOST -I viewer tests/traffic/spawnview.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c -lm -o "$B" || exit 2
python3 - "$B" "$L" <<'PY'
import sys, subprocess, re
B, L = sys.argv[1], sys.argv[2]
def run(lv, old):
    out = subprocess.run([B, f'{L}/l{lv}/level.shr', f'{L}/l{lv}/traffic.shr', str(old), '60'], capture_output=True, text=True).stdout
    m = re.search(r'RESULT (.*)', out)
    if not m: return None
    return {k: float(v) for k, v in (x.split('=') for x in m.group(1).split())}
fails, redSum, rows = 0, 0, []
print(f'  {"lvl":4} {"old: in-frame/reset/teleport":30} {"new: in-frame/reset/teleport":30} {"in-frame cars old->new":24} {"near60 old->new":18} spawns/min old->new')
for lv in range(1, 8):
    o, n = run(lv, 1), run(lv, 0)
    if not o or not n: print(f'  L{lv}: no data'); fails += 1; continue
    ov = o['visible'] + o['reset'] + o['teleport']; nv = n['visible'] + n['reset'] + n['teleport']; redSum += ov
    fr, nr = n['inframe'] / max(o['inframe'], 1e-6), n['near60'] / max(o['near60'], 1e-6); rows.append((fr, nr))
    bad = nv > 0 or fr < .85 or nr < .85; fails += bad
    print(f'  L{lv}  {int(o["visible"]):5d} / {int(o["reset"]):3d} / {int(o["teleport"]):3d}              {int(n["visible"]):5d} / {int(n["reset"]):3d} / {int(n["teleport"]):3d}'
          f'              {o["inframe"]:.2f} -> {n["inframe"]:.2f} ({fr:4.0%})    {o["near60"]:.2f} -> {n["near60"]:.2f} ({nr:4.0%})  {o["spawnsPerMin"]:.0f} -> {n["spawnsPerMin"]:.0f}  {"FAIL" if bad else "ok"}')
af = sum(r[0] for r in rows) / max(1, len(rows)); an = sum(r[1] for r in rows) / max(1, len(rows))
avg_ok = af >= .9 and an >= .9; red = redSum > 0
print(f'GATE spawnview: old born in frame {redSum} ({"RED as it must be" if red else "NOT RED"}), new {"0 on all levels" if not fails else "see FAIL rows"}, '
      f'density avg in-frame {af:.0%} near60 {an:.0%} ({"ok" if avg_ok else "DROP"}) -> {"PASS" if red and not fails and avg_ok else "FAIL"}')
sys.exit(0 if red and not fails and avg_ok else 1)
PY
r=$?; rm -f "$B"; exit $r
