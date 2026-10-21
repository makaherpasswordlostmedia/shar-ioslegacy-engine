#!/usr/bin/env python3
"""Ночь ботов одной кнопкой (пункт Б5, docs/БОТЫ-ИГРОКИ_2026-09-28.md §4–§6). Только процессор Мака, без AI и сети.
  python3 tools/bots/night.py [--procs 8] [--until 07:00]     ночь: каскадёр 3 · догонялки 2 · миссионер/навигатор 3 процесса (nice)
  python3 tools/bots/night.py --day                           днём: 2 процесса фоном (догонялки 1 · миссионер/навигатор 1) до 23:00
  python3 tools/bots/night.py --morning DIR                   пересобрать утреннюю страницу по готовой ночи
  python3 tools/bots/night.py --gate                          гейт Б5 (красный контроль, потом зелёный)
Дорожки крутят свои прогоны (tools/bots/explorer.py, chase.py, missions.py, nav.py) до срока; после каждого прогона итог
сливается в build/bots/nights/<время>/night.json, на диске остаются только кластеры и лучшие проходы (keep/), сырые папки
прогонов удаляются. Диск: новый прогон не начинается, если свободно < 5 ГБ или ночь > 1 ГБ.
Утренний станок (пункт 10в): за 15 минут до срока дорожки встают, прогоняются обход предметов (tools/cartest/props_sweep.py),
дороги трафика под коллизией (tools/cartest/roadblock.c) и крыши по данным ночи (tools/bots/roofs.py); итоги — в утро.
Утро: build/bots/morning.md (одна страница) — сравнение с прошлой ночью и «вернулось»: исправленные кластеры из
docs/state/fixed-clusters.tsv (столбцы: ключ, вид, повтор, x, y, z, заметка) проигрываются каждую ночь; воспроизвёлся = вернулся.
Неизменяемая ночь (Т1.1): в начале всё, чем она играет, копируется в папку ночи — бинарники (bin/), входы (in/build/: уровень,
комнаты, карточки/осы/гэги, Гомер, дороги, трамплины, крыши, имена объектов, цели, миссии) и управляющие скрипты (scripts/);
MANIFEST.tsv — SHA-256 каждого файла, его отпечаток — в night.json и у каждого кластера. Дневная пересборка build/ ночь не меняет.
Ключ кластера — tools/bots/clusterkey.py (уровень + событие + слой опоры + объект + клетка 8 м).
  python3 tools/bots/night.py --gate-t14      гейт Т1.4: откат каждого исправления из fixed-clusters.tsv -> утро наверху «Вернулось»
  python3 tools/bots/night.py --gate-t13      гейт Т1.3: подложенный новый кластер первым, известное — в свёртке
  python3 tools/bots/night.py --gate-t11      гейт Т1.1: ключ (дорога и крыша), поимка по высоте, заморозка (красный, потом зелёный)"""
import argparse, datetime, hashlib, json, math, os, re, shutil, signal, subprocess, sys, threading, time
from pathlib import Path
from clusterkey import cluster_key, obj_name, parse_key
ROOT = Path(__file__).resolve().parents[2]
BIN = Path(os.environ.get('BOTS_BIN', ROOT / 'build/bots'))   # ночь играет своей копией бинарников (дневная пересборка их не трогает)
NIGHTS = ROOT / 'build/bots/nights'
IN, SCR = ROOT / 'build', ROOT / 'tools/bots'   # входы и скрипты ночи; run_night подменяет на замороженные копии (Т1.1)
def LVL(): return IN / 'level.shr'
def HOM(): return IN / 'homer.shr'
def RDS(): return IN / 'sandbox/roads-l1.bin'
IN_FILES = ('level.shr', 'homer.shr', 'interiors-l1.bin', 'collect-l1.shr', 'traffic.shr', 'sandbox/roads-l1.bin', 'sandbox/roads-l1.meta.tsv', 'sandbox/routes-l1.tsv', 'sandbox/routes-l1.json',
            'sandbox/colnames-l1.json', 'bots/targets-l1.tsv', 'missions/level01.msn')
# 03.10 (разбор ночи 02.10, приёмка L1): мир миссий ночи = мир EBOOT. Без этих спутников миссионер играл другую игру: машины миссий —
# кузова трафика/famil_v (m6: самосвал cBone другой формы, машина Мардж по SetForcedCar не подменялась — таран не ронял игры, m6
# «застрял» 22 прогона из 22), разговоры кончались за 1 с вместо длины реплик (m0: машина вставала у двери Kwik-E-Mart в другое
# время). У music.sap в ночь кладётся только оглавление дорожек (имя и длина, 64 Б на дорожку, ~34 КБ из 108 МБ): звук ботам не
# нужен, длины реплик — да (tools/bots/msn_audio_host.c читает только его). NIGHT_INPUTS_OLD=1 — прежний набор (красный контроль
# tests/bots/night_inputs.sh)
IN_GAME_FILES = ('msncars-l1.shr', 'audio/sfx.sab', 'audio/music.sap')
if not os.environ.get('NIGHT_INPUTS_OLD'): IN_FILES = IN_FILES + IN_GAME_FILES
TABLE_ONLY = {'audio/music.sap'}
# 03.10: миссия на прогон — до 1500 с игры (как tools/bots/campaign.sh). Прогон детерминирован (один и тот же итог 22 раза за ночь
# 02.10), а 300 с не хватало честным проходам мира EBOOT: m2 297 с, m5 312 с, sr1 370 с, m3 640 с (три захода стадии с таймером).
# NIGHT_MSN_SECS_OLD=1 — прежний потолок 300 с
MSN_SECS_CAP = 300 if os.environ.get('NIGHT_MSN_SECS_OLD') else 1500


def copy_in(s, d, f):
    """вход ночи: копия файла; у music.sap — заголовок и таблица дорожек (SAP1: число дорожек @8, смещение таблицы @12, по 64 Б)"""
    d.parent.mkdir(parents=True, exist_ok=True)
    if f not in TABLE_ONLY: shutil.copy2(s, d); return
    import struct
    with open(s, 'rb') as fh: h = fh.read(64); nt, to = struct.unpack_from('<II', h, 8); fh.seek(0); b = fh.read(to + nt * 64)
    if h[:4] != b'SAP1' or len(b) != to + nt * 64: raise SystemExit(f'night: {s} — не SAP1 или оборван')
    d.write_bytes(b)
BINS = ('explorer', 'chase', 'missioner', 'nav', 'game_headless', 'probe')
SCRIPTS = ('explorer.py', 'chase.py', 'missions.py', 'nav.py', 'roofs.py', 'clusterkey.py')
FIXED = ROOT / 'docs/state/fixed-clusters.tsv'
KNOWN = ROOT / 'docs/state/known.tsv'   # известное с причиной и владельцем (Т1.3): утро сворачивает
MIN_FREE, MAX_NIGHT = 5 << 30, 1 << 30


def rel(p): return str(Path(p).resolve().relative_to(ROOT))


def dirsize(p): return sum(f.stat().st_size for f in Path(p).rglob('*') if f.is_file())


def deadline(hhmm):
    h, m = map(int, hhmm.split(':')); now = datetime.datetime.now(); t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    return (t if t > now else t + datetime.timedelta(days=1)).timestamp()


# ------------------------------------------------------------------ состояние ночи и слияние
class Night:
    def __init__(self, d, procs, until):
        self.d, self.lock = d, threading.Lock()
        (d / 'keep').mkdir(parents=True, exist_ok=True); (d / 'raw').mkdir(exist_ok=True)
        self.s = dict(stamp=d.name, started=time.strftime('%Y-%m-%d %H:%M'), procs=procs, until=time.strftime('%Y-%m-%d %H:%M', time.localtime(until)),
                      finished=None, stopped=None, gameMinutes=dict(explore=0, chase=0, missions=0, nav=0), runs=dict(explore=0, chase=0, missions=0, nav=0),
                      explore=dict(reach={}, reached={}, clusters={}, plantedRoof=False, replayBad=0, approach={}),
                      chase=dict(first=None, last=None, corners={}, stuck={}, weak=0, confirm=2),   # confirm 2: угол подтверждён и по следу беглеца
                      missions={}, nav=dict(routes=0, reached=0, replayOk=0), regress=[], manifest=None, runlog=[])

    def save(self):
        (self.d / 'night.json').write_text(json.dumps(self.s, ensure_ascii=False, indent=1))

    def keep(self, src, sub, name=None):
        dst = self.d / 'keep' / sub; dst.mkdir(parents=True, exist_ok=True); dst = dst / (name or Path(src).name)
        shutil.copy(src, dst); return rel(dst)

    def merge_explore(self, r):
        E = self.s['explore']; self.s['gameMinutes']['explore'] += r['gameMinutes']; self.s['runs']['explore'] += 1
        for k, (a, b) in r['reach'].items(): E['reach'][k] = b
        E['plantedRoof'] |= r['plantedRoof']; E['replayBad'] += r['reached'] - r['replayOk'] - (1 if r['plantedRoof'] else 0)
        E['capReached'] = E.get('capReached', False) or bool(r.get('capReached'))
        for row in r['rows']:
            if not row['replay']: continue
            old = E['reached'].get(row['name'])
            if not old or row['t'] < old['t']: E['reached'][row['name']] = dict(kind=row['kind'], t=row['t'], foot=row['foot'], repro=self.keep(ROOT / row['repro'], 'explore'))
        A = E.setdefault('approach', {})
        for n, a in r.get('approach', {}).items():   # недостигнутые: лучший подход за ночь (плоскость + 2 × нехватка высоты)
            if n not in A or a['d'] + 2 * a['h'] < A[n]['d'] + 2 * A[n]['h']: A[n] = a
        for e in r['events']:
            if not e['replay']: continue
            key = cluster_key(e['kind'], e['x'], e['z'], e.get('layer', 0), e.get('obj', '-'))
            old = E['clusters'].get(key)
            if not old: E['clusters'][key] = dict(kind=e['kind'], x=e['x'], y=e['y'], z=e['z'], layer=e.get('layer', 0), obj=e.get('obj', '-'), n=e['n'], t=e['t'],
                                                  repro=self.keep(ROOT / e['repro'], 'explore'), manifest=self.s['manifest'])
            else:
                old['n'] += e['n']
                if e['t'] < old['t']: old.update(x=e['x'], y=e['y'], z=e['z'], t=e['t'], repro=self.keep(ROOT / e['repro'], 'explore'), manifest=self.s['manifest'])   # кратчайший повтор

    def log(self, lane, i, seed, r, what):
        """журнал прогонов (Т1.1): отпечаток итога без времени и путей + чем играл (уровень) — гейт заморозки сравнивает ночи по нему"""
        dig = hashlib.sha256(json.dumps(what, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        self.s['runlog'].append(dict(lane=lane, i=i, seed=seed, levelSha=r.get('levelSha'), digest=dig))

    def merge_chase(self, r):
        C = self.s['chase']; self.s['gameMinutes']['chase'] += r['gameMinutes']; self.s['runs']['chase'] += 1
        g = r['generations']
        if g:
            if C['first'] is None: C['first'] = g[0]
            C['last'] = g[-1]
        C['weak'] += r['weakCorners']
        for c in r['clusters']:
            if not c['replay']: continue
            box = C['corners'] if c['kind'] == 'eternal_corner' else C['stuck']
            key = cluster_key(c['kind'], c['x'], c['z'], c.get('layer', 0), c.get('obj', '-'))
            if key in box: box[key]['n'] += c['n']
            else: box[key] = dict(kind=c['kind'], x=c['x'], y=c['y'], z=c['z'], layer=c.get('layer', 0), obj=c.get('obj', '-'), n=c['n'],
                                  repro=self.keep(ROOT / c['file'], 'chase', key.replace(':', '_') + '.round'), manifest=self.s['manifest'])

    def merge_missions(self, rows, out):
        order = {'пройдена': 0, 'провал': 2}
        for r in rows:
            self.s['gameMinutes']['missions'] += r.get('frames', 0) / 3600
            old = self.s['missions'].get(r['id']); rank = order.get(r['result'], 1)
            better = not old or rank < old['rank'] or (rank == old['rank'] == 0 and r['time'] < old['time'])
            if better:
                rp = out / f"m{r['index']}.in"
                self.s['missions'][r['id']] = dict(index=r['index'], title=r['title'], result=r['result'], why=r['why'], time=r['time'], rank=rank, cls=r.get('cls', ''),
                                                   place=r['place'], object=r.get('object', ''), repro=self.keep(rp, 'missions') if rp.exists() else None)
        self.s['runs']['missions'] += 1

    def merge_nav(self, r):
        N = self.s['nav']; self.s['gameMinutes']['nav'] += r.get('gameMinutes', 0); self.s['runs']['nav'] += 1
        N['routes'] += r['routes']; N['reached'] += r['reached']; N['replayOk'] += r['replayOk']


def regions(clusters, min_n=1):
    """Кластеры ботов (клетки 8 м) -> связные места по виду и слою опоры (соседство по 8 направлениям): одно место = одна
    поломка; дорога и крыша над ней — разные места (Т1.1). -> список {kind, layer, objs, n, cells, x, y, z, repro, keys}
    (представитель — кратчайший повтор)."""
    by = {}
    for k, v in clusters.items():
        if v['n'] >= min_n:
            c = by.setdefault((v['kind'], v.get('layer', 0)), {}).setdefault((int(v['x'] // 8), int(v['z'] // 8)), [])
            c.append((k, v))
    out = []
    for (kind, layer), cells in by.items():
        seen = set()
        for c in cells:
            if c in seen: continue
            st, comp = [c], []; seen.add(c)
            while st:
                x, z = st.pop(); comp += cells[(x, z)]
                for dx in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        nb = (x + dx, z + dz)
                        if nb in cells and nb not in seen: seen.add(nb); st.append(nb)
            rep = min(comp, key=lambda kv: kv[1].get('t', 0))[1]
            objs = sorted({v.get('obj', '-') for _, v in comp} - {'-'})
            out.append(dict(kind=kind, layer=layer, objs=objs, n=sum(v['n'] for _, v in comp), cells=len({(int(v['x'] // 8), int(v['z'] // 8)) for _, v in comp}),
                            x=rep['x'], y=rep['y'], z=rep['z'], repro=rep['repro'], keys=[k for k, _ in comp]))
    return sorted(out, key=lambda r: -r['n'])


# ------------------------------------------------------------------ дорожки
def py(script, args, out, until=None):
    """прогон дорожки; until — жёсткий срок (Т1.6): не успел — вся группа процессов (скрипт и его бинарники) снимается,
    итога прогона нет. Без срока навигатор, начатый за 4 минуты до 07:00, доигрывал бы до конца (замечено 28.09)"""
    env = dict(os.environ, BOTS_NO_BUILD='1', BOTS_IN=str(IN), BOTS_ROOT=str(ROOT), BOTS_BIN=str(BIN))
    pr = subprocess.Popen([sys.executable, str(SCR / script), *map(str, args), '--out', str(out)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, env=env, start_new_session=True)
    try: so, se = pr.communicate(timeout=None if until is None else max(1.0, until - time.time()))
    except subprocess.TimeoutExpired:
        os.killpg(pr.pid, signal.SIGTERM); so, se = pr.communicate(); so += '\nсрок ночи: прогон снят'
    (out.parent / (out.name + '.log')).write_text(so[-4000:] + se[-4000:])
    return pr.returncode


def disk_ok(N):
    free = shutil.disk_usage(ROOT).free; size = dirsize(N.d)
    if free < MIN_FREE or size > MAX_NIGHT:
        with N.lock: N.s['stopped'] = f"диск: свободно {free >> 30} ГБ, ночь {size >> 20} МБ — новые прогоны не начинаются"; N.save()
        return False
    return True


def lane_explore(N, k, until, seed0, stop):
    i = 0
    while not stop.is_set() and until - time.time() > 120 and disk_ok(N):
        secs = int(min(300, until - time.time() - 90)); out = N.d / 'raw' / f'explore-{i}'
        py('explorer.py', ['--procs', k, '--secs', secs, '--seed', seed0 + 100 * i], out, until)
        if (out / 'explore.json').exists():
            with N.lock: N.merge_explore(json.loads((out / 'explore.json').read_text())); N.save(); morning(N.d)
        shutil.rmtree(out, ignore_errors=True); i += 1


def lane_chase(N, k, until, seed0, stop):
    i = 0
    while not stop.is_set() and until - time.time() > 120 and disk_ok(N):
        out = N.d / 'raw' / f'chase-{i}'; g, p, r = os.environ.get('NIGHT_CHASE', '40 24 4').split()   # гейт Т1.1 мельчит раунды
        py('chase.py', ['--procs', k, '--gens', g, '--pop', p, '--rounds', r, '--seed', seed0 + 100 * i], out, until)
        if (out / 'chase.json').exists():
            R = json.loads((out / 'chase.json').read_text())
            what = dict(g=R['generations'], rounds=R['roundsPlayed'], weak=R['weakCorners'],
                        clu=sorted((c['kind'], c['x'], c['y'], c['z'], c.get('layer'), c.get('obj'), c['n'], c['replay']) for c in R['clusters']))
            with N.lock: N.log('chase', i, seed0 + 100 * i, R, what); N.merge_chase(R); N.save(); morning(N.d)
        else:
            with N.lock: N.log('chase', i, seed0 + 100 * i, {}, 'нет итога'); N.save()
        shutil.rmtree(out, ignore_errors=True); i += 1


def lane_play(N, k, until, seed0, stop):
    i = 0
    while not stop.is_set() and until - time.time() > 180 and disk_ok(N):
        out = N.d / 'raw' / f'play-{i}'
        if i % 2 == 0:   # миссионер: 13 миссий на k процессах, время на миссию — сколько влезает
            secs = int(max(60, min(MSN_SECS_CAP, (until - time.time() - 120) * k / 13)))
            py('missions.py', ['--procs', k, '--secs', secs], out, until)
            if (out / 'missions.json').exists():
                with N.lock: N.merge_missions(json.loads((out / 'missions.json').read_text()), out); N.save(); morning(N.d)
        else:
            py('nav.py', ['--procs', k, '--routes', 24, '--gens', 40, '--seed', seed0 + i], out, until)
            if (out / 'nav.json').exists():
                with N.lock: N.merge_nav(json.loads((out / 'nav.json').read_text())); N.save(); morning(N.d)
        shutil.rmtree(out, ignore_errors=True); i += 1


# ------------------------------------------------------------------ вечный гейт: исправленные кластеры
def fixed_rows(path):
    rows = []
    if path.exists():
        for l in path.read_text().splitlines():
            if not l.strip() or l.startswith('#'): continue
            f = l.split('\t')
            if len(f) >= 6 and f[0].startswith('bots:'): rows.append(dict(key=f[0], kind=f[1], repro=f[2], x=float(f[3]), y=float(f[4]), z=float(f[5]), note=f[6] if len(f) > 6 else ''))
    return rows


def headless_end(p):
    s = re.search(r'--start ([-0-9.e ]+) --input', Path(p).read_text().split('\n', 1)[0]).group(1).split()
    o = subprocess.run([str(BIN / 'game_headless'), str(LVL()), str(HOM()), '--input', str(p), '--start', *s], capture_output=True, text=True).stdout
    m = re.search(r'игрок ([-0-9.]+) ([-0-9.]+) ([-0-9.]+)', o)
    return tuple(map(float, m.groups()))


def regress(path):
    """Проиграть каждый исправленный кластер ботов: воспроизвёлся = вернулся (гейт навсегда)."""
    if os.environ.get('NIGHT_BREAK_REGRESS'): return []   # отрицательный контроль гейта Б5: проверка «вернулось» выключена
    res = []
    for r in fixed_rows(path):
        p = ROOT / r['repro']
        if not p.exists(): res.append(dict(r, back=None, why='нет файла повтора')); continue
        if r['kind'] in ('eternal_corner', 'pursuer_stuck'):
            back = subprocess.run([str(BIN / 'chase'), str(LVL()), str(HOM()), str(RDS()), '--replay', str(p)], capture_output=True).returncode == 0
        else:
            x, y, z = headless_end(p)
            back = (y < r['y'] + 3) if r['kind'] == 'fall' else math.hypot(x - r['x'], z - r['z']) < 1.0
        res.append(dict(r, back=back))
    return res


# ------------------------------------------------------------------ известное (Т1.3)
def known_rows(path=None):
    """docs/state/known.tsv -> [{kind, cells {(x, z)}, cause, owner, note}]; NIGHT_NO_KNOWN=1 — отрицательный контроль: без свёртки"""
    path = Path(path or os.environ.get('NIGHT_KNOWN') or KNOWN)
    if os.environ.get('NIGHT_NO_KNOWN') or not path.exists(): return []
    out = []
    for l in path.read_text().splitlines():
        if not l.strip() or l.startswith('#'): continue
        f = l.split('\t')
        if len(f) < 4: continue
        cells = {tuple(int(v) for v in c.split(':')) for c in f[1].split(',') if ':' in c}
        out.append(dict(kind=f[0], cells=cells, cause=f[2], owner=f[3], note=f[4] if len(f) > 4 else ''))
    return out


def split_known(regs, known):
    """места -> (новые, {(причина, владелец): [места]}): место известно, если вид тот же и хоть одна его клетка 8 м в строке known"""
    new, fold = [], {}
    for r in regs:
        cells = {(parse_key(k)['cx'], parse_key(k)['cz']) for k in r['keys']}
        k = next((k for k in known if k['kind'] == r['kind'] and cells & k['cells']), None)
        if k: fold.setdefault((k['cause'], k['owner']), []).append(r)
        else: new.append(r)
    return new, fold


# ------------------------------------------------------------------ утренняя страница
def finished_nights(before=None):
    """настоящие ночи: завершённые (finished), не гейтовые и не дневные (-gate, -day), по имени (= времени начала)"""
    out = []
    for p in sorted(NIGHTS.glob('*/night.json')):
        n = p.parent.name
        if not re.fullmatch(r'\d{8}-\d{4}', n) or (before and n >= before): continue   # только настоящие: без -day, -gate, -test (NIGHT_SUFFIX)
        try: S = json.loads(p.read_text())
        except Exception: continue
        if S.get('finished'): out.append((p, S))
    return out


def prev_night(d):
    c = finished_nights(before=d.name)
    return c[-1][1] if c else None


def morning(d, write_root=True):
    d = Path(d); S = json.loads((d / 'night.json').read_text()); P = prev_night(d)
    gm = S['gameMinutes']; total = sum(gm.values())
    E, C = S['explore'], S['chase']
    got = {}
    for n, r in E['reached'].items(): got[r['kind']] = got.get(r['kind'], 0) + 1
    L = [f"# Утро · ночь {S['started']} → {S['finished'] or 'идёт'} · {S['procs']} процессов", '',
         f"Игры за ночь: **{total / 60:.1f} ч** (каскадёр {gm['explore'] / 60:.1f}, догонялки {gm['chase'] / 60:.1f}, миссии {gm['missions'] / 60:.1f}, навигатор {gm['nav'] / 60:.1f}); "
         f"прогонов {sum(S['runs'].values())}" + (f"; остановлено: {S['stopped']}" if S['stopped'] else ''),
         (f"Входы ночи заморожены: манифест `{S['manifest']}` ({rel(d / 'MANIFEST.tsv')})" + ('' if S.get('intact') is not False else ' — **ИЗМЕНИЛИСЬ за ночь**'))
         if S.get('manifest') else 'Входы ночи **не заморожены** (ночь до Т1.1 или контроль): пересборка build/ могла менять мир посреди ночи', '']
    back = [r for r in S['regress'] if r.get('back')]
    L += ['## Вернулось (исправленные кластеры снова воспроизводятся)', ''] + (
        [f"- **{r['key']}** ({r['note'] or r['kind']}) — повтор `{r['repro']}`" for r in back] if back else ['- нет' + (f" (проверено {len(S['regress'])})" if S['regress'] else ' (исправленных кластеров ботов пока нет)')]) + ['']
    L += ['## Миссии уровня 1 (класс: игра — два независимых водителя не доехали; водитель; нет данных; намеренно — правило миссии)', '']
    pk = S.get('packs')
    if pk: L += [f"Мир миссий: кузовов машин миссий {pk['carGeo']}, реплики и музыка {'да' if pk['audio'] else 'нет'}, комнат {pk['rooms']}, трафик {'да' if pk['traffic'] else 'нет'}"
                 + ('' if pk['carGeo'] and pk['audio'] else ' — **не как у EBOOT: итог миссий не мерит игру**'), '']
    L += ['| миссия | итог | класс | время, с | изменение |', '|---|---|---|---|---|']
    for mid, m in sorted(S['missions'].items(), key=lambda kv: kv[1]['index']):
        pm = P and P['missions'].get(mid); ch = ''
        if pm and pm['result'] != m['result']: ch = f"было «{pm['result']}»"
        elif pm and m['result'] == 'пройдена': ch = f"{m['time'] - pm['time']:+.1f} с"
        L.append(f"| {mid} {m['title'][:28]} | {m['result']}{(' — ' + m['why'][:40]) if m['result'] != 'пройдена' else ''} | {m.get('cls', '') or '—'} | {m['time']:.0f} | {ch} |")
    L += ['', '## Достижимость с дороги (каскадёр и пешеход)', '']
    kinds = sorted(E['reach'])
    L.append(' · '.join(f"{k} {got.get(k, 0)} из {E['reach'][k]}" + (f" (было {sum(1 for r in P['explore']['reached'].values() if r['kind'] == k)})" if P else '') for k in kinds))
    if P:
        lost = sorted(set(P['explore']['reached']) - set(E['reached']))
        if lost: L.append(f"Новые недостигнутые ({len(lost)}): " + ', '.join(lost[:20]))
    if E['plantedRoof']: L.append('**Подложенная крыша достигнута — проверка крыш сломана**')
    if E.get('capReached'): L.append('Архив ячеек каскадёра заполнялся: «не достигнуто» отчасти потолок архива, а не уровень')
    if E['replayBad']: L.append(f"**Повторов целей разошлось: {E['replayBad']}**")
    L += ['', '## Догонялки', '']
    if C['last']:
        L.append(f"Время беглеца до поимки (последнее поколение) {C['last']['meanCatch']} с, доля поимок {C['last']['catchRate']}" +
                 (f" (прошлая ночь {P['chase']['last']['meanCatch']} с, {P['chase']['last']['catchRate']})" if P and P['chase']['last'] else '') +
                 f"; опровергнуто углов {C['weak']}")
        newc = [k for k in C['corners'] if not P or k not in P['chase']['corners']]
        L += [f"- вечный угол {C['corners'][k]['x']:.0f} {C['corners'][k]['z']:.0f} ×{C['corners'][k]['n']} — `{C['corners'][k]['repro']}`" + (' **новый**' if k in newc else '')
              for k in sorted(C['corners'], key=lambda k: -C['corners'][k]['n'])[:5]]
    N = S['nav']
    if N['routes']: L += ['', f"Навигатор: маршрутов {N['routes']}, доехал {N['reached']}, повтор {N['replayOk']}"]
    # топ-10 мест поломок: связные клетки 8 м одного вида (события каскадёра, застрявшая погоня, вечные углы), кратчайший повтор
    regs = regions({**E['clusters'], **C['stuck'], **C['corners']}, 3)
    old = set(P['explore']['clusters']) | set(P['chase']['stuck']) | set(P['chase']['corners']) if P else set()
    nm = next((json.loads(q.read_text()) for q in (d / 'in/build/sandbox/colnames-l1.json', ROOT / 'build/sandbox/colnames-l1.json') if q.exists()), None)
    def floor(l): return 'земля' if l == 0 else 'под опорами' if l < 0 else f'верх {l}'
    newr, fold = split_known(regs, known_rows())   # Т1.3: известное (docs/state/known.tsv) — одной строкой на причину, новое наверху
    L += ['', f"## Топ-10 новых мест поломок (всего мест {len(regs)}, из них известных {len(regs) - len(newr)}; место — связные клетки 8 м одного вида и этажа, повтор кратчайший)", '',
          '| вид | место | этаж | объект | клеток | раз | повтор |', '|---|---|---|---|---|---|---|'] + [
        f"| {r['kind']} | {r['x']:.0f} {r['y']:.1f} {r['z']:.0f} | {floor(r['layer'])} | {', '.join(obj_name(o, nm) for o in r['objs'][:2]) or '—'} | {r['cells']} | {r['n']} | `{r['repro']}` |"
        + (' новое' if P and not set(r['keys']) & old else '') for r in newr[:10]]
    L += ['', '## Известное, ждёт владельца (docs/state/known.tsv)', ''] + (
        [f"- {c} — **{o}**: мест {len(rs)}, раз {sum(r['n'] for r in rs)}" for (c, o), rs in sorted(fold.items(), key=lambda kv: -sum(r['n'] for r in kv[1]))] or ['- нет'])
    ST = S.get('station')
    if ST:
        pr = ST.get('props', {}); rb = ST.get('roadblock', {}); rf = ST.get('roofs')
        L += ['', '## Утренний станок', '',
              f"Предметы (обход): {', '.join(f'{k} {v}' for k, v in pr.get('verdicts', {}).items()) or ST.get('propsError', '—')}; аномалий удара {pr.get('energy', '—')}, падений в дыры {pr.get('holes', '—')}",
              f"Дороги трафика под коллизией: мест {rb.get('places', ST.get('roadblockError', '—'))} (проб в коллизии {rb.get('bad', '—')} из {rb.get('probes', '—')})" + (f"; на срезках ИИ без трафика в коллизии {rb['shortcutBad']} проб (справочно)" if rb.get('shortcutBad') is not None else '') + (f"; крыши достижимы {rf[0]} из {rf[1]}" if rf else '')]
    worse = []
    if P:
        for k in kinds:
            a, b = got.get(k, 0), sum(1 for r in P['explore']['reached'].values() if r['kind'] == k)
            if a < b: worse.append(f"{k}: достигнуто {a}, было {b}")
        for mid, m in S['missions'].items():
            pm = P['missions'].get(mid)
            if pm and (m['rank'] > pm['rank'] or (m['rank'] == pm['rank'] == 0 and m['time'] > pm['time'] + 5)): worse.append(f"{mid}: {pm['result']} {pm['time']:.0f} с → {m['result']} {m['time']:.0f} с")
    worse += [f"вернулся {r['key']}" for r in back]
    L += ['', '## Что стало хуже', ''] + ([f'- {w}' for w in worse] if worse else ['- ничего' if P else '- не с чем сравнить: первая ночь'])
    txt = '\n'.join(L) + '\n'
    (d / 'morning.md').write_text(txt)
    if write_root and d.parent.resolve() == NIGHTS.resolve() and re.fullmatch(r'\d{8}-\d{4}', d.name): (ROOT / 'build/bots/morning.md').write_text(txt)   # гейтовые, дневные, пробные не трогают утро
    return txt


# ------------------------------------------------------------------ ночь целиком
def station(N):
    """утренний станок: предметы, дороги трафика, крыши — числа в night.json['station']"""
    st = {}
    try:
        out = N.d / 'keep' / 'props-sweep.json'
        subprocess.run([sys.executable, str(ROOT / 'tools/cartest/props_sweep.py'), '--out', str(out), '--level', str(LVL()), '--bin', str(BIN / 'props_sweep')],
                       capture_output=True, timeout=900)
        if out.exists():
            r = json.loads(out.read_text()); c = {}
            for part in ('prp1', 'spr1'):
                for v in r[part].values(): c[v['verdict']] = c.get(v['verdict'], 0) + 1
            st['props'] = dict(verdicts=c, energy=sum(v.get('flew', 0) for v in r['prp1'].values()), holes=sum(v.get('fellIntoHole', 0) for v in r['prp1'].values()))
    except Exception as e: st['propsError'] = str(e)[:200]
    try:
        binp = BIN / 'roadblock'   # собран в начале ночи (freeze); читает build/level.shr от cwd — замороженная папка in/
        r = subprocess.run([str(binp)], capture_output=True, text=True, timeout=300, cwd=IN.parent)
        if r.returncode: raise RuntimeError(f'roadblock: код {r.returncode} ' + r.stderr[-200:])
        pts = [l.split('\t') for l in r.stdout.splitlines() if l.startswith('R\t')]
        tot = next((int(l.split('\t')[1]) for l in r.stdout.splitlines() if l.startswith('S\t')), 0)
        sc = next((l.split('\t') for l in r.stdout.splitlines() if l.startswith('Q\t')), None)   # срезки ИИ (shortcut, без трафика) — справочно, не в счёт
        st['roadblock'] = dict(probes=tot, bad=len(pts), places=len({(int(float(x[2]) // 16), int(float(x[4]) // 16)) for x in pts}),
                               shortcutBad=int(sc[2]) if sc else None)
    except Exception as e: st['roadblockError'] = str(e)[:200]
    try:
        r = subprocess.run([sys.executable, str(SCR / 'roofs.py'), str(N.d)], capture_output=True, text=True, timeout=300, env=dict(os.environ, BOTS_IN=str(IN), BOTS_ROOT=str(ROOT)))
        m = re.search(r'Достижимы (\d+) из (\d+)', r.stdout)
        if m: st['roofs'] = [int(m.group(1)), int(m.group(2))]
    except Exception as e: st['roofsError'] = str(e)[:200]
    return st


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def freeze(d):
    """Неизменяемый комплект ночи (Т1.1): бинарники -> bin/, входы из NIGHT_SRC (по умолчанию build/) -> in/build/, скрипты -> scripts/;
    станок утра (предметы, дороги трафика) собирается сейчас же — тем же кодом, что вся ночь. MANIFEST.tsv: sha256 и путь.
    NIGHT_NO_FREEZE=1 — отрицательный контроль гейта: входы и скрипты читаются общие, как до Т1.1 (бинарники копируются, как было).
    -> (папка входов, папка скриптов, отпечаток манифеста)"""
    src = Path(os.environ.get('NIGHT_SRC') or ROOT / 'build')
    b = d / 'bin'; b.mkdir(parents=True, exist_ok=True)
    for n in BINS: shutil.copy2(ROOT / 'build/bots' / n, b / n)
    V = ROOT / 'viewer'
    subprocess.run(['bash', '-c', 'V=viewer; . tools/bots/lib.sh; cc -std=c11 -O1 -DSKIN_HOST -I viewer -I tools/bots tools/cartest/roadblock.c '
                    '$BOTS_LIB -lm -o "$0"', str(b / 'roadblock')], cwd=ROOT, check=True, capture_output=True, timeout=300)   # общий список (tools/bots/lib.sh)
    subprocess.run([sys.executable, str(ROOT / 'tools/cartest/props_sweep.py'), '--bin', str(b / 'props_sweep'), '--build-only'], check=True, capture_output=True, timeout=300)
    if os.environ.get('NIGHT_NO_FREEZE'): return src, ROOT / 'tools/bots', None
    inp, scr = d / 'in' / 'build', d / 'scripts'
    for f in IN_FILES:
        if (src / f).exists(): copy_in(src / f, inp / f, f)
    scr.mkdir(exist_ok=True)
    for f in SCRIPTS: shutil.copy2(ROOT / 'tools/bots' / f, scr / f)
    rows = [f"{sha_file(p)}\t{p.relative_to(d)}" for p in sorted(list(b.iterdir()) + list(inp.rglob('*')) + list(scr.iterdir())) if p.is_file() and p.suffix != '.pyc']
    rows.append(f"# git {subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()}")
    (d / 'MANIFEST.tsv').write_text('\n'.join(rows) + '\n')
    return inp, scr, sha_file(d / 'MANIFEST.tsv')[:16]


def msn_packs(inp):
    """что из спутников игры видит мир миссий на этих входах (missioner --packs): кузовов машин миссий, звук, комнат, трафик"""
    try:
        r = subprocess.run([str(BIN / 'missioner'), *(str(Path(inp) / f) for f in ('level.shr', 'homer.shr', 'sandbox/roads-l1.bin', 'missions/level01.msn')), '--packs'],
                           capture_output=True, text=True, timeout=120)
        f = next(l for l in r.stdout.splitlines() if l.startswith('P\t')).split('\t')
        return dict(carGeo=int(f[1]), audio=int(f[2]), rooms=int(f[3]), traffic=int(f[4]))
    except Exception: return None


def manifest_intact(d):
    """все файлы манифеста на месте и не изменились (конец ночи, гейт Т1.1)"""
    m = d / 'MANIFEST.tsv'
    if not m.exists(): return None
    for l in m.read_text().splitlines():
        if l.startswith('#'): continue
        h, p = l.split('\t')
        if not (d / p).exists() or sha_file(d / p) != h: return False
    return True


def run_night(d, procs, until, fixed, lanes=None, station_on=True):
    global BIN, IN, SCR
    d.mkdir(parents=True, exist_ok=True)
    IN, SCR, man = freeze(d); BIN = d / 'bin'; os.environ['BOTS_BIN'] = str(BIN)
    N = Night(d, procs, until); N.s['manifest'] = man; N.s['frozen'] = man is not None; N.s['packs'] = msn_packs(IN)
    N.s['regress'] = regress(fixed); N.save(); morning(d)
    if lanes is None:
        if procs <= 2: lanes = dict(explore=0, chase=1, play=max(1, procs - 1))
        else: e = max(1, round(procs * 3 / 8)); c = max(1, round(procs * 2 / 8)); lanes = dict(explore=e, chase=c, play=max(1, procs - e - c))
    stop = threading.Event(); seed0 = int(os.environ.get('NIGHT_SEED') or int(time.time()) % 100000)
    lane_until = until - 15 * 60 if station_on and until - time.time() > 40 * 60 else until   # 15 минут на утренний станок
    th = [threading.Thread(target=f, args=(N, lanes[n], lane_until, seed0 + j, stop)) for j, (n, f) in enumerate((('explore', lane_explore), ('chase', lane_chase), ('play', lane_play))) if lanes[n] > 0]
    for t in th: t.start()
    try:
        for t in th: t.join()
    except KeyboardInterrupt:
        stop.set(); N.s['stopped'] = 'остановлено вручную'
    if station_on and lane_until < until:
        with N.lock: N.save()
        N.s['station'] = station(N)
    N.s['regress'] = regress(fixed)   # утром ещё раз: вернулось ли после ночных правок
    N.s['intact'] = manifest_intact(d)   # входы ночи не менялись до конца
    N.s['finished'] = time.strftime('%Y-%m-%d %H:%M'); N.save()
    shutil.rmtree(d / 'raw', ignore_errors=True)
    return morning(d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--procs', type=int, default=8); ap.add_argument('--until', default='07:00'); ap.add_argument('--day', action='store_true')
    ap.add_argument('--fixed', type=Path, default=FIXED); ap.add_argument('--morning', type=Path); ap.add_argument('--gate', action='store_true')
    ap.add_argument('--gate-t11', action='store_true'); ap.add_argument('--gate-t13', action='store_true'); ap.add_argument('--gate-t14', action='store_true')
    a = ap.parse_args()
    try: os.nice(5)
    except OSError: pass
    if a.morning: print(morning(a.morning)); return 0
    subprocess.run([str(ROOT / 'tools/bots/build.sh')], check=True, capture_output=True)   # один раз на ночь
    if a.gate: return gate()
    if a.gate_t11: return gate_t11()
    if a.gate_t13: return gate_t13()
    if a.gate_t14: return gate_t14()
    if a.day: a.procs, a.until = 2, '23:00'
    # день — своя папка «-day» и без станка: в нём нет каскадёра, и он не должен становиться «прошлой ночью» или затирать крыши
    d = NIGHTS / (time.strftime('%Y%m%d-%H%M') + ('-day' if a.day else '') + os.environ.get('NIGHT_SUFFIX', ''))   # пробная ночь: NIGHT_SUFFIX=-test
    txt = run_night(d, a.procs, deadline(a.until), a.fixed, station_on=not a.day)
    print(txt.split('\n## ')[0]); print('->', ROOT / 'build/bots/morning.md'); return 0


def gate():
    """Гейт Б5: исправленный кластер снова подложен -> утро показывает его в «Вернулось». Подкладываем настоящий открытый
    кластер (провал Гомера за край земли из гейта Б3) как «исправленный»: он воспроизводится, значит обязан вернуться."""
    src = sorted(ROOT.glob('build/bots/runs/explore/*-gate/good/repro/ev_fall_*.in'))
    if not src: print('гейт Б5: нет повтора провала из гейта Б3 (python3 tools/bots/explorer.py --gate)'); return 1
    stamp = time.strftime('%Y%m%d-%H%M%S'); base = NIGHTS / (stamp + '-gate'); base.mkdir(parents=True, exist_ok=True)
    p = src[0]; x, y, z = headless_end(p); planted = base / 'fixed-planted.tsv'
    rp = base / 'planted.in'; shutil.copy(p, rp)
    planted.write_text(f"# подложено гейтом Б5\nbots:fall:{int(x // 8) * 8}:{int(z // 8) * 8}\tfall\t{rel(rp)}\t{x:.2f}\t{y:.2f}\t{z:.2f}\tподложенный «исправленный» провал\n")
    until = time.time() + 240; lanes = dict(explore=1, chase=1, play=0)
    def shows(txt): return 'подложенный «исправленный» провал' in txt.split('## Вернулось')[1].split('## ')[0]
    os.environ['NIGHT_BREAK_REGRESS'] = '1'
    t_bad = run_night(base / 'broken', 2, until, planted, lanes); del os.environ['NIGHT_BREAK_REGRESS']
    t_ok = run_night(base / 'planted', 2, time.time() + 240, planted, lanes)
    empty = base / 'fixed-empty.tsv'; empty.write_text('# пусто\n')
    t_none = run_night(base / 'none', 2, time.time() + 150, empty, dict(explore=0, chase=1, play=0))
    bad, ok, none = shows(t_bad), shows(t_ok), shows(t_none)
    S = json.loads((base / 'planted' / 'night.json').read_text())
    lines = [f"контроль (проверка «вернулось» выключена): {'зелёный — ГЕЙТ НЕ ЛОВИТ' if bad else 'КРАСНЫЙ — подложенный кластер не показан'}",
             f"рабочая ночь: {'зелёный — утро показывает подложенный кластер в «Вернулось»' if ok else 'КРАСНЫЙ — не показан'}; без подложенного — {'ЛОЖНО показан' if none else 'не показан'}; "
             f"игры за 4 мин: {sum(S['gameMinutes'].values()) / 60:.1f} ч; ночь на диске {dirsize(base / 'planted') >> 10} КБ",
             f"RESULT: {'OK' if (not bad and ok and not none) else 'FAIL'}"]
    (base / 'gate.txt').write_text('\n'.join(lines) + '\n'); print('\n'.join(lines)); print('->', base)
    return 0 if (not bad and ok and not none) else 1


def gate_t11():
    """Гейт Т1.1 (docs/handoff/ДВА_ТЕСТИРОВЩИКА_2026-09-28.md §3): каждая часть сначала красная на заведомо плохом входе.
    (1) ключ: дорога и крыша над ней в одной клетке 8 м (пара с настоящей карты, tools/bots/probe --pairs) — два кластера;
        контроль BOTS_KEY_FLAT=1 (ключ до Т1.1) сливает их в один.
    (2) поимка: беглец на крыше, погоня на дороге под ней (перепад > 2 м) — не поимка; бок о бок на одной дороге — поимка;
        контроль -DCHASE_FLAT_CATCH=1 (поимка по плоскости, как до Т1.1) ловит и на крыше.
    (3) заморозка: три короткие ночи с одним seed (только догонялки, мелкие раунды) на копии входов; посреди ночи копия уровня
        «пересобирается» (вся коллизия выше на 3 м): замороженная ночь даёт те же итоги прогонов, что ночь без пересборки;
        контроль NIGHT_NO_FREEZE=1 (входы общие, как до Т1.1) — итоги меняются."""
    stamp = time.strftime('%Y%m%d-%H%M%S'); base = NIGHTS / (stamp + '-gate-t11'); base.mkdir(parents=True)
    probe = [str(ROOT / 'build/bots/probe'), str(ROOT / 'build/level.shr'), str(ROOT / 'build/homer.shr')]
    pr = subprocess.run(probe + ['--pairs', '1'], capture_output=True, text=True).stdout.split('\n')[0].split('\t')
    if len(pr) < 4: print('гейт Т1.1: на карте нет пары дорога/крыша — проба не нашла'); return 1
    A, B, C = ([float(v) for v in f.split()] for f in pr[1:4])
    lines = [f"пара с карты: дорога {A}, крыша {B}, та же дорога рядом {C}"]
    # (1) ключ
    def where(p): w = subprocess.run(probe + ['--where', *map(str, p)], capture_output=True, text=True).stdout.split('\t'); return int(w[1]), w[3].strip()
    (la, oa), (lb, ob) = where(A), where(B)
    dummy = base / 'dummy.in'; dummy.write_text('# повтор-заглушка гейта\n')
    def merged(flat):
        if flat: os.environ['BOTS_KEY_FLAT'] = '1'
        try:
            n = Night(base / ('key-flat' if flat else 'key'), 1, time.time())
            ev = [dict(kind='foot_trapped', x=p[0], y=p[1], z=p[2], layer=l, obj=o, n=3, t=1.0, replay=True, repro=rel(dummy)) for p, l, o in ((A, la, oa), (B, lb, ob))]
            n.merge_explore(dict(gameMinutes=0, reach={}, plantedRoof=False, reached=0, replayOk=0, rows=[], events=ev))
            return len(n.s['explore']['clusters']), len(regions(n.s['explore']['clusters'], 3))
        finally: os.environ.pop('BOTS_KEY_FLAT', None)
    kf, kg = merged(True), merged(False)
    k_ok = kf == (1, 1) and kg == (2, 2) and la != lb
    lines.append(f"(1) ключ: слой дороги {la}, крыши {lb}; контроль (ключ до Т1.1): кластеров/мест {kf} — {'КРАСНЫЙ, слил' if kf == (1, 1) else 'не слил — КОНТРОЛЬ НЕ ЛОВИТ'}; "
                 f"рабочий: {kg} — {'зелёный' if kg == (2, 2) else 'КРАСНЫЙ'}")
    # (2) поимка
    env = dict(os.environ, BINS='chase', SUF='_flat'); subprocess.run([str(ROOT / 'tools/bots/build.sh'), '-DCHASE_FLAT_CATCH=1'], check=True, capture_output=True, env=env)
    def caught(b, f, c): return 'ПОЙМАН' in subprocess.run([str(ROOT / 'build/bots' / b), str(ROOT / 'build/level.shr'), str(ROOT / 'build/homer.shr'),
                                                              str(ROOT / 'build/sandbox/roads-l1.bin'), '--catch-probe', *map(str, f + c)], capture_output=True, text=True).stdout
    fr, gr, gs = caught('chase_flat', B, A), caught('chase', B, A), caught('chase', A, C)
    c_ok = fr and not gr and gs
    lines.append(f"(2) поимка: контроль (по плоскости) беглец на крыше над погоней — {'КРАСНЫЙ, пойман' if fr else 'не пойман — КОНТРОЛЬ НЕ ЛОВИТ'}; "
                 f"рабочая: крыша/дорога — {'не пойман, зелёный' if not gr else 'ПОЙМАН, красный'}, бок о бок на дороге — {'пойман, зелёный' if gs else 'НЕ ПОЙМАН, красный'}")
    # (3) заморозка
    src = base / 'src'
    for f in IN_FILES:
        if (ROOT / 'build' / f).exists(): copy_in(ROOT / 'build' / f, src / f, f)
    def rebuild():   # «пересборка» уровня: та же карта, вся коллизия (треугольники COL1) выше на 3 м
        import struct
        b = bytearray((src / 'level.shr').read_bytes()); co = struct.unpack_from('<I', b, 92)[0]; ntri = struct.unpack_from('<I', b, co + 24)[0]
        for t in range(ntri):
            for v in (1, 4, 7): o = co + 48 + 48 * t + 4 * v; struct.pack_into('<f', b, o, struct.unpack_from('<f', b, o)[0] + 3.0)
        tmp = src / 'level.shr.new'; tmp.write_bytes(bytes(b)); os.replace(tmp, src / 'level.shr')
    empty = base / 'fixed-empty.tsv'; empty.write_text('# пусто\n')
    os.environ.update(NIGHT_SRC=str(src), NIGHT_SEED='4242', NIGHT_CHASE='2 4 1')
    def night(name, mutate, nofreeze):
        if nofreeze: os.environ['NIGHT_NO_FREEZE'] = '1'
        d = base / name; stop = threading.Event()
        def watch():
            while not stop.is_set():
                try:
                    if json.loads((d / 'night.json').read_text())['runlog']: rebuild(); return
                except Exception: pass
                time.sleep(.2)
        th = threading.Thread(target=watch) if mutate else None
        if th: th.start()
        try: run_night(d, 1, time.time() + 200, empty, dict(explore=0, chase=1, play=0), station_on=False)
        finally:
            stop.set(); os.environ.pop('NIGHT_NO_FREEZE', None)
            if th: th.join()
        for f in IN_FILES:   # вернуть копию входов к исходной для следующей ночи
            if (ROOT / 'build' / f).exists(): copy_in(ROOT / 'build' / f, src / f, f)
        return json.loads((d / 'night.json').read_text())
    try:
        base_n, froz, ctrl = night('base', False, False), night('frozen', True, False), night('control', True, True)
    finally:
        for k in ('NIGHT_SRC', 'NIGHT_SEED', 'NIGHT_CHASE'): os.environ.pop(k, None)
    def same(S):   # итоги прогонов с тем же номером совпадают с ночью без пересборки (с 2-го прогона: пересборка после 1-го)
        b = {r['i']: r['digest'] for r in base_n['runlog']}; s = {r['i']: r['digest'] for r in S['runlog']}
        common = sorted(set(b) & set(s) - {0}); return sum(b[i] == s[i] for i in common), len(common)
    fs, cs = same(froz), same(ctrl)
    f_ok = fs[1] >= 2 and fs[0] == fs[1] and len({r['levelSha'] for r in froz['runlog']}) == 1 and froz.get('intact') is True
    c_red = cs[1] >= 1 and cs[0] < cs[1]
    lines.append(f"(3) заморозка: прогонов без пересборки {len(base_n['runlog'])}; контроль (входы общие) после пересборки совпало {cs[0]} из {cs[1]} — "
                 f"{'КРАСНЫЙ, мир поменялся посреди ночи' if c_red else 'не поменялся — КОНТРОЛЬ НЕ ЛОВИТ'}; замороженная: совпало {fs[0]} из {fs[1]}, "
                 f"уровень один ({len({r['levelSha'] for r in froz['runlog']})}), манифест цел {froz.get('intact')} — {'зелёный' if f_ok else 'КРАСНЫЙ'}")
    ok = k_ok and c_ok and f_ok and c_red
    lines.append(f"RESULT: {'OK' if ok else 'FAIL'}")
    (base / 'gate.txt').write_text('\n'.join(lines) + '\n'); print('\n'.join(lines)); print('->', base)
    return 0 if ok else 1


def gate_t14():
    """Гейт Т1.4: у каждой строки docs/state/fixed-clusters.tsv есть повтор и «исправлено <коммит>». Для каждой: копия viewer/ с
    обратно наложенным исправлением (git show <коммит> -- viewer | git apply -R) -> свои game_headless и chase -> «вернулось» проигрывает
    повтор -> утро гейтовой ночи показывает строку в «Вернулось» первым разделом (красный на откате); с нынешним кодом — не показывает."""
    global BIN
    rows = fixed_rows(FIXED); stamp = time.strftime('%Y%m%d-%H%M%S'); base = NIGHTS / (stamp + '-gate-t14'); base.mkdir(parents=True)
    if not rows: print('гейт Т1.4: в fixed-clusters.tsv нет строк — нечего проверять'); return 1
    lines, ok = [], True
    for r in rows:
        m = re.search(r'исправлено ([0-9a-f]{7,40})', r['note']); rp = ROOT / r['repro']
        if not m or not rp.exists(): lines.append(f"{r['key']}: {'нет повтора' if not rp.exists() else 'нет «исправлено <коммит>» в заметке'} — КРАСНЫЙ"); ok = False; continue
        sha = m.group(1); rv = base / f'revert-{sha}'
        if not (rv / 'bin/game_headless').exists():   # 01.10: строк с одним коммитом несколько — откат собирается один раз (copytree падал на второй)
            shutil.rmtree(rv, ignore_errors=True); shutil.copytree(ROOT / 'viewer', rv / 'viewer', ignore=shutil.ignore_patterns('build'))
            diff = subprocess.run(['git', 'show', sha, '--', 'viewer'], cwd=ROOT, capture_output=True).stdout
            ap = subprocess.run(['patch', '-R', '-p1', '-s', '-d', str(rv)], input=diff, capture_output=True)   # не git apply: в папке репозитория он молча пропускает пути
            if ap.returncode: lines.append(f"{r['key']}: откат {sha} не накладывается на нынешний код — {ap.stderr.decode()[:120]}"); ok = False; continue
            env = dict(os.environ, BINS='game_headless chase', V_DIR=str(rv / 'viewer'), OUT_DIR=str(rv / 'bin'))
            b = subprocess.run([str(ROOT / 'tools/bots/build.sh')], capture_output=True, text=True, env=env)
            if b.returncode: lines.append(f"{r['key']}: сборка отката не прошла — {b.stderr[-160:]}"); ok = False; continue
        def page(name, binp, rows1):
            global BIN
            keep = BIN; BIN = binp
            try:
                d = base / name; N = Night(d, 0, time.time()); N.s['regress'] = [dict(x, back=None) for x in rows1]
                tmp = d / 'fixed.tsv'; tmp.write_text(FIXED.read_text()); N.s['regress'] = regress(tmp); N.s['finished'] = 'гейт'; N.save()
                return morning(d, write_root=False), N.s['regress']
            finally: BIN = keep
        tb, rb = page(f'reverted-{sha}', rv / 'bin', rows); tg, rg = page(f'current-{sha}', ROOT / 'build/bots', rows)
        def shown(txt): sec = txt.split('## Вернулось')[1].split('\n## ')[0] if '## Вернулось' in txt else ''; return r['key'] in sec
        def first(txt): return [l for l in txt.splitlines() if l.startswith('## ')][:1] == ['## Вернулось (исправленные кластеры снова воспроизводятся)']
        red, green = shown(tb) and first(tb), not shown(tg)
        ok &= red and green
        lines.append(f"{r['key']} ({sha}): откат — {'КРАСНЫЙ, «Вернулось» первым разделом утра' if red else 'не вернулся — ГЕЙТ НЕ ЛОВИТ'}; нынешний код — {'зелёный, не вернулся' if green else 'ВЕРНУЛСЯ — исправление не держит'}")
    lines.append(f"RESULT: {'OK' if ok else 'FAIL'}")
    (base / 'gate.txt').write_text('\n'.join(lines) + '\n'); print('\n'.join(lines)); print('->', base)
    return 0 if ok else 1


def gate_t13():
    """Гейт Т1.3: копия последней настоящей ночи + подложенный новый кластер (Гомер заперт, вдали от известного, раз меньше, чем у
    самой частой канавы) -> утро: подложенный — первая строка новых, канавы только в свёртке одной строкой.
    Контроль NIGHT_NO_KNOWN=1 (свёртки нет, как до Т1.3): первыми стоят канавы, подложенный не первый."""
    fin = finished_nights()
    if not fin: print('гейт Т1.3: нет завершённой ночи'); return 1
    stamp = time.strftime('%Y%m%d-%H%M%S'); base = NIGHTS / (stamp + '-gate-t13'); base.mkdir(parents=True)
    S = json.loads(fin[-1][0].read_text()); top = max(v['n'] for v in S['explore']['clusters'].values())
    key = cluster_key('foot_trapped', 1000.5, 1000.5, 0, 'b1')
    S['explore']['clusters'][key] = dict(kind='foot_trapped', x=1000.5, y=5.0, z=1000.5, layer=0, obj='b1', n=top // 2 + 3, t=1.0, repro='подложено гейтом Т1.3')
    def page(name, env):
        d = base / name; d.mkdir(); (d / 'night.json').write_text(json.dumps(S, ensure_ascii=False))
        if env: os.environ[env] = '1'
        try: return morning(d, write_root=False)
        finally: os.environ.pop(env or '_', None)
    def first(txt): sec = txt.split('## Топ-10')[1].split('\n## ')[0]; rows = [l for l in sec.splitlines() if l.startswith('| ') and not l.startswith('| вид')]; return rows[0] if rows else ''
    def canals_in_top(txt): return sum(1 for l in txt.split('## Топ-10')[1].split('\n## ')[0].splitlines() if l.startswith('| fall'))
    tb, tg = page('control', 'NIGHT_NO_KNOWN'), page('known', None)
    red = 'подложено гейтом' not in first(tb)
    fold = '11.3 канавы' in tg.split('## Известное')[1].split('\n## ')[0] if '## Известное' in tg else False
    green = 'подложено гейтом' in first(tg) and canals_in_top(tg) == 0 and fold
    lines = [f"контроль (без свёртки): первая строка — {first(tb)[:60]} — {'КРАСНЫЙ, подложенный не первый' if red else 'подложенный первый — КОНТРОЛЬ НЕ ЛОВИТ'}",
             f"рабочее утро: первая строка — {first(tg)[:60]}; канав в топе {canals_in_top(tg)}; канавы в свёртке {'да' if fold else 'НЕТ'} — {'зелёный' if green else 'КРАСНЫЙ'}",
             f"RESULT: {'OK' if red and green else 'FAIL'}"]
    (base / 'gate.txt').write_text('\n'.join(lines) + '\n'); print('\n'.join(lines)); print('->', base)
    return 0 if red and green else 1


if __name__ == '__main__':
    sys.exit(main())
