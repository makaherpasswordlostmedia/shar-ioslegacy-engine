#!/bin/bash
# Гейт трафика в эмуляторе (одна очередь PPSSPP через tools/smoke.sh): сценарий tests/traffic/scenario.txt у Kwik-E-Mart.
#   tests/traffic/emu.sh [DIR]      DIR — EBOOT.PBP и данные (по умолчанию build/)
# Два прогона одного EBOOT: настоящий (должен пройти) и подброшенный — перед пешеходом «flag trfnosolid» (трафик не
# твёрдый; обязан провалиться). По строкам TRF движка (раз в секунду) и снимкам окна проверяется:
#   kwik    — стоящие машины у стоянки в кадре (parkdrawn >= 2), все места из данных на месте (park = число мест);
#   traffic — машины трафика есть и едут (moving >= 1), хоть одна в кадре (flag trfahead: машина на полосе впереди);
#   homer   — Гомер вышел, служебный пешеход в 3 м впереди по камере и 0.45 м в стороне, 3 с ↑: подошёл вплотную
#             (pedmin <= 1.2 м), не вошёл в него (pedmin >= 0.6 м = радиусы 0.3 + 0.35 минус допуск) и не обошёл (центр
#             Гомера вдоль бега остался перед центром пешехода); пешеходы в кадре (pedsdrawn >= 1);
#   FPS/кадр/куча — как смоук (tools/smoke_report.py по тем же сценам).
# Итог: build/smoke/<время>/ обоих прогонов (снимки, smoke.txt), строка GATE. Код 0 = настоящий зелёный, подброска красная.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
SRC="${1:-$ROOT/build}"
. .venv/bin/activate
check() {   # $1 = папка отчёта smoke -> печать проверок, код 0/1
  python3 - "$1" <<'PY'
import sys, re
from pathlib import Path
out = Path(sys.argv[1]); log = (out / 'smoke.txt').read_text().splitlines() if (out / 'smoke.txt').exists() else []
scene, rows, shots = 'start', {}, []
for l in log:
    p = l.split()
    if not p: continue
    if p[0] == 'SCENE': scene = p[1]
    if p[0] == 'SHOT': shots.append(p[1])
    if p[0] == 'TRF':
        d = dict(kv.split('=', 1) for kv in p[1:] if '=' in kv); d['scene'] = scene; rows.setdefault(scene, []).append(d)
def mx(sc, k): return max((float(r[k]) for r in rows.get(sc, [])), default=-1)
def last(sc, k): return float(rows[sc][-1][k]) if rows.get(sc) else -1
fails = 0
def ck(name, v, lo, hi):
    global fails
    ok = lo <= v <= hi; fails += not ok
    print(f'  {"ok" if ok else "FAIL":4} {name:48} {v:8.2f}  [{lo}, {hi}]')
ck('kwik: parked cars drawn (max)', mx('kwik', 'parkdrawn'), 2, 1e9)
ck('kwik: parked spots placed', mx('kwik', 'park'), 1, 1e9)
ck('traffic: cars moving (max)', max(mx('traffic', 'moving'), mx('traffic2', 'moving')), 1, 1e9)
ck('traffic: traffic cars drawn (max)', max(mx('traffic', 'drawn'), mx('traffic2', 'drawn')), 1, 1e9)
ck('homer: on foot at the end', last('homer', 'onfoot'), 1, 1)
ck('homer: pedestrians drawn (max)', mx('homer', 'pedsdrawn'), 1, 1e9)
pm = last('homer', 'pedmin')
ck('homer: closest to the pedestrian, m (walked up)', pm, -1e9, 1.2)
ck('homer: closest to the pedestrian, m (not through)', pm, .6, 1e9)
pt = next((l.split() for l in log if l.startswith('PEDTEST')), None)   # не обошёл: вдоль бега Гомер остался перед пешеходом
adv = 99.
if pt and rows.get('homer'):
    import math
    d = dict(kv.split('=', 1) for kv in pt[1:] if '=' in kv)
    h0 = [float(v) for v in d['homer'].split(',')]; p0 = [float(v) for v in d['ped'].split(',')]; a = float(d['yaw'])
    u = [math.sin(a), math.cos(a)]; along = (p0[0] - h0[0]) * u[0] + (p0[1] - h0[1]) * u[1]   # пешеход на 3 м вперёд, 0.45 м вбок
    h1 = [float(v) for v in rows['homer'][-1]['homer'].split(',')]
    adv = (h1[0] - h0[0]) * u[0] + (h1[1] - h0[1]) * u[1] - along
ck('homer: short of the pedestrian centre at the end, m', adv, -1e9, -.1)
ta = next((l.split() for l in log if l.startswith('TRFAHEAD')), None)
ck('traffic: car put on the lane ahead', float(dict(kv.split('=', 1) for kv in ta[1:] if '=' in kv)['ok']) if ta else 0, 1, 1)
ck('shots taken', len(shots), 4, 1e9)
sys.exit(1 if fails else 0)
PY
}
run() {   # $1 = сценарий -> путь отчёта
  local log; log=$(SMOKE_SCN="$1" tools/smoke.sh "$SRC" 2>&1); echo "$log" | head -1 >&2
  echo "$log" | sed -n 's/^отчёт: \([^ ]*\)\/summary.txt.*/\1/p'
}
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
awk '/^flag pedtest/ { print "flag trfnosolid" } { print }' tests/traffic/scenario.txt > "$TMP/planted.txt"
echo "== real"; A=$(run tests/traffic/scenario.txt); [ -n "$A" ] || { echo "FAIL: смоук не дал отчёта"; exit 1; }
echo "   $A"; check "$A"; ra=$?; grep -q '^OK' "$A/summary.txt" && fa=0 || fa=1; echo "   smoke_report: $(head -1 "$A/summary.txt")"
echo "== planted: flag trfnosolid (Homer and pedestrians not solid)"; B=$(run "$TMP/planted.txt")
echo "   $B"; check "$B"; rb=$?
if [ $ra = 0 ] && [ $fa = 0 ] && [ $rb != 0 ]; then echo "GATE traffic emu: real GREEN, planted RED -> PASS"; exit 0; fi
echo "GATE traffic emu: real $([ $ra = 0 ] && [ $fa = 0 ] && echo GREEN || echo RED), planted $([ $rb != 0 ] && echo RED || echo 'NOT CAUGHT') -> FAIL"; exit 1
