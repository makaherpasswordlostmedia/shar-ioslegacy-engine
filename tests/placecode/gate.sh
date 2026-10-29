#!/bin/bash
# Гейт кодов мест (правка Роба 58): код в счётчике EBOOT (viewer/placecode.h) и обратный ход tools/place.py — одно правило.
#   tests/placecode/gate.sh              зелёный: ~16 000 точек (случайные + края квадратов и участков) — коды C и Python совпадают;
#                                        центр участка, названного кодом, даёт тот же код; места оригинала — в своих квадратах
#   tests/placecode/gate.sh --negative   красный: C собран с -DPLACE_BREAK (участки 7 8 9 сверху) — сверка обязана упасть
#   tests/placecode/gate.sh --emu [DIR]  эмулятор (tools/smoke.sh, tests/placecode/scenario.txt): на паузе у Kwik-E-Mart строка
#                                        PLACE движка = код tools/place.py по той же точке, K10 (снимок kwik_pause — код внизу слева)
set -u; cd "$(dirname "$0")/../.."
if [ "${1:-}" = --emu ]; then
  L=$(SMOKE_SCN=tests/placecode/scenario.txt tools/smoke.sh "${2:-build}" 2>&1); R=$(echo "$L" | sed -n 's/^отчёт: \(.*\)\/summary\.txt.*/\1/p')
  [ -n "$R" ] || { echo "FAIL: нет отчёта smoke: $(echo "$L" | head -1)"; exit 1; }
  .venv/bin/python - "$R/smoke.txt" <<'PY'
import re, sys
sys.path.insert(0, 'tools'); import place as P
rows = [l for l in open(sys.argv[1], errors='replace') if l.startswith('PLACE ')]
if not rows: print('FAIL: нет строки PLACE — код на паузе не выведен'); sys.exit(1)
m = re.match(r'PLACE L(\d) (\S+) pos=([-\d.]+),([-\d.]+)', rows[0])
want = P.code(float(m.group(3)), float(m.group(4)))
if m.group(2) != want or not want.startswith('K10'): print(f'FAIL: на паузе {m.group(2)}, по точке {want}'); sys.exit(1)
print(f'OK: на паузе L{m.group(1)} {m.group(2)} = tools/place.py; снимок {sys.argv[1].rsplit("/", 1)[0]}/kwik_pause.png')
PY
  exit $?
fi
DEF=""; [ "${1:-}" = --negative ] && DEF="-DPLACE_BREAK"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
cc -O1 $DEF -o "$T/pc" tests/placecode/host.c -lm || { echo "FAIL: не собрался host.c"; exit 1; }
.venv/bin/python - "$T/pc" "${1:-}" <<'PY'
import random, subprocess, sys
sys.path.insert(0, 'tools')
import place as P
exe, neg = sys.argv[1], sys.argv[2] == '--negative'
rnd = random.Random(58)
pts = [(rnd.uniform(-800, 600), rnd.uniform(-800, 900)) for _ in range(16000)]
for k in range(-1, P.COLS * 3 + 2):                      # края участков: чуть до и чуть после границы
    for e in (-0.01, 0.01):
        pts.append((P.X0 + k * P.CELL / 3 + e, rnd.uniform(-700, 800))); pts.append((rnd.uniform(-700, 500), P.Z0 + k * P.CELL / 3 + e))
out = subprocess.run([exe], input=''.join(f'{x:.4f} {z:.4f}\n' for x, z in pts), capture_output=True, text=True).stdout.split()
bad = [(x, z, c, P.code(float(f'{x:.4f}'), float(f'{z:.4f}'))) for (x, z), c in zip(pts, out) if c != P.code(float(f'{x:.4f}'), float(f'{z:.4f}'))]
fails = []
if len(out) != len(pts): fails.append(f'C вернул {len(out)} кодов из {len(pts)}')
if bad: fails.append(f'коды C и Python расходятся в {len(bad)} точках, например x {bad[0][0]:.2f} z {bad[0][1]:.2f}: C {bad[0][2]}, Python {bad[0][3]}')
rt = 0
for c in sorted(set(out)):                                # обратный ход: центр участка -> тот же код
    if c == '--': continue
    lv, col, row, sub = P.parse(c); x, z, _ = P.center(col, row, sub)
    if P.code(x, z) != c: rt += 1
if rt: fails.append(f'обратный ход: {rt} кодов не возвращаются в себя')
pl = P.places(1)
if len(pl) < 10: fails.append(f'мест оригинала уровня 1 {len(pl)} (< 10)')
kw = next((p for p in pl if p[0] == 'Kwik E Mart'), None)
if not kw or P.code(kw[1], kw[2]) != 'K10-7': fails.append(f'Kwik E Mart не в K10-7 ({kw and P.code(kw[1], kw[2])})')
# №688: за сеткой код ближайшего места, а не прочерк: углы и края вне сетки, трасса L2 (C1-5) и соседи
edge = {(-800.0, -800.0): 'A1-1', (600.0, 900.0): 'M15-9', (-800.0, 900.0): 'A15-7', (600.0, -800.0): 'M1-3', (-450.0, -690.0): 'C1-2', (-450.0, -720.0): 'C1-2', (0.0, 900.0): 'H15-7'}
ee = subprocess.run([exe], input=''.join(f'{x} {z}\n' for x, z in edge), capture_output=True, text=True).stdout.split()
for (pt, want), got in zip(edge.items(), ee):
    if got != want and not neg: fails.append(f'за сеткой {pt}: C {got}, ждали {want}')
    if P.code(*pt) != got and not neg: fails.append(f'за сеткой {pt}: Python {P.code(*pt)} != C {got}')
if any(c == '--' for c in out) and not neg: fails.append('в сетке и за ней остались прочерки «--»')
n = len(set(out) - {'--'})
if neg:
    print(('PASS (красный пойман): ' + fails[0]) if fails else 'FAIL (красный не пойман)'); sys.exit(0 if fails else 1)
if fails: print('FAIL: ' + fails[0]); [print('  - ' + f) for f in fails[1:]]; sys.exit(1)
print(f'OK: {len(pts)} точек, коды C и Python совпадают ({n} разных участков), обратный ход точный, Kwik E Mart = K10-7')
PY
