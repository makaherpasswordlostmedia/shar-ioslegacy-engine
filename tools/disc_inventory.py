#!/usr/bin/env python3
"""Опись всех 3D-файлов диска SHAR (*.p3d, 1328 шт.): что внутри, кто их читает в оригинале, что из них есть у порта.

Задача Роба 04.10: «Ты просканировал полностью все 3D-модели, которые есть в исходнике? Чтобы мы ничего не упустили».
Перепись миссий (tools/missions/census.py) шла от скриптов миссий; эта опись — от файлов диска.

  python3 tools/disc_inventory.py --capture [--levels "2 3 4 5 6 7"] [--jobs 4]
      ФАКТ «что читает порт»: запускает команды правил выпуска (tools/ship_files.sh --rules, как tools/ship.sh) с перехватом
      открытия файлов (sys.addaudithook через sitecustomize в PYTHONPATH) и пишет build/disc_inventory/opens.tsv:
      «правило · файл диска · кто открыл (файл:функция экспортёра)». Пакеты пишутся во временную папку и потом стираются,
      build/<пакет> не трогается (побочные файлы экспортёров — build/tmp_*, build/ui/, build/missions.shr, build/roomvis,
      build/roomcam_view — те же, что при обычном tools/ship.sh). Один экспортёр — не больше одной команды сразу (общие
      временные файлы). ~5 мин на уровень 1 и общие пакеты в 4 потока; --levels "2 3 4 5 6 7" --levels-only — ещё ~25 мин.
      Без --levels — только то, что едет на PSP сейчас (SHIP_LEVELS пуст: уровень 1 и общие пакеты). --levels — ещё
      правила l{N}/… этих уровней (в выпуск они пока не едут — в описи отдельной колонкой). Ролики: один (vuglogo) —
      p3d они читают только ради рамки меню, одинаково для всех роликов. Модули ядра (*.prx) — не запускаются (диск не читают).
  python3 tools/disc_inventory.py [--opens build/disc_inventory/opens.tsv] [--tsv build/disc_inventory/inventory.tsv]
                                  [--doc docs/ОПИСЬ_3D_ДИСКА_2026-10-04.md]
      опись: каждый .p3d диска — размер, чанки (геометрия, кожа, скелет, анимации, текстуры, камеры, локаторы, частицы, мир,
      коллизия, стейтпропы, Scrooby), ссылки оригинала (ниже), открывает ли файл экспорт пакетов выпуска (opens.tsv).

Кто читает файл в оригинале — только по уликам с диска, без догадок по имени:
  * исполняемый файл PS2 SLES_518.97: строки путей (art\\wrench.p3d, ART\\L1_TERRA.P3D, scrooby\\ingamel1.p3d…) и шаблоны
    (art\\chars\\%s_m.p3d, art\\cars\\%s.p3d, …\\cars2d\\, …\\skins2d\\, …\\scrapbook\\, %s%sloading%d.p3d, %s%slicenseP.p3d);
  * скрипты scripts/**/*.mfk (разбор tools/missions/mfk.py, комментарии отброшены): LoadP3DFile, LoadDisposableCar, BindReward,
    GagBegin/AddGagBinding (art/nis/gags), SetDynaLoadData/AddTeleportDest/StreetRacePropsLoad (art/), SetPresentationBitmap,
    AddVehicleSelectInfo; имена персонажей и машин (AddCharacter, AddNPC, AddAmbientCharacter, AddPed, AddStageVehicle…)
    -> art/chars/<имя[:6]>_m.p3d и art/cars/<имя>.p3d — по шаблонам исполняемого файла; какие скрипты грузит уровень — как
    исполняемый файл: level0N\\level.mfk, leveli.mfk, %si.mfk/%sl.mfk миссий из AddMission/AddBonusMission (+ вступления sd);
  * scripts/cars/*.con машин, которые грузит уровень: SetDriver(имя) -> модель водителя;
  * ссылки внутри самих p3d, по цепочке: ресурсы проектов Scrooby (0x18100/0x18101 -> art/frontend/scrooby/resource/…),
    списки зон в триггерах загрузки террейна (0x3000005 в lN_terra.p3d -> art/lNz*/lNr*/lNi*), локаторы машин мира (0x3000005
    тип 3 с именем машины: «rocke» в l1r3 -> art/cars/rocke_v.p3d), праздничные подмены ресурсов меню (_C/_H/_T.p3d).
  Файл без единой ссылки — «оригинал не грузит» (где искали — выше); отдельно: только демо-режим, только скрипты, которых никто
  не грузит (d1*, e3*, level-d), языковые копии, копии байт в байт, косвенные улики (имя в таблице исполняемого файла, «D»).
Что взял порт — по функции экспортёра, открывшей файл (таблица WHO): есть / часть (только частицы или точки) / мерка / нет.

Содержимое p3d — по номерам чанков (donut P3DChunk.h, GPL — только номера). Читалка — hit-and-run-web/tools/p3d.py (MIT).
"""
import argparse, hashlib, os, re, shutil, struct, subprocess, sys, tempfile, time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / 'hit-and-run-web/source/game'
ELF = ROOT / 'hit-and-run-web/source/disc/SLES_518.97'
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
sys.path.insert(0, str(ROOT / 'tools/missions'))
OUTDIR = ROOT / 'build/disc_inventory'

# ----------------------------------------------------------------------------------------------------------------------
# 1. Перехват: что открывают экспортёры пакетов выпуска
# ----------------------------------------------------------------------------------------------------------------------
HOOK = r'''
import sys, os
def _discinv():
    log, disc = os.environ.get('DISCINV_LOG'), os.environ.get('DISCINV_DISC')
    if not log or not disc: return
    tag = os.environ.get('DISCINV_TAG', '?'); disc = disc.rstrip('/') + '/'
    f = open(log, 'a', buffering=1)
    busy = [False]
    def who():
        fr = sys._getframe(2)
        while fr is not None:
            fn = fr.f_code.co_filename
            if ('/tools/' in fn or '/tests/' in fn) and not fn.endswith(('/p3d.py', 'sitecustomize.py')):
                return '%s:%s' % (os.path.relpath(fn, os.environ.get('DISCINV_ROOT', '/')), fr.f_code.co_name)
            fr = fr.f_back
        return '?'
    def hook(ev, args):
        if ev != 'open' or busy[0]: return
        p = args[0]
        if isinstance(p, int): return
        busy[0] = True
        try:
            mode, flags = args[1], args[2]
            if mode is not None and not any(c in str(mode) for c in 'r+'): return
            if mode is None and isinstance(flags, int) and (flags & 3) != os.O_RDONLY: return
            p = os.path.abspath(os.fsdecode(p))
            if not p.startswith(disc):
                p2 = os.path.realpath(p)
                if not p2.startswith(disc): return
                p = p2
            f.write('%s\t%s\t%s\n' % (tag, p[len(disc):], who()))
        except Exception:
            pass
        finally:
            busy[0] = False
    sys.addaudithook(hook)
_discinv()
del _discinv
'''


def ship_rules(levels):
    env = dict(os.environ, SHIP_LEVELS=levels)
    out = subprocess.run(['bash', str(ROOT / 'tools/ship_files.sh'), '--rules'], cwd=ROOT, env=env,
                         capture_output=True, text=True, check=True).stdout
    rules = []
    for line in out.splitlines():
        name, path, deps, cmd = [x.strip() for x in line.split('|', 3)]
        rules.append((name, path, deps, cmd))
    return rules


def capture(levels, jobs, out_tsv, levels_only=False, only=None):
    """Команды правил выпуска под перехватом open(); пакеты — во временную папку. Возвращает число строк журнала.
    levels_only — только правила l{N}/… уровней --levels (общие пакеты и уровень 1 уже сняты прежним прогоном)"""
    work = Path(tempfile.mkdtemp(prefix='discinv-'))
    (work / 'hook').mkdir()
    (work / 'hook/sitecustomize.py').write_text(HOOK)
    log = work / 'opens.raw'; log.write_text('')
    plan, skipped = [], []
    base = {r[0] for r in ship_rules('')}
    rules = [] if levels_only else ship_rules('')
    if levels.strip():
        rules += [r for r in ship_rules(levels) if r[0] not in base]
    seen_movie = False
    for name, path, deps, cmd in rules:
        if only and name not in only: continue
        if name.endswith('.prx'):
            skipped.append((name, 'модуль ядра: make, диск не читает')); continue
        if name.startswith('movies/'):
            if seen_movie:
                skipped.append((name, 'ролик: p3d читается только ради рамки меню, как у movies/vuglogo.smv')); continue
            if 'vuglogo' not in name:
                skipped.append((name, 'ролик: p3d читается только ради рамки меню, как у movies/vuglogo.smv')); continue
            seen_movie = True
        lvl = name.split('/')[0] if re.match(r'l\d/', name) else 'L1+общие'
        tmp = work / 'out' / name.replace('/', '__')
        tmp.parent.mkdir(parents=True, exist_ok=True)
        c = cmd.replace('{out}', str(tmp / Path(name).name)).replace('{outdir}', str(tmp / Path(name).parent))
        (tmp / Path(name).parent).mkdir(parents=True, exist_ok=True)
        plan.append((name, lvl, c))
    venv = ROOT / '.venv/bin'
    env0 = dict(os.environ, PYTHONPATH=str(work / 'hook') + os.pathsep + os.environ.get('PYTHONPATH', ''),
                DISCINV_LOG=str(log), DISCINV_DISC=str(GAME.resolve()), DISCINV_ROOT=str(ROOT),
                PYTHONDONTWRITEBYTECODE='1', PATH=f'{venv}{os.pathsep}{os.environ.get("PATH", "")}', VIRTUAL_ENV=str(ROOT / '.venv'))
    t0 = time.time(); running, results = [], []
    print(f'перехват: {len(plan)} команд, пропущено {len(skipped)}; пакеты -> {work}/out, журнал -> {out_tsv}', flush=True)
    queue = list(plan)
    key = lambda c: (re.search(r'tools/\S+\.(?:py|sh)', c) or re.search(r'\S+', c)).group(0)   # экспортёр команды
    while queue or running:
        while queue and len(running) < jobs:
            # один экспортёр — не больше одной команды сразу: у psp_export/collect_export/interior_export общие временные файлы
            # (public/assets/psp_sp_tmp.json, build/tmp_collect, build/tmp_interiors) — параллельно разные уровни падают
            busy_keys = {key(r[3]) for r in running}
            pick = next((i for i, q in enumerate(queue) if key(q[2]) not in busy_keys), None)
            if pick is None: break
            name, lvl, c = queue.pop(pick)
            env = dict(env0, DISCINV_TAG=name)
            lf = open(work / ('log__' + name.replace('/', '__') + '.txt'), 'w')
            p = subprocess.Popen(['bash', '-c', c], cwd=ROOT, env=env, stdout=lf, stderr=subprocess.STDOUT)
            running.append((p, name, lvl, c, time.time(), lf))
        time.sleep(0.5)
        for item in list(running):
            p, name, lvl, c, ts, lf = item
            if p.poll() is None: continue
            running.remove(item); lf.close()
            results.append((name, lvl, p.returncode, round(time.time() - ts)))
            print(f'  {"ок " if p.returncode == 0 else "СБОЙ"} {name} ({round(time.time() - ts)} с, всего {round(time.time() - t0)} с)', flush=True)
    out_tsv.parent.mkdir(parents=True, exist_ok=True)
    rows = Counter()
    for line in log.read_text(errors='replace').splitlines():
        parts = line.split('\t')
        if len(parts) == 3: rows[tuple(parts)] += 1
    lvl_of = {n: l for n, l, _ in plan}
    with open(out_tsv, 'w') as f:
        f.write('# disc_inventory --capture: правило\tуровень правила\tфайл диска (от source/game)\tкто открыл\tраз\n')
        f.write(f'# дата {subprocess.run(["date", "+%Y-%m-%d %H:%M"], capture_output=True, text=True).stdout.strip()}; '
                f'SHIP_LEVELS="" + --levels "{levels}"; команд {len(plan)}\n')
        for name, lvl, rc, sec in results:
            f.write(f'#rule\t{name}\t{lvl}\trc={rc}\t{sec}s\n')
        for name, why in skipped:
            f.write(f'#skip\t{name}\t{why}\n')
        for (tag, rel, who), n in sorted(rows.items()):
            f.write(f'{tag}\t{lvl_of.get(tag, "?")}\t{rel}\t{who}\t{n}\n')
    bad = [r for r in results if r[2] != 0]
    shutil.rmtree(work / 'out', ignore_errors=True)   # пакеты не нужны — только журнал открытий
    print(f'журнал: {len(rows)} строк, {len({r[1] for r in rows})} файлов диска; сбоев {len(bad)}: {[b[0] for b in bad]}')
    print(f'логи команд: {work}')
    return len(rows)


# ----------------------------------------------------------------------------------------------------------------------
# 2. Диск: что внутри каждого p3d
# ----------------------------------------------------------------------------------------------------------------------
from p3d import decompress, chunks, walk   # noqa: E402  (MIT)
import mfk                                  # noqa: E402

CH = {   # номер чанка -> колонка «что внутри» (donut P3DChunk.h)
    0x10000: 'геом', 0x10001: 'кожа', 0x4500: 'скелет', 0x4512: 'составной',
    0x121000: 'аним', 0x20000: 'аним-объект', 0x48A0: 'мультиконтр', 0x121202: 'мультиконтр', 0x21000: 'выражение',
    0x19000: 'текст', 0x19005: 'спрайт', 0x22000: 'шрифт',
    0x2200: 'кам', 0x3000100: 'кам-след',
    0x14000: 'лок', 0x3000005: 'лок', 0x3000006: 'триггер',
    0x15800: 'частицы', 0x17002: 'биллборд', 0x3001000: 'обломки', 0x3001001: 'частицы-мир', 0x3F0000D: 'блик',
    0x3F00000: 'мир', 0x3F00002: 'мир', 0x3F00003: 'мир', 0x3F00009: 'мир', 0x3F00010: 'мир', 0x3F0000E: 'мир',
    0x3F00008: 'мир', 0x3000000: 'забор', 0x3F00007: 'забор', 0x3000003: 'дороги', 0x3000004: 'дороги', 0x300000B: 'дороги',
    0x7010000: 'колл', 0x8020000: 'стейтпроп', 0x18000: 'scrooby', 0x2380: 'свет', 0x13000: 'свет', 0x120100: 'сцена',
    0x3000600: 'удар', 0x3000602: 'atc',
}
COLS = ['геом', 'кожа', 'скелет', 'составной', 'аним', 'аним-объект', 'мультиконтр', 'выражение', 'текст', 'спрайт', 'шрифт',
        'кам', 'кам-след', 'лок', 'триггер', 'частицы', 'биллборд', 'обломки', 'частицы-мир', 'блик', 'мир', 'забор', 'дороги',
        'колл', 'стейтпроп', 'scrooby', 'свет', 'сцена', 'удар', 'atc']


def norm(p):
    p = str(p).replace('\\', '/').strip().lower()
    while p.startswith('./'): p = p[2:]
    return re.sub(r'/+', '/', p)


def scan_disc():
    """{путь от source/game в нижнем регистре: dict(size, raw, cnt Counter колонок, refs [(chunk id, строка)], err)}"""
    files = {}
    for path in sorted(GAME.rglob('*')):
        if not path.is_file() or path.suffix.lower() != '.p3d': continue
        rel = norm(path.relative_to(GAME))
        d = dict(path=path, size=path.stat().st_size, raw=0, cnt=Counter(), refs=[], err='', carstarts=[])
        try:
            data = path.read_bytes(); d['md5'] = hashlib.md5(data).hexdigest()
            raw = decompress(data); d['raw'] = len(raw)
            for top in chunks(raw):
                for c in walk(top):
                    if c.id == 0x7000: continue                    # история экспорта (p3dcompress x.p3d) — не ссылка
                    col = CH.get(c.id)
                    if col: d['cnt'][col] += 1
                    if c.id == 0x3000005:                          # локатор: тип 3 с именем машины — машина мира (ракетная L1)
                        try:
                            n = c.data[0]; nm = c.data[1:1 + n].split(b'\0')[0].decode('latin1').lower()
                            if struct.unpack_from('<I', c.data, 1 + n)[0] == 3: d['carstarts'].append(nm)
                        except Exception: pass
                    if b'.p3d' in c.data.lower():
                        for m in re.finditer(rb'[\x21-\x7e]+\.p3d', c.data, re.I):
                            d['refs'].append((c.id, m.group(0).decode('latin1')))
        except Exception as e:
            d['err'] = f'{type(e).__name__}: {e}'
        files[rel] = d
    return files


def content(d):
    if d['err']: return 'не читается: ' + d['err']
    c = d['cnt']
    return ' · '.join(f'{k} {c[k]}' for k in COLS if c.get(k)) or 'пусто'


def category(rel):
    """(группа как в задаче, подкатегория)"""
    if rel.startswith('art/frontend/scrooby/resource/'): return 'art/frontend', 'меню: ресурсы Scrooby (3D-сцены меню, радар, ирис)'
    if rel.startswith('art/frontend/scrooby/'): return 'art/frontend', 'меню: проекты Scrooby (экраны)'
    if rel.startswith('art/frontend/dynaload/cars/'): return 'art/frontend', 'меню: машины 3D (будка, награды)'
    m = re.match(r'art/frontend/dynaload/images/(msnicons|cars2d|skins2d|scrapbook|license|loading)/', rel)
    if m:
        return 'art/frontend', {'msnicons': 'картинки: значки заданий (HUD)', 'cars2d': 'картинки: машины 2D (альбом, награды)',
                                'skins2d': 'картинки: костюмы 2D (альбом)', 'scrapbook': 'картинки: альбом миссий',
                                'license': 'картинки: лицензия', 'loading': 'картинки: газеты загрузки'}[m.group(1)]
    if rel.startswith('art/frontend/dynaload/images/'): return 'art/frontend', 'картинки: брифинги и прочие'
    if rel.startswith('art/missions/generic/'): return 'art/missions', 'миссии: общие (generic)'
    m = re.match(r'art/missions/level0(\d)/', rel)
    if m: return 'art/missions', f'миссии: уровень {m.group(1)}'
    if rel.startswith('art/nis/'): return 'art/nis', 'гэги (NIS)'
    if rel.startswith('art/chars/'):
        b = rel.rsplit('/', 1)[1]
        if b.endswith(('_electrocuted.p3d', '_kickwave.p3d')): return 'art/chars', 'персонажи: эффекты (удар током, пинок)'
        if b.endswith('_a.p3d'): return 'art/chars', 'персонажи: анимации'
        if b.endswith('_m.p3d'): return 'art/chars', 'персонажи: модели'
        return 'art/chars', 'персонажи: общие'
    if rel.startswith('art/cars/'): return 'art/cars', 'машины'
    b = rel.rsplit('/', 1)[-1]
    if re.match(r'l\d_terra\.p3d$', b): return 'уровни (art/lN*)', 'мир: террейн уровня'
    if re.match(r'l\d[zr]\d', b): return 'уровни (art/lN*)', 'мир: зоны z и участки r'
    if re.match(r'l\di\d', b): return 'уровни (art/lN*)', 'мир: комнаты (интерьеры)'
    if re.match(r'l\d_sr\dp\.p3d$', b) or b == 'l1m7door.p3d': return 'уровни (art/lN*)', 'пропы уличных гонок'
    if re.match(r'l0\d_fx\.p3d$', b): return 'уровни (art/lN*)', 'эффекты уровня (l0N_fx)'
    if re.match(r'b0\d', b): return 'мини-игра (art/b0*)', 'трассы мини-игры'
    return 'прочее', 'прочее (wrench, cards, камеры, atc, snapshot)'


# ----------------------------------------------------------------------------------------------------------------------
# 3. Оригинал: кто читает каждый файл (улики)
# ----------------------------------------------------------------------------------------------------------------------
LANGS = ('french', 'german', 'spanish')


class Refs:
    """ссылки оригинала: rel -> [(scope, источник, что)], scope: L1..L7 | all (любой уровень) | fe (меню вне уровня) |
    mini (мини-игра) | demo (демо-режим) | lang (языковые копии fr/de/es) | none (скрипт, который ничто не грузит)"""
    def __init__(self, files):
        self.files = files
        self.r = defaultdict(list)
        self.missing = defaultdict(list)      # ссылка на файл, которого на диске нет
        self.weak, self.dup = {}, {}          # косвенные улики; копии байт в байт

    def add(self, rel, scope, src, what):
        rel = norm(rel)
        if rel in self.files:
            if (scope, src, what) not in self.r[rel]: self.r[rel].append((scope, src, what))
            return True
        self.missing[rel].append((scope, src, what))
        return False

    # -- имена -> файлы по шаблонам исполняемого файла (art\\chars\\%s_m.p3d, art\\chars\\%s_a.p3d, art\\chars\\%s.cho,
    #    art\\cars\\%s.p3d). Имена моделей персонажей на диске — первые 6 букв (grandpa -> grandp_m, milhouse -> milhou_m)
    def char(self, name, scope, src, what, rig=None):
        n = norm(name)
        if not n or n in ('none', 'null', 'current', ''): return
        for stem in dict.fromkeys([n, n[:6]]):
            if f'art/chars/{stem}_m.p3d' in self.files: break
        self.add(f'art/chars/{stem}_m.p3d', scope, src, what)
        if rig: self.add(f'art/chars/{norm(rig)}_a.p3d', scope, src, what + ' (риг)')

    def car(self, name, scope, src, what):
        n = norm(name)
        if not n or n in ('current', 'null', 'none', 'default'): return False
        return self.add(f'art/cars/{n}.p3d', scope, src, what)


# что грузит уровень: исполняемый файл — scripts\\missions\\level0%d\\{level,leveli}.mfk, %si.mfk/%sl.mfk миссий,
# demo.mfk/demoi.mfk (демо-режим), scripts\\missions\\rewards.mfk, scripts\\ss.mfk/ssi.mfk (мини-игра)
CHAR_OPS = {'AddNPC': 0, 'AddAmbientCharacter': 0, 'AddStageCharacter': 0, 'AddPed': 0, 'AddDriver': 0, 'SetCharacterToHide': 0,
            'AddNPCCharacterBonusMission': 0, 'AddBonusMissionNPCWaypoint': 0, 'AddObjectiveNPCWaypoint': 0,
            'AddAmbientNPCWaypoint': 0, 'AddPurchaseCarReward': 1}
RIG_ARG = {'AddNPCCharacterBonusMission': 1, 'AddPurchaseCarReward': 2}
CAR_OPS = {'AddStageVehicle': 0, 'InitLevelPlayerVehicle': 0, 'AddTrafficModel': 0, 'CreateChaseManager': 0, 'ActivateVehicle': 0}
PATH_BASE = {'GagBegin': 'art/nis/gags/', 'AddGagBinding': 'art/nis/gags/', 'SetDynaLoadData': 'art/', 'AddTeleportDest': 'art/',
             'StreetRacePropsLoad': 'art/'}
SKIP_PATH_OPS = {'StreetRacePropsUnload'}


def level_scripts(lv):
    """{имя файла: scope} скриптов папки level0N: что грузит уровень, демо, и чего не грузит никто (по имени)"""
    d = GAME / f'scripts/missions/level{lv:02d}'
    names = {f.name.lower(): f for f in d.glob('*.mfk')}
    loaded = {'level.mfk', 'leveli.mfk'}
    for fn in ('level.mfk', 'leveli.mfk'):
        if fn not in names: continue
        calls, _ = mfk.parse_file(names[fn])
        for c in calls:
            if c.op in ('AddMission', 'AddBonusMission') and c.args:
                m = norm(c.args[0])
                loaded |= {f'{m}i.mfk', f'{m}l.mfk', f'{m}sdi.mfk', f'{m}sdl.mfk'}
    out = {}
    for n, f in sorted(names.items()):
        out[n] = (f, f'L{lv}' if n in loaded else ('demo' if n in ('demo.mfk', 'demoi.mfk') else 'none'))
    return out


def elf_strings():
    b = ELF.read_bytes()
    return [m.group(0).decode('latin1') for m in re.finditer(rb'[\x20-\x7e]{3,}', b)]


def collect_refs(files):
    R = Refs(files)
    # ---- исполняемый файл
    S = elf_strings()
    sset = set(S)
    for s in S:
        low = norm(s)
        if not low.endswith('.p3d') or not low.startswith('art'): continue
        if '%' in low: continue
        m = re.match(r'art/l(\d)_(terra|inter)\.p3d$', low)
        m2 = re.match(r'art/frontend/scrooby/ingamel(\d)\.p3d$', low)
        m3 = re.match(r'art/frontend/dynaload/images/mis0(\d)_08\.p3d$', low)
        if m: scope = f'L{m.group(1)}'
        elif m2: scope = f'L{m2.group(1)}'
        elif m3: scope = f'L{m3.group(1)}'
        elif re.match(r'art/b0\d\.p3d$', low) or low.endswith('scrooby/minigame.p3d'): scope = 'mini'
        elif re.search(r'scrooby/(bootup|frontend|backend|language)\.p3d$', low): scope = 'fe'
        else: scope = 'all'
        R.add(low, scope, 'SLES_518.97', f'строка «{s}»')
    if 'art\\B0%ddata.p3d' in sset:
        for i in range(8): R.add(f'art/b0{i}data.p3d', 'mini', 'SLES_518.97', 'шаблон «art\\B0%ddata.p3d»')
    if '%s%slicenseP.p3d' in sset:
        R.add('art/frontend/dynaload/images/license/licensep.p3d', 'fe', 'SLES_518.97', 'шаблон «%s%slicenseP.p3d» (+ license\\)')
        for lg in LANGS:
            R.add(f'art/frontend/dynaload/images/license/{lg}/licensep.p3d', 'lang', 'SLES_518.97', f'шаблон «%s%slicenseP.p3d», язык {lg}')
    if '%s%sloading%d.p3d' in sset:
        for i in range(1, 8):
            R.add(f'art/frontend/dynaload/images/loading/loading{i}.p3d', f'L{i}', 'SLES_518.97',
                  f'шаблон «%s%sloading%d.p3d» (газета уровня {i})')
            for lg in LANGS:
                R.add(f'art/frontend/dynaload/images/loading/{lg}/loading{i}.p3d', 'lang', 'SLES_518.97', f'шаблон «%s%sloading%d.p3d», язык {lg}')
    scrap = 'art\\frontend\\dynaload\\images\\scrapbook\\' in sset and '%smis%02d_%02d.p3d' in sset
    # rig sets: строки «npd art\\chars\\global.p3d … nps ndr art\\chars\\%s_m.p3d … art\\chars\\%s_a.p3d … art\\chars\\%s.cho»
    for rig in ('npd', 'nps', 'ndr'):
        if rig in sset:
            for suf in ('_a.p3d', '_m.p3d'):
                R.add(f'art/chars/{rig}{suf}', 'all', 'SLES_518.97', f'риг «{rig}» рядом с «art\\chars\\global.p3d» и шаблонами art\\chars\\%s_m/_a.p3d')

    # ---- скрипты
    cars_by_scope = defaultdict(set)
    rewards = []   # (имя, путь, вид, уровень)

    def scan_calls(calls, scope, srcname):
        gag_interior = None
        for i, c in enumerate(calls):
            src = f'{srcname}:{c.line}'
            what = c.op
            if c.op == 'GagBegin':
                gag_interior = None
                for c2 in calls[i + 1:i + 40]:
                    if c2.op == 'GagEnd': break
                    if c2.op == 'GagSetInterior' and c2.args: gag_interior = str(c2.args[0])
                if gag_interior: what = f'GagBegin (в комнате {gag_interior})'
                else: what = 'GagBegin (на улице)'
            if c.op not in SKIP_PATH_OPS:
                for a in c.args:
                    if not isinstance(a, str) or '.p3d' not in a.lower(): continue
                    for part in re.split(r'[;,\s]+', a):
                        if not part.lower().endswith('.p3d'): continue
                        p = norm(part)
                        if '/' not in p: p = PATH_BASE.get(c.op, 'art/') + p
                        R.add(p, scope, src, what)
                        if p.startswith('art/cars/'): cars_by_scope[scope].add(p.rsplit('/', 1)[1][:-4])
            if c.op == 'AddCharacter' and c.args:
                R.char(c.args[0], scope, src, 'AddCharacter (игрок уровня)')
                if len(c.args) > 1:
                    R.add(f'art/chars/{norm(c.args[1])}_a.p3d', scope, src, 'AddCharacter (клипы игрока)')
            if c.op in CHAR_OPS and len(c.args) > CHAR_OPS[c.op]:
                rig = c.args[RIG_ARG[c.op]] if c.op in RIG_ARG and len(c.args) > RIG_ARG[c.op] else None
                R.char(c.args[CHAR_OPS[c.op]], scope, src, c.op, rig=rig)
            if c.op == 'AddStageVehicle' and len(c.args) > 4 and str(c.args[4]).strip():
                R.char(c.args[4], scope, src, 'AddStageVehicle (водитель)')
            if c.op in CAR_OPS and len(c.args) > CAR_OPS[c.op]:
                if R.car(c.args[CAR_OPS[c.op]], scope, src, c.op): cars_by_scope[scope].add(norm(c.args[CAR_OPS[c.op]]))
            if c.op == 'AddVehicleSelectInfo' and len(c.args) >= 2:   # машины персонажей в будке (PhoneBooth): 2D и 3D превью
                n = norm(c.args[1])
                if 'art\\frontend\\dynaload\\cars\\' in sset:
                    R.add(f'art/frontend/dynaload/cars/{n}.p3d', scope, src, f'AddVehicleSelectInfo + «art\\frontend\\dynaload\\cars\\» (будка)')
                if 'art\\frontend\\dynaload\\images\\cars2D\\' in sset:
                    R.add(f'art/frontend/dynaload/images/cars2d/{n}.p3d', scope, src, f'AddVehicleSelectInfo + «…\\images\\cars2D\\» (будка)')
                if len(c.args) > 2: R.char(c.args[2], scope, src, 'AddVehicleSelectInfo (водитель)')

    for lv in range(1, 8):
        for n, (f, scope) in level_scripts(lv).items():
            calls, _ = mfk.parse_file(f)
            scan_calls(calls, scope, f'level{lv:02d}/{n}')
    rw = GAME / 'scripts/missions/rewards.mfk'
    calls, _ = mfk.parse_file(rw)
    scan_calls([c for c in calls if c.op != 'BindReward'], 'all', 'rewards.mfk')
    for c in calls:   # награды: BindReward(имя, путь, car|skin, вид, уровень, …) — уровень награды и есть scope
        if c.op == 'BindReward' and len(c.args) >= 5:
            rewards.append((norm(c.args[0]), norm(c.args[1]), norm(c.args[2]), c.args[4] if isinstance(c.args[4], int) else 0, c.line))
    for name, path, kind, lv, line in rewards:
        sc = f'L{lv}' if 1 <= lv <= 7 else 'all'
        R.add(path, sc, f'rewards.mfk:{line}', f'BindReward {kind} уровня {lv}')
        if kind == 'car':
            cars_by_scope[sc].add(name)
            if 'art\\frontend\\dynaload\\cars\\' in sset:
                R.add(f'art/frontend/dynaload/cars/{name}.p3d', sc, 'SLES_518.97 + rewards.mfk', f'«art\\frontend\\dynaload\\cars\\» + награда {name} (будка, экран наград)')
            if 'art\\frontend\\dynaload\\images\\cars2d\\' in sset:
                R.add(f'art/frontend/dynaload/images/cars2d/{name}.p3d', sc, 'SLES_518.97 + rewards.mfk', f'«…\\images\\cars2d\\» + награда {name} (альбом, экран наград)')
        if kind == 'skin' and 'art\\frontend\\dynaload\\images\\skins2d\\' in sset:
            R.add(f'art/frontend/dynaload/images/skins2d/{name}.p3d', sc, 'SLES_518.97 + rewards.mfk', f'«…\\images\\skins2d\\» + костюм {name} (альбом)')
    for f in ('ss.mfk', 'ssi.mfk'):
        calls, _ = mfk.parse_file(GAME / 'scripts' / f)
        scan_calls(calls, 'mini', f)
    for f in sorted((GAME / 'scripts/missions').glob('*.mfk')):
        if f.name.lower() in ('rewards.mfk',): continue
        calls, _ = mfk.parse_file(f)
        scan_calls(calls, 'none', f.name.lower())          # e3rwrds.mfk — исполняемый файл его не называет
    if scrap:
        for lv in range(1, 8):
            for ms in range(0, 10):
                R.add(f'art/frontend/dynaload/images/scrapbook/mis{lv:02d}_{ms:02d}.p3d', f'L{lv}', 'SLES_518.97',
                      'шаблон «%smis%02d_%02d.p3d» + «…\\images\\scrapbook\\» (альбом миссий в меню)')

    # ---- машины уровня -> scripts/cars/<имя>.con: SetDriver(имя) -> модель водителя
    for scope, names in list(cars_by_scope.items()):
        for n in sorted(names):
            con = GAME / f'scripts/cars/{n}.con'
            if not con.exists():
                cands = [p for p in (GAME / 'scripts/cars').glob('*.con') if p.name.lower() == f'{n}.con']
                if not cands: continue
                con = cands[0]
            calls, _ = mfk.parse_file(con)
            for c in calls:
                if c.op == 'SetDriver' and c.args and norm(c.args[0]) not in ('none', ''):
                    R.char(c.args[0], scope, f'cars/{con.name}:{c.line}', f'SetDriver (водитель {n})')

    # ---- ссылки внутри p3d: ресурсы Scrooby, списки зон террейна; передаются по цепочке (scope файла-источника)
    changed = True
    while changed:
        changed = False
        for rel, d in files.items():
            scopes = {s for s, _, _ in R.r.get(rel, [])}
            if not scopes: continue
            for nm in d['carstarts']:
                cands = [nm] if (nm and f'art/cars/{nm}.p3d' in files) else ([nm + '_v'] if f'art/cars/{nm}_v.p3d' in files else [])
                for car in cands:
                    for sc in scopes:
                        key = (sc, rel, f'локатор машины «{nm}» (тип 3) в {rel.rsplit("/", 1)[1]}')
                        if key not in R.r[f'art/cars/{car}.p3d']:
                            R.r[f'art/cars/{car}.p3d'].append(key); changed = True
            if not d['refs']: continue
            base = rel.rsplit('/', 1)[0] + '/'
            for cid, s in d['refs']:
                for part in re.split(r'[;:$@,]+', s):
                    if not part.lower().endswith('.p3d'): continue
                    p = norm(part)
                    if rel.startswith('art/frontend/scrooby/'): cand = 'art/frontend/scrooby/resource/' + p
                    elif '/' in p: cand = p
                    else: cand = base + p
                    if cand not in files and ('art/' + p) in files: cand = 'art/' + p
                    for sc in scopes:
                        key = (sc, rel, f'внутри {rel.rsplit("/", 1)[1]} (чанк 0x{cid:X})')
                        if cand in files and key not in R.r[cand]:
                            R.r[cand].append(key); changed = True
                        elif cand not in files:
                            R.missing[cand].append(key)
        # праздничные подмены ресурсов меню: «Replacing normal P3D file w/ special holidays file:», суффиксы _C/_H/_T
        if 'Replacing normal P3D file w/ special holidays file:' in sset and {'_C.p3d', '_H.p3d', '_T.p3d'} <= sset:
            for rel in list(files):
                m = re.match(r'(art/frontend/scrooby/resource/pure3d/.+)_([cht])\.p3d$', rel)
                if not m or R.r.get(rel): continue
                basef = m.group(1) + '.p3d'
                for sc in {x for x, _, _ in R.r.get(basef, [])}:
                    R.r[rel].append((sc, 'SLES_518.97', f'праздничная подмена {basef.rsplit("/", 1)[1]} по дате приставки '
                                     f'(строки «Replacing normal P3D file w/ special holidays file:», «_{m.group(2).upper()}.p3d»)'))
                    changed = True

    # копии байт в байт файлов, на которые ссылки есть (images/loadingN = images/loading/loadingN)
    by_md5 = defaultdict(list)
    for rel, d in files.items(): by_md5[d.get('md5')].append(rel)
    for rel, d in files.items():
        if R.r.get(rel): continue
        twins = [x for x in by_md5[d.get('md5')] if x != rel and R.r.get(x)]
        if twins: R.dup[rel] = twins[0]
    # косвенные улики для файлов без прямой ссылки: имя в таблицах исполняемого файла, вариант «D» картинки машины
    low = {x.lower() for x in S}
    for rel in files:
        if R.r.get(rel): continue
        b = rel.split('/')[-1][:-4]
        if rel.startswith('art/frontend/dynaload/images/cars2d/') and b.endswith('d') and R.r.get(rel[:-5] + '.p3d'):
            R.weak[rel] = (f'вариант «D» картинки {b[:-1]} (внутри {b[:-1]}D.png); шаблона с «D» в исполняемом файле нет — '
                           'вероятно, «закрытая» машина на экране наград/в альбоме', {x for x, _, _ in R.r[rel[:-5] + '.p3d']})
            continue
        stems = {b, re.sub(r'_[ma]$', '', b)}
        hit = sorted(x for x in stems if x in low and len(x) > 3)
        if hit:
            R.weak[rel] = (f'имя «{hit[0]}» есть в таблице имён исполняемого файла, но ни шаблон пути, ни скрипт его не грузят', set())
    return R


SCOPE_ORDER = ['L1', 'all', 'fe', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7', 'mini', 'demo', 'lang', 'none']


def scopes_of(R, rel):
    return sorted({s for s, _, _ in R.r.get(rel, [])}, key=SCOPE_ORDER.index)


def used_l1(sc): return bool({'L1', 'all', 'fe'} & set(sc))


# ----------------------------------------------------------------------------------------------------------------------
# 4. Порт: что открывают экспортёры (opens*.tsv) — и какую часть берут
# ----------------------------------------------------------------------------------------------------------------------
# кто открыл -> (вид/часть/данные/мерка, что берёт). «вид» — содержимое едет в пакете (модель, текстура, анимация, картинка,
# камера); «часть» — из файла взяты только частицы/их текстуры (сцена, модель, анимация — нет); «данные» — позиции, триггеры,
# пути, свет, тексты (видимого содержимого файла в пакете нет); «мерка» — файл только осмотрен (размер, есть ли кожа, где лежит
# эффект), в пакет из него ничего не идёт
WHO = {
    'hit-and-run-web/tools/convert.py:export': ('вид', 'геометрия и текстуры (конвертер)'),
    'tools/char_export.py:export': ('вид', 'модель и клипы персонажа'),
    'tools/homer_export.py:load_needed': ('вид', 'клипы игрока'),
    'tools/msnart_export.py:export_file': ('вид', 'модели/значки миссии (msnart)'),
    'tools/msnart_export.py:export_race_props': ('вид', 'пропы гонки: меш и заборы'),
    'tools/psp_export.py:main': ('вид', 'мир уровня'), 'tools/psp_export.py:<lambda>': ('вид', 'мир уровня (небо)'),
    'tools/psp_export.py:car_export': ('вид', 'машина игрока'), 'tools/psp_export.py:prop_entities': ('вид', 'пропы'),
    'tools/fx_export.py:parse_file': ('часть', 'только частицы'), 'tools/fx_pack.py:file_tex': ('часть', 'только текстуры частиц'),
    'tools/traffic_export.py:car_model': ('вид', 'модель машины'), 'tools/traffic_export.py:ped_blob': ('вид', 'модель пешехода'),
    'tools/collect_export.py:base': ('вид', 'гэг/карточка/оса'), 'tools/collect_export.py:gag_type': ('вид', 'гэг'),
    'tools/collect_export.py:card_type': ('вид', 'карточка'), 'tools/collect_export.py:wasp_type': ('вид', 'оса'),
    'tools/collect_export.py:model': ('вид', 'модель предмета'), 'tools/collect_export.py:actor_type': ('вид', 'летающий актёр'),
    'tools/frontend3d_export.py:<dictcomp>': ('вид', 'сцена меню 3D'),
    'tools/load_export.py:sprite_images': ('вид', 'картинка экрана'), 'tools/load_export.py:fe_anim': ('вид', 'анимация экрана'),
    'tools/ui_export.py:__init__': ('вид', 'экраны Scrooby'), 'tools/ui_export.py:bake_radar_map': ('вид', 'карта радара'),
    'tools/iris_export.py:parse': ('вид', 'ирис переходов'), 'tools/interior_export.py:main': ('вид', 'комната'),
    'tools/shop_export.py:reward_scene': ('вид', 'подиум награды'), 'tools/bootmarks.py:rgba_sources': ('вид', 'знаки заставки'),
    'tools/prp2_export.py:_add_breakables': ('вид', 'обломки'), 'tools/prp2_export.py:_add_stateprop': ('вид', 'стейтпроп'),
    'tools/prp2_export.py:add_wrenches': ('вид', 'гаечные ключи'), 'tools/prp2_export.py:_scan': ('вид', 'анимированные пропы'),
    'tools/animobj_export.py:_scan': ('вид', 'анимированные объекты'),
    'tools/msncam_export.py:frames': ('вид', 'камера старта миссии'), 'tools/interior_export.py:room_cams': ('вид', 'камеры зон'),
    'tools/missions/p3dlocs.py:read_locators': ('данные', 'локаторы миссий'),
    'tools/collect_export.py:all_locators': ('данные', 'локаторы'), 'tools/interior_export.py:locators': ('данные', 'локаторы'),
    'tools/interior_export.py:light_group': ('данные', 'свет'), 'tools/level_light.py:group_light': ('данные', 'свет'),
    'tools/sound_export.py:locators': ('данные', 'локаторы звука'), 'tools/sound_export.py:sound_objects': ('данные', 'объекты звука'),
    'hit-and-run-web/tools/campaign.py:locators': ('данные', 'локаторы'),
    'tools/jumps_export.py:wrenches': ('данные', 'точки ключей'), 'tools/jumps_export.py:car_starts': ('данные', 'старты машин'),
    'tools/animobj_export.py:action_locators': ('данные', 'точки действий'),
    'tools/traffic_export.py:parked_spots': ('данные', 'стоянки'), 'tools/traffic_export.py:spot_masks': ('данные', 'маски стоянок'),
    'tools/traffic_export.py:road_network': ('данные', 'дороги'), 'tools/traffic_export.py:dyna_loaders': ('данные', 'загрузчики зон'),
    'tools/traffic_export.py:ped_paths_zones': ('данные', 'пути пешеходов'), 'tools/regions_export.py:dyna_sources': ('данные', 'загрузчики зон'),
    'tools/psp_export.py:atc_rows': ('данные', 'таблица ATC'), 'tools/psp_export.py:atc_mass_table': ('данные', 'таблица ATC'),
    'tools/stateprop_dump.py:atc_table': ('данные', 'таблица ATC'), 'tools/skins_export.py:spots': ('данные', 'точки гардероба'),
    'tools/missions/compile.py:bible': ('данные', 'тексты'), 'tools/ui_export.py:load_bible': ('данные', 'тексты'),
    'tools/save_export.py:bible_hash': ('данные', 'тексты'),
    'tools/ui_export.py:msnicon_images': ('мерка', 'размер значков'), 'tools/ui_export.py:objective_icon_extent': ('мерка', 'размер значков'),
    'tools/collect_export.py:has_skin': ('мерка', 'есть ли кожа'), 'tools/psp_export.py:car_measure': ('мерка', 'мерка кузова'),
    'tools/fx_export.py:mission_effect_files': ('мерка', 'поиск файла эффекта'),
}
KIND_ORDER = ['вид', 'часть', 'данные', 'мерка']


def load_opens(paths):
    """{rel: [(правило, уровень правила, кто, вид/данные/мерка, что)]}, {правило: 'rc=0 …'}, неизвестные «кто»"""
    out, rules, unknown = defaultdict(list), {}, Counter()
    for path in paths:
        p = Path(path)
        if not p.exists(): continue
        for line in p.read_text().splitlines():
            if line.startswith('#rule\t'):
                _, name, lvl, rc, sec = line.split('\t'); rules[name] = (lvl, rc, sec); continue
            if line.startswith('#'): continue
            tag, lvl, rel, who, _ = line.split('\t')
            rel = norm(rel)
            if not rel.endswith('.p3d'): continue
            kind, what = WHO.get(who, ('данные', who))
            if who not in WHO: unknown[who] += 1
            out[rel].append((tag, lvl, who, kind, what))
    return out, rules, unknown


VISIBLE = ('геом', 'кожа', 'текст', 'спрайт', 'шрифт', 'частицы', 'биллборд', 'аним', 'аним-объект', 'кам')


def port_status(opens, rel, level_filter, cnt=None):
    """-> ('есть' | 'часть' | 'мерка' | '', строки журнала). «есть» — видимое содержимое в пакете, или файл без видимого
    содержимого (локаторы, таблица ATC, тексты) взят как данные; «часть» — взяты только частицы или только точки файла,
    в котором есть модель/картинка/анимация"""
    rows = [o for o in opens.get(rel, []) if level_filter(o[1])]
    if not rows: return '', []
    kinds = {o[3] for o in rows}
    k = next(x for x in KIND_ORDER if x in kinds)
    if k == 'вид': return 'есть', rows
    if k == 'данные' and cnt is not None and not any(cnt.get(v) for v in VISIBLE): return 'есть', rows
    if k in ('часть', 'данные'): return 'часть', rows
    return 'мерка', rows


# ----------------------------------------------------------------------------------------------------------------------
# 5. Итог: строки описи, TSV, документ
# ----------------------------------------------------------------------------------------------------------------------
SCR = {'frontend': 'главное меню (3D-гостиная, альбом)', 'ingame': 'в игре: HUD, пауза, награды', 'backend': 'экраны загрузки',
       'bootup': 'заставки при включении', 'minigame': 'мини-игра', 'language': 'выбор языка (PAL)',
       **{f'ingamel{i}': f'HUD уровня {i}' for i in range(1, 8)}}


def where_txt(R, rel, scopes=None, n=3):
    """где оригинал это показывает: «L1 m3 (m3l.mfk:5 LoadP3DFile)», «исполняемый файл», «меню»"""
    out = []
    for sc, src, what in R.r.get(rel, []):
        if scopes and sc not in scopes: continue
        m = re.match(r'level0(\d)/([a-z0-9_-]+)\.mfk:(\d+)', src)
        if m:
            fn = m.group(2)
            if fn in ('level', 'leveli'): place = 'весь уровень'
            else:
                mm = re.match(r'(m\d|sr\d|gr\d|bm\d)(sd)?[il]$', fn)
                place = (mm.group(1) + (' вступление' if mm.group(2) else '')) if mm else fn
            out.append(f'L{m.group(1)} {place} ({fn}.mfk:{m.group(3)} {what})')
        elif src.startswith('rewards.mfk'): out.append(f'{what} ({src})')
        elif src.startswith('SLES_518.97'): out.append(f'исполняемый файл: {what}')
        elif src.startswith('cars/'): out.append(f'{what} ({src})')
        elif src.startswith('art/frontend/scrooby/'):
            prj = src.rsplit('/', 1)[1][:-4]
            out.append(f'{SCR.get(prj, prj)} (ресурс проекта Scrooby {prj}.p3d)')
        elif re.match(r'art/l\d_terra\.p3d$', src): out.append(f'триггер загрузки зон в {src.rsplit("/", 1)[1]}')
        else: out.append(f'{what}')
    out = list(dict.fromkeys(out))
    return '; '.join(out[:n]) + (f'; … ещё {len(out) - n}' if len(out) > n else '')


def notice(cat, cnt, rel=''):
    """насколько заметно (по виду файла и чанкам)"""
    c = cnt
    b = rel.split('/')[-1]
    if b == 'dummy.p3d': return 'невидимо: заглушка ресурса'
    if rel.startswith('art/chars/') and b.endswith('_m.p3d') and set(c) <= {'скелет'}: return 'невидимо: только скелет рига'
    if b == 'common.p3d': return 'свечение фар машин (общие биллборды)'
    if 'scrapbook/' in rel or 'skins2d/' in rel: return 'альбом в главном меню'
    if b.startswith('misxx_'): return 'картинка брифинга гонки/бонуса'
    if 'pure3d' in rel and re.search(r'_[cht]\.p3d$', b): return 'меню в праздник (по дате приставки)'
    if b.startswith('gag') and 'pure3d' in rel: return 'гэг в гостиной меню'
    if b == 'language.p3d': return 'экран выбора языка'
    if cat.startswith('мир: '): return 'видно сразу (город)'
    if cat == 'пропы уличных гонок': return 'ограждения трассы'
    if cat.startswith('персонажи: модели'): return 'персонаж в мире'
    if cat.startswith('персонажи: анимации'): return 'движения персонажа'
    if cat.startswith('персонажи: эффекты'): return 'эффект удара/пинка персонажа'
    if cat == 'машины': return 'машина в мире'
    if cat == 'гэги (NIS)': return 'гэг: сценка по действию'
    if cat.startswith('картинки: значки'): return 'значок в HUD'
    if cat.startswith('картинки'): return 'картинка на экране'
    if cat.startswith('меню'): return 'меню'
    if c.get('геом') or c.get('кожа'):
        return 'модель в мире' + (' + частицы' if c.get('частицы') else '')
    if c.get('частицы') or c.get('биллборд'): return 'эффект'
    if c.get('кам'): return 'камера (облёт/наезд)'
    if c.get('лок') or c.get('триггер'): return 'невидимо: точки/триггеры'
    return '—'


def build_rows(files, R, opens1, opens27):
    rows = []
    for rel, d in sorted(files.items()):
        grp, cat = category(rel)
        sc = scopes_of(R, rel)
        l1 = used_l1(sc)
        st1, by1 = port_status(opens1, rel, lambda lv: not lv.startswith('l'), d['cnt'])
        st27 = {}
        for lv in range(2, 8):
            st, _ = port_status(opens27, rel, lambda x, lv=lv: x == f'l{lv}', d['cnt'])
            if st: st27[lv] = st
        weak = R.weak.get(rel)
        if sc and set(sc) - {'demo', 'none'}: orig = 'грузит'
        elif sc and set(sc) <= {'demo'} | {'none'} and 'demo' in sc: orig = 'только демо-режим'
        elif sc: orig = 'только из скриптов, которые никто не грузит'
        else: orig = 'ссылок нет'
        if sc == ['lang']: orig = 'языковая копия (fr/de/es)'
        rows.append(dict(
            rel=rel, grp=grp, cat=cat, size=d['size'], content=content(d), cnt=d['cnt'], scopes=sc, l1=l1, orig=orig,
            orig_where=where_txt(R, rel), orig_where_l1=where_txt(R, rel, {'L1', 'all', 'fe'}),
            port1=st1, port1_by=[x for _, x in sorted({(KIND_ORDER.index(o[3]), f'{o[0]} ← {o[2].split("/")[-1]} ({o[4]})') for o in by1})],
            port27=st27, weak=weak, notice=notice(cat, d['cnt'], rel)))
    return rows


def write_tsv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        f.write('файл\tгруппа\tкатегория\tразмер\tчто внутри\tоригинал\tгде (уровни)\tоригинал на L1\tгде на L1\t'
                'порт L1 (выпуск)\tкто открыл\tпорт L2-7 (не в выпуске)\tкосвенная улика\n')
        for r in rows:
            f.write('\t'.join([r['rel'], r['grp'], r['cat'], str(r['size']), r['content'], r['orig'],
                               ','.join(r['scopes']) or '—', 'да' if r['l1'] else 'нет', r['orig_where_l1'],
                               r['port1'] or 'нет', '; '.join(r['port1_by']),
                               ' '.join(f'l{k}:{v}' for k, v in sorted(r['port27'].items())) or '—',
                               r['weak'][0] if r['weak'] else '']) + '\n')


def md_esc(s): return str(s).replace('|', '\\|')


def summarize(rows, key):
    agg = defaultdict(Counter)
    for r in rows:
        a = agg[key(r)]
        a['files'] += 1
        a['l1'] += r['l1']
        a['vid'] += bool(r['l1'] and r['port1'] == 'есть')
        a['data'] += bool(r['l1'] and r['port1'] == 'часть')
        a['miss'] += bool(r['l1'] and r['port1'] in ('', 'мерка'))
        a['other_lv'] += bool(not r['l1'] and r['orig'] == 'грузит')
        a['dead'] += r['orig'] != 'грузит'
        a['port_extra'] += bool(not r['l1'] and r['port1'] == 'есть')
    return agg


def md_summary(agg, title):
    out = [f'| {title} | файлов | оригинал грузит на L1 (L1, любой уровень, меню) | у порта есть | у порта только часть (частицы/точки) | '
           f'**нет у порта, хотя L1 грузит** | грузит только на L2–7 / мини-игре | оригинал не грузит вовсе* | у порта есть сверх L1 |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    tot = Counter()
    for k in sorted(agg, key=lambda k: (-agg[k]['files'], k)):
        a = agg[k]; tot.update(a)
        out.append(f"| {k} | {a['files']} | {a['l1']} | {a['vid']} | {a['data']} | {a['miss'] or ''} | {a['other_lv']} | {a['dead']} | {a['port_extra']} |")
    out.append(f"| **всего** | **{tot['files']}** | **{tot['l1']}** | **{tot['vid']}** | **{tot['data']}** | **{tot['miss']}** | "
               f"**{tot['other_lv']}** | **{tot['dead']}** | **{tot['port_extra']}** |")
    return out


def short(rel): return rel.replace('art/frontend/dynaload/images/', '…images/').replace('art/frontend/scrooby/resource/pure3d/', '…pure3d/')


def write_doc(rows, R, rules1, rules27, path):
    L = ['<!-- auto:begin — пишет tools/disc_inventory.py, правки руками ниже маркера auto:end -->', '']
    now = subprocess.run(['date', '+%Y-%m-%d %H:%M'], capture_output=True, text=True).stdout.strip()
    L.append(f'Таблицы собраны `python3 tools/disc_inventory.py` ({now}); строка на каждый файл — `build/disc_inventory/inventory.tsv`. '
             f'Перехват: {len(rules1)} команд правил выпуска уровня 1 и общих (SHIP_LEVELS пуст — это и едет на PSP), '
             f'{len(rules27)} команд правил l2…l7 (в выпуск не едут).')
    bad = sorted(n for n, (lv, rc, sec) in {**rules1, **rules27}.items() if rc != 'rc=0')
    if bad: L.append(f'**Команды перехвата со сбоем (журнал их открытий неполный): {", ".join(bad)}.**')
    L += ['', '### Сводка по группам диска', ''] + md_summary(summarize(rows, lambda r: r['grp']), 'группа')
    L += ['', '\\* «не грузит вовсе» — ни одной ссылки, или только из демо-режима / скриптов, которые исполняемый файл не грузит, '
          'или языковая копия; разбор ниже.', '', '### Сводка по категориям', ''] + md_summary(summarize(rows, lambda r: r['cat']), 'категория')

    miss = [r for r in rows if r['l1'] and r['port1'] in ('', 'мерка')]
    L += ['', f'### Чего нет у порта, хотя оригинал на L1 это грузит — {len(miss)} файлов', '',
          '| файл | что внутри | где оригинал это грузит/показывает | заметность | у порта |', '|---|---|---|---|---|']
    for r in sorted(miss, key=lambda r: (r['cat'], r['rel'])):
        L.append(f"| `{short(r['rel'])}` | {r['content']} | {md_esc(r['orig_where_l1'])} | {r['notice']} | "
                 f"{'только мерка: ' + md_esc('; '.join(r['port1_by'][:2])) if r['port1'] == 'мерка' else 'файл не открывает ни один экспорт выпуска'} |")
    data = [r for r in rows if r['l1'] and r['port1'] == 'часть']
    L += ['', f'### У порта только часть файла (частицы, точки, тексты, таблицы), основное видимое содержимое не взято — L1, {len(data)}', '',
          '| файл | что внутри | где оригинал | что берёт порт |', '|---|---|---|---|']
    for r in data:
        L.append(f"| `{short(r['rel'])}` | {r['content']} | {md_esc(r['orig_where_l1'])} | {md_esc('; '.join(r['port1_by'][:3]))} |")

    L += ['', '### Оригинал не грузит вовсе (с уликой)', '']
    groups = [('ссылок нет', 'Ни одной ссылки и ни одной косвенной улики: ни скрипты (все *.mfk и *.con, включая демо), ни исполняемый '
               'файл (строки путей, шаблоны, таблицы имён), ни ссылки внутри других p3d (Scrooby, триггеры зон, локаторы машин)'),
              ('только демо-режим', 'Только из демо-режима (demo.mfk / demoi.mfk уровней — исполняемый файл грузит их для демо, в игре — нет)'),
              ('только из скриптов, которые никто не грузит', 'Только из скриптов, которых исполняемый файл не грузит (d1*, e3*, level-d)'),
              ('языковая копия (fr/de/es)', 'Языковые копии (french/german/spanish) — грузятся только при другом языке приставки')]
    weak_rows = [r for r in rows if r['orig'] == 'ссылок нет' and r['weak']]
    if weak_rows:
        L += [f'**Без прямой ссылки, но с косвенной уликой — возможно, грузит код (не уверен): {len(weak_rows)}**', '',
              '| файл | что внутри | косвенная улика | у порта |', '|---|---|---|---|']
        dvar = [r for r in weak_rows if 'вариант «D»' in r['weak'][0]]
        if dvar:
            L.append(f"| {len(dvar)} картинок машин 2D с «D» на конце: " + ', '.join(f"`{r['rel'].split('/')[-1]}`" for r in dvar) +
                     f" | {dvar[0]['content']} | внутри картинка `<машина>D.png`; шаблона пути с «D» в исполняемом файле нет — "
                     f"вероятно, «закрытая» машина на экране наград / в альбоме | {', '.join(sorted({r['port1'] for r in dvar if r['port1']})) or '—'} |")
        for r in weak_rows:
            if r in dvar: continue
            L.append(f"| `{r['rel']}` | {r['content']} | {md_esc(r['weak'][0])} | {r['port1'] or '—'} |")
        L.append('')
    for key, title in groups:
        rs = [r for r in rows if r['orig'] == key and not (key == 'ссылок нет' and r['weak'])]
        if not rs: continue
        L += [f'**{title}: {len(rs)}**', '']
        bycat = defaultdict(list)
        for r in rs: bycat[r['cat']].append(r)
        L += ['| категория | файлы | что внутри (пример) | у порта |', '|---|---|---|---|']
        for cat, lst in sorted(bycat.items(), key=lambda x: -len(x[1])):
            dup = R.dup
            names = ', '.join(f"`{short(r['rel']).split('art/')[-1]}`" + (f" (копия `{short(dup[r['rel']])}` байт в байт)" if r['rel'] in dup else '')
                              for r in lst[:60]) + (f' … ещё {len(lst) - 60}' if len(lst) > 60 else '')
            portx = sorted({r['port1'] for r in lst if r['port1']})
            L.append(f"| {cat} ({len(lst)}) | {names} | {md_esc(lst[0]['content'])} | {', '.join(portx) or '—'} |")
        L.append('')

    L += ['### Уровни 2–7 (в выпуск не едут: SHIP_LEVELS пуст по слову Роба 01.10)', '',
          '«У порта» здесь — файл открыл экспорт правил l{N}/… (снято перехватом, пакеты во временной папке) или общий пакет выпуска '
          '(персонажи chars/*.chr и т. п.).', '',
          '| уровень | оригинал грузит на уровне | у порта есть | только часть | нет у порта | из них: категории (файлов) |', '|---|---:|---:|---:|---:|---|']
    for lv in range(2, 8):
        tag = f'L{lv}'
        rs = [r for r in rows if tag in r['scopes']]
        def st(r):
            ks = {r['port1'], r['port27'].get(lv, '')}
            return next((k for k in ('есть', 'часть', 'мерка') if k in ks), '')
        vid = sum(st(r) == 'есть' for r in rs); dat = sum(st(r) == 'часть' for r in rs)
        ms = [r for r in rs if st(r) in ('', 'мерка')]
        cats = Counter(r['cat'] for r in ms)
        L.append(f"| {lv} | {len(rs)} | {vid} | {dat} | {len(ms)} | {'; '.join(f'{k} {v}' for k, v in cats.most_common(6))} |")
    L += ['', '<!-- auto:end -->']
    text = '\n'.join(L) + '\n'
    if path.exists():
        old = path.read_text()
        if '<!-- auto:begin' in old and '<!-- auto:end -->' in old:
            a = old.index('<!-- auto:begin'); b = old.index('<!-- auto:end -->') + len('<!-- auto:end -->')
            text = old[:a] + text.rstrip('\n') + old[b:]
    else:
        text = '# Опись 3D-файлов диска (*.p3d)\n\n' + text
    path.write_text(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--capture', action='store_true'); ap.add_argument('--levels', default='')
    ap.add_argument('--levels-only', action='store_true'); ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--opens', default=None, help='журнал перехвата уровня 1 и общих (по умолчанию build/disc_inventory/opens.tsv)')
    ap.add_argument('--opens27', default=None, help='журналы правил l2…l7 через запятую (по умолчанию build/disc_inventory/opens-l2-7*.tsv)')
    ap.add_argument('--only', default='', help='--capture: только эти правила (через запятую) — повтор упавших')
    ap.add_argument('--tsv', default=str(OUTDIR / 'inventory.tsv'))
    ap.add_argument('--doc', default=None)
    a = ap.parse_args()
    if a.capture:
        capture(a.levels, a.jobs, Path(a.opens or OUTDIR / ('opens-l2-7.tsv' if a.levels_only else 'opens.tsv')), a.levels_only,
                {x.strip() for x in a.only.split(',') if x.strip()} or None)
        return
    files = scan_disc()
    R = collect_refs(files)
    o1, rules1, unk1 = load_opens([a.opens or OUTDIR / 'opens.tsv'])
    o27, rules27, unk27 = load_opens(a.opens27.split(',') if a.opens27 else sorted(OUTDIR.glob('opens-l2-7*.tsv')))
    if not rules1: sys.exit('нет журнала перехвата: сначала python3 tools/disc_inventory.py --capture')
    rows = build_rows(files, R, o1, o27)
    write_tsv(rows, Path(a.tsv))
    agg = summarize(rows, lambda r: 'всё')['всё']
    print(f"p3d на диске: {agg['files']}; оригинал грузит на L1: {agg['l1']}; у порта есть {agg['vid']}, только часть {agg['data']}, "
          f"нет {agg['miss']}; грузит только на L2–7/мини-игре {agg['other_lv']}; не грузит вовсе {agg['dead']}")
    if unk1 or unk27: print('кто открыл — не размечено в WHO (считается «данные»):', dict(unk1 + unk27))
    print(f'-> {a.tsv}')
    if a.doc:
        write_doc(rows, R, rules1, rules27, Path(a.doc)); print(f'-> {a.doc}')


if __name__ == '__main__':
    main()
