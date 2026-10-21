#!/usr/bin/env python3
"""Правка Роба 348 (05.10, голосом): «В MISSION SELECT (DEV SAVE) не отображаются названия миссий — только 1 2 3 4, галочки и
тёмно-серый прямоугольник выбора; LEVEL 1 и статус — шрифты кривые, строки очень плотные; переключаться между уровнями».
Гейт в безоконном PPSSPP (scen.py скилла shar-level-polish, свой SCEN_HOME — карта с нуля, рядом с EBOOT файл devsave и наборы
уровней 2 и 7, SHIP_LEVELS="2 7"): LOAD GAME -> DEV SAVE -> уровень 1 -> пауза -> MISSION SELECT:
  1  экран оригинала открыт, DEV, уровней в списке 3 (1, 2, 7)
  2  названия всех 7 строк нарисованы и не обрезаны: правый край букв строки k = x + ширина строки гранью пакета (±), у номера свои
     буквы; шаг строк по буквам = шаг пакета и не плотнее 1,3 строки грани (до 348: 14 px при строке 11)
  3  ► -> LEVEL 2: названия уровня 2 (строка 0 — «Detention Deficit Disorder» по ширине), шарик ► красный сразу после нажатия и
     серый потом; ► -> LEVEL 7 (строка 3 — «There's Something About Monty»); ◄ -> LEVEL 2
  4  X на строке 5 уровня 2 -> загружен уровень 2 (LEVELUP 1 -> 2, LEVEL ev=load n=2), миссия m5 «Better Than Beef»
  5  полоса выбора в пакете — во всю строку: от номера до значка состояния
  5а правка 363 (по кадру LEVEL 1): номера по одному левому краю букв, поле от жёлтой линии рамки до номеров, до Status справа и до
     планки LEVEL N сверху — 8..14 px; номер и название на одной линии; LEVEL N по центру лица планки (не ниже), Status на той же
     высоте; шаг строк не меньше 1,5 строки грани. Красный 363 — прежний пакет (UI_MS_348=1 = pextra.shr правки 348): обязан упасть
  6  мост типографики (без эмулятора): pextra.shr с проверочным json — ms_rows шаг 22: строки шагом 22, значок и полоса выбора строки
     k сдвинуты как название строки k (rowcarry); ms_status — грань swz721n_10@1
КРАСНЫЙ (--red): тот же прогон с «flag uimsselold» (прежнее поведение: названия не рисуются, ◄ ► не листают) и мост выключен
(UI_TYPO=0 при том же ожидании) — гейт обязан упасть. --no-emu — только пункт 6.
python3 tests/ui/msel_348.py [--red] [EBOOT] [--pextra PAK]  -> 0 = PASS. GATE_OUT — папка (build/gates/msel348),
GATE_SCEN_OUT — куда scen.py кладёт прогоны (по умолчанию build/twins/scen/full дерева данных)"""
import json, os, re, shutil, struct, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path.home() / '.claude/skills/shar-level-polish/scripts'
DATA = Path(os.environ.get('SCEN_ROOT', '/Users/USER/Downloads/shar-psp'))
OUT = Path(os.environ.get('GATE_OUT', str(ROOT / 'build/gates/msel348')))
PX_MS = 1   # pextra.shr: экран 1 — MissionSelect
MENU = ['flag menu', 'flag saves', 'wait 1.5'] + ['press left', 'wait 0.3'] * 4 + ['press cross', 'wait 2', 'press down', 'wait 0.4',
        'press cross', 'wait 2.5', 'press cross', 'wait 7', 'flag svlog']
OPEN = ['press start', 'wait 1', 'press down', 'wait 0.4', 'press down', 'wait 0.4', 'press cross', 'wait 1']
FLOW = ['shot ms_l1', 'press right', 'wait 0.15', 'shot ms_l2_arrow', 'wait 0.4', 'shot ms_l2', 'press right', 'wait 0.5', 'shot ms_l7',
        'press left', 'wait 0.5', 'press up', 'wait 0.3', 'press up', 'wait 0.3', 'shot ms_l2b', 'press cross', 'wait 16', 'flag svlog',
        'shot l2_msn', 'end']


def pak(path):
    b = Path(path).read_bytes(); assert b[:4] == b'UIP1', path
    h = struct.unpack_from('<4s19Ii3f', b, 0)
    nitem, off_item, nscr, off_scr, nfont, off_font, nstr, off_str = h[4:12]
    strs = [b[o:b.index(b'\0', o)].decode('latin-1') for o in struct.unpack_from('<%dI' % nstr, b, off_str)]
    fonts = []
    for i in range(nfont):
        tex, lh, base, pad, name, _ = struct.unpack_from('<4H2I', b, off_font + i * (16 + 8 * 256))
        g = [struct.unpack_from('<HHBbBB', b, off_font + i * (16 + 8 * 256) + 16 + 8 * c) for c in range(256)]
        fonts.append(dict(name=strs[name], lh=lh, adv=[x[4] if x[5] else None for x in g], left=[x[3] for x in g], w=[x[2] for x in g]))
    first, count = struct.unpack_from('<4I', b, off_scr + 16 * PX_MS)[:2]
    its = []
    for i in range(first, first + count):
        r = struct.unpack_from('<8B4h2I4B2H3fIf3I', b, off_item + 64 * i)
        its.append(dict(type=r[0], field=r[3], flags=r[7], x=r[8], y=r[9], w=r[10], h=r[11], font=r[16], menu=r[17],
                        strings=strs[r[18]:r[18] + r[19]] if r[0] == 3 else []))
    return its, fonts


def width(f, s):
    q = f['adv'][ord('?')] or 0
    return sum((f['adv'][ord(c)] if f['adv'][ord(c)] is not None else q) for c in s)


def ink_right(f, s, x):
    """правый край букв строки s от x: ширина минус пустое у последней буквы (адванс − левый край − ширина рисунка)"""
    c = ord(s[-1]); a = f['adv'][c] or 0
    return x + width(f, s) - max(0, a - f['left'][c] - f['w'][c]) - 1


def rows_of(its):
    texts = [t for t in its if t['type'] == 3]
    names = sorted((t for t in texts if t['flags'] & 8 and len(t['strings']) == 7), key=lambda t: t['menu'])   # F_MENU, 7 уровней
    nums = sorted((t for t in texts if re.fullmatch(r'\d\.', (t['strings'] or [''])[0])), key=lambda t: t['y'])
    icons = sorted((t for t in its if t['type'] == 2 and FIELD_MS0 <= t['field'] < FIELD_MS0 + 7), key=lambda t: t['y'])   # MissionStatus0..6
    bars = [t for t in its if t['type'] == 0 and t['flags'] & 32]   # F_SELONLY
    return names, nums, icons, bars


def ink_cols(img, x0, x1, y0, y1, thr=140):
    a = np.asarray(img.convert('RGB')).astype(int)[max(0, y0):y1, max(0, x0):x1]
    lum = a.max(-1)
    cols = np.where((lum > thr).any(0))[0]; rows = np.where((lum > thr).any(1))[0]
    return (cols.min() + x0, cols.max() + x0, rows.min() + y0, rows.max() + y0) if len(cols) else None


def run(name, lines, eboot, pextra, home, levels):
    f = OUT / (name + '.txt'); f.write_text('\n'.join(lines) + '\n')
    flag = OUT / 'devsave'; flag.write_text('')
    ov = 'devsave=%s' % flag + (',pextra.shr=%s' % pextra if pextra else '')
    env = dict(os.environ, SCEN_EBOOT=eboot, SCEN_HOME=str(home), SHIP_LEVELS=levels, SCEN_OVERRIDE=ov)
    so = os.environ.get('GATE_SCEN_OUT')
    code = ('import sys; sys.path.insert(0, %r); import scen; from pathlib import Path; %s'
            'scen.run(%r, open(%r).read().splitlines())') % (str(SCRIPTS), 'scen.C.OUT = Path(%r); ' % so if so else '', 'ms348_' + name, str(f))
    r = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True, timeout=1200)
    m = re.search(r'^dir (\S+) bad', r.stdout, re.M)
    return Path(m.group(1)) if m else OUT / ('missing_' + name)


def kv(l): return dict(re.findall(r'(\w+)=(\S+)', l))


def first(log, pre, **want):
    for l in log:
        if l.startswith(pre) and all(kv(l).get(k) == v for k, v in want.items()): return l
    return None


def check_names(img, names, nums, fonts, lv, bad, tag):
    """строки уровня lv (0..6) на снимке: номер и название нарисованы, правый край букв названия = расчёт по грани (±3)"""
    got = []
    for k, t in enumerate(names):
        s = t['strings'][lv]; f = fonts[t['font']]; lh = f['lh']
        x1 = min([472] + [n['x'] - 2 for n in ROWS_ICONS])   # до столбца значков
        ink = ink_cols(img, t['x'] - 1, x1, t['y'] - 1, t['y'] + lh + 1)
        want = ink_right(f, s, t['x'])
        if ink is None: bad.append('%s: строка %d «%s» не нарисована' % (tag, k + 1, s)); got.append(None); continue
        if abs(ink[1] - want) > 3 or ink[0] > t['x'] + 3:
            bad.append('%s: строка %d «%s» — буквы %d..%d, ждём %d..%d (обрезана / не та)' % (tag, k + 1, s, ink[0], ink[1], t['x'], want))
        n = nums[k]; ni = ink_cols(img, n['x'] - 1, t['x'] - 1, n['y'] - 1, n['y'] + fonts[n['font']]['lh'] + 1)
        if ni is None: bad.append('%s: номер %d не нарисован' % (tag, k + 1))
        got.append(((ink[2] + ink[3]) / 2.0))
    return got


ROWS_ICONS = []
EDGE_MIN, EDGE_MAX = 8, 14   # правка 363: поле от жёлтой линии рамки до номеров, Status и планки LEVEL N (MS_EDGE 10)


def yellow_edges(img):
    """жёлтая линия рамки доски на кадре: (последний столбец слева, первый столбец справа, последняя строка сверху) — по середине"""
    a = np.asarray(img.convert('RGB')).astype(int); y = a[150]; col = a[:, 240]
    yel = lambda p: p[0] > 180 and p[1] > 130 and p[2] < 120
    xs = [x for x in range(20, 80) if yel(y[x])]; xr = [x for x in range(400, 470) if yel(y[x])]; ys = [r for r in range(20, 60) if yel(col[r])]
    return (max(xs) if xs else None, min(xr) if xr else None, max(ys) if ys else None)


def layout_363(img, its, names, nums, fonts, bad, notes):
    """правка 363 (Роб: «номера неровные — 2, 3 вылазят; отступ чуть больше; LEVEL N и Status выше, ближе к верху, свободнее; Status от
    края; LEVEL на планке выше; строки красивее»): по кадру LEVEL 1 и пакету"""
    xl, xr, yt = yellow_edges(img)
    if None in (xl, xr, yt): bad.append('363: на кадре не найдена жёлтая линия рамки'); return
    lefts = []
    for t in nums:
        q = ink_cols(img, t['x'] - 4, t['x'] + 20, t['y'] - 1, t['y'] + fonts[t['font']]['lh'] + 1)
        lefts.append(q[0] if q else None)
    if None in lefts or max(lefts) != min(lefts): bad.append('363: номера не по одному левому краю букв: %s' % lefts)
    elif not EDGE_MIN <= lefts[0] - xl - 1 <= EDGE_MAX: bad.append('363: от рамки до номеров %d px (ждём %d..%d)' % (lefts[0] - xl - 1, EDGE_MIN, EDGE_MAX))
    rows = [(t['y'], n['y']) for t, n in zip(names, nums)]
    if any(a_ != b_ for a_, b_ in rows): bad.append('363: номер и название строки не на одной линии букв: %s' % rows)
    st = next((t for t in its if t['type'] == 3 and t['strings'][:1] == ['Status']), None)
    a = np.asarray(img.convert('RGB')).astype(int)
    sq = None
    if st is not None:
        q = a[st['y'] - 2:st['y'] + 16, 340:xr]; m = (q[..., 0] > 150) & (q[..., 1] > 150) & (q[..., 2] < 120)
        cs = np.where(m.any(0))[0]; rs = np.where(m.any(1))[0]
        if len(cs): sq = (340 + cs.max(), st['y'] - 2 + rs.min(), st['y'] - 2 + rs.max())
    if sq is None: bad.append('363: Status не найден на кадре')
    elif not EDGE_MIN <= xr - sq[0] - 1 <= EDGE_MAX: bad.append('363: от Status до рамки справа %d px (ждём %d..%d)' % (xr - sq[0] - 1, EDGE_MIN, EDGE_MAX))
    bar = next((t for t in its if t['type'] == 2 and t['w'] > 100 and 15 <= t['h'] < 40 and t['y'] < 90), None)   # LevelBar
    if bar is None: bad.append('363: нет планки LevelBar'); return
    if not EDGE_MIN <= bar['y'] - yt - 1 <= EDGE_MAX: bad.append('363: планка LEVEL N на %d px от верхней линии (ждём %d..%d; ближе к верху)' % (bar['y'] - yt - 1, EDGE_MIN, EDGE_MAX))
    face = bar['y'] + bar['h'] * 0.4                      # [диск] levelbar.png: лицо — 16 строк из 20, центр 8/20
    q = a[bar['y']:bar['y'] + int(bar['h'] * 0.8), bar['x'] + 30:bar['x'] + bar['w'] - 30].max(-1) < 50
    rs = np.where(q.sum(1) > 2)[0]
    if not len(rs): bad.append('363: букв LEVEL N на планке не видно'); return
    cc = bar['y'] + (rs.min() + rs.max() + 1) / 2.0
    if not -1.5 <= cc - face <= 0.75: bad.append('363: LEVEL N на планке — центр букв %.1f при центре лица %.1f (ниже)' % (cc, face))
    if sq is not None and abs((sq[1] + sq[2] + 1) / 2.0 - cc) > 1.5: bad.append('363: Status и LEVEL N не на одной высоте (%.1f и %.1f)' % ((sq[1] + sq[2] + 1) / 2.0, cc))
    if not any(x.startswith('363') for x in bad):
        notes.append('363: номера с x %d (поле %d px), Status до рамки %d px, планка на %d px от верха, LEVEL N по центру лица (%.1f/%.1f)' %
                     (lefts[0], lefts[0] - xl - 1, xr - sq[0] - 1, bar['y'] - yt - 1, cc, face))
PY = str(ROOT / '.venv/bin/python') if (ROOT / '.venv/bin/python').exists() else '/Users/USER/Downloads/shar-psp/.venv/bin/python'


def typo_check(red, bad, notes):
    """мост: pextra.shr без настроек и с проверочным json (ms_rows pitch 22, ms_status face) — строки, значки, полосы"""
    tmp = OUT / 'typo'; tmp.mkdir(parents=True, exist_ok=True)
    js = tmp / 'test.json'; js.write_text(json.dumps({'version': 1, 'groups': {'ms_rows': {'pitch': 22}, 'ms_status': {'face': 'swz721n_10@1'}}}))
    out = {}
    for nm, typo in (('base', '0'), ('test', '0' if red else str(js))):
        env = dict(os.environ, UI_TYPO=typo, UI_SCRATCH=str(tmp / 'scratch'))
        r = subprocess.run([PY, 'tools/menu_export.py', '--pack', 'pextra', '--out', str(tmp / (nm + '.shr'))], cwd=ROOT, env=env,
                           capture_output=True, text=True)
        if r.returncode: bad.append('мост: экспорт pextra упал: %s' % (r.stderr.strip().splitlines() or ['?'])[-1]); return
        out[nm] = pak(tmp / (nm + '.shr'))
    (a, fa), (b, fb) = out['base'], out['test']
    na, ua, ia, ba = rows_of(a); nb, ub, ib, bb = rows_of(b)
    if len(nb) != 7 or len(ib) != 7: bad.append('мост: в пакете с json нет 7 строк'); return
    p = nb[1]['y'] - nb[0]['y']
    if p != 22: bad.append('мост: шаг строк %d, просили 22' % p)
    bar = lambda bs, k: next((x for x in bs if x['menu'] == k), None)
    for k in range(7):
        dy = nb[k]['y'] - na[k]['y']; di = ib[k]['y'] - ia[k]['y']; b0, b1 = bar(ba, k), bar(bb, k)
        if di != dy or (b0 and b1 and b1['y'] - b0['y'] != dy):
            bad.append('мост: строка %d — название сдвинуто на %d, значок на %d, полоса на %s (rowcarry)' % (k + 1, dy, di, b1['y'] - b0['y'] if b0 and b1 else '?'))
    st = next((t for t in b if t['type'] == 3 and t['strings'][:1] == ['Status']), None)
    if not st or fb[st['font']]['name'] != 'swz721n_10@1': bad.append('мост: Status не гранью swz721n_10@1 (%s)' % (fb[st['font']]['name'] if st else '-'))
    if not any('мост' in x for x in bad): notes.append('мост ms_rows/ms_status: шаг 22, значки и полосы едут со строками, Status — swz721n_10@1')


def main():
    red = '--red' in sys.argv; noemu = '--no-emu' in sys.argv; args = [a for a in sys.argv[1:] if a not in ('--red', '--no-emu')]
    pextra = None
    if '--pextra' in args: i = args.index('--pextra'); pextra = args[i + 1]; del args[i:i + 2]
    eboot = args[0] if args else str(DATA / 'build/EBOOT.PBP')
    pk = pextra or str(DATA / 'build/pextra.shr')
    OUT.mkdir(parents=True, exist_ok=True)
    its, fonts = pak(pk); names, nums, icons, bars = rows_of(its); ROWS_ICONS[:] = icons
    bad, notes = [], []
    typo_check(red, bad, notes)
    if noemu:
        print(('FAIL: ' + '; '.join(bad)) if bad else 'PASS: ' + '; '.join(notes)); return 1 if bad else 0
    if len(names) != 7 or len(nums) != 7:
        print('FAIL: в пакете %s нет 7 строк с названиями всех 7 уровней (строк %d, номеров %d) — пакет до 348?' % (pk, len(names), len(nums)))
        return 1
    have = [n for n in (2, 7) if (DATA / ('build/levels/l%d/level.shr' % n)).exists()]
    levels = ' '.join(str(n) for n in have)
    home = OUT / ('home_red' if red else 'home'); shutil.rmtree(home, ignore_errors=True)
    lines = MENU + (['flag uimsselold'] if red else []) + OPEN + FLOW
    d = run('red' if red else 'green', lines, eboot, pextra, home, levels)
    log = (d / 'smoke.txt').read_text(errors='replace').splitlines() if (d / 'smoke.txt').exists() else []
    op = first(log, 'MSNSEL open')
    if not op or kv(op).get('rows') != '1': bad.append('MISSION SELECT не экран оригинала: %s' % op)
    elif kv(op).get('levels') != str(1 + len(have)) or kv(op).get('dev') != '1':
        bad.append('уровней в списке %s (ждём %d: 1 и наборы %s), dev=%s' % (kv(op).get('levels'), 1 + len(have), levels, kv(op).get('dev')))
    else: notes.append('открыт: DEV, уровней %s' % kv(op)['levels'])
    shot = lambda s: Image.open(d / (s + '.png')) if (d / (s + '.png')).exists() else None
    a = shot('ms_l1')
    if a is None: bad.append('нет снимка ms_l1')
    else:
        cy = check_names(a, names, nums, fonts, 0, bad, 'LEVEL 1')
        pitch = names[1]['y'] - names[0]['y']; lh = fonts[names[0]['font']]['lh']
        cys = [c for c in cy if c is not None]
        if len(cys) == 7:
            dd = [round(cys[i + 1] - cys[i]) for i in range(6)]
            if any(abs(x - pitch) > 1 for x in dd): bad.append('шаг строк по буквам %s, в пакете %d' % (dd, pitch))
        if pitch < 1.5 * lh: bad.append('строки плотные: шаг %d при строке грани %d (меньше 1,5; правка 363)' % (pitch, lh))
        else: notes.append('строки: шаг %d px при строке грани %d (%s), названия LEVEL 1 целиком' % (pitch, lh, fonts[names[0]['font']]['name']))
        layout_363(a, its, names, nums, fonts, bad, notes)
    if have:
        if not first(log, 'MSNSEL level=2', moved='1'): bad.append('► не перелистнул на LEVEL 2')
        b = shot('ms_l2')
        if b is not None and 2 in have: check_names(b, names, nums, fonts, 1, bad, 'LEVEL 2')
        ar, b2 = shot('ms_l2_arrow'), b
        rb = next((t for t in its if t['type'] == 2 and t['field'] == FIELD_RARROW), None)
        if ar is not None and b2 is not None and rb is not None:
            def red_of(im):
                q = np.asarray(im.convert('RGB')).astype(int)[rb['y']:rb['y'] + rb['h'], rb['x']:rb['x'] + rb['w']]
                return float((q[..., 0] - q[..., 1]).mean())
            r1, r2 = red_of(ar), red_of(b2)
            if not r1 > r2 + 15: bad.append('шарик ► не покраснел после нажатия (красный−зелёный %.0f сразу, %.0f потом)' % (r1, r2))
            else: notes.append('шарик ►: красный сразу после нажатия (%.0f), серый потом (%.0f)' % (r1, r2))
        c = shot('ms_l7')
        if 7 in have:
            if not first(log, 'MSNSEL level=7', moved='1'): bad.append('► не перелистнул на LEVEL 7')
            elif c is not None: check_names(c, names, nums, fonts, 6, bad, 'LEVEL 7')
        if not first(log, 'MSNSEL want', level='2', row='4'): bad.append('X на строке 5 уровня 2 не выбран (нет MSNSEL want level=2 row=4)')
        lu, ld = first(log, 'LEVELUP', **{'from': '1', 'to': '2'}), first(log, 'LEVEL ev=load', n='2')
        sel = first(log, 'MSN select m5', level='2', row='4'); mm = first(log, 'MSN mission m5')
        if not (lu and ld and sel and mm): bad.append('уровень 2 с миссией m5 не загрузился (LEVELUP %s, load %s, select %s, mission %s)' %
                                                 (bool(lu), bool(ld), bool(sel), bool(mm)))
        else: notes.append('X на «Better Than Beef» (LEVEL 2): уровень 2 загружен за %s мс, миссия %s' % (kv(ld).get('ms'), mm.split('"')[1]))
    else: notes.append('наборов build/levels/l2, l7 нет — листание не проверено')
    # 5: полоса выбора во всю строку (пакет)
    x0n = min(n['x'] for n in nums); x1i = max(i['x'] + i['w'] for i in icons)
    if not bars or any(b['x'] > x0n - 2 or b['x'] + b['w'] < x1i + 2 for b in bars):
        bad.append('полоса выбора не во всю строку: %s при номерах с %d и значках до %d' % ([(b['x'], b['w']) for b in bars[:1]], x0n, x1i))
    else: notes.append('полоса выбора %d..%d (номера с %d, значки до %d)' % (bars[0]['x'], bars[0]['x'] + bars[0]['w'], x0n, x1i))
    print(('FAIL: ' + '; '.join(bad)) if bad else 'PASS: ' + '; '.join(notes))
    print('прогон: %s' % d)
    return 1 if bad else 0


FIELD_RARROW, FIELD_MS0 = 81, 69   # tools/ui_export.py FIELDS (viewer/ui.h UI_F_MS_RARROW, UI_F_MS0)
if __name__ == '__main__':
    sys.path.insert(0, str(ROOT / 'tools'))
    try:
        import ui_export as U
        FIELD_RARROW, FIELD_MS0 = U.FIELDS.index('MS_RARROW'), U.FIELDS.index('MS0')
    except Exception:
        pass
    sys.exit(main())
