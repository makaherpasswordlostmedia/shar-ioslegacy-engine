#!/bin/bash
# №951б приёмка: Ink 2 Tone по объекту (деревья/пальмы и высокие предметы обводятся, тон — из средней краски текстуры куска; линии мира — один тон на уровень из текстур; герои и тени чёрные).
#   accept60.sh EBOOT  — зелёный (новый код) и красный (тот же сценарий + flag ink951bold 1: Tone как №951) гоняются вместе; Ink 1 Black по умолчанию не меняется (проверка INK951 style=1).
# Последняя строка PASS / FAIL. RUN=<дерево>/tools/emu_run.sh, OUT — рабочая папка
D=$(cd "$(dirname "$0")" && pwd); I=$(cd "$D/../.." && pwd); RUN=${RUN:-$I/tools/emu_run.sh}; export OUT=${OUT:-$D/out}; export EMU_OWNER=${EMU_OWNER:-Управление}; export EMU_MINE=${EMU_MINE:-2}; mkdir -p $OUT
EB=${1:?EBOOT}; [ -f "$EB" ] || { echo "нет EBOOT $EB"; echo FAIL; exit 1; }
awk '{print} /^flag repair/ && !d {print "flag ink951bold 1"; d=1}' $D/scenario.txt > $OUT/scenario_red.txt
$RUN $D/scenario.txt n "$EB" 400 >/dev/null 2>&1 & $RUN $OUT/scenario_red.txt o "$EB" 400 >/dev/null 2>&1 & wait
python3 -I - $OUT/out_n/smoke.txt $OUT/out_o/smoke.txt <<'PYEOF'
import re, sys
def read(p):
    try: return open(p, errors='replace').read()
    except OSError: return ''
def stats(log):
    sc = None; tall = {}; tone = {}; inkt = []
    for l in log.split('\n'):
        m = re.match(r'SCENE (\S+)', l)
        if m: sc = m.group(1); continue
        m = re.match(r'PROPTOON .*tone=(\d) tall=(\S+)', l)
        if m and sc: tall.setdefault(sc, []).append(float(m.group(2))); tone.setdefault(sc, []).append(int(m.group(1)))
        m = re.match(r'INKTONE level=\d+ world=(\S+) tex=(\d+)', l)
        if m: inkt.append((m.group(1), int(m.group(2))))
    return tall, tone, inkt
ok = True
def need(c, msg):
    global ok; print(('  ok   ' if c else '  FAIL ') + msg); ok = ok and c
for name, path, want in (('зелёный (новый код)', sys.argv[1], True), ('красный (flag ink951bold 1)', sys.argv[2], False)):
    log = read(path); tall, tone, inkt = stats(log); print('== ' + name)
    need('END' in log or 'EXIT739' in log, 'сценарий дошёл до конца') if want else None
    tb = tall.get('INKB_B', []); tt = tall.get('INKB_T', [])
    if want:
        need(bool(tt) and max(tt) >= 1.0, 'Ink 2: обведены высокие предметы (деревья, пальмы): PROPTOON tall max %s' % (max(tt) if tt else None))
        need(not tb or max(tb) == 0.0, 'Ink 1 Black: высоких обводок нет (прежнее): %s' % (max(tb) if tb else 'нет строк'))
        need(any(w not in ('00000000', 'ff420e20', 'ff0e2042') and n >= 8 for w, n in inkt), 'тон линий мира по текстурам уровня: INKTONE %s' % inkt[:2])
    else:
        red = (max(tt) if tt else 0.0)
        need(red < 1.0 and not any(n >= 8 for w, n in inkt), 'красный: Tone как №951 — высоких обводок нет (tall %.1f), тона мира нет (%s)' % (red, inkt[:1])) if tt else need(False, 'красный: нет строк PROPTOON')
print('PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
PYEOF
