#!/usr/bin/env python3
"""Боты по всем уровням 1–7 и всем известным рискам (правка Роба 415, 09.10). Только процессор Мака: без AI, без API, без
сети, без эмулятора и без окон. Боты меряют, код игры и данные уровня не меняют, карту не правят.

  python3 tools/bots/allrisk.py                          проверочный пакет: все 7 уровней, коротко (≤ 10 мин на уровень)
  python3 tools/bots/allrisk.py --night                  ночь: больше seed, мест, машин; до --until (по умолчанию 07:00)
  python3 tools/bots/allrisk.py --levels 1,5 --modes roll,jumps
  python3 tools/bots/allrisk.py --baseline DIR           сравнить с этим прогоном (иначе — с отмеченной базой BASELINE)
  python3 tools/bots/allrisk.py --set-baseline           отметить этот прогон базой для следующих
  python3 tools/bots/allrisk.py --report DIR             пересобрать отчёт готового прогона (сравнение — с базой)
  python3 tools/bots/allrisk.py --cflags "-DCAR_TYRE_LEVER_OLD=1 -DCAR_WEEBLE_GROUND_OLD=1"   отрицательный контроль: игра
                                                         собрана с флагом прежнего поведения (код не меняется), отчёт обязан
                                                         поднять флаг на семействе; такой прогон базой не становится

Что гоняется на каждом уровне (данные уровня — те же файлы, что у EBOOT: level.shr, player.shr, levelNN.msn, traffic.shr,
carzone/collect/msncars рядом; дороги build/sandbox/roads-lN.bin):
  tools/bots/allrisk.c   progress (логичное прохождение одним миром, длинный мир, бюджет кадра), roll (89 машин на прямых
                         уровня: перевороты, две колеса, крен наружу/внутрь, клевок), jumps (все зоны прыжка × скорость × сдвиг,
                         камеры зон), hedges (изгороди), traffic (тараны трафика: что делает сбитая машина), phantom (невидимые
                         стены: радиальные заезды у дорог и у мест из замечаний Роба)
  существующие проверки (как наблюдения, без своих красных): tests/pockets/host.c census (карманы за заборами),
                         tests/traffic/rejoin.c (возврат трафика на полосу, регресс №400), tests/aicar/host.c (машины миссий и
                         гонок с ИИ среди трафика), tests/hnr/police_host.c (полиция: дистанция у стоящего, пешком, в погоне),
                         tests/cars/cornering.c (89 машин на ровной площадке; один раз на прогон, уровень «все»)
Результат: build/bots/allrisk/<время>/ — cases.tsv (дописывается по мере готовности задач), jobs/*.tsv (сырой вывод),
РЕЗУЛЬТАТ.md + result.json (семейство × уровень, сравнение с базой, флаги, повтор каждого случая), MANIFEST.tsv (SHA-256
бинарников и данных), bin/ (замороженные бинарники прогона: повтор не зависит от дневной пересборки).
Повтор случая: строка «повтор» в отчёте — бинарник из bin/, те же данные (хэши в MANIFEST), --mode, --seed, --only <id>."""
import argparse
import collections
import concurrent.futures as cf
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
OUTS = ROOT / 'build/bots/allrisk'
BASEFILE = OUTS / 'BASELINE'
HOVER = ('hbike_v', 'frink_v')     # машины без колёс по сценариям диска (hover / SetWheelsHidden)
FOCUS = {5: ['K8-2'], 1: ['F4-8', 'K13-2', 'J9-4', 'K3-1']}   # места из замечаний Роба: 414 (L5 K8-2 фантом), 339, 346, 173, аудит п. 5
MODES = ('progress', 'roll', 'jumps', 'hedges', 'traffic', 'phantom', 'pockets', 'rejoin', 'aicar', 'police', 'cornering', 'determinism')

# риск из замечания 415 -> семейства отчёта
RISKS = [
    ('Перевороты в поворотах и на ручнике (89 машин)', ['rollover', 'rollover_flat']),
    ('Направление крена и клевка', ['roll_direction', 'pitch_direction']),
    ('Езда на двух колёсах', ['two_wheel']),
    ('Карманы и заборы', ['pockets', 'pocket_trap']),
    ('Невидимые стены, фантомы', ['invisible_wall', 'air_wall', 'invisible_fence']),
    ('Изгороди', ['hedges']),
    ('Прыжки и посадки (дом)', ['jumps', 'jump_landing', 'jump_stuck', 'jump_approach']),
    ('Удары машина-машина, трафик после удара', ['traffic_hit', 'traffic_rejoin', 'traffic_on_side', 'traffic_hover']),
    ('ИИ миссий и гонок против трафика', ['ai_cars', 'ai_car_state']),
    ('Полиция: дистанция', ['police']),
    ('Летающие машины', ['hover_car']),
    ('Камеры: зоны и прыжки, за машиной', ['jump_camera', 'camera_follow']),
    ('Длинный мир без сброса', ['long_world', 'car_destroyed', 'fall_through', 'auto_return', 'stuck']),
    ('Логичное прохождение уровня', ['progress_leg']),
    ('Бюджет кадра (заменитель на Маке)', ['perf']),
    ('Детерминизм (повтор = тот же мир)', ['determinism']),
]
FAM_RU = {'rollover': 'переворот', 'rollover_flat': 'переворот (ровная площадка)', 'roll_direction': 'крен внутрь поворота',
          'pitch_direction': 'нос вверх при торможении', 'two_wheel': 'на двух колёсах', 'pockets': 'карманы за заборами',
          'pocket_trap': 'RESET возвращает в ловушку', 'invisible_wall': 'невидимая стена', 'air_wall': 'невидимая стена в воздухе',
          'invisible_fence': 'забор данных без рисунка', 'hedges': 'изгородь', 'jumps': 'прыжок', 'jump_landing': 'посадка',
          'jump_stuck': 'встал после прыжка', 'jump_approach': 'разгон к трамплину', 'traffic_hit': 'таран трафика',
          'traffic_rejoin': 'трафик после удара едет задом', 'traffic_on_side': 'трафик едет на боку', 'traffic_hover': 'трафик висит',
          'ai_cars': 'машины ИИ миссий', 'ai_car_state': 'машина ИИ в воздухе/на крыше', 'police': 'полиция', 'hover_car': 'летающая машина',
          'jump_camera': 'камера зоны прыжка', 'camera_follow': 'камера за машиной (заменитель)', 'long_world': 'длинный мир',
          'car_destroyed': 'машина разбита', 'fall_through': 'провал под землю', 'auto_return': 'автовозврат машины', 'stuck': 'застрял',
          'progress_leg': 'отрезок прохождения', 'perf': 'время кадра', 'determinism': 'детерминизм'}


def log(m):
    print(time.strftime('%H:%M:%S'), m, flush=True)


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()[:16]


def rel(p):
    p = Path(p)
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def data_root(arg):
    """build/ этого дерева; в рабочей копии (worktree) без собранных уровней — build/ основного дерева (только чтение)"""
    if arg:
        return Path(arg).resolve()
    if os.environ.get('SHAR_DATA'):
        return Path(os.environ['SHAR_DATA']).resolve()
    if (ROOT / 'build/level.shr').exists() and (ROOT / 'build/levels/l2/level.shr').exists():
        return ROOT / 'build'
    common = Path(subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--git-common-dir'], capture_output=True, text=True).stdout.strip())
    if not common.is_absolute():
        common = (ROOT / common).resolve()
    return common.parent / 'build'


def level_files(D, n):
    if n == 1:
        f = dict(level=D / 'level.shr', player=D / 'homer.shr', msn=D / 'missions/level01.msn', traffic=D / 'traffic.shr',
                 msncars=D / 'msncars-l1.shr', carzone=D / 'carzone-l1.shr', collect=D / 'collect-l1.shr')
    else:
        L = D / 'levels' / f'l{n}'
        pl = L / 'player.shr'
        f = dict(level=L / 'level.shr', player=pl if pl.exists() else D / 'homer.shr', msn=L / f'level0{n}.msn', traffic=L / 'traffic.shr',
                 msncars=L / f'msncars-l{n}.shr', carzone=L / f'carzone-l{n}.shr', collect=L / f'collect-l{n}.shr')
    f['roads'] = D / f'sandbox/roads-l{n}.bin'
    return f


def place_center(code):
    sys.path.insert(0, str(ROOT / 'tools'))
    import place  # noqa: E402  (сетка кодов мест, viewer/placecode.h)
    _, c, r, sub = place.parse(code)
    x, z, _ = place.center(c, r, sub)
    return x, z


# ---------------------------------------------------------------------------------------------------------- сборка
def build(bindir, cflags):
    bindir.mkdir(parents=True, exist_ok=True)
    cc = 'cc -std=c11 -O2 -w -DSKIN_HOST -I viewer -I tools/bots ' + cflags
    lib = 'V=viewer; . tools/bots/lib.sh; '
    cmds = {
        'allrisk': f'{lib}{cc} -DALLRISK_MISSION_LIBRARY tools/bots/allrisk.c tools/bots/missioner.c $BOTS_LIB viewer/camsafe.c viewer/carzone.c -lm -o {bindir}/allrisk',
        'pockets': f'{cc} tests/pockets/host.c viewer/car.c viewer/col.c -lm -o {bindir}/pockets',
        'cornering': f'{cc} tests/cars/cornering.c viewer/car.c viewer/col.c -lm -o {bindir}/cornering',
        'rejoin': f'{cc} tests/traffic/rejoin.c viewer/traffic.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c -lm -o {bindir}/rejoin',
        'aicar': f'{cc} tests/aicar/host.c viewer/msncar.c viewer/car.c viewer/col.c viewer/traffic.c viewer/homer.c viewer/skin.c '
                 f'viewer/mission/msn_file.c viewer/mission/msn_ops.c -lm -o {bindir}/aicar',
        'police': f'{lib}{cc} tests/hnr/police_host.c $BOTS_LIB -lm -o {bindir}/police',
    }
    bad = {}

    def one(k):
        r = subprocess.run(['bash', '-c', cmds[k]], cwd=ROOT, capture_output=True, text=True)
        if r.returncode:
            bad[k] = (r.stderr.strip().splitlines() or ['?'])[-1][:200]
    with cf.ThreadPoolExecutor(6) as ex:
        list(ex.map(one, cmds))
    return bad


# ---------------------------------------------------------------------------------------------------------- задачи
class Run:
    def __init__(self, a):
        self.a = a
        self.D = data_root(a.data)
        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S') + ('-night' if a.night else '') + ('-control' if a.cflags else '')
        self.dir = OUTS / stamp
        self.dir.mkdir(parents=True)
        (self.dir / 'jobs').mkdir()
        self.bin = self.dir / 'bin'
        self.lock = threading.Lock()
        self.cases = self.dir / 'cases.tsv'
        self.cases.write_text('# семейство\tвердикт\tid\tуровень\tместо\tx\ty\tz\tслой:объект\tкадр\tметрики\tповтор\tзадача\n')
        self.status = dict(started=dt.datetime.now().isoformat(timespec='seconds'), jobs={}, dir=rel(self.dir))
        self.stop = None
        self.deadline = None
        if a.night:
            now = dt.datetime.now(); h, m = map(int, a.until.split(':'))
            d = now.replace(hour=h, minute=m, second=0, microsecond=0)
            self.deadline = d if d > now else d + dt.timedelta(days=1)

    def manifest(self, levels):
        rows = ['# путь\tsha256[:16]\tбайт']
        git = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain', '--', 'viewer', 'tools/bots', 'tests'], capture_output=True, text=True).stdout.strip()
        meta = dict(git=git, dirty=bool(dirty), data=str(self.D), cflags=self.a.cflags, files={})
        for p in sorted(self.bin.glob('*')):
            meta['files'][rel(p)] = sha(p); rows.append(f'{rel(p)}\t{meta["files"][rel(p)]}\t{p.stat().st_size}')
        for n in levels:
            for k, p in level_files(self.D, n).items():
                if p.exists():
                    meta['files'][str(p)] = sha(p); rows.append(f'{p}\t{meta["files"][str(p)]}\t{p.stat().st_size}')
        (self.dir / 'MANIFEST.tsv').write_text('\n'.join(rows) + '\n')
        self.meta = meta

    def jobs(self, levels, rnd=1):
        """задачи круга rnd: первый — всё; следующие (ночь) — новые seed прохождения, другие прямые, места тарана и узлы"""
        a = self.a; J = []; B = self.bin; k = 3 if a.night else 1
        modes = set(a.modes) if rnd == 1 else set(a.modes) & {'progress', 'roll', 'traffic', 'phantom'}
        sfx = '' if rnd == 1 else f':r{rnd}'
        for n in levels:
            f = level_files(self.D, n)
            if not f['level'].exists():
                J.append(dict(level=n, name='data', cmd=None, why=f'нет {f["level"]}')); continue
            withMsn = [str(B / 'allrisk'), str(f['level']), str(f['player']), str(f['roads']), str(f['msn']) if f['msn'].exists() else '-']
            noMsn = withMsn[:4] + ['-']   # случаи (roll, jumps, …) без сценариев миссий: старт миссии уровня ставит игрока на свою точку

            def ar(name, mode, *extra, timeout=600):
                if mode in modes or name.split(':')[0] in modes:
                    base = withMsn if mode == 'progress' else noMsn
                    J.append(dict(level=n, name=name, kind='allrisk', mode=mode, base=base, extra=list(extra), timeout=timeout,
                                  cmd=base + ['--mode', mode] + list(extra), env={'BW_LEVEL': str(n)}))
            ns = 8 if a.night else 2
            for s in range((rnd - 1) * ns + 1, rnd * ns + 1):
                ar(f'progress:s{s}', 'progress', '--seed', str(s), '--secs', '3600', timeout=1800)
            ar('roll' + sfx, 'roll', '--n', str(3 * k), '--seed', str(rnd), timeout=1800)
            ar('jumps', 'jumps', timeout=1200)
            ar('hedges', 'hedges', '--n', str(16 * k), timeout=900)
            ar('traffic' + sfx, 'traffic', '--n', str(12 * k), '--seed', str(rnd), timeout=900)
            foc = []
            for code in (FOCUS.get(n, []) if rnd == 1 else []):
                x, z = place_center(code); foc += ['--focus', code, '%.1f' % x, '%.1f' % z]
            ar('phantom' + sfx, 'phantom', '--n', str(10 * k), '--seed', str(rnd), *foc, timeout=900)
            if 'determinism' in modes:
                for t in 'ab':
                    J.append(dict(level=n, name=f'determinism:{t}', kind='allrisk', mode='progress', base=withMsn, extra=['--seed', '1', '--secs', '300'],
                                  timeout=600, cmd=withMsn + ['--mode', 'progress', '--seed', '1', '--secs', '300'], env={'BW_LEVEL': str(n)}))
            if 'pockets' in modes:
                J.append(dict(level=n, name='pockets', kind='pockets', timeout=900, cmd=[str(B / 'pockets'), str(f['level']), 'census']))
            if 'rejoin' in modes:
                J.append(dict(level=n, name='rejoin', kind='rejoin', timeout=300, cmd=[str(B / 'rejoin'), str(f['level']), str(f['traffic'])]))
            if 'aicar' in modes:
                J.append(dict(level=n, name='aicar', kind='aicar', timeout=900, cmd=[str(B / 'aicar'), str(f['level']), str(f['traffic']), str(f['msn']), str(f['msncars'])]))
            if 'police' in modes:
                J.append(dict(level=n, name='police', kind='police', timeout=900, cmd=[str(B / 'police'), str(f['level']), str(f['player']), str(f['msn'])]))
        if 'cornering' in modes:
            J.append(dict(level=0, name='cornering', kind='cornering', timeout=300, cmd=[str(B / 'cornering')]))
        return J

    # ------------------------------------------------------------------------------------------------- исполнение
    def run_job(self, j):
        tag = f'L{j["level"]}_{j["name"].replace(":", "_")}'
        out = self.dir / 'jobs' / (tag + '.tsv')
        if j.get('cmd') is None:
            rows = [self.row('data', 'fail', 'data', j['level'], '--', 0, 0, 0, '-', 0, j['why'], '-', j['name'])]
            self.append(rows, j, 'нет данных'); return
        if self.stop:
            self.status['jobs'][tag] = dict(state='пропущена', why=self.stop); return
        timeout = j['timeout']
        if self.deadline:
            timeout = min(timeout, max(30, (self.deadline - dt.datetime.now()).total_seconds()))
        t0 = time.time()
        with out.open('w') as fo:
            p = subprocess.Popen(['nice', '-n', '10'] + j['cmd'], cwd=ROOT, stdout=fo, stderr=subprocess.STDOUT, start_new_session=True,
                                 env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', **j.get('env', {})))
            try:
                code = p.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGTERM); p.wait(); code = 'timeout'
        rows = self.parse(j, out.read_text(errors='replace'), code)
        self.append(rows, j, 'код %s за %.0f с' % (code, time.time() - t0))

    def row(self, fam, verdict, cid, level, place, x, y, z, obj, frame, metrics, repro, job):
        return [fam, verdict, cid, f'L{level}' if isinstance(level, int) else level, place, str(x), str(y), str(z), obj, str(frame), metrics, repro, job]

    def repro(self, j, cid):
        pre = ''.join(f'{k}={v} ' for k, v in j.get('env', {}).items())
        return pre + self.repro_cmd(j, cid)

    def repro_cmd(self, j, cid):
        if j['kind'] != 'allrisk':
            return ' '.join(shlex.quote(rel(c)) for c in j['cmd'])
        if cid.startswith('progress:'):
            return ' '.join(shlex.quote(rel(c)) for c in j['cmd'])
        return ' '.join(shlex.quote(rel(c)) for c in j['base'] + ['--mode', j['mode']] + j['extra'] + ['--only', cid])

    def parse(self, j, text, code):
        L = j['level']; rows = []; name = j['name']
        if j['kind'] == 'allrisk':
            for ln in text.splitlines():
                f = ln.split('\t')
                if f[0] == 'CASE' and len(f) >= 12:
                    fam, verdict, cid = f[1], f[2], f[3]
                    rows.append(self.row(fam, verdict, cid, L, f[5], f[6], f[7], f[8], f[9], f[10], f[11], self.repro(j, cid), name))
                elif f[0] == 'STAT':
                    kv = dict(x.split('=', 1) for x in f[2:] if '=' in x)
                    if f[1] == 'data' and name in ('progress:s1', 'roll'):
                        rows.append(self.row('perf', 'info', f'data:{name}', L, '--', 0, 0, 0, '-', 0, 'данные уровня: ' + ' '.join(f'{k}={v}' for k, v in kv.items()), self.repro(j, ''), name))
                    if f[1] == 'perf':
                        rows.append(self.row('perf', 'info', f'perf:{name}', L, '--', 0, 0, 0, '-', 0, ' '.join(f'{k}={v}' for k, v in kv.items()), self.repro(j, ''), name))
                    if f[1] == 'progress':
                        bad = int(kv.get('falls', 0)) > 0
                        rows.append(self.row('long_world', 'risk' if bad else 'ok', f'progress:{name}', L, '--', 0, 0, 0, '-', 0,
                                             ' '.join(f'{k}={v}' for k, v in kv.items()), self.repro(j, 'progress:'), name))
                        rows.append(self.row('camera_follow', 'info', f'progress:{name}', L, '--', 0, 0, 0, '-', 0,
                                             'заменитель камеры за машиной (точка FollowCameraData без сглаживания и без правила 331), проб раз в 15 кадров: '
                                             f'глаз за стеной {kv.get("cam_eye_wall")}, под землёй {kv.get("cam_ground")}, зажата <2 м {kv.get("cam_squeezed")}', self.repro(j, 'progress:'), name))
                        j.setdefault('stat', {}).update(kv)
            if code not in (0,):
                rows.append(self.row('data', 'fail', name, L, '--', 0, 0, 0, '-', 0, f'бот завершился с кодом {code}: ' + (text.strip().splitlines() or [''])[-1][:160], self.repro(j, ''), name))
            return rows
        cmd = self.repro(j, '')
        if j['kind'] == 'pockets':
            for ln in text.splitlines():
                if ln.startswith(('FAIL', 'ok ')):
                    rows.append(self.row('pockets', 'risk' if ln.startswith('FAIL') else 'ok', 'pockets:' + ln.split(':')[0].split()[-1], L, '--', 0, 0, 0, '-', 0, ln.strip()[:300], cmd, name))
                elif ln.startswith(('ПЛОХО', 'ТОЛЧОК', 'ВЫТАЛКИВАЕТ')):
                    m = re.search(r'\((-?[\d.]+)[, ]+(-?[\d.]+)', ln)
                    rows.append(self.row('pockets', 'risk', 'pockets:point', L, '--', m.group(1) if m else 0, 0, m.group(2) if m else 0, '-', 0, ln.strip()[:300], cmd, name))
            itog = next((x for x in text.splitlines() if x.startswith('ИТОГ')), '')
            if itog:
                rows.append(self.row('pockets', 'info', 'pockets:census', L, '--', 0, 0, 0, '-', 0, itog.split(':', 1)[-1].strip()[:300], cmd, name))
        elif j['kind'] == 'rejoin':
            t = text.strip().splitlines()[-1] if text.strip() else ''
            nodata = 'shoved 0' in t
            rows.append(self.row('traffic_rejoin', 'info' if nodata else ('ok' if code == 0 else 'risk'), 'rejoin', L, '--', 0, 0, 0, '-', 0,
                                 (t + (' — точки tests/traffic/rejoin.c только с карты уровня 1: здесь возврат на полосу меряет бот traffic' if nodata else ''))[:300], cmd, name))
        elif j['kind'] == 'aicar':
            for ln in text.splitlines():
                s = ln.strip()
                if s.startswith(('ok ', 'FAIL ')):
                    rows.append(self.row('ai_cars', 'risk' if s.startswith('FAIL') else 'ok', 'aicar:' + re.sub(r'\s+', '_', s[5:40].strip()), L, '--', 0, 0, 0, '-', 0, s[:300], cmd, name))
                elif s.startswith('худший'):
                    rows.append(self.row('ai_cars', 'info', 'aicar:worst', L, '--', 0, 0, 0, '-', 0, s[:300], cmd, name))
        elif j['kind'] == 'police':
            for ln in text.splitlines():
                m = re.match(r'CHECK (\w+)\s+(\w+)\s+(.*)', ln.strip())
                if m:
                    xz = re.search(r'\((-?\d+), (-?\d+)\)', m.group(3))
                    rows.append(self.row('police', 'ok' if m.group(2) == 'OK' else 'risk', f'police:{m.group(1)}', L, '--', xz.group(1) if xz else 0, 0, xz.group(2) if xz else 0, '-', 0, m.group(3)[:300], cmd, name))
        elif j['kind'] == 'cornering':
            for ln in text.splitlines():
                f = ln.split()
                if len(f) == 8 and f[0] != 'car':
                    two = float(f[4]) > 10
                    flip = f[7] == 'FLIP'
                    rows.append(self.row('rollover_flat', 'risk' if flip or two else 'ok', f'cornering:{f[0]}:{f[1]}', 'Lall', '--', 0, 0, 0, '-', 0,
                                         f'car={f[0]} mode={f[1]} v_in={f[2]} roll_max={f[3]} two_wheel%={f[4]} air%={f[5]} rights={f[6]} flip={int(flip)}', cmd + ' ' + f[0], name))
                    if f[0] in HOVER:
                        rows.append(self.row('hover_car', 'risk' if flip or two else 'ok', f'cornering:{f[0]}:{f[1]}', 'Lall', '--', 0, 0, 0, '-', 0, f'ровная площадка: {ln.strip()}', cmd + ' ' + f[0], name))
        if not rows:
            rows.append(self.row('data', 'fail', name, L, '--', 0, 0, 0, '-', 0, f'проверка не дала строк (код {code}): ' + (text.strip().splitlines() or [''])[-1][:160], cmd, name))
        return rows

    def append(self, rows, j, note):
        with self.lock:
            with self.cases.open('a') as f:
                for r in rows:
                    f.write('\t'.join(x.replace('\t', ' ').replace('\n', ' ') for x in r) + '\n')
            tag = f'L{j["level"]}_{j["name"]}'
            self.status['jobs'][tag] = dict(state='готово', note=note, rows=len(rows), stat=j.get('stat'))
            tmp = self.dir / 'status.json.tmp'; tmp.write_text(json.dumps(self.status, ensure_ascii=False, indent=1)); tmp.replace(self.dir / 'status.json')
        log(f'  L{j["level"]} {j["name"]}: {note}, строк {len(rows)}')


# ---------------------------------------------------------------------------------------------------------- отчёт
def load_cases(d):
    rows = []
    for ln in (Path(d) / 'cases.tsv').read_text(errors='replace').splitlines():
        if not ln or ln.startswith('#'):
            continue
        f = ln.split('\t')
        if len(f) >= 13:
            rows.append(dict(fam=f[0], verdict=f[1], id=f[2], level=f[3], place=f[4], x=f[5], y=f[6], z=f[7], obj=f[8], frame=f[9], metrics=f[10], repro=f[11], job=f[12]))
    return rows


def summarize(rows):
    S = collections.defaultdict(lambda: dict(cases=0, risk=0, fail=0, ok=0, info=0, keys=set()))
    for r in rows:
        s = S[(r['fam'], r['level'])]
        s['cases'] += 1; s[r['verdict']] = s.get(r['verdict'], 0) + 1
        if r['verdict'] in ('risk', 'fail'):
            s['keys'].add(cluster(r))
    return S


def cluster(r):
    """ключ места: семейство, уровень, код места, слой и примитив (как tools/bots/clusterkey.py, клетка — участок кода места)"""
    obj = r['obj'] if r['obj'] not in ('-1:-',) else '-'
    if r['place'] == '--' and r['x'] in ('0', '0.0', '0.00'):
        return f'{r["fam"]}:{r["level"]}:{r["id"]}'
    return f'{r["fam"]}:{r["level"]}:{r["place"]}:{obj}'


def perf_of(rows):
    P = {}
    for r in rows:
        if r['fam'] != 'perf':
            continue
        kv = dict(x.split('=', 1) for x in r['metrics'].split() if '=' in x)
        if 'us_avg' not in kv:
            continue
        try:
            p99 = float(kv.get('us_p99', 0)); avg = float(kv.get('us_avg', 0))
        except ValueError:
            continue
        a = P.setdefault(r['level'], dict(p99=0.0, avg=0.0, n=0, traffic=0))
        a['p99'] = max(a['p99'], p99); a['avg'] += avg; a['n'] += 1; a['traffic'] = max(a['traffic'], int(kv.get('traffic_max', 0) or 0))
    for a in P.values():
        a['avg'] /= max(1, a['n'])
    return P


def determinism(rows):
    out = {}
    by = collections.defaultdict(list)
    for r in rows:
        if r['fam'] == 'long_world' and r['job'].startswith('determinism:'):
            h = re.search(r'\bhash=(\w+)', r['metrics']); by[r['level']].append(h.group(1) if h else '?')
    for lv, hs in by.items():
        out[lv] = dict(ok=len(hs) == 2 and hs[0] == hs[1], hashes=hs)
    return out


def brief(rows, base_rows, base_dir, flags, *, comparable=True):
    """A bounded first screen; risk observations and failed checks stay separate.

    Compare locations even when the old flag threshold would hide one new risk.
    A newly covered place is labelled separately from an observed regression.
    """
    if not base_rows:
        return ['Сравнения с прошлой ночью нет: это первый прогон или база недоступна',
                f'Наблюдения: рисков {sum(r["verdict"] == "risk" for r in rows)}, '
                f'неудачных проверок {sum(r["verdict"] == "fail" for r in rows)}',
                'Места и команды повторения в полной таблице ниже']
    old_bad = {cluster(r) for r in base_rows if r['verdict'] == 'risk'}
    covered = {cluster(r) for r in base_rows}
    groups = collections.defaultdict(set)
    new_places = collections.defaultdict(set)
    for r in rows:
        if r['verdict'] != 'risk' or cluster(r) in old_bad:
            continue
        target = groups if cluster(r) in covered else new_places
        target[r['fam']].add(r['level'] + (' (место не определено)' if r['place']=='--' else ' ' + r['place']))
    L = ['Что изменилось против ' + ('прошлой ночи' if Path(base_dir).name.endswith('-night') else 'базы') + ' (`' + Path(base_dir).name + '`)']
    if not comparable:
        L.append('Сравнение условное: тождество бинарника и данных не подтверждено; причина изменений ещё не установлена')
    notices = []
    for prefix, found in [('Новый риск в проверенном месте', groups), ('Впервые проверенное место с риском', new_places)]:
        for fam, places in sorted(found.items(), key=lambda x: (-len(x[1]), x[0])):
            ordered = sorted(places)
            notices.append(f'- {prefix}: {FAM_RU.get(fam, fam)}; {", ".join(ordered[:2])}'
                           + (f'; ещё мест {len(ordered)-2}' if len(ordered) > 2 else ''))
    if not notices:
        L.append('Новых мест риска не обнаружено в выполненных проверках')
    L += notices[:5]
    if len(notices) > 5:
        L.append(f'Ещё групп с новыми рисками: {len(notices)-5}; подробности ниже')
    failed = [r for r in rows if r['verdict'] == 'fail']
    if failed:
        places = sorted({r['level'] + ' ' + FAM_RU.get(r['fam'], r['fam']) for r in failed})
        L.append(f'Не удалось проверить: {len(failed)} случаев; {"; ".join(places[:2])}'
                 + (f'; ещё групп {len(places)-2}' if len(places)>2 else ''))
    old_coverage = {(r['fam'], r['level']) for r in base_rows}
    coverage = {(r['fam'], r['level']) for r in rows}
    missing = sorted(old_coverage - coverage)
    if missing:
        L.append(f'Нет прежнего покрытия: {len(missing)} групп; {"; ".join(l+" "+FAM_RU.get(f,f) for f,l in missing[:2])}')
    other = [x for x in flags if x['fam'] in ('determinism', 'perf') or x['why'].startswith('хуже базы')]
    if other:
        L.append(f'Дополнительных ухудшений счёта/повтора/времени: {len(other)}; список флагов ниже')
    return L


def dossiers(rows):
    """Observed obstacles with explicit, unproven hypotheses and exact repeats."""
    if os.environ.get('BOT_DOSSIER_OLD'):
        return []
    explanations = {
        'pocket_trap': ('точка RESET попадает в тот же непроезжаемый участок', 'сопоставить точку до/после RESET с опорой и свободным выездом'),
        'stuck': ('контакт около указанного объёма ограничивает путь бота', 'снять контакты в этом кадре, проверить ширину кузова и свободный обход'),
        'invisible_wall': ('твёрдый объём не совпадает с видимым рисунком или его активной позой', 'связать примитив с моделью/суставом/PVIS и сверить кадр игры'),
        'air_wall': ('боковая грань объёма перекрывает траекторию в воздухе', 'проверить верх/боковую грань, высоту машины и исходную коллизию'),
        'fall_through': ('опора не удерживает машину при прохождении этого участка', 'сверить ground-полигон, глубину и момент восстановления'),
        'pockets': ('проверка фиксирует непроезжаемую опору или карман', 'локализовать точку из исходного pockets-проверяльщика, затем записать контакты'),
    }
    groups = collections.defaultdict(list)
    for r in rows:
        if r['fam'] in explanations and r['verdict'] in ('risk', 'info', 'fail'):
            groups[cluster(r)].append(r)
    result = []
    for key, cases in sorted(groups.items(), key=lambda x: (-len(x[1]), x[0])):
        r = cases[0]; guess, check = explanations[r['fam']]
        # A failed harness isn't evidence of an in-game obstacle.
        if r['verdict'] == 'fail':
            guess, check = 'проверка не завершилась; причина в игре ещё не подтверждена', 'сначала устранить ошибку проверки из её журнала'
        known = None
        if r['verdict'] != 'fail' and (r['level'],r['place'],r['obj']) == ('L3','H7-7','0:b409'):
            known = dict(cause='табло beefboard: коллизия оставалась в локальном начале, без преобразования исходной кости root',
                evidence='docs/handoff/ТАБЛО_357_429_2026-10-09.md; codex4/beefboard-20261009 8660b04',
                status='исправлено в отдельной ветке; этот старый риск не является повторной проверкой исправления')
            check = 'после слияния 8660b04 повторить ту же задачу на новых L3/L6 пакетах; source/pack gate уже зелёный'
        elif r['verdict'] != 'fail' and (r['level'],r['place'],r['obj']) == ('L7','F12-9','0:b745'):
            known = dict(cause='исходный объём milShape1 l7z3: ящик 23×24×14 м, боковые грани шире наклонного рисунка крыши',
                evidence='docs/handoff/СТЕНЫ_СВЕРКА_PS2_2026-10-09.md, проверка b745',
                status='тот же объём есть в оригинале; дефект порта этой строкой не доказан')
            check = 'сравнить контакт с готовой или новой записью PS2; исходный ящик не менять по одному риску бота'
        result.append(dict(key=key, family=r['fam'], level=r['level'], place=r['place'],
            object=r['obj'], count=len(cases), position=[float(r[k]) for k in ('x','y','z')], frame=r['frame'],
            observed=r['metrics'], hypothesis=guess, verify=check, repro=r['repro'], job=r['job'],
            verdict=r['verdict'], seeds=len({x['job'] for x in cases}), known=known))
    return result


def report(d, base_dir, meta=None):
    d = Path(d); rows = load_cases(d)
    meta = meta or (json.loads((d / 'result.json').read_text()).get('meta') if (d / 'result.json').exists() else {})
    S = summarize(rows); P = perf_of(rows); DET = determinism(rows)
    B, BP, base_rows = {}, {}, []
    if base_dir and Path(base_dir).resolve() != d.resolve() and (Path(base_dir) / 'cases.tsv').exists():
        base_rows = load_cases(base_dir); B = summarize(base_rows); BP = perf_of(base_rows)
    levels = sorted({r['level'] for r in rows if r['level'] != 'Lall'}, key=lambda s: (len(s), s)) + (['Lall'] if any(r['level'] == 'Lall' for r in rows) else [])
    flags = []
    # флаги: семейство хуже базы (рисков больше на max(2, 25 %) или доля выросла на 10 п.), новые места, детерминизм, время кадра
    for (fam, lv), s in sorted(S.items()):
        if fam in ('perf', 'long_world', 'progress_leg'):
            continue
        b = B.get((fam, lv))
        bad = s['risk'] + s['fail']
        if s['fail']:
            flags.append(dict(fam=fam, level=lv, why=f'проверка не прошла (fail {s["fail"]}): нет данных или бот упал'))
        if b is not None:
            bb = b['risk'] + b['fail']; rate, brate = bad / max(1, s['cases']), bb / max(1, b['cases'])
            new = sorted(s['keys'] - b['keys'])
            if bad > bb + max(2, .25 * bb) or (rate - brate > .10 and bad > bb):
                flags.append(dict(fam=fam, level=lv, why=f'хуже базы: рисков {bb} → {bad} (доля {brate:.0%} → {rate:.0%})', new=new[:5]))
            elif new and fam not in ('invisible_fence', 'stuck', 'car_destroyed', 'auto_return', 'jump_approach'):
                flags.append(dict(fam=fam, level=lv, why=f'новые места рисков: {len(new)}', new=new[:5]))
    for lv, x in DET.items():
        if not x['ok']:
            flags.append(dict(fam='determinism', level=lv, why='два прогона с одним seed дали разный мир: ' + ', '.join(x['hashes'])))
    for lv, p in P.items():
        bp = BP.get(lv)
        if bp and p['avg'] > 1.5 * bp['avg'] and p['avg'] - bp['avg'] > 5:
            flags.append(dict(fam='perf', level=lv, why=f'среднее время кадра на Маке {bp["avg"]:.1f} → {p["avg"]:.1f} мкс (заменитель, не PSP; p99 {bp["p99"]:.0f} → {p["p99"]:.0f})'))
    bmeta = json.loads((Path(base_dir) / 'result.json').read_text()).get('meta', {}) if B and (Path(base_dir) / 'result.json').exists() else {}
    bot_now = next((v for k, v in (meta or {}).get('files', {}).items() if k.endswith('/bin/allrisk')), None)
    bot_base = next((v for k, v in bmeta.get('files', {}).items() if k.endswith('/bin/allrisk')), None)
    data_now = {Path(k).name + '@' + Path(k).parent.name: v for k, v in (meta or {}).get('files', {}).items() if k.endswith('.shr') or k.endswith('.msn') or k.endswith('.bin') and 'roads' in k}
    data_base = {Path(k).name + '@' + Path(k).parent.name: v for k, v in bmeta.get('files', {}).items() if k.endswith('.shr') or k.endswith('.msn') or k.endswith('.bin') and 'roads' in k}
    changed = sorted(k for k in data_now if k in data_base and data_now[k] != data_base[k])
    same_bot = bot_now == bot_base if bot_now and bot_base else None
    ds = dossiers(rows)
    res = dict(kind='allrisk-v1', dir=rel(d), baseline=rel(base_dir) if base_dir else None, meta=meta,
               table={f'{f}|{l}': {k: v for k, v in s.items() if k != 'keys'} for (f, l), s in S.items()},
               perf=P, determinism=DET, flags=flags, dossiers=ds)
    (d / 'result.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    # ---- РЕЗУЛЬТАТ.md
    short = [] if os.environ.get('BOT_BRIEF_OLD') else brief(rows, base_rows, base_dir, flags,
                          comparable=same_bot is True and bool(data_now) and bool(data_base) and not changed)
    Lr = [f'# Боты по всем уровням: {d.name}', ''] + short + ['', '## Полный отчёт', '',

          f'Код `{(meta or {}).get("git", "?")[:10]}`{" (есть незакоммиченные правки viewer/tools/tests)" if (meta or {}).get("dirty") else ""}, '
          f'данные `{(meta or {}).get("data", "?")}`{", флаги сборки: " + meta["cflags"] if (meta or {}).get("cflags") else ""}. '
          f'База сравнения: {("`" + rel(base_dir) + "`") if B else "нет (первый прогон или база не отмечена)"}. '
          'Хэши бинарников и данных: `MANIFEST.tsv`. Это наблюдения ботов на процессоре Мака, не приёмка: ощущение принимает Роб на PSP.', '']
    if B:
        Lr += [('С базой бинарник ботов ' + ('тот же' if same_bot else 'другой (сравнение условное: изменился сам бот или код игры)') if same_bot is not None else 'Хэш бинарника базы неизвестен')
               + ('; изменились данные: ' + ', '.join(changed[:8]) if changed else '; данные уровней те же') + '.', '']
    Lr += ['## Флаги', '']
    Lr += [f'- **{FAM_RU.get(x["fam"], x["fam"])}** ({x["fam"]}), {x["level"]}: {x["why"]}' + (f'; места: {", ".join(x["new"])}' if x.get('new') else '') for x in flags] or (['- нет: ни одно семейство не хуже базы'] if B else ['- базы нет; новых ухудшений пока определить нельзя'])
    Lr += ['', '## Покрытие: риск × уровень', '', 'В клетке: случаев / рисков (fail — проверка не смогла пройти). «—» — не покрыто на этом уровне.', '',
           '| Риск | ' + ' | '.join(levels) + ' |', '|---|' + '---|' * len(levels)]
    for title, fams in RISKS:
        cells = []
        for lv in levels:
            c = sum(S[(f, lv)]['cases'] for f in fams if (f, lv) in S); r = sum(S[(f, lv)]['risk'] for f in fams if (f, lv) in S)
            fl = sum(S[(f, lv)]['fail'] for f in fams if (f, lv) in S)
            if fams == ['determinism']:
                x = DET.get(lv); cells.append('—' if not x else ('совпал' if x['ok'] else '**разошёлся**')); continue
            if fams == ['perf']:
                p = P.get(lv); cells.append('—' if not p else f'p99 {p["p99"]:.0f} мкс'); continue
            flag = any(x['level'] == lv and x['fam'] in fams for x in flags)
            cells.append('—' if not c else (f'{c} / {r}' + (f' / fail {fl}' if fl else '')) + (' ⚑' if flag else ''))
        Lr.append(f'| {title} | ' + ' | '.join(cells) + ' |')
    Lr += ['', '## Семейства по уровням (с базой)', '', '| Семейство | Уровень | Случаев | Рисков | fail | База: рисков/случаев |', '|---|---|---|---|---|---|']
    for (fam, lv), s in sorted(S.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        b = B.get((fam, lv))
        Lr.append(f'| {FAM_RU.get(fam, fam)} | {lv} | {s["cases"]} | {s["risk"]} | {s["fail"]} | {(str(b["risk"] + b["fail"]) + "/" + str(b["cases"])) if b else "—"} |')
    Lr += ['', '## Топ случаев по семействам (первые 3 места; повтор — команда из корня проекта)', '']
    by = collections.defaultdict(list)
    for r in rows:
        if r['verdict'] in ('risk', 'fail'):
            by[r['fam']].append(r)
    for fam in sorted(by, key=lambda f: -len(by[f])):
        rs = by[fam]; seen = collections.Counter(cluster(r) for r in rs); shown = set()
        Lr.append(f'- **{FAM_RU.get(fam, fam)}** ({fam}): {len(rs)} случаев, мест {len(seen)}')
        for r in sorted(rs, key=lambda r: -seen[cluster(r)]):
            k = cluster(r)
            if k in shown:
                continue
            shown.add(k)
            Lr.append(f'  - {r["level"]} {r["place"]} ({float(r["x"]):.0f}, {float(r["y"]):.0f}, {float(r["z"]):.0f}) объект {r["obj"]} ×{seen[k]}: {r["metrics"][:220]}')
            Lr.append(f'    повтор: `{r["repro"]}`' + (f' (кадр {r["frame"]})' if r['id'].startswith('progress:') else ''))
            if len(shown) >= 3:
                break
    Lr += ['', '## Досье непроезжаемых мест', '',
           'Риски сохранены как наблюдения; известные причины помечены отдельно от гипотез. Одна строка риска не доказывает дефект игры.', '']
    for x in ds[:20]:
        place = x['level'] + (' (место не определено)' if x['place']=='--' else ' ' + x['place'])
        Lr += [f'### {place}: {FAM_RU.get(x["family"], x["family"])}', '',
               f'Наблюдение ({x["verdict"]}): {x["observed"]}. Повторов {x["count"]}, задач {x["seeds"]}; '
               f'объект `{x["object"]}`, кадр {x["frame"]}, xyz {x["position"]}', '',
               (f'Известная причина: {x["known"]["cause"]}. {x["known"]["status"]}. Источник: {x["known"]["evidence"]}'
                if x['known'] else f'Гипотеза: {x["hypothesis"]}'), f'Проверить: {x["verify"]}',
               f'Повтор: `{x["repro"]}`', '']
    if len(ds)>20:
        Lr.append(f'Ещё досье {len(ds)-20}: полный список в result.json → dossiers')
    if not ds:
        Lr.append('Таких наблюдений нет в выполненных проверках')
    Lr += ['', '## Длинный мир и прохождение', '']
    for r in rows:
        if r['fam'] == 'long_world' and not r['job'].startswith('determinism'):
            kv = dict(x.split('=', 1) for x in r['metrics'].split() if '=' in x)
            Lr.append(f'- {r["level"]} {r["job"]}: отрезков {kv.get("legs")}, доехал {kv.get("reached")}, RESET {kv.get("resets")}, вмешательств теста {kv.get("rescues")}, '
                      f'игры {kv.get("game_s")} с, {kv.get("km")} км, провалов {kv.get("falls")}, невидимых стен {kv.get("invisible")}, в воздухе {kv.get("air_walls")}, '
                      f'камера-заменитель: глаз за стеной {kv.get("cam_eye_wall")}, зажата {kv.get("cam_squeezed")}, камер прыжков {kv.get("jump_cams")}; отпечаток мира {kv.get("hash")}')
    Lr += ['', 'Что значат вердикты: ok — норма прошла; risk — найден известный риск (переворот, крен внутрь, невидимая стена…); info — наблюдение без нормы '
           '(застрял бот, забор данных без рисунка, камера-заменитель); fail — проверка не смогла пройти (нет данных/точек на уровне). '
           '«Вмешательство теста» (новая машина вместо разбитой, перенос из ловушки на дорогу) отмечено в случаях и не выдаётся за игру.']
    (d / 'РЕЗУЛЬТАТ.md').write_text('\n'.join(Lr) + '\n')
    return d / 'РЕЗУЛЬТАТ.md', flags


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--levels', default='1,2,3,4,5,6,7')
    ap.add_argument('--modes', default=','.join(MODES))
    ap.add_argument('--night', action='store_true', help='ночной объём: 8 seed прохождения, втрое больше мест и машин')
    ap.add_argument('--until', default='07:00')
    ap.add_argument('--max-rounds', type=int, default=200, help='ночь: не больше стольких кругов')
    ap.add_argument('--procs', type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument('--data', default=None, help='папка build/ с уровнями (по умолчанию — своя или основного дерева)')
    ap.add_argument('--baseline', default=None)
    ap.add_argument('--set-baseline', action='store_true')
    ap.add_argument('--cflags', default='', help='флаги сборки ботов (отрицательный контроль прежним поведением игры)')
    ap.add_argument('--report', default=None, help='только пересобрать отчёт готового прогона')
    a = ap.parse_args()
    base = Path(a.baseline) if a.baseline else (ROOT / BASEFILE.read_text().strip() if BASEFILE.exists() else None)
    if a.night and not a.baseline:   # ночь сравнивается с прошлой ночью (тот же объём), короткий прогон — с отмеченной базой
        prev = sorted(p.parent for p in OUTS.glob('*-night/result.json'))
        base = prev[-1] if prev else base
    if a.report:
        p, flags = report(a.report, base); print(p); return 0
    a.modes = [m.strip() for m in a.modes.split(',') if m.strip()]
    levels = [int(x) for x in a.levels.split(',')]
    OUTS.mkdir(parents=True, exist_ok=True)
    lockf = (OUTS / 'allrisk.lock').open('a')
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('прогон ботов уже идёт (build/bots/allrisk/allrisk.lock) — второй не запускаю'); return 1
    R = Run(a)
    log(f'боты по всем уровням → {rel(R.dir)}; данные {R.D}; уровни {levels}; процессов {a.procs}' + (f'; до {R.deadline:%d.%m %H:%M}' if R.deadline else ''))
    bad = build(R.bin, a.cflags)
    if bad:
        for k, v in bad.items():
            log(f'  сборка {k} не удалась: {v}')
    R.manifest(levels)
    def interrupted(*_):
        R.stop = 'остановлен вручную'
    signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGHUP, interrupted)
    rnd = 1
    try:
        while True:
            jobs = [j for j in R.jobs(levels, rnd) if not (j.get('cmd') and Path(j['cmd'][0]).name in bad)]
            log(f'круг {rnd}: задач {len(jobs)}')
            with cf.ThreadPoolExecutor(a.procs) as ex:
                futs = [ex.submit(R.run_job, j) for j in sorted(jobs, key=lambda j: -j.get('timeout', 0))]
                for f in cf.as_completed(futs):
                    f.result()
                    if R.deadline and dt.datetime.now() >= R.deadline:
                        R.stop = 'срок ' + a.until
            report(R.dir, base, R.meta)   # отчёт после каждого круга: утром он есть, даже если ночь прервали
            rnd += 1
            if not a.night or R.stop or (R.deadline and dt.datetime.now() >= R.deadline) or rnd > a.max_rounds:
                break
            if shutil.disk_usage(R.dir).free < 10 * 1024 ** 3:
                R.stop = 'свободного места меньше 10 ГБ'; break
    except KeyboardInterrupt:
        R.stop = 'остановлен вручную'
    R.status['rounds'] = rnd - 1
    R.status['finished'] = dt.datetime.now().isoformat(timespec='seconds'); R.status['stopped'] = R.stop
    (R.dir / 'status.json').write_text(json.dumps(R.status, ensure_ascii=False, indent=1))
    p, flags = report(R.dir, base, R.meta)
    if a.set_baseline and not a.cflags:
        BASEFILE.write_text(rel(R.dir) + '\n'); log(f'база: {rel(R.dir)}')
    log(f'отчёт: {rel(p)}; флагов {len(flags)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
