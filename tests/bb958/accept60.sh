#!/bin/bash
# №958б приёмка: значок цели в чёрном ящике игры — поле ico в каждой секундной строке BB и события ICON (хвост blackbox.txt + smoke.txt) при каждой смене значка/текста цели.
# Путь игрока без служебных флагов: menu → NEW GAME на L6 → пауза → MISSION SELECT L6→L5→L6 (tests/msn958/s6_hop.txt). Зелёный — новая сборка; красный — сборка с -DBBICON958_OLD=1 (поля и событий нет).
# Последняя строка PASS / FAIL.  REUSE=1 — не пересобирать и не гонять эмулятор, если прогон уже есть.
export PATH=$HOME/Downloads/shar-psp/build/xcshim/bin:$PATH
W="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$W"; export PSPDEV=$W/pspdev PATH=$W/pspdev/bin:$PATH EMU_OWNER=${EMU_OWNER:-Glyuki} EMU_MINE=2 OUT=$W/run
SET=${SET:-$HOME/Downloads/shar-psp-integ/build/test63tour/PSP/GAME/SHARTEST15}; export SET
FL="-DJITTER_STRIPS_OLD=1 -DJITTER_CAR_OLD=1 -DFE_DEMO_PS2_OLD=1 -DBB_SYNC_OLD=1 -DZF932_OLD=1"
mk() { [ "${REUSE:-0}" = 1 ] && [ -f viewer/$1/EBOOT.PBP ] && return 0; ( cd viewer && psp-cmake -S . -B $1 -DSHAR_RELEASE=ON -DSHAR_RELEASE_KEEP_DIAG=ON -DSHAR_RELEASE_KEEP_HUD=ON -DSHAR_RELEASE_KEEP_SMOKE=ON -DCMAKE_C_FLAGS="$FL $2" >/dev/null 2>&1 && cmake --build $1 -j4 >$W/run/bb958_$1.log 2>&1 ); }
mk build_t60 "" && mk build_old958 "-DBBICON958_OLD=1" || { echo "сборка не удалась"; echo FAIL; exit 2; }
if [ "${REUSE:-0}" != 1 ] || [ ! -f run/out_gn/blackbox.txt ]; then rm -rf run/out_gn run/out_go
  bash tools/emu_run.sh tests/msn958/s6_hop.txt gn viewer/build_t60/EBOOT.PBP 400 >/dev/null 2>&1 &
  bash tools/emu_run.sh tests/msn958/s6_hop.txt go viewer/build_old958/EBOOT.PBP 400 >/dev/null 2>&1 &
  wait; fi
python3 - <<'PYEOF'
import re, sys
def rd(p):
    try: return open(p, errors='replace').read()
    except OSError: return ''
def stat(tag):
    bb = rd('run/out_%s/blackbox.txt' % tag); sm = rd('run/out_%s/smoke.txt' % tag)
    ico = re.findall(r' ico (\S+)/(\d+)/(\d)/L(\d)/(\S+)', bb)
    tail = [l for l in bb.splitlines() if l.startswith('# ICON ')]
    ev = [l for l in sm.splitlines() if l.startswith('ICON ')]
    return ico, tail, ev
ok = True
def need(c, m):
    global ok; print(('  ok   ' if c else '  FAIL ') + m); ok = ok and c
ico, tail, ev = stat('gn')
print('новое: поле ico в строках ящика %d, событий ICON в smoke.txt %d, в хвосте blackbox.txt %d' % (len(ico), len(ev), len(tail)))
need(len(ico) >= 10, 'секундные строки BB несут ico (имя/поле/картинка/уровень цели/текст): %d' % len(ico))
need(any(i[2] == '1' and i[1] == '1000' for i in ico), 'в какой-то строке значок цели есть (поле 1000, картинка 1)')
lv = {i[3] for i in ico}; need('6' in lv, 'уровень цели в строках: %s (L6 есть)' % sorted(lv))
setl = [e for e in ev if e.startswith('ICON set ')]
need(len(setl) >= 3, 'событий смены значка (set): %d, уровни цели: %s' % (len(setl), sorted({re.search(r'/L(\d)/', e).group(1) for e in setl if re.search(r'/L(\d)/', e)})))
need(any('cleanup' in e or 'off' in e or 'shutdown' in e for e in ev), 'события гашения значка (off/cleanup/shutdown) есть')
need(len(tail) >= 1, 'хвост blackbox.txt хранит события ICON после кольца: %d' % len(tail))
oi, ot, oe = stat('go')
print('прежнее (-DBBICON958_OLD=1): ico %d, событий smoke %d, хвост %d' % (len(oi), len(oe), len(ot)))
need(len(oi) == 0 and len(oe) == 0 and len(ot) == 0, 'красный: в прежней сборке поля и событий нет (контроль краснеет)')
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
PYEOF
