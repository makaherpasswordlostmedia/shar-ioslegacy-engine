#!/usr/bin/env python3
"""Сверка прогона tests/ui/tutorial_scenario.txt: подсказки обучения Барта (Tutorial.scr, viewer/tutorial.c).
  tutorial_check.py RUN_DIR   -> первая строка итог, код 0 = OK
  · уровень 1 включает подсказки (EnableTutorialMode(1) в leveli.mfk), в пакете 22 строки TUTORIAL_NNN
  · порядок: ходьба (msg 2) -> «△ — сесть» (4) -> газ (3, закрыта □ Disable) -> «△ — войти» (13) -> «машина взорвана» (15)
  · X раньше «Continue» не закрывает (без реплики — 2 с): закрыта не раньше 2 с; пока подсказка на экране — мир стоит (↑ 1 с не
    сдвинул Гомера); после □ подсказок нет, пока строка Tutorial в Settings паузы не включена снова (OPT tut=1)
  · с репликой (tutvoice): Continue — только когда реплика Барта кончилась
  · «машина взорвана» — не сразу после взрыва (Гомер успевает упасть: запись PS2 33:33 -> 33:36)
  · раскладка (UITUT, как ушло в GE) по данным Scrooby (R1–R3 tools/ui_export.py): рамка SmallBoard.pag Frame_Bgd, текст целиком
    внутри рамки; правка 267 — шаг буква + 1 px, блок по центру под значком Барта, поля по бокам от 12 px (прежнее при old=1)
  · снимки есть"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

run = Path(sys.argv[1]); log = (run / 'smoke.txt').read_text(errors='replace').splitlines() if (run / 'smoke.txt').exists() else []
kv = lambda l: dict(p.split('=', 1) for p in l.split()[1:] if '=' in p)
bad, info = [], []

mode = [kv(l) for l in log if l.startswith('TUTORIAL mode')]
if not mode or mode[0].get('level') != '1' or mode[0].get('texts') != '22':
    bad.append(f'уровень 1 не включил подсказки или в пакете нет 22 строк TUTORIAL_NNN: {mode[:1]}')
ev = [(l.split()[1], kv(l), i) for i, l in enumerate(log) if l.startswith('TUTORIAL ') and not l.startswith('TUTORIAL mode')]
ons = [d.get('ev') for e, d, _ in ev if e == 'on']
info.append('подсказки: ' + ' '.join(f"{e}:{d.get('ev')}/{d.get('msg')}@{d.get('t')}" for e, d, _ in ev))
want = ['walk', 'getin', 'gas', 'inside', 'destroyed', 'getin']
if ons != want: bad.append(f'порядок подсказок {ons} != {want}')
msg = {'walk': '2', 'getin': '4', 'gas': '3', 'inside': '13', 'destroyed': '15'}
for e, d, _ in ev:
    if e == 'on' and d.get('ev') in msg and d.get('msg') != msg[d['ev']]: bad.append(f"{d['ev']}: строка {d.get('msg')} != {msg[d['ev']]}")
    if e == 'off' and float(d.get('t', 0)) < 2.0: bad.append(f"{d.get('ev')}: закрыта X раньше Continue (t={d.get('t')})")
if not any(e == 'disable' and d.get('ev') == 'gas' for e, d, _ in ev): bad.append('□ на подсказке газа не выключил подсказки')
# с репликой (последняя «△ — сесть»): реплика incarps2 звучит, Continue — когда она кончилась (4,2 с), X раньше не закрывает
gv = [(e, d) for e, d, _ in ev if d.get('ev') == 'getin'][2:]
if len(gv) < 2 or gv[0][1].get('voice', '-1') == '-1' or gv[1][0] != 'off' or float(gv[1][1].get('t', 0)) < 4.0:
    bad.append(f'подсказка с репликой: реплика не звучит или закрыта раньше её конца (4,2 с): {gv}')

# мир стоит: строки HOMER между «on walk» и «off walk» — одна точка (в сценарии ↑ 1 с на подсказке)
iw = next((i for e, d, i in ev if e == 'on' and d.get('ev') == 'walk'), None)
ow = next((i for e, d, i in ev if e == 'off' and d.get('ev') == 'walk'), None)
if iw is not None and ow is not None:
    pos = {kv(l).get('pos') for l in log[iw:ow] if l.startswith('HOMER ')}
    if len(pos) != 1: bad.append(f'мир не стоял на подсказке ходьбы: Гомер {sorted(pos)}')
    else: info.append(f'мир стоит: Гомер {pos.pop()} все {sum(l.startswith("HOMER ") for l in log[iw:ow])} с подсказки')
# после □ — ничего до включения строки Tutorial
idis = next((i for e, d, i in ev if e == 'disable'), None)
ion = next((i for i, l in enumerate(log) if l.startswith('OPT ') and kv(l).get('tut') == '1' and idis is not None and i > idis), None)
if idis is None or ion is None: bad.append('строка Tutorial в Settings паузы не включила подсказки (нет OPT tut=1 после □)')
elif any(e == 'on' and idis < i < ion for e, d, i in ev): bad.append('подсказка показана, пока подсказки выключены')
if idis is not None and not any(l.startswith('OPT ') and kv(l).get('tut') == '0' for l in log[idis:]):
    bad.append('после □ строка Tutorial в Settings не показывает Off')
# «машина взорвана» — не сразу после взрыва
ib = next((i for i, l in enumerate(log) if l.startswith('BOOM ')), None)
idd = next((i for e, d, i in ev if e == 'on' and d.get('ev') == 'destroyed'), None)
if ib is None or idd is None: bad.append('нет взрыва или подсказки «машина взорвана»')
else:
    tb = float(kv(log[ib])['t']); hs = [float(kv(l)['t']) for l in log[ib:idd] if l.startswith('HOMER ')]
    if not hs or max(hs) < tb + 1.0: bad.append(f'«машина взорвана» сразу после взрыва (t {tb}, секунды до подсказки {hs})')
    else: info.append(f'«машина взорвана»: взрыв t={tb}, подсказка после t={max(hs)}')

# раскладка по данным Scrooby: R1 S = 272/480, R2 якорь C: x' = S*x + (480 - 640*S)/2, R3 y' = S*y (Scrooby y — снизу)
import ui_export as U
S = 272 / 480; CX = (480 - 640 * S) / 2
prj = U.project('ingame.p3d')
def rect(page, name, kind):
    for path, e in U.iter_leaves(prj.pages[page]):
        if e['name'] == name and e['kind'] == kind:
            return e['x'] * S + CX, (480 - e['y'] - e['h']) * S, e['w'] * S, e['h'] * S
box = rect('SmallBoard.pag', 'Frame_Bgd', 'poly'); place = rect('Tutorial.pag', 'TutorialMessage', 'sprite')
ut = [kv(l) for l in log if l.startswith('UITUT ')]
if not ut: bad.append('нет строк UITUT (подсказка не нарисована)')
for d in ut:
    bx, by, bw, bh = map(int, d['box'].split(',')); tx, ty, tw, th = map(int, d['text'].split(','))
    g, pitch = int(d['glyph']), int(d['pitch'])
    if max(abs(bx - box[0]), abs(by - box[1]), abs(bw - box[2]), abs(bh - box[3])) > 1.5:
        bad.append(f"msg {d['msg']}: рамка {bx},{by},{bw},{bh} != Scrooby {tuple(round(v, 1) for v in box)}")
    if not (bx <= tx and tx + tw <= bx + bw and by <= ty and ty + th <= by + bh):
        bad.append(f"msg {d['msg']}: текст {tx},{ty},{tw},{th} вылез из рамки {bx},{by},{bw},{bh}")
    if d.get('old', '1') == '1':   # прежняя раскладка (до правки 267): первая строка на центре места, шаг — половина места
        if abs(ty + g / 2 - (place[1] + place[3] / 2)) > 1.5:
            bad.append(f"msg {d['msg']}: первая строка на y {ty + g / 2} != центр места TutorialMessage {place[1] + place[3] / 2:.1f}")
        if abs(pitch - place[3] / 2) > 1.0: bad.append(f"msg {d['msg']}: шаг строк {pitch} != половина места {place[3] / 2:.1f}")
    else:   # правка 267: шаг — буква + 1 px, блок по центру между низом значка Барта и низом рамки, поля по бокам >= 12 px
        av = int(d['avbot']); top, bot = ty - av, by + bh - (ty + th)
        if pitch != g + 1: bad.append(f"msg {d['msg']}: шаг строк {pitch} != буква {g} + 1")
        if abs(top - bot) > 2 or min(top, bot) < 4: bad.append(f"msg {d['msg']}: блок не по центру (сверху {top}, снизу {bot})")
        if min(tx - bx, bx + bw - tx - tw) < 12: bad.append(f"msg {d['msg']}: поле сбоку {min(tx - bx, bx + bw - tx - tw)} < 12")
    if abs(bx + bw / 2 - 240) > 1.0: bad.append(f"msg {d['msg']}: рамка не по центру экрана ({bx + bw / 2})")
if ut: info.append(f"раскладка: рамка {ut[0]['box']}, строка 1 на {place[1] + place[3] / 2:.1f}, шаг {place[3] / 2:.1f}; "
                   + ' '.join(f"msg{d['msg']}:{d['text']}" for d in ut if d.get('cont') == '0'))
for s in ('tut_walk', 'tut_walk_cont', 'tut_getin', 'tut_gas', 'tut_off', 'tut_settings_on', 'tut_inside', 'tut_destroyed', 'tut_voice'):
    if not (run / f'{s}.png').exists(): bad.append(f'нет снимка {s}')
print('tutorial: ' + ('PASS' if not bad else 'FAIL — ' + '; '.join(dict.fromkeys(bad))))
for x in info: print('  ' + x)
sys.exit(1 if bad else 0)
