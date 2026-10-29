#!/usr/bin/env python3
"""Вердикт «зелёный / жёлтый / красный» по каждой сцене замер-тура с PSP, без видео.

  python3 tools/hw_verdict.py ПАПКА_ТУРА [--thr tests/hw_thresholds.txt] [--out ВЕРДИКТ.md] [--strict]
  (ПАПКА_ТУРА — та, где лежит smoke.txt, например build/psp-tour/20261015-2208-SHARTEST19)

Источники в smoke.txt (все пишет viewer/smoke.h, новых строк движка для базового вердикта не нужно):
  STAT      — итог сцены: кадров, p95/p99/max мс работы, пропуски периода, видимые незагруженные клетки, отказы памяти, ошибки чтения;
  SLOWFRAME — каждый пропущенный кадр: t, work (УЖЕ без времени журнала: smoke.h вычитает smkIoUs), io (мс записи журнала в этом кадре), логика;
  RFAST     — раз в секунду: dd (дальность города, м), ktris, draws; dd на полу регулятора = резать дальностью больше нечего;
  RBLD      — раз в секунду: мс на кадр по подсистемам (city/car/npc/trf/mcr/props/fx/ui) — кого винить;
  CLIPG     — раз в секунду: seen_close / drawn_close / hidden (viewer/clipguard.h, ветка clip-guard): объект нарисован ближе 0,3 м к глазу;
  CAMIN     — итог правила камеры за сцену (viewer/main_loop.h, команда «camin»): кадры «глаз внутри», рядом с землёй, в машине, в человеке;
  SCENE     — границы сцен по времени (CLIPG/RFAST привязываются к сцене по t).
Вердикт по work (время игры), а не по io журнала: кадр, где журнал дал >= IO_ART мс, помечается «артефакт теста» и не краснит сцену,
если без таких кадров сцена проходит. Пороги — tests/hw_thresholds.txt (default + правила по regexp имени сцены, последнее совпавшее побеждает).
Выход: таблица сцена · вердикт · что красное · кому, и одна строка итога. Код возврата: 0 нет красных, 1 есть красные, 2 нет данных."""
import re, sys, argparse
from pathlib import Path
from collections import defaultdict

IO_ART = 2.0   # мс журнала в кадре, с которого кадр считается испорченным самим тестом

# кому писать: подсистема кадра -> владелец (наряд 15.10)
OWNER = {'city': 'Сборка', 'water': 'Сборка', 'car': 'Стены', 'npc': 'Стены', 'trf': 'Стены', 'mcr': 'Стены', 'props': 'Стены',
         'fx': 'Стены', 'ui': 'Аудит-Типографики', 'load': 'Загрузка2', 'cam': 'Камера', 'logic': 'Стены', 'build': 'Сборка'}


def load_thr(path):
    d = dict(p95=32.5, p99=40.0, max=75.0, miss_pct=3.0, streak=4, ddfloor_pct=60.0, ddfloor_p95=30.0, missvis=0, clip=0, camin=0,
             memfail=0, readerr=0, eyein=0, eyeedge=0, wallvox=0, wallfront=0, heapmin=6.0)
    rules = []
    if path and Path(path).exists():
        for ln in Path(path).read_text().splitlines():
            ln = ln.split('#', 1)[0].strip()
            if not ln: continue
            p = ln.split()
            kv = {a.split('=')[0]: float(a.split('=')[1]) for a in p[1:] if '=' in a}
            if p[0] == 'default': d.update(kv)
            else: rules.append((re.compile(p[0]), kv))
    return d, rules


def thr_for(name, d, rules):
    t = dict(d)
    for rx, kv in rules:
        if rx.search(name): t.update(kv)
    return t


def kv_of(parts):
    out = {}
    for x in parts:
        if '=' in x:
            k, v = x.split('=', 1); out[k] = v
    return out


def num(s, default=0.0):
    try: return float(s.split('/')[0])
    except Exception: return default


_TAGS = ('STAT', 'SLOWFRAME', 'SCENE', 'RFAST', 'RBLD', 'CLIPG', 'CAMIN', 'CAMCLIPSTAT', 'GGSTAT', 'SHOT', 'FOOT', 'PLACE', 'TELEPORT', 'IRIS', 'PHSEC', 'PHSUB', 'PHDRAW')
_GLUE = re.compile(r'(?<=[0-9a-z.\)=])(?=(?:' + '|'.join(_TAGS) + r') )')
GLUED = [0]


def unglue(lines):
    """строки, приклеенные к оборванной предыдущей (движок обрезал TQTOP без перевода строки): режем по тегу, иначе STAT/SLOWFRAME пропадают из вердикта"""
    out = []
    for ln in lines:
        if ln and ln[0] != ' ' and _GLUE.search(ln):
            parts = _GLUE.split(ln); GLUED[0] += len(parts) - 1; out += parts
        else: out.append(ln)
    return out


def parse(smoke):
    smoke = unglue(smoke)
    sc_t = []          # (t, имя) границы сцен
    stat = {}          # имя -> dict
    slow = defaultdict(list)    # имя -> [(t, work, io, logic, cpu)]
    rfast = defaultdict(list)   # имя -> [(dd, ktris, draws)]
    rbld = defaultdict(list)    # имя -> [dict подсистем]
    clip = []          # (t, seen, drawn, hidden)
    cclip = []         # (t, кадров, глаз внутри ящика куска города, глаз ближе 0,3 м к грани, макс. кусков под ближней плоскостью)
    gg = []            # (t, кадров, кадров с ggOn): срез города на CPU для всего кадра (ближняя плоскость < NEAR_Z)
    dpc = []           # (t, сцена, drawpiece на кадр) из RBLD
    secrows = defaultdict(list)   # имя сцены -> [(t, пропуски, видимые недогруженные)] из строки раз в секунду
    tele = []          # моменты телепорта сценарием: FOOT, PLACE (goto в журнал не пишется)
    iris = []          # моменты строки IRIS (ирис/газета: игрок видит мир)
    marks = []         # моменты, когда сам тест пишет пачку строк/снимок: граница сцены, SHOT
    camin = defaultdict(lambda: defaultdict(int))
    order = []
    for ln in smoke:
        if ln.startswith('SCENE '):
            p = ln.split()
            if len(p) >= 3:
                try: sc_t.append((float(p[2]), p[1])); marks.append((float(p[2]) - 0.4, float(p[2]) + 0.4))
                except ValueError: pass
        elif ln.startswith(('FOOT ', 'PLACE ', 'TELEPORT ')):
            m = re.search(r' t=([\d.]+)', ln)
            if m: tele.append(float(m.group(1)))
        elif ln.startswith('IRIS '):
            m = re.search(r' t=([\d.]+)', ln)
            if m: iris.append(float(m.group(1)))
        elif ln[:1].isdigit() and len(ln.split()) > 12 and re.match(r'^\d+\.\d ', ln):
            q = ln.split()
            try: secrows[q[1]].append((float(q[0]), num(q[10]), num(q[11])))
            except (ValueError, IndexError): pass
        elif ln.startswith('SHOT ') and len(ln.split()) > 2:
            try: t0 = float(ln.split()[2]); marks.append((t0 - 0.4, t0 + 0.8))   # снимок: bmp 390 КБ на карту
            except ValueError: pass
        elif ln.startswith('STAT '):
            p = ln.split(); kv = dict(zip(p[2::2], p[3::2]))
            if kv.get('frames', '0') != '0':
                stat[p[1]] = kv; order.append(p[1])
        elif ln.startswith('SLOWFRAME '):
            kv = kv_of(ln.split())
            slow[kv.get('scene', '?')].append((num(kv.get('t')), num(kv.get('work')), num(kv.get('io')), num(kv.get('logic')), num(kv.get('cpu'))))
        elif ln.startswith('RFAST '):
            kv = kv_of(ln.split()); rfast[kv.get('sc', '?')].append((num(kv.get('dd')), num(kv.get('ktris')), num(kv.get('draws'))))
        elif ln.startswith('GGSTAT '):
            kv = kv_of(ln.split()); gg.append((num(kv.get('t')), num(kv.get('frames')), num(kv.get('ggOn'))))
        elif ln.startswith('RBLD '):
            kv = kv_of(ln.split()); dpc.append((num(kv.get('t')), kv.get('sc', '?'), num(kv.get('drawpiece'), -1)))
            rbld[kv.get('sc', '?')].append({k: num(kv[k]) for k in ('city', 'car', 'npc', 'trf', 'mcr', 'props', 'fx', 'ui') if k in kv})
        elif ln.startswith('CAMCLIPSTAT '):
            kv = kv_of(ln.split()); cclip.append((num(kv.get('t')), num(kv.get('frames')), num(kv.get('eye_inside')), num(kv.get('near03')), num(kv.get('clip_pieces_max')), num(kv.get('wall_vox'), -1), num(kv.get('wall_grid'), -1), num(kv.get('wall_front'), -1)))
        elif ln.startswith('CLIPG '):
            kv = kv_of(ln.split()); clip.append((num(kv.get('t')), num(kv.get('seen_close')), num(kv.get('drawn_close')), num(kv.get('hidden'))))
        elif ln.startswith('CAMIN '):
            kv = kv_of(ln.split())
            # CAMIN печатается в конце сцены сценарием «camin»; сцену берём по t
            camin[num(kv.get('t'))] = kv
    return sc_t, stat, order, slow, rfast, rbld, clip, camin, marks, cclip, secrows, tele, iris, gg, dpc


def scene_at(sc_t, t):
    cur = None
    for tt, n in sc_t:
        if tt <= t + 1e-6: cur = n
        else: break
    return cur


def streaks(frames, per):
    """самая длинная серия подряд идущих медленных кадров (между соседями не больше ~двух периодов)"""
    gap = per * 0.0167 * 2.1
    best = cur = 0; prev = None
    for t in sorted(f[0] for f in frames):
        cur = cur + 1 if prev is not None and t - prev <= gap else 1
        best = max(best, cur); prev = t
    return best


FLOOR_DD = [0.0]


def judge(name, kv, frames, rf, rb, clipn, caminv, thr, marks=(), cc=None, secs=(), tele=(), iris=(), scene_t0=None):
    per = int(num(kv.get('per'), 2)) or 2
    scale = per / 2.0   # пороги даны для 30 FPS (per=2); для 60 FPS (per=1) вдвое строже
    nfr = int(num(kv.get('frames')))
    p95, p99, mx = num(kv.get('p95')), num(kv.get('p99')), num(kv.get('max'))
    missed = int(num(kv.get('missed')))
    red, amber, art = [], [], []
    # --- кадры: артефакт журнала отдельно от игры
    def spoiled(f): return f[2] >= IO_ART or any(a <= f[0] <= b for a, b in marks)   # журнал >= 2 мс, либо рядом граница сцены / снимок
    clean = [f for f in frames if not spoiled(f)]
    dirty = [f for f in frames if spoiled(f)]
    mx_clean = max([f[1] for f in clean], default=0.0)
    mx_all = max([mx] + [f[1] for f in frames])
    st_all = streaks(frames, per); st_clean = streaks(clean, per)
    miss_pct = 100.0 * missed / max(nfr, 1)
    miss_clean_pct = 100.0 * len(clean) / max(nfr, 1)
    T = {k: thr[k] for k in thr}
    P95, P99, MX = T['p95'] * scale, T['p99'] * scale, T['max'] * scale
    own = {}
    # --- p95/p99: считаются по всем кадрам; если красные только из-за журнала (≥ половины медленных кадров с io) — «артефакт»
    io_dom = frames and len(dirty) >= max(1, len(frames) // 2)
    if p95 > P95:
        (art if io_dom and miss_clean_pct <= T['miss_pct'] else red).append(f'p95 {p95:.1f} > {P95:.1f} мс')
    elif p95 > P95 * 0.95: amber.append(f'p95 {p95:.1f} (порог {P95:.1f})')
    if p99 > P99:
        (art if io_dom and miss_clean_pct <= T['miss_pct'] else red).append(f'p99 {p99:.1f} > {P99:.1f} мс')
    # --- худший кадр: если он с io — артефакт
    if mx_all > MX:
        if mx_clean <= MX and dirty and max(f[1] for f in dirty) > MX:
            w = max(dirty, key=lambda f: f[1])
            art.append(f'худший кадр {w[1]:.0f} мс при записи журнала {w[2]:.0f} мс (t={w[0]:.1f}) — артефакт теста')
        else: red.append(f'худший кадр {mx_all:.0f} мс > {MX:.0f}')
    # --- пропуски периода
    if miss_pct > T['miss_pct']:
        (art if miss_clean_pct <= T['miss_pct'] else red).append(f'пропусков {missed} из {nfr} = {miss_pct:.1f} % > {T["miss_pct"]:.1f} %' + (f' (без кадров журнала {miss_clean_pct:.1f} %)' if dirty else ''))
    elif miss_pct > T['miss_pct'] * 0.7: amber.append(f'пропусков {miss_pct:.1f} %')
    # --- серия медленных кадров
    if st_clean > T['streak']: red.append(f'серия медленных кадров {st_clean} подряд > {int(T["streak"])}')
    elif st_all > T['streak'] and st_clean <= T['streak']: art.append(f'серия {st_all} подряд прерывается журналом (без него {st_clean})')
    # --- недорисовано
    mv = int(num(kv.get('missvis'))); mvmax = int(num(kv.get('missvismax')))
    # недогруз видимых клеток: красный всегда, кроме первой 1,0 с после телепорта сценария (goto/foot/place: клетки догружаются, игрок мир не видит).
    # Исключение из исключения: рядом с ирисом/газетой (сброс машины, переход к миссии) телепорт игровой, там красный всегда. Окно не расширять (слово дирижёра 16.10).
    if mv > T['missvis']:
        def tele_win(ts):   # строка раз в секунду с меткой t описывает (t-1.05, t]; окно телепорта [tp, tp+1.0]
            for tp in tele:   # старт сцены после загрузки уровня/газеты НЕ телепорт: игрок видит мир, красный всегда (слово дирижёра 16.10)
                if tp - 0.05 <= ts <= tp + 1.05 and not any(abs(i - tp) <= 1.5 for i in iris): return True   # строка (ts-1.05, ts]: секунда телепорта и следующая; позже — красный (аудит 16.10: прежнее условие прощало до tp+2,05)
            return False
        bad_secs = [r for r in secs if r[2] > 0 and not tele_win(r[0])]
        if secs and not bad_secs:
            art.append(f'недогруженные клетки на экране {mv} кадров только в первую секунду после телепорта сценария (goto/foot) — справка, не провал')
        else:
            red.append(f'недогруженные клетки на экране: {mv} кадров (до {mvmax} клеток разом)' + (f'; вне окна телепорта в секундах: {", ".join(f"{r[0]:.0f}" for r in bad_secs[:6])}' if bad_secs else ''))
    hm = num(kv.get('heapmin'), 1e9)
    if hm < T['heapmin']: red.append(f'куча: минимум {hm:.2f} МБ < {T["heapmin"]:.0f} МБ (запас на стриминг и дальние версии кусков)')
    elif hm < T['heapmin'] + 1.5: amber.append(f'куча: минимум {hm:.2f} МБ (порог {T["heapmin"]:.0f})')
    if int(num(kv.get('memfail'))) > T['memfail']: red.append(f'отказы памяти {kv.get("memfail")}')
    if int(num(kv.get('readerr'))) > T['readerr']: red.append(f'ошибки чтения карты {kv.get("readerr")}')
    if kv.get('gebad', '0') not in ('0', '0.00', '0.0'): red.append(f'кадров с ошибкой списка GE {kv.get("gebad")}')
    # --- дальность на полу регулятора: резать нечем, а кадр всё равно длинный
    if rf:
        floor = (FLOOR_DD[0] if FLOOR_DD[0] else 150.0) + .5 if per >= 2 else 100.5   # пол регулятора берётся из лога тура (TEST21/22: 200, TEST19/23: 150)
        fl = sum(1 for r in rf if r[0] <= floor); pct = 100.0 * fl / len(rf)
        if pct >= T['ddfloor_pct'] and p95 > T['ddfloor_p95'] * scale and not (io_dom):
            red.append(f'дальность на полу ({floor - 0.5:.0f} м) {pct:.0f} % времени, а p95 {p95:.1f}: регулятору нечем резать (стоимость вне дальности)')
        elif pct >= T['ddfloor_pct']: amber.append(f'дальность на полу {pct:.0f} % времени')
    # --- проваливание камеры
    if clipn is not None:
        seen, drawn, hid = clipn
        if drawn > T['clip']: red.append(f'камера: нарисовано ближе 0,3 м к глазу {int(drawn)} (машины/NPC/пропы), скрыто {int(hid)}')
    if caminv:
        any_ = int(num(caminv.get('any'))); eye = int(num(caminv.get('eye'))); near = int(num(caminv.get('near')))
        if any_ > T['camin']: red.append(f'камера внутри геометрии: {any_} кадров (глаз {eye}, ближняя плоскость {near}, земля {caminv.get("ground")}, машина {caminv.get("car")}, человек {caminv.get("person")})')
    if cc is not None:
        ein, nr, mxp, wv, wg, wf = int(cc[0]), int(cc[1]), int(cc[2]), int(cc[3]), int(cc[4]), int(cc[5])
        # ящик куска (AABB) — не геометрия: глаз над улицей почти всегда внутри ящика большого куска мостовой/квартала (TEST20b: 22 ложных красных,
        # на снимках чистая трава и улица). Красным считается только то, что подтверждено геометрией: поле wall_vox (занят воксель стены у глаза,
        # camgrid) или CAMIN any > 0 в той же сцене. Голый счёт по ящику — справка (жёлтое), а не провал.
        # wall_vox считает воксель глаза и 6 соседей на 0,3 м В ЛЮБОЙ стороне: на снимках TEST22 (причал, такси на открытой дороге L5) это стена сбоку/сзади или
        # бордюр, которая в кадре не мешает — красным его делать нельзя. Красным считается wall_front (воксель ПЕРЕД глазом по взгляду, в пределах ближней
        # плоскости + запас) либо CAMIN any > 0 в той же сцене; wall_vox без них — справка.
        if wf > T['wallfront']: red.append(f'камера: стена перед глазом по взгляду (wall_front) {wf} кадров')
        elif wv > T['wallvox'] and wf < 0 and caminv and int(num(caminv.get('any'))) > 0: red.append(f'камера: стена у глаза (wall_vox {wv} кадров) и CAMIN any>0')
        elif wv > T['wallvox'] and wf < 0: art.append(f'камера: wall_vox {wv} кадров (справка: воксель в любой стороне от глаза, не по взгляду; красным не считается)')
        elif wv == 0 and wg == 0 and wf <= 0: art.append('камера: сетка стен не была построена ни в одном кадре сцены (wall_grid=0), проверка «стена у глаза» не состоялась — не доказательство, что стены нет')
        elif (ein > T['eyein'] or nr > T['eyeedge']) and wv < 0:
            (red if caminv and int(num(caminv.get('any'))) > 0 else art).append(f'камера: глаз в ящике куска {ein} / ближе 0,3 м к ящику {nr} кадров (справка: по ящику, геометрией не подтверждено' + (', CAMIN any>0 — подтверждено' if caminv and int(num(caminv.get('any'))) > 0 else '') + ')')
    # --- кого винить: подсистемы из RBLD + фазы медленных кадров
    culprit = ''
    if rb:
        avg = {k: sum(r.get(k, 0) for r in rb) / len(rb) for k in ('city', 'car', 'npc', 'trf', 'mcr', 'props', 'fx', 'ui')}
        top = sorted(avg.items(), key=lambda x: -x[1])[:2]
        culprit = ' · '.join(f'{k} {v:.1f} мс' for k, v in top)
        own['top'] = top[0][0]
    if frames:
        n = len(frames)
        lg = sum(f[3] for f in frames) / n; bd = sum(max(f[4] - f[3], 0) for f in frames) / n
        own['phase'] = 'сборка списка GE' if bd > lg * 1.5 else 'логика'
    heavy_art = any(x.startswith(('p95', 'пропусков')) for x in art)   # справка по ящику в art тоже есть, но на вердикт не влияет   # журнал испортил главную меру сцены — зелёным не называем
    v = 'КРАСНЫЙ' if red else ('ЖЁЛТЫЙ' if amber else ('НЕ ДОКАЗАНО' if heavy_art else ('ЗЕЛЁНЫЙ' if not art else 'ЗЕЛЁНЫЙ*')))
    return dict(verdict=v, red=red, amber=amber, art=art, culprit=culprit, own=own, p95=p95, miss_pct=miss_pct, nfr=nfr)


def owner_of(res):
    if not res['red']: return ''
    txt = res['red'][0]
    if 'камера' in txt: return OWNER['cam']
    if 'недогруж' in txt or 'ошибки чтения' in txt or 'отказы памяти' in txt: return OWNER['load']
    t = res['own'].get('top')
    if t and res['own'].get('phase') == 'сборка списка GE' and t in OWNER: return OWNER[t]
    return OWNER.get(t, 'Сборка') if t else 'Сборка'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir'); ap.add_argument('--thr', default=str(Path(__file__).resolve().parent.parent / 'tests' / 'hw_thresholds.txt'))
    ap.add_argument('--out'); ap.add_argument('--ab', help='ACCT другого прохода (файл acct.txt или папка): проход A (этот тур) против B по шести счетам, порог шума по двум одинаковым отрезкам (tools/acct_ab.py)'); ap.add_argument('--same', default='', help='имена двух одинаковых сцен для порога шума (--ab)'); ap.add_argument('--base', help='тур-база: сравнить drawpiece на кадр по одноимённым сценам (без префикса T19_/T20_)'); ap.add_argument('--strict', action='store_true', help='жёлтое тоже считать провалом (код 1)')
    a = ap.parse_args()
    d = Path(a.dir); f = d / 'smoke.txt'
    if not f.exists(): print(f'нет {f}'); return 2
    sc_t, stat, order, slow, rfast, rbld, clip, camin, marks, cclip, secrows, tele, iris, gg, dpc = parse(f.read_text(errors='replace').splitlines())
    if not stat: print('в smoke.txt нет строк STAT с кадрами'); return 2
    base, rules = load_thr(a.thr)
    alldd = [round(r[0]) for v in rfast.values() for r in v if r[0] > 0]   # пол дальности = наименьшее dd, которое держится в >= 5 % строк RFAST тура
    if alldd:
        from collections import Counter
        cnt = Counter(alldd); FLOOR_DD[0] = float(min(k for k, c in cnt.items() if c >= 0.05 * len(alldd)))
    nostat = [n for t, n in sc_t if n not in stat and not n.endswith('_load') and n != 'start']
    clipsc = defaultdict(lambda: [0.0, 0.0, 0.0])
    for t, s, dr, h in clip:
        n = scene_at(sc_t, t - 0.5)   # строка пишется раз в секунду за прошедшую секунду
        if n: c = clipsc[n]; c[0] += s; c[1] += dr; c[2] += h
    ccsc = {}
    for t, fr, ein, nr, mxp, wv, wg, wf in cclip:
        n = scene_at(sc_t, t - 0.5)
        if n: c = ccsc.setdefault(n, [0, 0, 0, -1, -1, -1]); c[5] = (max(c[5], 0) + wf) if wf >= 0 else c[5]; c[4] = (max(c[4], 0) + wg) if wg >= 0 else c[4]; c[0] += ein; c[1] += nr; c[2] = max(c[2], mxp); c[3] = wv if (wv >= 0 and c[3] < 0) else (c[3] + max(wv, 0) if wv >= 0 else c[3])
    caminsc = {}
    for t, kv in camin.items():
        n = scene_at(sc_t, t)
        if n: caminsc[n] = kv
    t0s = {n: t for t, n in sc_t}
    ggs = defaultdict(lambda: [0.0, 0.0]); dps = defaultdict(list)
    for t, fr, on in gg:
        n = scene_at(sc_t, t - 0.5)
        if n and t >= t0s.get(n, 0) + 2.0: ggs[n][0] += fr; ggs[n][1] += on
    for t, n, v in dpc:
        if v >= 0 and n in t0s and t >= t0s[n] + 2.0: dps[n].append(v)
    basedp = {}
    if a.base and (Path(a.base) / 'smoke.txt').exists():
        b = parse((Path(a.base) / 'smoke.txt').read_text(errors='replace').splitlines())
        bt0 = {n: t for t, n in b[0]}; tmp = defaultdict(list)
        for t, n, v in b[14]:
            if v >= 0 and n in bt0 and t >= bt0[n] + 2.0: tmp[n.split('_', 1)[-1]].append(v)
        basedp = {k: sum(x) / len(x) for k, x in tmp.items() if x}
    rows = []; counts = defaultdict(int)
    for name in order:
        kv = stat[name]; thr = thr_for(name, base, rules)
        res = judge(name, kv, slow.get(name, []), rfast.get(name, []), rbld.get(name, []), clipsc.get(name) if clip else None, caminsc.get(name), thr, marks, ccsc.get(name), secrows.get(name, []), tele, iris, t0s.get(name))
        ginfo = ''
        g = ggs.get(name)
        if g and g[0] > 0 and g[1] / g[0] >= 0.2: ginfo += f'ggOn (срез города на CPU) {100 * g[1] / g[0]:.0f} % кадров'
        dv = dps.get(name); bd = basedp.get(name.split('_', 1)[-1])
        if dv:
            m = sum(dv) / len(dv)
            if bd and m >= 1.5 * bd and m - bd >= 10: ginfo += ('; ' if ginfo else '') + f'drawpiece на кадр {m:.0f} против базы {bd:.0f} (×{m / bd:.1f})'
            elif not bd and m >= 120: ginfo += ('; ' if ginfo else '') + f'drawpiece на кадр {m:.0f}'
        res['info'] = ginfo
        res['name'] = name; res['owner'] = owner_of(res); rows.append(res); counts[res['verdict'].rstrip('*')] += 1
    out = [f'# Вердикт замер-тура · {d.name}', '']
    if caminsc: out += ['**Внимание:** в туре сценарий включает `flag camin 1` (сбор всех треугольников у глаза каждый кадр): по замеру Камеры 16.10 это 3–5,7 мс на железе. Время кадра завышено; сравнивать только с турами, где camin включён так же (TEST19 без camin).', '']
    if FLOOR_DD[0]: out += [f'Пол регулятора дальности в этом туре: {FLOOR_DD[0]:.0f} м (по логу RFAST).', '']
    if GLUED[0]: out += [f'Склеенных строк журнала разобрано: {GLUED[0]} (движок обрезал строку TQTOP без перевода строки; без разбора STAT и SLOWFRAME терялись).', '']
    if nostat: out += [f'**Тур неполный:** сцены без итога STAT: {", ".join(nostat)}', '']
    out.append('Источник: smoke.txt (STAT, SLOWFRAME, RFAST, RBLD' + (', CLIPG' if clip else '; CLIPG в этом туре нет — движок без clip-guard, счётчик «камера у объекта» не проверен') +
               (', CAMIN' if caminsc else '; CAMIN в этом туре нет — правило «глаз внутри» не проверено') + (', CAMCLIPSTAT' if cclip else '; CAMCLIPSTAT нет — «глаз в ящике куска города» не проверено') + '). Пороги: ' + str(a.thr))
    out += ['', '| сцена | кадров | p95 мс | пропуски % | вердикт | что красное / жёлтое | кому |', '|---|---|---|---|---|---|---|']
    for r in rows:
        why = '; '.join(r['red']) or '; '.join(r['amber'])
        if r.get('info'): why = (why + '; ' if why else '') + '[справка: ' + r['info'] + ']'
        if r['art']: why = (why + '; ' if why else '') + '[артефакт теста / справка: ' + '; '.join(r['art']) + ']'
        if r['red'] and r['culprit']: why += f' · по подсистемам: {r["culprit"]} ({r["own"].get("phase", "")})'
        out.append(f'| {r["name"]} | {r["nfr"]} | {r["p95"]:.1f} | {r["miss_pct"]:.1f} | {r["verdict"]} | {why or "—"} | {r["owner"] or "—"} |')
    red = counts['КРАСНЫЙ']; tot = len(rows)
    nd = counts['НЕ ДОКАЗАНО']
    summary = f'ИТОГ: {"КРАСНЫЙ" if red else ("НЕ ДОКАЗАНО" if nd else "ЗЕЛЁНЫЙ")} · сцен {tot}: зелёных {counts["ЗЕЛЁНЫЙ"]}, жёлтых {counts["ЖЁЛТЫЙ"]}, красных {red}, не доказано (журнал испортил замер, перегнать) {nd}' + \
              (' · красные: ' + ', '.join(r['name'] for r in rows if r['verdict'] == 'КРАСНЫЙ') if red else '')
    out += ['', 'НЕ ДОКАЗАНО — p95 или пропуски вышли за порог только из-за кадров, испорченных самим тестом; сцену перегнать с буфером журнала (claude/smk-buf).', 'ЗЕЛЁНЫЙ* — зелёный после вычета кадров, испорченных самим журналом (запись на карту >= 2 мс в кадре).', '', summary]
    if (d / 'acct.txt').exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location('acct_ab', Path(__file__).resolve().parent / 'acct_ab.py'); ab = importlib.util.module_from_spec(spec); spec.loader.exec_module(ab)
        A = ab.parse(str(d / 'acct.txt'))
        secs = sum(len(v) for v in A.values()); cost = [r['acct_us'] for v in A.values() for r in v if 'acct_us' in r]
        out += ['', f'Учёт ACCT: {secs} секунд в {len(A)} сценах; цена учёта в секунду: среднее {sum(cost) / len(cost):.0f} мкс, макс {max(cost):.0f} мкс.' if cost else f'Учёт ACCT: {secs} секунд.']
        empty = [n for n in A if n not in stat]   # сцены, где STAT пуст (например, после RESUME кадры не «успокоились»): сводка по учёту
        if empty:
            out += ['', 'Сцены без итога STAT, по учёту ACCT (секунды без первых двух):', '', '| сцена | секунд | work ср. | work макс | cpu ср. | ждём GE | ктрис | draws | недогруз макс |', '|---|---|---|---|---|---|---|---|---|']
            for n in empty:
                v = A[n]; w = v[2:] or v; av = lambda k: sum(r.get(k, 0) for r in w) / len(w)
                out.append(f'| {n} | {len(v)} | {av("w"):.2f} | {max(r.get("wmax", 0) for r in w):.2f} | {av("cpu"):.2f} | {av("ge"):.2f} | {av("kt"):.1f} | {av("draws"):.0f} | {max(r.get("late", 0) for r in w):.0f} |')
        if a.ab:
            bp = Path(a.ab); bp = bp / 'acct.txt' if bp.is_dir() else bp
            if bp.exists():
                B = ab.parse(str(bp)); pairs = ab.noise_pairs(A, [x for x in a.same.split(',') if x]); nz = ab.noise(A, pairs)
                sig = []
                for sc in A:
                    if sc not in B: continue
                    for acc, ks in ab.ACC.items():
                        for k in ks:
                            x, y = ab.mean(A[sc], k), ab.mean(B[sc], k)
                            if x is None or y is None: continue
                            lim = max(2.0 * nz.get(k, 0), ab.FLOOR.get(k, 0))
                            if abs(y - x) > lim: sig.append(f'{sc}/{acc}/{k}: A {x:.2f} → B {y:.2f} (шум {nz.get(k, 0):.2f})')
                out += ['', f'Проход A против B по счетам (шум по {", ".join(f"{p[0]}~{p[1] or chr(0x432)+"тор. половина"}" for p in pairs) or "нет пар"}): значимых различий {len(sig)}' + (':' if sig else '.')] + [f'- {x}' for x in sig]
            else: out += ['', f'--ab: нет {bp}']
    txt = '\n'.join(out) + '\n'
    (Path(a.out) if a.out else d / 'ВЕРДИКТ.md').write_text(txt)
    print(txt if len(txt) < 12000 else '\n'.join(out[:3] + [x for x in out if 'КРАСНЫЙ' in x] + ['', summary]))
    return 1 if red or (a.strict and (counts['ЖЁЛТЫЙ'] or nd)) else 0


if __name__ == '__main__':
    sys.exit(main())
