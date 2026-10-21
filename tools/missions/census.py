#!/usr/bin/env python3
"""Перепись миссий уровней 1–7: всё, что скрипты миссий ставят в мир и на экран, — и есть ли это у порта.

  python3 tools/missions/census.py [--root ДЕРЕВО] [--use имя=файл ...] [--tsv ВЫХОД.tsv] [--doc ВЫХОД.md]
                                   [--check tests/missions/census_expected.tsv] [--brief]

Источник правды — скрипты диска (hit-and-run-web/source/game/scripts/missions/levelNN, только чтение), собранные тем же
компилятором, что пакеты level0N.msn (tools/missions/compile.py: расписание AddMission/AddBonusMission, переставленные на диске
файлы — по SelectMission, загрузочные списки mXl/mXsdl, синтетические вступления бонусов). По каждой команде-«вещи» строка:
уровень / миссия / фаза / этап / команда / ресурс / есть ли у порта (улика) / чего нет. Что проверяется у порта:
  * компилятор: команда диска дошла до пакета (файл+строка+команда), локатор найден в данных уровня;
  * игра исполняет команду: tools/missions/coverage.py (runtime / engine / offline / ignored) и глубже — нужный обработчик
    интерфейса MsnGameApi поставлен игрой (props.item_show — предметы целей delivery/dump, props.item_collected — эффект подбора,
    props.state_prop — стейтпроп-предмет L7 ...);
  * ресурс в пакетах выпуска: имена пакетов — tools/ship_files.sh --pairs с SHIP_LEVELS="2 3 4 5 6 7" (что поедет на PSP,
    если включить уровни 2–7; сейчас по слову Роба 01.10 едет только уровень 1), содержимое — разбором самих пакетов:
    msnart (MSA2: составные объекты и значки по файлам LoadP3DFile), msncars (MCR1), collect (CLT1: гэги), msncam (MCM1),
    racefence (RFN1), fx (FXP1: системы частиц эффектов), music.sap (SAP1: реплики), chars/*.chr + viewer/msn_view.c npcFiles,
    movies/*.smv; содержимое p3d диска — по чанкам (донат: P3DChunk.h, GPL — только номера чанков).
--use имя=файл — подменить пакет выпуска (как tools/ship.sh --use), чтобы померить новый экспорт до выкладки.
--check — гейт: число строк «нет» по семействам и уровням не больше записанного в таблице ожиданий (регрессия = FAIL), а
семейства, помеченные там «0», обязаны быть нулём. Красный контроль: прежний экспорт (tests/missions/census.sh).
Правила порта (не факт оригинала) помечены в колонке улики словом «правило порта».
"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import argparse, os, re, struct, subprocess, sys
from pathlib import Path
from collections import defaultdict, Counter

HERE = Path(__file__).resolve().parent
ROOT0 = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT0 / 'hit-and-run-web/tools'))
import compile as MC          # noqa: E402  тот же компилятор, что пакеты level0N.msn
import commands as CMD        # noqa: E402
import coverage as COV        # noqa: E402
import mfk                    # noqa: E402
from p3d import read as p3d_read, string as p3d_str, walk as p3d_walk   # noqa: E402  (MIT)

GAME = ROOT0 / 'hit-and-run-web/source/game'
LEVELS = range(1, 8)
PLAYER_OF_LEVEL = {}   # заполняется из AddCharacter leveli.mfk


def norm(p): return str(p).replace('\\', '/').lower().strip()
def stem(p): return norm(p).rsplit('/', 1)[-1].split('.')[0]


# ------------------------------------------------------------------ пакеты выпуска
class Packs:
    """Пакеты выпуска: имя на PSP -> файл (tools/ship_files.sh --pairs, все уровни), с подменами --use."""
    def __init__(self, root, uses):
        env = dict(os.environ, SHIP_LEVELS='2 3 4 5 6 7')
        out = subprocess.run(['bash', str(root / 'tools/ship_files.sh'), '--pairs'], cwd=root, env=env,
                             capture_output=True, text=True, check=True).stdout
        self.root = root
        self.pairs = {}
        for ln in out.splitlines():
            if '|' in ln:
                n, p = ln.split('|', 1); self.pairs[n.strip()] = root / p.strip()
        for u in uses:
            n, p = u.split('=', 1); self.pairs[n] = Path(p).resolve()
        self.cache = {}

    def name(self, lv, base):
        """имя набора уровня на PSP: уровень 1 — корень, 2–7 — l<N>/ (viewer/main.c levelFile)"""
        return base if lv == 1 else f'l{lv}/{base}'

    def path(self, name):
        p = self.pairs.get(name)
        return p if p is not None and p.exists() else None

    def shipped(self, name): return name in self.pairs

    def get(self, name, reader):
        key = (name, reader.__name__)
        if key not in self.cache:
            p = self.path(name)
            self.cache[key] = reader(p) if p else None
        return self.cache[key]


def rd_msnart(p):
    b = p.read_bytes()
    if b[:4] != b'MSA2': return {}
    n, ot, _ = struct.unpack_from('<III', b, 4); out = {}
    for i in range(n):
        path, o, _ = struct.unpack_from('<80sII', b, ot + 96 * i)
        path = path.split(b'\0')[0].decode()
        _, nd, ni, _, od, oi = struct.unpack_from('<6I', b, o)
        dr = [b[o + od + 64 * k:o + od + 64 * k + 32].split(b'\0')[0].decode().lower() for k in range(nd)]
        im = [b[o + oi + 48 * k:o + oi + 48 * k + 32].split(b'\0')[0].decode().lower() for k in range(ni)]
        out[path] = (dr, im)
    return out


def rd_msncars(p):
    b = p.read_bytes()
    if b[:4] != b'MCR1': return set()
    _, _, n, oc = struct.unpack_from('<4I', b, 4)
    return {b[oc + 176 * i:oc + 176 * i + 16].split(b'\0')[0].decode().lower() for i in range(n)}


def rd_collect(p):
    b = p.read_bytes()
    if b[:4] != b'CLT1': return set()
    h = struct.unpack_from('<15I', b, 4); ngag, og = h[10], h[11]
    return {b[og + 128 * i:og + 128 * i + 16].split(b'\0')[0].decode().lower() for i in range(ngag)}


def rd_msncam(p):
    b = p.read_bytes()
    if b[:4] != b'MCM1': return set()
    n, _ = struct.unpack_from('<II', b, 4); out = set()
    for i in range(n):
        o = 16 + 64 * i
        cam = b[o:o + 32].split(b'\0')[0].decode().lower(); ph = b[o + 48:o + 64].split(b'\0')[0].decode().lower()
        out.add((ph, cam)); out.add(('', cam))
    return out


def rd_racefence(p):
    b = p.read_bytes()
    if b[:4] != b'RFN1': return {}
    n, = struct.unpack_from('<I', b, 4); off = 8; out = {}
    for _ in range(n):
        nm = b[off:off + 32].split(b'\0')[0].decode().lower(); k, = struct.unpack_from('<I', b, off + 32)
        out[nm] = k; off += 36 + 24 * k
    return out


def rd_fx(p):
    b = p.read_bytes()
    if b[:4] != b'FXP1': return set()
    h = struct.unpack_from('<15I', b, 4); nsys, osys = h[2], h[9]
    return {b[osys + 56 * i:osys + 56 * i + 32].split(b'\0')[0].decode().lower() for i in range(nsys)}


def rd_sap(p):
    b = p.read_bytes()
    if b[:4] != b'SAP1': return set()
    _, n, tbl = struct.unpack_from('<III', b, 4)
    return {b[tbl + 64 * i:tbl + 64 * i + 28].split(b'\0')[0].decode().lower() for i in range(n)}


def rd_bytes(p): return p.read_bytes()
def rd_lower(p): return p.read_bytes().lower()


# ------------------------------------------------------------------ содержимое p3d диска
_P3D = {}
def p3d_content(path):
    """путь диска -> {'comp': {имя: (пропы, эффекты)}, 'sprite': [], 'camera': [], 'stateprop': [], 'loc': n, 'psys': n,
    'skin': [], 'exists': bool}"""
    k = norm(path)
    if k in _P3D: return _P3D[k]
    fp = MC_FILES.find(k)
    d = dict(exists=fp is not None, comp={}, sprite=[], camera=[], stateprop=[], loc=0, psys=0, skin=[], file=fp)
    if fp is not None:
        root = p3d_read(fp)
        for c in root.children:
            try: nm = p3d_str(c.data)[0].lower()
            except Exception: nm = ''
            if c.id == 0x4512:
                props = [p3d_str(x.data)[0].lower() for x in p3d_walk(c) if x.id == 0x4516]
                eff = [p3d_str(x.data)[0].lower() for x in p3d_walk(c) if x.id == 0x4518]
                d['comp'][nm] = (props, eff)
            elif c.id == 0x19005: d['sprite'].append(nm.rsplit('.', 1)[0])
            elif c.id == 0x2200: d['camera'].append(nm)
            elif c.id == 0x8020000: d['stateprop'].append(p3d_str(c.data, 4)[0].lower())
            elif c.id in (0x3000005, 0x14000): d['loc'] += 1
            elif c.id == 0x15800: d['psys'] += 1
            elif c.id == 0x10001: d['skin'].append(nm)
    _P3D[k] = d
    return d


# ------------------------------------------------------------------ движок
class Engine:
    def __init__(self, root):
        src = root / 'viewer'
        self.installed = COV.installed(src)                      # {(группа, функция)}
        self.cov = {r['name']: r for r in COV.classify(src, root / 'tools').values()}
        t = (src / 'msn_view.c').read_text(errors='replace')
        m = re.search(r'npcFiles\[\]\s*=\s*\{(.*?)\};', t, re.S)
        self.npc_files = set(re.findall(r'"chars/([\w-]+)\.chr"', m.group(1))) if m else set()
        self.marker_draw = 'msnartDraw(H.marker.drawable' in t
        # предметы delivery / dump: обработчик props.item_show или рисование списка предметов в mvDrawMarkers (drawItems)
        self.item_draw = bool(re.search(r'\bdrawItems\(ex, ey, ez, t\);', t)) and 'msnartDraw(dr, p, ex, ey, ez, t)' in t
        m = re.search(r'#define RACE_SEG_MAX (\d+)', t); self.race_seg_max = int(m.group(1)) if m else 0
        ma = re.search(r'#define MAXE (\d+)', (src / 'msnart.c').read_text(errors='replace')); self.msnart_maxe = int(ma.group(1)) if ma else 0
        mc = (src / 'msncar.c').read_text(errors='replace') + read_main(src / 'main.c', errors="replace")
        self.yrule = len(re.findall(r'< -10\.f', t))   # правило порта «ниже −10 м — комната» (msn_view.c: маркер, персонажи, радар, предметы)
        self.driver_draw = bool(re.search(r'(skinDraw|modelFor)\([^;]*driver', mc)) or bool(re.search(r'static void drawDrivers\(', t))   # водитель в машине миссии рисуется?
        self.giver_icon = 'msnartDraw(icon, p' in t or 'msnartDrawNpcMarker(icon, rt, p' in t
        self.src_all = '\n'.join(read_main(f, errors='replace') for f in sorted(src.glob('*.c')) if not re.search(r'_v\d+\w*\.c$', f.name))
        self.tools_all = {f.name: f.read_text(errors='replace') for f in sorted((root / 'tools').glob('*.py'))}

    def has(self, group, fn): return (group, fn) in self.installed

    def status(self, op):
        r = self.cov.get(op); return r['status'] if r else 'нет в реестре'


# ------------------------------------------------------------------ строки
FAM = {   # команда -> (семейство, по-русски)
    'LoadP3DFile': ('load', 'Подгрузка p3d (модели, значки, камеры, локаторы)'),
    'SetDestination': ('marker', 'Маркер цели (сфера / предмет на точке)'),
    'AddCollectible': ('item', 'Предметы и точки цели (delivery / dump / race)'),
    'SetCollectibleEffect': ('effect', 'Эффект подбора / прибытия'),
    'SetHUDIcon': ('icon', 'Значок задания в пузыре'),
    'SetPresentationBitmap': ('brief', 'Картинка брифинга'),
    'AddNPC': ('npc', 'Персонажи в мире'), 'AddAmbientCharacter': ('npc', 'Персонажи в мире'),
    'AddNPCCharacterBonusMission': ('npc', 'Персонажи в мире'), 'AddPurchaseCarReward': ('npc', 'Персонажи в мире'),
    'AddStageCharacter': ('npc', 'Персонажи в мире'), 'AddDriver': ('npc', 'Персонажи в мире'),
    'SetCharacterToHide': ('npc', 'Персонажи в мире'),
    'AddCharacter': ('player', 'Игрок уровня'),
    'AddStageVehicle': ('car', 'Машины миссий'), 'LoadDisposableCar': ('car', 'Машины миссий'),
    'ActivateVehicle': ('car', 'Машины миссий'), 'SetForcedCar': ('car', 'Машины миссий'),
    'InitLevelPlayerVehicle': ('car', 'Машины миссий'),
    'SetMissionStartCameraName': ('cam', 'Камеры старта («наезды»)'), 'SetAnimatedCameraName': ('cam', 'Камеры старта («наезды»)'),
    'SetFMVInfo': ('fmv', 'Ролики'), 'GagPlayFMV': ('fmv', 'Ролики'),
    'StreetRacePropsLoad': ('race', 'Пропы и заборы уличных гонок'),
    'GagBegin': ('gag', 'Гэги'),
    'AddCollectibleStateProp': ('sprop', 'Стейтпропы миссий (бочки L7)'), 'SetStatepropShadow': ('sprop', 'Стейтпропы миссий (бочки L7)'),
    'AddShield': ('wasp', 'Осы, щиты, летающие'), 'AddFlyingActorByLocator': ('wasp', 'Осы, щиты, летающие'),
    'SetDialogueInfo': ('voice', 'Реплики разговоров'), 'SetCompletionDialog': ('voice', 'Реплики разговоров'),
    'BindReward': ('reward', 'Награды (машины, костюмы) и продавцы'),
    'SetCoinDrawable': ('misc', 'Прочее уровня'), 'SetParticleTexture': ('misc', 'Прочее уровня'),
}
FAM_RU = {}
for _op, (_k, _ru) in FAM.items(): FAM_RU.setdefault(_k, _ru)
FAM_RU['compile'] = 'Компилятор: команда диска не дошла до пакета'
FAM_RU['locator'] = 'Локатор не найден в данных'
FAM_RU['driver'] = 'Водители в машинах миссий'
FAM_RU['cap'] = 'Ёмкость движка (записи msnart, заборы трассы)'
FAM_RU['room'] = 'Точки в городе ниже −10 м (правило «комната»)'
NOT_WORLD = {'voice', 'reward', 'misc'}   # не «вещь в 3D», но ресурс — в перепись


class Row(dict):
    pass


class Census:
    def __init__(self, root, uses):
        self.root = root
        self.packs = Packs(root, uses)
        self.eng = Engine(root)
        self.rows = []

    # -------------------------------------------------- обход пакета
    def level(self, lv):
        c = MC.Compiler(lv); c.compile(); P = c.pack
        self.P, self.lv = P, lv
        S = lambda i: P.strings[i]
        self.S = S
        lf, lc, inf, inc, rf, rc = P.level[:6]
        level_files = [norm(S(P.args[P.cmds[k][3]][2])) for k in range(lf, lf + lc) if CMD.SPECS[P.cmds[k][0] - 1].name == 'LoadP3DFile']
        self.level_loads = level_files
        ctx = dict(mission='уровень', phase='level.mfk', stage='-', obj='', loads=level_files)
        for k in range(lf, lf + lc): self.cmd(k, ctx)
        ctx = dict(mission='уровень', phase='leveli.mfk', stage='-', obj='', loads=level_files)
        for k in range(inf, inf + inc): self.cmd(k, ctx)
        ctx = dict(mission='награды', phase='rewards.mfk', stage='-', obj='', loads=level_files)
        for k in range(rf, rf + rc): self.cmd(k, ctx)
        for m in P.missions:
            mid = S(m[0]); prev = []   # файлы вступления (mXsdl) остаются в памяти до конца миссии (msnart: сброс на старте миссии)
            for phi in (m[5], m[6]):
                if phi == 0xFFFF: continue
                ph = P.phases[phi]
                own = [norm(S(P.args[P.cmds[k][3]][2])) for k in range(ph[5], ph[5] + ph[4])
                       if CMD.SPECS[P.cmds[k][0] - 1].name == 'LoadP3DFile']
                loads = own + prev + level_files; prev = prev + own
                base = dict(mission=mid, phase=S(ph[0]), loads=loads, obj='')
                for k in range(ph[5], ph[5] + ph[4]): self.cmd(k, dict(base, stage='загрузка'))
                for k in range(ph[2], ph[2] + ph[3]): self.cmd(k, dict(base, stage='миссия'))
                for si, st in enumerate(P.stages[ph[6]:ph[6] + ph[7]]):
                    obj = CMD.OBJECTIVES[st[9] - 1] if st[9] else '?'
                    for k in range(st[0], st[0] + st[1]): self.cmd(k, dict(base, stage=str(si), obj=obj))
        self.compile_drops(c)
        self.capacity()

    def capacity(self):
        """ёмкость движка: записей msnart одновременно (уровень + миссия + брифинг + пропы гонки + местность) <= MAXE msnart.c;
        заборов трассы <= RACE_SEG_MAX msn_view.c"""
        P, S, M = self.P, self.S, self.msnart()
        lvl = [x for x in dict.fromkeys(self.level_loads) if x in M] + [f'art/l{self.lv}_terra.p3d']
        for m in P.missions:
            need = set(lvl)
            for phi in (m[5], m[6]):
                if phi == 0xFFFF: continue
                ph = P.phases[phi]
                ks = list(range(ph[5], ph[5] + ph[4])) + list(range(ph[2], ph[2] + ph[3])) + \
                     [k for st in P.stages[ph[6]:ph[6] + ph[7]] for k in range(st[0], st[0] + st[1])]
                for k in ks:
                    spec, a, _, _ = self.args(k)
                    if spec.name in ('LoadP3DFile', 'SetPresentationBitmap') and norm(a[0]) in M: need.add(norm(a[0]))
                    if spec.name == 'StreetRacePropsLoad':
                        for nm in str(a[0]).replace(':', ';').split(';'):
                            if stem(nm) and f'art/{stem(nm)}.p3d' in M: need.add(f'art/{stem(nm)}.p3d')
            ctx = dict(mission=S(m[0]), phase='-', stage='-', obj='')
            lim = self.eng.msnart_maxe; ok = len(need) <= lim
            self.add(ctx, 'msnart', '-', 'cap', f'записей msnart {len(need)} из {lim}', 'есть' if ok else 'нет',
                     'msnart.c MAXE' if ok else '', '' if ok else f'не влезут {len(need) - lim} записей: модели/значки не загрузятся', '')
        rfn = self.packs.name(self.lv, 'racefence.bin' if self.lv == 1 else f'racefence-l{self.lv}.bin')
        for nm, k in (self.packs.get(rfn, rd_racefence) or {}).items():
            lim = self.eng.race_seg_max; ok = k <= lim
            self.add(dict(mission='гонки', phase='-', stage='-', obj=''), 'racefence', '-', 'cap', f'{nm}: заборов {k} из {lim}',
                     'есть' if ok else 'нет', 'msn_view.c RACE_SEG_MAX' if ok else '', '' if ok else f'{k - lim} заборов отбрасываются', '')

    def args(self, k):
        P = self.P; op, n, _, a0, line, f = P.cmds[k]
        out, locs = [], []
        for t, loc, v in P.args[a0:a0 + n]:
            out.append(self.S(v) if t in (MC.ARG_STR, MC.ARG_BARE) else v); locs.append(loc)
        return CMD.SPECS[op - 1], out, locs, f'{self.S(P.files[f])}:{line}'

    def add(self, ctx, op, src, fam, res, ok, ev, miss='', args=''):
        self.rows.append(Row(level=self.lv, mission=ctx['mission'], phase=ctx['phase'], stage=ctx['stage'], obj=ctx.get('obj', ''),
                             cmd=op, args=args, res=res, ok=ok, ev=ev, miss=miss, fam=fam, src=src))

    # -------------------------------------------------- проверки ресурсов
    def msnart(self):
        return self.packs.get(self.packs.name(self.lv, 'msnart.shr'), rd_msnart) or {}

    def art_objs(self, loads):
        M = self.msnart(); dr, im = set(), set()
        for p in loads:
            e = M.get(p)
            if e: dr |= set(e[0]); im |= set(e[1])
        return dr, im

    def comp_source(self, name, loads):
        """в каком из загруженных файлов диска лежит составной объект name"""
        for p in loads:
            if name in p3d_content(p)['comp']: return p
        return None

    def cmd(self, k, ctx):
        spec, a, locs, src = self.args(k)
        op = spec.name
        for i in spec.locs:   # локатор не найден — у порта точки нет
            if i < len(a) and isinstance(a[i], str) and a[i] and not locs[i] and op not in ('SetDestination',) \
                    and a[i].lower() not in ('null', 'current', 'none', ''):
                self.locator_row(ctx, op, src, a[i], a)
        self.room_rule(ctx, op, src, a, locs)
        f = FAM.get(op)
        if not f: return
        fam = f[0]
        st = self.eng.status(op)
        h = getattr(self, 'c_' + op, None)
        if st == 'ignored' and h is None:
            self.add(ctx, op, src, fam, short(a), 'нет', f'coverage.py: {st} — игра не исполняет команду', 'команда', short(a)); return
        if h: h(ctx, op, src, fam, a, locs, st)

    # LoadP3DFile: что в файле и где оно у порта
    def c_LoadP3DFile(self, ctx, op, src, fam, a, locs, st):
        p = norm(a[0]); d = p3d_content(p)
        if not d['exists']:
            self.add(ctx, op, src, fam, p, 'нет', 'файла нет на диске', 'файл диска', p); return
        M = self.msnart(); e = M.get(p)
        have, lack, ev = [], [], []
        comps = d['comp']
        if p.startswith('art/cars/'):
            car = stem(p); cars = self.packs.get(self.packs.name(self.lv, f'msncars-l{self.lv}.shr'), rd_msncars) or set()
            tr = self.packs.get(self.packs.name(self.lv, 'traffic.shr'), rd_lower) or b''
            if car in cars: ev.append(f'msncars-l{self.lv}.shr: {car}')
            elif tr and (car.encode() + b'\0') in tr: ev.append(f'traffic.shr: {car}')
            elif car == 'huska' and 'huska.p3d' in self.eng.tools_all.get('psp_export.py', ''): ev.append('остов машины — level.shr CAR1 (psp_export.py)')
            else: lack.append(f'машина {car}')
        elif p == 'art/cards.p3d':   # карточки — пакет коллекции (tools/collect_export.py), значок будки — msnart (PICK)
            cl = self.packs.get(self.packs.name(self.lv, f'collect-l{self.lv}.shr'), rd_bytes)
            ncard = struct.unpack_from('<I', cl, 28)[0] if cl and cl[:4] == b'CLT1' else 0
            (ev if ncard else lack).append(f'карточки: {ncard} — collect-l{self.lv}.shr' if ncard else 'карточки: нет пакета коллекции')
            dr = set((e or ([], []))[0])
            (ev if 'phone_icon' in dr else lack).append('значок будки phone_icon — ' + ('msnart' if 'phone_icon' in dr else 'нет в msnart'))
        elif comps or d['sprite']:
            want_c = [n for n, (pr, ef) in comps.items() if pr]          # есть меш/квады — рисуется
            only_fx = [n for n, (pr, ef) in comps.items() if not pr and ef]
            if p.startswith('art/chars/'):
                tag = 'эффект персонажа (пинок, удар током)'
                fx = self.packs.get(self.packs.name(self.lv, 'fx.shr'), rd_bytes) or b''
                hb = self.packs.get('homer.shr', rd_bytes) or b''
                cl = self.packs.get(self.packs.name(self.lv, f'collect-l{self.lv}.shr'), rd_bytes) or b''   # 16.10 (Спрайты): kickwave/electrocuted — стейтпропы collect-lN.shr
                got = [n for n in want_c if (n.encode() in fx) or (n.encode() in hb) or (n.encode() in cl)]
                if len(cl) >= 72 and cl[:4] == b'CLT1':   # CLT1 v3: kickFx @64 и shockFx @68 (u32, -1 нет) — экземпляры эффектов персонажа (tools/collect_export.py)
                    kf, sf = struct.unpack_from('<2I', cl, 64)
                    if ('kickwave' in p and kf < 0x80000000) or ('electrocuted' in p and sf < 0x80000000): got = got or list(want_c) or [p]
                (ev if got else lack).append(f'{tag}: {", ".join(want_c)}' + (' — fx.shr/homer.shr/collect-lN.shr' if got else ''))
            elif p.startswith('art/l0') and p.endswith('_fx.p3d'):
                fxs = self.packs.get(self.packs.name(self.lv, 'fx.shr'), rd_fx)
                ev.append(f'частицы уровня — fx.shr ({len(fxs or ())} систем)' if fxs else '');
                if not fxs: lack.append('fx.shr')
            elif p == 'art/wrench.p3d':   # гаечные ключи мира — level.shr (game.c gameWrenchStep); wrench_collect — эффект подбора
                dr = set((e or ([], []))[0])
                ev.append('гаечные ключи мира — level.shr (game.c gameWrenchStep)')
                (ev if 'wrench_collect' in dr else lack).append('эффект wrench_collect — ' + ('msnart' if 'wrench_collect' in dr else
                    'нет в msnart (файл не взят экспортёром: фильтр путей msnart_export.py)'))
            elif p.startswith('art/frontend/dynaload/images/') and 'msnicons/' not in p and not p.split('/')[-1].startswith('mis'):
                lack.append('картинка ' + ', '.join(d['sprite']) + ' — скрипты на неё не ссылаются (экран кода оригинала, конец игры?) — вопрос близнецу')
            elif p == 'art/phonecamera.p3d':
                ph = self.packs.path(self.packs.name(self.lv, 'phone.shr'))   # экраны будки/лавки/гардероба есть у уровней 1–7 (пакет уровня)
                (ev if ph else lack).append('камера телефонной будки' + (f' — {self.packs.name(self.lv, "phone.shr")} (экран будки)' if ph else f' (будка уровня {self.lv}: нет {self.packs.name(self.lv, "phone.shr")})'))
            else:
                dr, im = (e if e else ([], []))
                for n in want_c:
                    (have if n in dr else lack).append(n)
                for n in d['sprite']:
                    (have if n.lower() in im else lack).append('значок ' + n)
                if only_fx: ev.append('только частицы (fx.shr): ' + ', '.join(only_fx))
                if have: ev.append(f'msnart: {", ".join(have[:6])}' + ('…' if len(have) > 6 else ''))
                if lack and not e:
                    lack = [x + (' (файл не взят экспортёром: фильтр путей msnart_export.py)' if not (p.startswith('art/missions/') or 'msnicons/' in p) else ' (нет записи в msnart)') for x in lack]
        elif d['camera']:
            ev.append('камеры: ' + ', '.join(d['camera'][:4]) + ' — см. строки камер старта (msncam)')
        elif d['stateprop']:
            ev.append('стейтпропы: ' + ', '.join(d['stateprop']))
        elif d['loc']:
            ev.append(f'локаторы ({d["loc"]}) — компилятор миссий (level{self.lv:02d}.msn)')
        else:
            ev.append('нет рисуемого содержимого')
        if d['stateprop'] and not (p.startswith('art/l0') and p.endswith('_fx.p3d')):
            sp = self.eng.has('props', 'state_prop')
            (ev if sp else lack).append('стейтпроп ' + ', '.join(d['stateprop']) + ('' if sp else ' (props.state_prop не подключён, в пакетах нет)'))
        ok = 'нет' if lack and not have and not [x for x in ev if x] else ('частично' if lack else 'есть')
        self.add(ctx, op, src, fam, p, ok, '; '.join(x for x in ev if x), '; '.join(lack), p)

    def _drawable(self, name, loads):
        """составной объект name: (есть в msnart, файл диска, только частицы)"""
        dr, _ = self.art_objs(loads)
        srcf = self.comp_source(name, loads)
        fxonly = bool(srcf) and not p3d_content(srcf)['comp'][name][0]
        return name in dr, srcf, fxonly

    ROOM_ARG = {'SetDestination': 0, 'AddCollectible': 0, 'AddNPC': 1, 'AddAmbientCharacter': 1, 'AddNPCCharacterBonusMission': 2,
                'AddCollectibleStateProp': 1}
    def room_rule(self, ctx, op, src, a, locs):
        """правило порта «точка ниже −10 м — в комнате» (msn_view.c: маркер цели, персонажи миссий, радар, предметы): точка снаружи
        ниже −10 м (река и набережная L3 до −68 м) в городе не рисуется. Комната — по рамкам мешей файлов комнат диска"""
        i = self.ROOM_ARG.get(op)
        if i is None or i >= len(locs) or not locs[i] or not self.eng.yrule: return
        if op == 'AddCollectible' and ctx.get('obj') == 'dump': return   # рисуется с места выпадения
        L = self.P.locs[locs[i] - 1]; pos = L['pos']
        if pos[1] >= -10.0: return
        rm = in_room(self.lv, pos)
        if rm: return
        self.add(ctx, op, src, 'room', f'{a[i]} y={pos[1]:.1f}', 'нет', '',
                 'точка в городе ниже −10 м: правило порта «y < −10 — комната» (msn_view.c, ' + str(self.eng.yrule) + ' мест) прячет её в городе '
                 '(маркер / персонаж / предмет / ромб радара)', short(a))

    def locator_row(self, ctx, op, src, name, a):
        hit = disc_has_name(self.lv, name)
        if hit: self.add(ctx, op, src, 'locator', name, 'нет', f'на диске есть: {hit}', 'компилятор не нашёл локатор', short(a))
        else: self.add(ctx, op, src, 'locator', name, 'есть', 'локатора нет ни в одном p3d уровня на диске — как в оригинале (опечатка скрипта)', '', short(a))

    def c_SetDestination(self, ctx, op, src, fam, a, locs, st):
        loc = a[0] if a else ''; dr = a[1].lower() if len(a) > 1 else ''
        if not locs[0] and loc and ctx.get('obj') not in ('interior', 'gooutside'):
            self.locator_row(ctx, op, src, loc, a)
        if not dr:
            self.add(ctx, op, src, fam, f'{loc} (без модели)', 'есть', 'невидимая точка: стрелка и радар', '', short(a)); return
        have, srcf, fxonly = self._drawable(dr, ctx['loads'])
        draw = self.eng.marker_draw and self.eng.has('nav', 'marker')
        ev = f'msnart ({srcf}); msn_view.c рисует маркер цели' if have else ''
        miss = []
        if not have: miss.append(f'модель {dr}' + (f' (в {srcf}, не в msnart)' if srcf else ' (нет в загруженных файлах)'))
        if not draw: miss.append('маркер не рисуется')
        self.add(ctx, op, src, fam, dr, 'есть' if not miss else 'нет', ev, '; '.join(miss), short(a))

    def c_AddCollectible(self, ctx, op, src, fam, a, locs, st):
        loc = a[0]; dr = a[1].lower() if len(a) > 1 else ''
        obj = ctx.get('obj', '')
        if not dr:   # предмет без модели: объект мира, который надо сломать (m4 щитки), или невидимая точка гонки
            if obj == 'delivery':
                ok = self.eng.has('props', 'activate_tag')
                self.add(ctx, op, src, fam, f'{loc} (сломать объект мира)', 'есть' if ok else 'нет',
                         'стейтпроп уровня, props.activate_tag (game_msn.c GAME_MSN_BREAKABLES)' if ok else '', '' if ok else 'props.activate_tag', short(a))
            else:
                self.add(ctx, op, src, fam, f'{loc} (без модели)', 'есть', f'{obj}: невидимая точка, радар', '', short(a))
            return
        have, srcf, fxonly = self._drawable(dr, ctx['loads'])
        miss, ev = [], []
        if have: ev.append(f'msnart ({srcf})')
        else: miss.append(f'модель {dr}' + (f' (в {srcf}, не в msnart)' if srcf else ' (нет в загруженных файлах)'))
        if obj == 'race':
            ev.append('гонка: модель следующей точки — маркер цели (msn_game.c send_marker), правило порта: по одной')
        elif self.eng.has('props', 'item_show') or self.eng.item_draw:
            ev.append('msn_view.c drawItems (все неподобранные, как запись PS2 25:45 bm1)' if self.eng.item_draw else 'props.item_show')
        else:
            miss.append(f'{obj}: предмет не рисуется (props.item_show не подключён; только радар)')
        if len(a) > 2 and isinstance(a[2], str) and a[2]:
            ev.append(f'реплика при подборе «{a[2]}» — см. голос')
        self.add(ctx, op, src, fam, dr, 'есть' if not miss else ('частично' if have else 'нет'), '; '.join(ev), '; '.join(miss), short(a))

    def c_SetCollectibleEffect(self, ctx, op, src, fam, a, locs, st):
        nm = a[0].lower() if a else ''
        if nm in ('', 'none'):
            self.add(ctx, op, src, fam, nm or '-', 'есть', 'без эффекта', '', short(a)); return
        srcf = self.comp_source(nm, ctx['loads'])
        miss, ev = [], []
        if not srcf:
            miss.append(f'{nm}: нет в загруженных файлах')
        else:
            props, effs = p3d_content(srcf)['comp'][nm]
            fxs = self.packs.get(self.packs.name(self.lv, 'fx.shr'), rd_fx) or set()
            dr, _ = self.art_objs([srcf])
            if props:
                (ev if nm in dr else miss).append(f'квады/меш {nm} — ' + ('msnart' if nm in dr else f'не в msnart ({srcf})'))
            for e_ in effs:
                (ev if e_ in fxs else miss).append(f'частицы {e_} — ' + ('fx.shr' if e_ in fxs else 'не в fx.shr'))
        if not self.eng.has('props', 'item_collected'):
            miss.append('не рисуется: props.item_collected не подключён (помощник «эффекты»)')
        self.add(ctx, op, src, fam, nm, 'есть' if not miss else ('частично' if ev else 'нет'), '; '.join(ev), '; '.join(miss), short(a))

    def c_SetHUDIcon(self, ctx, op, src, fam, a, locs, st):
        nm = a[0].lower() if a else ''
        _, im = self.art_objs(ctx['loads'])
        ok = nm in im
        self.add(ctx, op, src, fam, nm, 'есть' if ok else 'нет', 'msnart: значок msnicons' if ok else '',
                 '' if ok else 'значка нет в msnart (файлы, загруженные миссией)', short(a))

    def c_SetPresentationBitmap(self, ctx, op, src, fam, a, locs, st):
        p = norm(a[0]); M = self.msnart(); e = M.get(p)
        ok = bool(e and e[1]) and self.eng.has('ui', 'presentation')
        self.add(ctx, op, src, fam, p, 'есть' if ok else 'нет', f'msnart: {e[1][0]}' if ok else '', '' if ok else 'картинки нет в msnart', short(a))

    def _char(self, name):
        n = name.lower()
        f = f'chars/{n}.chr'
        mp = MC_FILES.find(f'art/chars/{n[:6]}_m.p3d')
        if mp is not None and not any(c.id == 0x10001 for c in p3d_walk(p3d_read(mp))):
            return True, f'art/chars/{n[:6]}_m.p3d без кожи (только скелет) — невидим и в оригинале'
        sh, ex, lst = self.packs.shipped(f), self.packs.path(f) is not None, n in self.eng.npc_files
        if sh and ex and lst: return True, f'{f} (ship_rules + npcFiles)'
        why = [] if sh else ['нет правила выпуска']
        if not ex: why.append('нет файла')
        if not lst: why.append('нет в npcFiles')
        return False, f'{f}: ' + ', '.join(why)

    def _npc(self, ctx, op, src, fam, a, name, extra=''):
        ok, ev = self._char(name)
        spawn = self.eng.has('npc', 'spawn')
        miss = ([] if ok else [ev]) + ([] if spawn else ['npc.spawn не подключён'])
        self.add(ctx, op, src, fam, name.lower() + extra, 'есть' if not miss else 'нет', ev if ok else '', '; '.join(miss), short(a))

    def c_AddNPC(self, ctx, op, src, fam, a, locs, st): self._npc(ctx, op, src, fam, a, a[0])
    def c_AddAmbientCharacter(self, ctx, op, src, fam, a, locs, st): self._npc(ctx, op, src, fam, a, a[0])
    def c_AddNPCCharacterBonusMission(self, ctx, op, src, fam, a, locs, st):
        self._npc(ctx, op, src, fam, a, a[0])
        icon = a[4].lower() if len(a) > 4 else ''
        if icon:
            have, srcf, _ = self._drawable(icon, ctx['loads'])
            ok = have and self.eng.giver_icon
            self.add(ctx, op, src, 'marker', f'{icon} (значок над персонажем)', 'есть' if ok else 'нет',
                     f'msnart ({srcf}); msn_view.c правка 180' if ok else '', '' if ok else f'значок {icon}', short(a))
    def c_AddPurchaseCarReward(self, ctx, op, src, fam, a, locs, st):
        self._npc(ctx, op, src, fam, a, a[1], ' (продавец)')
        shop = self.packs.path(self.packs.name(self.lv, 'shop.shr'))
        self.add(ctx, op, src, 'reward', f'лавка {a[0]}', 'есть' if shop else 'нет',
                 f'{self.packs.name(self.lv, "shop.shr")} + reward-<k>.shr' if shop else '', '' if shop else f'экран покупки уровня {self.lv}: нет {self.packs.name(self.lv, "shop.shr")}', short(a))
    def _player_pack(self):
        """модель игрока уровня — пакет l<N>/player.shr (скин игрока уровня: Барт L2/L6, Лиза L3, Мардж L4, Апу L5); у L1 Гомер — homer.shr"""
        return self.packs.path(self.packs.name(self.lv, 'player.shr')) if self.lv > 1 else self.packs.path('homer.shr')
    def c_AddStageCharacter(self, ctx, op, src, fam, a, locs, st):
        nm = a[0].lower(); pl = PLAYER_OF_LEVEL.get(self.lv, 'homer')
        if nm == pl:   # постановка игрока
            ok = self.eng.status(op) in ('engine',)
            ev = 'игрок ставится (player)' if ok else ''
            miss = '' if (nm == 'homer' or self._player_pack()) else f'игрок уровня {nm}: нет пакета player.shr (порт ставит Гомера)'
            if nm != 'homer' and not miss: ev = f'игрок уровня {nm}: l{self.lv}/player.shr'
            self.add(ctx, op, src, 'player', nm, 'есть' if not miss else 'частично', ev, miss, short(a))
        else:
            self._npc(ctx, op, src, fam, a, nm)
    def c_AddDriver(self, ctx, op, src, fam, a, locs, st):
        okc, evc = self._char(a[0])
        miss = ([] if okc else [f'модель {evc}']) + ([] if self.eng.driver_draw else ['водитель в машине не рисуется'])
        if st == 'ignored': miss.append(f'coverage.py: {st}')
        self.add(ctx, op, src, 'driver', f'{a[0].lower()} в {a[1] if len(a) > 1 else ""}', 'есть' if not miss else 'нет', evc if okc else '', '; '.join(miss), short(a))
    def c_SetCharacterToHide(self, ctx, op, src, fam, a, locs, st):
        self.add(ctx, op, src, fam, a[0].lower(), 'нет' if st == 'ignored' else 'есть', f'coverage.py: {st}', 'команда' if st == 'ignored' else '', short(a))

    def c_AddCharacter(self, ctx, op, src, fam, a, locs, st):
        nm = a[0].lower(); PLAYER_OF_LEVEL[self.lv] = nm
        ok = nm == 'homer' or bool(self._player_pack())
        self.add(ctx, op, src, fam, nm, 'есть' if ok else 'нет', ('homer.shr' if nm == 'homer' else f'l{self.lv}/player.shr') if ok else '',
                 '' if ok else f'игрок уровня — {nm}: нет пакета l{self.lv}/player.shr (порт ставит Гомера), команда {st}', short(a))

    def _car(self, name):
        n = name.lower()
        cars = self.packs.get(self.packs.name(self.lv, f'msncars-l{self.lv}.shr'), rd_msncars) or set()
        if n in cars: return True, f'msncars-l{self.lv}.shr'
        tr = self.packs.get(self.packs.name(self.lv, 'traffic.shr'), rd_lower) or b''
        if tr and (n.encode() + b'\0') in tr: return True, 'traffic.shr'
        return False, f'нет в msncars-l{self.lv}.shr / traffic.shr'

    def c_AddStageVehicle(self, ctx, op, src, fam, a, locs, st):
        ok, ev = self._car(a[0]); miss = [] if ok else [ev]
        if not self.eng.has('cars', 'spawn'): miss.append('cars.spawn не подключён')
        self.add(ctx, op, src, fam, a[0].lower(), 'есть' if not miss else 'нет', ev if ok else '', '; '.join(miss), short(a))
        if len(a) > 4 and isinstance(a[4], str) and a[4] and a[4].lower() != 'none':   # водитель в машине
            okc, evc = self._char(a[4])
            miss = ([] if okc else [f'модель {evc}']) + ([] if self.eng.driver_draw else ['водитель в машине миссии не рисуется (msncar.c хранит имя)'])
            self.add(ctx, op, src, 'driver', f'{a[4].lower()} в {a[0]}', 'есть' if not miss else 'нет', evc if okc else '', '; '.join(miss), short(a))

    def c_LoadDisposableCar(self, ctx, op, src, fam, a, locs, st):
        car, slot = (a[1].lower() if len(a) > 1 else stem(a[0])), (a[2].upper() if len(a) > 2 else '')
        if slot == 'DEFAULT':
            self.add(ctx, op, src, fam, car, 'есть', 'машина игрока уровня — level.shr CAR1 (psp_export.py)', '', short(a)); return
        ok, ev = self._car(car)
        self.add(ctx, op, src, fam, car, 'есть' if ok else 'нет', ev if ok else '', '' if ok else ev, short(a))

    def c_ActivateVehicle(self, ctx, op, src, fam, a, locs, st):
        ok, ev = self._car(a[0])
        self.add(ctx, op, src, fam, a[0].lower(), 'есть' if ok else 'нет', ev if ok else '', '' if ok else ev, short(a))

    def c_SetForcedCar(self, ctx, op, src, fam, a, locs, st):
        ok = self.eng.has('player', 'vehicle')
        self.add(ctx, op, src, fam, '(навязанная машина)', 'есть' if ok else 'нет',
                 'компилятор: флаг миссии MF_FORCEDCAR; машину даёт InitLevelPlayerVehicle(…, "OTHER") — game_msn.c plVehicle, MCR1 v2' if ok else '',
                 '' if ok else 'player.vehicle не подключён', short(a))

    def c_InitLevelPlayerVehicle(self, ctx, op, src, fam, a, locs, st):
        car = a[0].lower(); slot = a[2].upper() if len(a) > 2 else ''
        if slot == 'OTHER':
            ok, ev = self._car(car)
            self.add(ctx, op, src, fam, car + ' (OTHER)', 'есть' if ok else 'нет', ev if ok else '', '' if ok else ev, short(a))
        else:
            self.add(ctx, op, src, fam, car, 'есть', 'level.shr CAR1 (psp_export.py: машина игрока уровня)', '', short(a))

    def _cam(self, ctx, op, src, fam, a):
        cam = a[0].lower() if a else ''
        M = self.packs.get(self.packs.name(self.lv, 'msncam.shr'), rd_msncam) or set()
        ok = (ctx['phase'].lower(), cam) in M or ('', cam) in M
        self.add(ctx, op, src, fam, cam, 'есть' if ok else 'нет', 'msncam.shr' if ok else '', '' if ok else 'камеры нет в msncam.shr', short(a))
    def c_SetMissionStartCameraName(self, ctx, op, src, fam, a, locs, st): self._cam(ctx, op, src, fam, a)
    def c_SetAnimatedCameraName(self, ctx, op, src, fam, a, locs, st): self._cam(ctx, op, src, fam, a)

    def _fmv(self, ctx, op, src, fam, a):
        nm = stem(a[0]); f = f'movies/{nm}.smv'
        sh, ex = self.packs.shipped(f), self.packs.path(f) is not None
        self.add(ctx, op, src, fam, nm, 'есть' if sh and ex else 'нет', f if sh and ex else '',
                 '' if sh and ex else (f'{f}: ' + ('нет правила выпуска' if not sh else 'нет файла')), short(a))
    def c_SetFMVInfo(self, ctx, op, src, fam, a, locs, st): self._fmv(ctx, op, src, fam, a)
    def c_GagPlayFMV(self, ctx, op, src, fam, a, locs, st): self._fmv(ctx, op, src, fam, a)

    def c_StreetRacePropsLoad(self, ctx, op, src, fam, a, locs, st):
        for nm in str(a[0]).replace(':', ';').split(';'):
            nm = stem(nm)
            if not nm: continue
            p = f'art/{nm}.p3d'; M = self.msnart(); e = M.get(p)
            rfn = self.packs.name(self.lv, 'racefence.bin' if self.lv == 1 else f'racefence-l{self.lv}.bin')
            R = self.packs.get(rfn, rd_racefence)
            ev, miss = [], []
            (ev if e and e[0] else miss).append(f'пропы {nm} — ' + ('msnart' if e and e[0] else 'нет в msnart'))
            if R is not None and nm in R: ev.append(f'заборы {nm}: {R[nm]} — {rfn}')
            else: miss.append(f'заборы трассы {nm}: ' + (f'нет пакета {rfn}' + ('' if self.packs.shipped(rfn) else ' (и правила выпуска)') if R is None else f'нет записи в {rfn}'))
            if not self.eng.has('props', 'race_props'): miss.append('props.race_props не подключён')
            self.add(ctx, op, src, fam, nm, 'есть' if not miss else ('частично' if ev else 'нет'), '; '.join(ev), '; '.join(miss), short(a))

    def c_GagBegin(self, ctx, op, src, fam, a, locs, st):
        nm = stem(a[0])
        G = self.packs.get(self.packs.name(self.lv, f'collect-l{self.lv}.shr'), rd_collect)
        ok = G is not None and nm in G
        self.add(ctx, op, src, fam, nm, 'есть' if ok else 'нет', f'collect-l{self.lv}.shr' if ok else '',
                 '' if ok else (f'нет пакета collect-l{self.lv}.shr' if G is None else f'гэга нет в collect-l{self.lv}.shr'), short(a))

    def c_AddCollectibleStateProp(self, ctx, op, src, fam, a, locs, st):
        nm = a[0].lower(); hit = [p for p in ctx['loads'] if nm in p3d_content(p)['stateprop']]
        ok = self.eng.has('props', 'state_prop')
        self.add(ctx, op, src, fam, nm, 'есть' if ok else 'нет', f'данные: {hit[0]}' if hit else '',
                 '' if ok else 'стейтпроп-предмет не ставится: props.state_prop не подключён, стейтпропов миссий нет в пакетах', short(a))
    def c_SetStatepropShadow(self, ctx, op, src, fam, a, locs, st):
        lp = 'def lightpool_prims' in (ROOT0 / 'tools/psp_export.py').read_text(errors='replace')   # правка 496: пятна — аддитивные куски города в level.shr (экспорт), не команда движка
        ok = lp or st != 'ignored'
        self.add(ctx, op, src, fam, f'{a[0]} → {a[1] if len(a) > 1 else ""}', 'есть' if ok else 'нет', 'tools/psp_export.py lightpool_prims (правка 496): пятно под каждым фонарём в level.shr' if lp else f'coverage.py: {st}',
                 '' if ok else 'световое пятно под фонарём (команда)', short(a))

    def c_AddShield(self, ctx, op, src, fam, a, locs, st):
        self.add(ctx, op, src, fam, f'{a[0]} / {a[1]}', 'есть' if st != 'ignored' else 'нет', f'coverage.py: {st} (collect_export.py)', '', short(a))
    def c_AddFlyingActorByLocator(self, ctx, op, src, fam, a, locs, st):
        G = self.packs.get(self.packs.name(self.lv, f'collect-l{self.lv}.shr'), rd_bytes) or b''
        ok = st != 'ignored' and a[0].encode() in G
        if st != 'ignored' and not ok and G:   # имя актёра в collect-lN.shr не пишется: ищем имена систем частиц его составного рисунка (L7: spaceship -> ufo_psShape, beam_sparkles_psShape)
            from p3d import read as _rd, string as _st
            for f in sorted((ROOT0 / 'hit-and-run-web/source/game/art/missions' / f'level{self.lv:02d}').glob('*.p3d')):
                try: r = _rd(f)
                except Exception: continue
                comp = next((c for c in r.children if c.id == 0x4512 and _st(c.data)[0] == a[0]), None)
                if comp is None: continue
                fx = [_st(e.data)[0] for l in comp.children for e in l.children if e.id == 0x4518]
                ok = any(n.encode() in G for n in fx if n); break
        self.add(ctx, op, src, fam, f'{a[0]} ({a[1] if len(a) > 1 else ""})', 'есть' if ok else 'нет',
                 f'coverage.py: {st}' + (f'; collect-l{self.lv}.shr' if ok else ''), '' if ok else 'летающий актёр не в пакете', short(a))

    def _voice(self, ctx, op, src, fam, a, conv):
        P = self.P; mission = ctx['mission'] if ctx['mission'] not in ('уровень', 'награды') else ''
        cands = [cv for cv in P.convs if self.S(cv[0]) == conv.lower()]
        cv = next((c for c in cands if self.S(c[1]) == mission), cands[0] if cands else None)
        if cv is None:
            self.add(ctx, op, src, fam, conv, 'нет', '', 'реплик нет в пакете миссий (на диске нет rsd)', short(a)); return
        sap = self.packs.get(self.packs.name(self.lv, 'audio/music.sap'), rd_sap) or set()
        sys.path.insert(0, str(self.root / 'tools'))
        from sound_export import voice_track_name
        files = [self.S(P.clips[i][0]) for i in range(cv[2], cv[2] + cv[3])]
        names = [voice_track_name(f) for f in files]
        got = [n for n in names if n and n.lower() in sap]
        miss = [f for f, n in zip(files, names) if not (n and n.lower() in sap)]
        self.add(ctx, op, src, fam, f'{conv} ({len(files)} реплик)', 'есть' if not miss else ('частично' if got else 'нет'),
                 f'music.sap: {len(got)}/{len(files)}' if got else '', ('нет дорожек: ' + ', '.join(m.rsplit('/', 1)[-1] for m in miss[:3])) if miss else '', short(a))
    def c_SetDialogueInfo(self, ctx, op, src, fam, a, locs, st):
        pl = PLAYER_OF_LEVEL.get(self.lv, 'homer')
        for who in (a[:2] if len(a) > 1 else a):
            w = who.lower()
            if not w: continue
            if w == pl:   # игрок уровня в разговоре
                if w != 'homer':
                    okp = bool(self._player_pack())
                    self.add(ctx, op, src, 'player', w + ' (в разговоре)', 'есть' if okp else 'частично', f'разговор идёт, модель игрока l{self.lv}/player.shr' if okp else 'разговор идёт (говорит Гомер-модель)', '' if okp else f'игрок уровня {w}: у порта Гомер', short(a))
                continue
            ok, ev = self._char(w)   # собеседник (и разговор двух персонажей без игрока: Пэтти и Сельма у гонок L1)
            self.add(ctx, op, src, 'npc', w + ' (в разговоре)', 'есть' if ok else 'нет', ev if ok else '', '' if ok else ev, short(a))
        if len(a) > 2: self._voice(ctx, op, src, fam, a, a[2])
    def c_SetCompletionDialog(self, ctx, op, src, fam, a, locs, st): self._voice(ctx, op, src, fam, a, a[0])

    def c_BindReward(self, ctx, op, src, fam, a, locs, st):
        name, kind, quest = a[0].lower(), (a[2].lower() if len(a) > 2 else ''), (a[3].lower() if len(a) > 3 else '')
        if kind == 'car':
            ph = self.packs.get(self.packs.name(self.lv, 'phonecars.txt'), rd_lower)
            ok = bool(ph) and name.encode() in ph
            self.add(ctx, op, src, fam, f'{name} ({quest})', 'есть' if ok else 'нет', f'{self.packs.name(self.lv, "phonecars.txt")} (будка)' if ok else '',
                     '' if ok else f'машина-награда уровня {self.lv}: нет в {self.packs.name(self.lv, "phonecars.txt")}', short(a))
        else:
            sk = self.packs.get(self.packs.name(self.lv, 'skins.txt'), rd_lower)
            ok = bool(sk) and name.encode() in sk
            self.add(ctx, op, src, fam, f'{name} ({quest})', 'есть' if ok else 'нет', f'{self.packs.name(self.lv, "skins.txt")} (гардероб)' if ok else '',
                     '' if ok else f'костюм уровня {self.lv}: нет в {self.packs.name(self.lv, "skins.txt")}', short(a))

    def c_SetCoinDrawable(self, ctx, op, src, fam, a, locs, st):
        self.add(ctx, op, src, fam, a[0], 'есть', f'coverage.py: {st}; монеты — модель порта coins.c (правило порта: имя не читается)', '', short(a))
    def c_SetParticleTexture(self, ctx, op, src, fam, a, locs, st):
        self.add(ctx, op, src, fam, f'{a[0]}: {a[1]}', 'есть' if st != 'ignored' else 'нет', f'coverage.py: {st} (fx_pack.py)', '', short(a))

    # -------------------------------------------------- компилятор: команды диска, не дошедшие до пакета
    def compile_drops(self, c):
        P = self.P
        have = Counter()
        for op, n, _, a0, line, f in P.cmds:
            have[(self.S(P.files[f]), line, CMD.SPECS[op - 1].name)] += 1
        for fi in P.files:
            fn = self.S(fi)
            if '#' in fn: continue
            p = GAME / 'scripts/missions' / fn
            if not p.exists(): continue
            calls, _ = mfk.parse_file(p, fn)
            for cl in calls:
                if cl.op not in FAM: continue
                if fn == 'rewards.mfk' and cl.op == 'BindReward' and (len(cl.args) < 5 or int(cl.args[4]) != self.lv): continue
                if have[(fn, cl.line, cl.op)] > 0: have[(fn, cl.line, cl.op)] -= 1; continue
                ctx = dict(mission='?', phase=fn, stage='-', obj='')
                self.add(ctx, cl.op, f'{fn}:{cl.line}', 'compile', short(cl.args), 'нет', '', 'компилятор не положил команду в пакет', short(cl.args))


_ROOMS = {}
def room_boxes(lv):
    """комнаты уровня — рамки мешей 0x10003 файлов art/l<N>i*.p3d диска -> [(файл, мин xyz, макс xyz)] в осях движка (z отражён)"""
    if lv not in _ROOMS:
        out = []
        for f in sorted((GAME / 'art').glob(f'l{lv}i*.p3d')):
            bbs = [struct.unpack_from('<6f', c.data) for c in p3d_walk(p3d_read(f)) if c.id == 0x10003 and len(c.data) >= 24]
            if not bbs: continue
            mn = [min(b[i] for b in bbs) for i in range(3)]; mx = [max(b[i + 3] for b in bbs) for i in range(3)]
            out.append((f.name, (mn[0] - 1, mn[1] - 3, -mx[2] - 1), (mx[0] + 1, mx[1] + 3, -mn[2] + 1)))
        _ROOMS[lv] = out
    return _ROOMS[lv]


def in_room(lv, pos):
    return next((n for n, a, b in room_boxes(lv) if all(a[i] <= pos[i] <= b[i] for i in range(3))), None)


_DISC = {}
def disc_has_name(lv, name):
    """имя (локатора) есть в каком-нибудь p3d уровня на диске? -> файл или None (art/missions/level0N, generic, зоны art/lN*)"""
    if lv not in _DISC:
        fs = sorted((GAME / f'art/missions/level0{lv}').glob('*.p3d')) + sorted((GAME / 'art/missions/generic').glob('*.p3d')) + \
             sorted((GAME / 'art').glob(f'l{lv}*.p3d'))
        _DISC[lv] = [(f, f.read_bytes().lower()) for f in fs]
    key = name.lower().encode()
    for f, b in _DISC[lv]:
        if key + b'\0' in b: return str(f.relative_to(GAME))
    return None


def short(a):
    s = ', '.join(str(x) for x in a)
    return s if len(s) <= 90 else s[:87] + '…'


MC_FILES = MC.FileIndex(GAME)


# ------------------------------------------------------------------ вывод
def summarize(rows):
    fam = defaultdict(lambda: dict(n=0, bad=0, part=0, lv=Counter(), what=Counter()))
    for r in rows:
        f = fam[r['fam']]; f['n'] += 1
        if r['ok'] == 'нет': f['bad'] += 1; f['lv'][r['level']] += 1
        elif r['ok'] == 'частично': f['part'] += 1; f['lv'][r['level']] += 1
        if r['ok'] != 'есть':
            f['what'][re.sub(r'\b[a-z0-9_]+\.(?:p3d|shr|bin|smv|chr)\b', '…', re.sub(r'«[^»]*»', '«…»', (r['miss'] or '?').split(';')[0]))] += 1
    return fam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=str(ROOT0), help='дерево порта (движок viewer/, tools/ship_files.sh, build/)')
    ap.add_argument('--use', action='append', default=[], help='имя=файл: подменить пакет выпуска')
    ap.add_argument('--tsv'); ap.add_argument('--doc'); ap.add_argument('--check'); ap.add_argument('--brief', action='store_true')
    ap.add_argument('--level', type=int, action='append')
    ap.add_argument('--grouped', help='сжатая таблица всех строк (одинаковые по уровню/миссии/фазе/команде/ресурсу — одной строкой с этапами)')
    ap.add_argument('--compare', help='TSV прежнего прогона (--tsv): колонка «не хватало» в документе и список починенного')
    a = ap.parse_args()
    root = Path(a.root).resolve()
    C = Census(root, a.use)
    for lv in (a.level or LEVELS): C.level(lv)
    rows = C.rows
    fam = summarize(rows)
    head = 'уровень\tмиссия\tфаза\tэтап\tцель\tкоманда\tресурс\tесть у порта\tулика\tчего нет\tсемейство\tисточник\tаргументы'
    if a.tsv:
        Path(a.tsv).parent.mkdir(parents=True, exist_ok=True)
        with open(a.tsv, 'w') as f:
            f.write('# сгенерировано tools/missions/census.py — не править руками\n' + head + '\n')
            for r in rows:
                f.write('\t'.join(str(r[k]).replace('\t', ' ') for k in ('level', 'mission', 'phase', 'stage', 'obj', 'cmd', 'res', 'ok', 'ev', 'miss', 'fam', 'src', 'args')) + '\n')
    tot = len(rows); bad = sum(1 for r in rows if r['ok'] != 'есть')
    print(f'строк {tot}; не хватает (нет/частично) {bad}')
    for k, f in sorted(fam.items(), key=lambda x: -(x[1]['bad'] + x[1]['part'])):
        print(f"  {k:8s} {FAM_RU.get(k, k)[:46]:46s} строк {f['n']:5d}  нет {f['bad']:4d}  частично {f['part']:4d}  по уровням "
              + ' '.join(f'L{n}={f["lv"][n]}' for n in LEVELS if f['lv'][n]))
        if not a.brief:
            for w, n in f['what'].most_common(4): print(f'           {n:4d} × {w[:150]}')
    old = read_tsv(Path(a.compare)) if a.compare else None
    if a.grouped: write_grouped(Path(a.grouped), rows)
    if a.doc: write_doc(Path(a.doc), rows, fam, old, a)
    if a.check:
        want = {}
        for ln in Path(a.check).read_text().splitlines():
            if not ln.strip() or ln.startswith('#'): continue
            k, v = ln.split('\t')[:2]; want[k] = int(v)
        fails = []
        for k, lim in want.items():
            n = fam[k]['bad'] + fam[k]['part'] if k in fam else 0
            if n > lim: fails.append(f'{k}: не хватает {n} > {lim}')
        for k in fam:
            if k not in want and fam[k]['bad'] + fam[k]['part']: fails.append(f'{k}: новое семейство с пропусками ({fam[k]["bad"] + fam[k]["part"]})')
        for x in fails: print('FAIL', x)
        print('RESULT:', 'FAIL' if fails else 'PASS')
        return 1 if fails else 0
    return 0


COLS = ('level', 'mission', 'phase', 'stage', 'obj', 'cmd', 'res', 'ok', 'ev', 'miss', 'fam', 'src', 'args')


def read_tsv(path):
    out = []
    for ln in path.read_text().splitlines():
        if ln.startswith('#') or ln.startswith('уровень\t'): continue
        v = ln.split('\t'); r = Row(zip(COLS, v + [''] * (len(COLS) - len(v)))); r['level'] = int(r['level']); out.append(r)
    return out


def group(rows, keys=('level', 'mission', 'phase', 'cmd', 'res', 'ok', 'miss', 'fam')):
    g = {}
    for r in rows:
        k = tuple(r[x] for x in keys)
        if k not in g: g[k] = dict(r, stages=[], n=0)
        e = g[k]; e['n'] += 1
        if r['stage'] not in e['stages']: e['stages'].append(r['stage'])
    return list(g.values())


def write_grouped(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        f.write('# сгенерировано tools/missions/census.py --grouped — не править руками; одинаковые строки (уровень, миссия, фаза, команда, '
                'ресурс, итог) сведены, «этапы» — где встречается, «раз» — сколько вызовов\n')
        f.write('уровень\tмиссия\tфаза\tэтапы\tкоманда\tресурс\tесть у порта\tулика\tчего нет\tсемейство\tраз\tпервый источник\n')
        for e in group(rows):
            f.write('\t'.join(str(x).replace('\t', ' ') for x in (e['level'], e['mission'], e['phase'], ','.join(e['stages']), e['cmd'], e['res'],
                                                                e['ok'], e['ev'], e['miss'], e['fam'], e['n'], e['src'])) + '\n')


def md(s): return str(s).replace('|', '\\|').replace('\n', ' ')


def write_doc(path, rows, fam, old, a):
    import datetime
    now = subprocess.run(['date', '+%Y-%m-%d %H:%M'], capture_output=True, text=True).stdout.strip()
    ofam = summarize(old) if old else {}
    L = []
    L.append(f'Сгенерировано `tools/missions/census.py` {now} (время — `date`): строк {len(rows)}, не хватает (нет/частично) '
             f'{sum(1 for r in rows if r["ok"] != "есть")}' + (f'; в прежнем экспорте — {sum(1 for r in old if r["ok"] != "есть")}' if old else '') + '.')
    L.append('')
    L.append('### Сводка по семействам')
    L.append('')
    L.append('| семейство | что | строк | не хватало (прежний экспорт) | не хватает (сейчас) | по уровням (сейчас) | главная причина |')
    L.append('|---|---|---:|---:|---:|---|---|')
    for k, f in sorted(fam.items(), key=lambda x: (-(x[1]['bad'] + x[1]['part']), x[0])):
        o = ofam.get(k); on = (o['bad'] + o['part']) if o else 0
        why = f['what'].most_common(1)[0][0] if f['what'] else ''
        L.append(f"| {k} | {md(FAM_RU.get(k, k))} | {f['n']} | {on if old else '—'} | {f['bad'] + f['part']} | "
                 + ' '.join(f'L{n} {f["lv"][n]}' for n in LEVELS if f['lv'][n]) + f' | {md(why[:110])} |')
    L.append('')
    if old:   # починено: строки, которых не хватало раньше и которые есть сейчас (ключ без улики)
        key = lambda r: (r['level'], r['mission'], r['phase'], r['stage'], r['cmd'], r['res'])
        now_ok = {key(r) for r in rows if r['ok'] == 'есть'}
        fixed = [r for r in old if r['ok'] != 'есть' and key(r) in now_ok]
        L.append(f'### Починено этой переписью — {len(fixed)} строк')
        L.append('')
        L.append('| семейство | уровни | строк | было «чего нет» |')
        L.append('|---|---|---:|---|')
        byf = defaultdict(list)
        for r in fixed: byf[r['fam']].append(r)
        for k, lst in sorted(byf.items(), key=lambda x: -len(x[1])):
            lv = Counter(r['level'] for r in lst); w = Counter(re.sub(r'\b[a-z0-9_]+\.(?:p3d|shr|bin|smv|chr)\b', '…', (r['miss'] or '?').split(';')[0]) for r in lst)
            L.append(f'| {k} | ' + ' '.join(f'L{n} {lv[n]}' for n in LEVELS if lv[n]) + f' | {len(lst)} | {md(w.most_common(1)[0][0][:110])} |')
        L.append('')
    L.append('### Уровни × семейства — сколько строк «нет / частично» сейчас')
    L.append('')
    fams = sorted(k for k in fam if fam[k]['bad'] + fam[k]['part'])
    L.append('| уровень | ' + ' | '.join(fams) + ' |'); L.append('|---' * (len(fams) + 1) + '|')
    for n in LEVELS: L.append(f'| L{n} | ' + ' | '.join(str(fam[k]['lv'][n] or '') for k in fams) + ' |')
    L.append('')
    L.append('### Чего не хватает — все строки (одинаковые сведены; этапы — номера этапов фазы, «загрузка» — список mXl/mXsdl)')
    L.append('')
    L.append('| уровень | миссия | фаза | этапы | команда | ресурс | есть у порта (улика) | чего нет | раз |')
    L.append('|---|---|---|---|---|---|---|---|---:|')
    WIDE = ('player', 'effect', 'room', 'driver', 'reward')   # массовые семейства — одной строкой на уровень и команду (миссии перечислены)
    gaps = group([r for r in rows if r['ok'] != 'есть' and r['fam'] not in WIDE])
    gaps.sort(key=lambda e: (e['level'], e['mission'], e['phase'], e['cmd'], e['res']))
    for e in gaps:
        L.append(f"| L{e['level']} | {md(e['mission'])} | {md(e['phase'])} | {md(','.join(e['stages']))} | {md(e['cmd'])} | {md(e['res'])} | "
                 f"{md(e['ok'])}: {md(e['ev'][:120])} | {md(e['miss'][:160])} | {e['n']} |")
    wide = {}
    for r in rows:
        if r['ok'] == 'есть' or r['fam'] not in WIDE: continue
        res = r['cmd'] if r['fam'] in ('room', 'driver', 'reward') else re.sub(r' \(.*\)$', '', r['res'])
        k = (r['fam'], r['level'], r['cmd'], res, re.sub(r'уровня \d', 'уровня N', r['miss']))
        e = wide.setdefault(k, dict(r, ms=[], n=0)); e['n'] += 1
        if r['mission'] not in e['ms']: e['ms'].append(r['mission'])
    for (f_, lv, cmd, res, miss), e in sorted(wide.items()):
        what = res if f_ not in ('room', 'driver', 'reward') else ('точки: ' if f_ == 'room' else '') + ', '.join(sorted({x['res'].split(' y=')[0] for x in rows if x['fam'] == f_ and x['level'] == lv and x['cmd'] == cmd and x['ok'] != 'есть'}))[:200]
        L.append(f"| L{lv} | {md(', '.join(e['ms']))} | все фазы | — | {md(cmd)} | {md(what)} | {md(e['ok'])}: {md(e['ev'][:120])} | {md(miss[:160])} | {e['n']} |")
    L.append('')
    # что есть: по миссиям — строк «есть» из всех по семействам
    L.append('### Есть у порта — по миссиям (строк «есть» / всего; семейства, где миссия что-то ставит)')
    L.append('')
    per = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        c = per[(r['level'], r['mission'])][r['fam']]; c[1] += 1; c[0] += r['ok'] == 'есть'
    fl = [k for k in ('marker', 'item', 'icon', 'brief', 'load', 'npc', 'car', 'cam', 'voice', 'race', 'gag', 'effect', 'driver', 'player', 'reward', 'sprop', 'fmv', 'wasp', 'misc', 'locator', 'cap') if k in fam]
    L.append('| уровень | миссия | ' + ' | '.join(fl) + ' |'); L.append('|---' * (len(fl) + 2) + '|')
    for (lv, ms), d in sorted(per.items(), key=lambda x: (x[0][0], x[0][1])):
        L.append(f'| L{lv} | {md(ms)} | ' + ' | '.join((f'{d[k][0]}/{d[k][1]}' if d[k][1] else '') for k in fl) + ' |')
    L.append('')
    gen = '\n'.join(L)
    text = path.read_text() if path.exists() else '# Миссии: полнота\n\n<!-- GEN:census -->\n<!-- /GEN:census -->\n'
    a0, a1 = text.index('<!-- GEN:census -->'), text.index('<!-- /GEN:census -->')
    path.write_text(text[:a0] + '<!-- GEN:census -->\n' + gen + '\n' + text[a1:])


if __name__ == '__main__':
    sys.exit(main())
