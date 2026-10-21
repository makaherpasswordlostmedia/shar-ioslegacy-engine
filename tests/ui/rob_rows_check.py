#!/usr/bin/env python3
"""Разбор прогона tests/ui/rob_rows_scenario.txt (tests/ui/rob_rows.sh): правки Роба 22, 25, 26, 36, 38, 41 — по тому, что
ушло в GE и что сделала игра (строки smoke.txt), не по флагам.
    rob_rows_check.py SMOKE_TXT   -> по разделу «OK» / «КРАСНОЕ» + строки проверок; код 0 — всё зелёное
Ожидания — из данных диска (скрипт m0sdi.mfk: жесты по репликам; значки заданий msnicons: круг; helptext: пузырь) и из
правил порта в коде (viewer/game_msn.h GAME_TALK_DIST, viewer/ui_anim.h UI_HNR_TRACK), числа границ — ниже."""
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
log = open(sys.argv[1], encoding='utf-8', errors='replace').read().splitlines()


def kv(line):
    return dict(m.groups() for m in re.finditer(r'(\w+)=(\S+)', line))


def section(name):
    a = next((i for i, l in enumerate(log) if l.startswith('SCENE %s ' % name)), None)
    if a is None:
        return []
    b = next((i for i in range(a + 1, len(log)) if log[i].startswith('SCENE ')), len(log))
    return log[a:b]


out, red = [], {}


def report(title, checks):
    ok = all(c for c, _ in checks)
    red[title] = not ok
    out.append('%s: %s' % (title, 'OK' if ok else 'КРАСНОЕ'))
    for c, s in checks:
        out.append('   %s %s' % ('ok  ' if c else 'FAIL', s))


# ---- 41: дверь Kwik-E-Mart по △, подсказка у двери дышит
D = section('door')
idx = lambda pred, frm=0: next((i for i in range(frm, len(D)) if pred(D[i])), None)
iFoot = idx(lambda l: l.startswith('FOOT '))
iUp = idx(lambda l: l.startswith('PRESS up'))
iTri = idx(lambda l: l.startswith('PRESS triangle'))
iTri2 = idx(lambda l: l.startswith('PRESS triangle'), (iTri or 0) + 1) if iTri is not None else None
iIn = idx(lambda l: l.startswith('ROOM ev=enter'))
iOut = idx(lambda l: l.startswith('ROOM ev=exit'))
chk = []
if None in (iFoot, iUp, iTri, iIn):
    chk.append((False, 'нет строк сценария двери (FOOT/PRESS/ROOM enter): foot=%s up=%s tri=%s enter=%s' % (iFoot, iUp, iTri, iIn)))
else:
    outside = [l for l in D[iFoot:iUp] if l.startswith('UIPULSE ')]
    atdoor = [kv(l) for l in D[iUp:iIn] if l.startswith('UIPULSE ')]
    chk.append((not outside, 'снаружи триггера двери △ нет: кадров с △ %d (нужно 0)' % len(outside)))
    chk.append((iIn > iTri, 'вход только после △: вход %s нажатия △' % ('после' if iIn > iTri else 'ДО')))
    chk.append((len(atdoor) >= 25, 'в триггере двери до △ подсказка видна: кадров %d (>= 25, ~1 с)' % len(atdoor)))
    chk.append((iOut is not None and iTri2 is not None and iOut > iTri2, 'выход из комнаты — по второму △: %s' %
                ('да' if iOut is not None and iTri2 is not None and iOut > iTri2 else 'нет')))
report('41 дверь по △ (эмулятор)', chk)
chk = []
if iUp is not None and iIn is not None:
    sc = [(float(d['age']), (float(d['x1']) - float(d['x0'])) / float(d['w0'])) for d in atdoor] if atdoor else []
    steady = [s for a, s in sc if a > 0.6]
    first = sc[0][1] if sc else 0
    amp = (max(steady) - min(steady)) if steady else 0
    chk.append((bool(sc) and first < 0.9, 'появление пружиной от центра: первый кадр x%.2f (< 0.9)' % first))
    chk.append((amp >= 0.10, 'дышит: размах масштаба %.3f после 0.6 с (>= 0.10; правило ±8%%)' % amp))
else:
    chk.append((False, 'нет кадров △ у двери'))
M = section('msn')
iDlg = next((i for i, l in enumerate(M) if l.startswith('MSN dialogue')), None)
talkPulse = [l for l in M[:iDlg] if l.startswith('UIPULSE ')] if iDlg is not None else []
chk.append((len(talkPulse) >= 10, '△ у собеседника (Мардж) до разговора: кадров %d (>= 10)' % len(talkPulse)))
report('41 подсказка △ пульсирует (эмулятор)', chk)

# ---- 22: аватар = высота пузыря (одно правило), значок 1:1
import ui_export as U  # noqa: E402
(c0x, c0y, c1x, c1y), (iw, ih) = U.avatar_circle('msn')
him = U.all_images()['helptext.png']; b0, b1 = him.getchannel('A').point(lambda a: 255 if a >= 128 else 0).getbbox()[1::2]
A = [kv(l) for l in M if l.startswith('UIAVATAR ')]; B = [kv(l) for l in M if l.startswith('UIBUBBLE ')]
chk = []
if not A or not B:
    chk.append((False, 'нет строк UIAVATAR / UIBUBBLE (аватар не рисовался)'))
else:
    a, b = A[-1], B[-1]
    x, y, w, h = (float(a[k]) for k in 'xywh'); bx, by, bw, bh = (float(b[k]) for k in ('x', 'y', 'w', 'h'))
    imw, imh = (int(v) for v in a['img'].split('x'))
    circ = h * (c1y - c0y) / ih; vis = bh * (b1 - b0) / him.height
    ccy = y + h * (c0y + c1y) / 2 / ih; bcy = by + bh * (b0 + b1) / 2 / him.height
    r = circ / vis
    chk.append((0.92 <= r <= 1.08, 'круг аватара %.1f px, видимый пузырь %.1f px: доля %.2f (0.92..1.08; было ~0.5)' % (circ, vis, r)))
    chk.append((abs(ccy - bcy) <= 2.0, 'центр круга по высоте на центре пузыря: разница %.1f px (<= 2)' % abs(ccy - bcy)))
    chk.append((imw / w >= 0.98, 'значок без растяжки: картинка %dx%d на %.0fx%.0f px экрана (текстель/пиксель %.2f >= 0.98)' % (imw, imh, w, h, imw / w)))
report('22 аватар = высота пузыря (эмулятор)', chk)

# ---- 48: пузырь в пропорциях оригинала (Hud.pag MessageBox 330x88), текст задания всегда внутри пузыря — и со значком, и без
pg = U.project('ingame.p3d').pages['Hud.pag']
src = next(e for _, e in U.iter_leaves(pg) if e['name'] == 'MessageBox')
T48 = [kv(l) for l in M if l.startswith('UIOBJTEXT ')]
chk = []
if not B or not T48:
    chk.append((False, 'нет строк UIBUBBLE / UIOBJTEXT (пузырь или текст задания не рисовались)'))
else:
    b = B[-1]; bx, by, bw, bh = (float(b[k]) for k in ('x', 'y', 'w', 'h'))
    asp, asp0 = bw / bh, src['w'] / src['h']
    chk.append((abs(asp / asp0 - 1) <= .03, 'пузырь %.0fx%.0f px: пропорции %.3f, в Hud.pag %.3f (±3 %%)' % (bw, bh, asp, asp0)))
    BT = {d['t']: d for d in B}   # пузырь того же кадра (при всплывании оба масштабируются от центра рамки)
    for pos, name in ((True, 'со значком'), (False, 'без значка')):
        L = [d for d in T48 if (d['icon'] == '1000') == pos and d['t'] in BT]
        if not L: chk.append((False, 'текст %s не рисовался' % name)); continue
        worst = min(L, key=lambda d: min(float(d['x']) - float(BT[d['t']]['x']),
                                         float(BT[d['t']]['x']) + float(BT[d['t']]['w']) - float(d['x']) - float(d['w'])))
        q = BT[worst['t']]; x0, x1 = float(worst['x']), float(worst['x']) + float(worst['w']); b0, b1 = float(q['x']), float(q['x']) + float(q['w'])
        chk.append((x0 >= b0 and x1 <= b1, 'текст %s (%d кадров): худший x %.1f..%.1f в пузыре %.1f..%.1f' % (name, len(L), x0, x1, b0, b1)))
report('48 пузырь как в оригинале, текст внутри (эмулятор)', chk)

# ---- 36: дорожка кольца полужёлтая, заливка — жёлтая целиком
G = [kv(l) for l in M if l.startswith('UIHNRBG ')]; F = [kv(l) for l in M if l.startswith('UIHNR ')]
chk = []


def abgr(s):
    v = int(s, 16); return (v >> 24) & 255, v & 255, (v >> 8) & 255, (v >> 16) & 255   # a, r, g, b


if not G:
    chk.append((False, 'нет строк UIHNRBG (дорожка кольца не рисуется — прозрачная)'))
else:
    al, r_, g_, b_ = abgr(G[-1]['col'])
    chk.append((0x60 <= al <= 0xA0 and r_ >= 200 and g_ >= 180 and b_ <= 80,
                'дорожка: цвет %s — жёлтый, альфа %d/255 (полужёлтая: 96..160)' % (G[-1]['col'], al)))
fills = [d for d in F if d.get('pursuit') == '0']
if fills:
    al, r_, g_, b_ = abgr(fills[-1]['col'])
    chk.append((al == 255 and r_ >= 200 and g_ >= 180 and b_ <= 80, 'заливка без погони: %s — жёлтая, непрозрачная' % fills[-1]['col']))
else:
    chk.append((False, 'нет строк UIHNR (заливка не рисовалась)'))
report('36 кольцо Hit & Run (эмулятор)', chk)

# ---- 26, 38: разговор — места, лицом друг к другу, жесты по данным, рот у говорящего
T = [kv(l) for l in M if l.startswith('TALK ')]
chk = []
mfk = (ROOT / 'hit-and-run-web/source/game/scripts/missions/level01/m0sdi.mfk').read_text(errors='replace')
npcA = re.findall(r'AddAmbientNpcAnimation\(\s*"([^"]*)"', mfk); pcA = re.findall(r'AddAmbientPcAnimation\(\s*"([^"]*)"', mfk)
pos = re.search(r'SetDialoguePositions\(\s*"([^"]*)"\s*,\s*"([^"]*)"', mfk)
if not T:
    chk.append((False, 'нет строк TALK (разговор не поставлен)'))
else:
    def ang(h, dx, dz):
        a = math.atan2(dx, dz) - h
        return abs((a + math.pi) % (2 * math.pi) - math.pi) * 180 / math.pi
    dist = [float(d['dist']) for d in T]
    herr, nerr = 0.0, 0.0
    for d in T:
        hx, hz, hh = (float(v) for v in d['homer'].split(',')); nx, nz, nh = (float(v) for v in d['npcpos'].split(','))
        herr = max(herr, ang(hh, nx - hx, nz - hz)); nerr = max(nerr, ang(nh, hx - nx, hz - nz))
    chk.append((min(dist) >= 1.4 and max(dist) <= 4.7 and max(dist) - min(dist) <= 0.05,
                'расстояние %.2f..%.2f м (места диска %s / %s; все разговоры диска 1.46..4.62 м), не друг в друге' %
                (min(dist), max(dist), pos.group(1) if pos else '-', pos.group(2) if pos else '-')))
    chk.append((herr <= 10.0, 'Гомер лицом к собеседнику: отклонение до %.1f° (<= 10)' % herr))
    chk.append((nerr <= 10.0, 'собеседник лицом к Гомеру: отклонение до %.1f° (<= 10)' % nerr))
    bad = []
    for d in T:
        ln = int(d['line']); g = d['gest'].split(',')
        want = [pcA[ln] if ln < len(pcA) else 'none', npcA[ln] if ln < len(npcA) else 'none']
        if g != want: bad.append('реплика %d: %s (данные %s)' % (ln, g, want))
    chk.append((not bad, 'жесты реплик = AddAmbientPc/NpcAnimation скрипта m0sdi.mfk' + ('' if not bad else ': ' + '; '.join(bad[:2]))))
    pcLines = [d for d in T if d['pc'] == '1']
    TL = [kv(l) for l in M if l.startswith('TALKLINE ')]   # итог каждой реплики: наибольшее открытие рта у каждого
    jh = [float(d['jawmax'].split(',')[0]) for d in TL if d['pc'] == '1']; lnn = [float(d['jawmax'].split(',')[1]) for d in TL if d['pc'] == '1']
    jn = [float(d['jawmax'].split(',')[1]) for d in TL if d['pc'] == '0']; lh = [float(d['jawmax'].split(',')[0]) for d in TL if d['pc'] == '0']
    chk.append((bool(jn) and min(jn) >= 0.12 and (not lh or max(lh) == 0.0), 'реплики собеседника: его рот до %s рад, Гомер молчит (%.2f)' %
                (','.join('%.2f' % v for v in jn) or '-', max(lh) if lh else 0)))
    chk.append((bool(jh) and min(jh) >= 0.12 and (not lnn or max(lnn) == 0.0), 'реплики Гомера: его рот до %s рад, собеседник молчит (%.2f)' %
                (','.join('%.2f' % v for v in jh) or '-', max(lnn) if lnn else 0)))
    chk.append((any(d['hclip'] == '1' for d in pcLines) or not any(pcA[int(d['line'])] != 'none' for d in pcLines if int(d['line']) < len(pcA)),
                'Гомер играет жест своей реплики (клип dialogue_* из homer.shr)'))
report('26+38 разговор (эмулятор)', chk)

# ---- 25: брифинг с первого нажатия X (Continue). Правка 52 (29.09, эталон PS2): «△ Cancel Mission» на карточке нет — △ её
# не закрывает; строка MSN briefing-loaded (конец LOADING) — не закрытие
chk = []
got = {'continue': 0, 'cancel': 0}; tri = 0
for i, l in enumerate(M):
    if not (l.startswith('MSN briefing ') and not l.startswith('MSN briefing-')):
        continue
    j = next((k for k in range(i + 1, len(M)) if M[k].startswith('MSN briefing-') and not M[k].startswith('MSN briefing-loaded')), None)
    if j is None:
        chk.append((False, 'брифинг %s не закрылся' % l.split()[2])); continue
    what = M[j].split()[1].split('-')[1]
    crosses = [p for p in M[i:j] if p.startswith('PRESS cross')]
    tri += sum(p.startswith('PRESS triangle') for p in M[i:j])
    chk.append((what == 'continue' and len(crosses) == 1, 'брифинг %s -> %s с %d-го нажатия X' % (l.split()[2], what, len(crosses))))
    got[what] = got.get(what, 0) + 1
chk.append((got['continue'] >= 2 and got['cancel'] == 0 and tri >= 1,
            'Continue %d раз, △ нажат %d раз и не закрыл (Cancel %d; правка 52 — кнопки Cancel нет)' % (got['continue'], tri, got['cancel'])))
report('25 брифинг с первого нажатия (эмулятор)', chk)

print('\n'.join(out))
sys.exit(1 if any(red.values()) else 0)
