#!/usr/bin/env python3
"""Песочница уровня на Маке (пакет «рецепт уровней 2–7», docs/РЕЦЕПТ_УРОВНЯ.md §5): одна команда проверяет, что уровень N
собран из СВОИХ данных диска и играется ботами без экрана (tools/bots, тот же C-код, что EBOOT). Без AI и сети, PSP не нужна.

  python3 tools/sandbox/level_check.py --level 1                 все стадии: disk, shr, packs, bots (миссии по базе lN)
  python3 tools/sandbox/level_check.py --level 3 --stages disk   только данные диска (без сборки, ~10 с)
  python3 tools/sandbox/level_check.py --level 1 --missions all  все миссии уровня (долго: ~5–10 мин на миссию, параллельно --procs)
  python3 tools/sandbox/level_check.py --level 1 --gate          гейт: заведомо плохие входы обязаны дать FAIL, настоящий — PASS
  --shr / --msn / --roads / --collect / --interiors / --traffic ПУТЬ   подменить вход (так делаются отрицательные контроли)
  --baseline-write                                               записать итог миссий в tools/sandbox/baseline/lN.tsv

Стадии (каждая — строки PASS / WARN / FAIL; итог FAIL, если есть хоть один FAIL):
  disk   данные диска уровня: файлы сцен/скриптов/Scrooby/музыки есть, всё, что грузят level.mfk/leveli.mfk, есть на диске,
         локатор старта level{N}_carstart найден, все команды скриптов известны компилятору миссий; справка: новые типы
         чанков против уровня 1 и типы без обработчика (docs/state/handlers.tsv) — WARN, не FAIL
  shr    level.shr: заголовок SHR7, секции PVS1/COL1/PRP2/CAR1 на месте; ПРИНАДЛЕЖНОСТЬ уровню N: старт в заголовке совпадает
         с локатором старта или точкой AddTeleportDest уровня N, под стартом и под точками телепорта есть земля карты высот
  packs  спутники уровня: миссии MSN1 (номер уровня в заголовке, число миссий = AddMission+AddBonusMission в level.mfk),
         карточки/осы/гэги CLT1 (номер уровня), комнаты SHI1 (комнат = файлов l{N}i*.p3d), трафик TRF1 (машины и пешеходы =
         leveli.mfk), дороги ботов (отрезки лежат на земле этого level.shr), звук SAP1/SAB1 и атмосфера (все ворота уровня
         привязаны к регионам ambience.rms), интерфейс UIP1 (радар l{N}hudmap на дорогах уровня, фон паузы ingamel{N}),
         камеры зон ZCM1, частицы FXP1, значки заданий MSA2, Гомер CHR1
  bots   игра без экрана: game_headless --selftest (детерминизм, сохранить/загрузить) + миссионер по миссиям из базы
         tools/sandbox/baseline/lN.tsv (что уже проходилось, обязано проходиться; регрессия = FAIL), остальное — «до идеала»
Итог: build/sandbox/level_check/lN/<время>/report.md + report.json; последняя строка stdout «RESULT: PASS|FAIL»; код 0/1."""
import argparse, collections, concurrent.futures, json, os, re, shutil, struct, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / 'hit-and-run-web/source/game'
ART = GAME / 'art'
SCR = GAME / 'scripts/missions'
BUILD = ROOT / 'build'
BIN = Path(os.environ.get('BOTS_BIN', BUILD / 'bots'))
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'tools/missions')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
sys.path.insert(0, str(ROOT / 'tests/levels'))   # проверки уровня: атмосфера, радар/пауза, трафик (29.09)

# ---------------------------------------------------------------- где лежат собранные данные уровня
# Уровень 1 — как сейчас кладёт tools/ship.sh (имена рядом с EBOOT); уровни 2–7 — tools/build_all_levels.sh (build/levels/lN/)
# и экспортёры с --level N. Первый существующий путь побеждает; какой взят — пишется в отчёт.
def candidates(n):
    L = BUILD / 'levels' / f'l{n}'
    one = n == 1
    return {
        'shr': ([BUILD / 'level.shr'] if one else []) + [L / 'level.shr'],
        'msn': [L / f'missions/level{n:02d}.msn', BUILD / f'missions/level{n:02d}.msn'] if not one else [BUILD / 'missions/level01.msn', L / 'missions/level01.msn'],
        'collect': [BUILD / f'collect-l{n}.shr', L / f'collect-l{n}.shr'],
        'interiors': [BUILD / f'interiors-l{n}.bin', L / f'interiors-l{n}.bin'],
        'interiors_gfx': [BUILD / f'interiors-l{n}-gfx.bin', L / f'interiors-l{n}-gfx.bin'],
        'traffic': ([BUILD / 'traffic.shr'] if one else []) + [L / 'traffic.shr'],
        'roads': [BUILD / f'sandbox/roads-l{n}.bin', L / f'roads-l{n}.bin'],
        'music': ([BUILD / 'audio/music.sap'] if one else []) + [L / 'audio/music.sap'],
        'sfx': ([BUILD / 'audio/sfx.sab'] if one else []) + [L / 'audio/sfx.sab'],
        'ui': [BUILD / ('ui.shr' if one else f'ui_l{n}.shr'), L / ('ui.shr' if one else f'ui_l{n}.shr'), L / 'ui.shr'],
        'homer': [BUILD / 'homer.shr'],
        'zonecam': [BUILD / f'zonecam-l{n}.shr', L / f'zonecam-l{n}.shr'],
        'fx': ([BUILD / 'fx.shr'] if one else []) + [L / 'fx.shr'],
        'msnart': ([BUILD / 'msnart.shr'] if one else []) + [L / 'msnart.shr'],
        'msncars': [BUILD / f'msncars-l{n}.shr', L / f'msncars-l{n}.shr'],   # кузова и ходовые машин миссий (MCR1)
    }
HOW = {   # чем собрать, если нет (для отчёта; флаги качества уровня — закон 1)
    'shr': 'LEVEL={n} tools/build_level.sh build/levels/l{n}/level.shr',
    'msn': 'python tools/missions/compile.py --level {n} --out build/levels/l{n}/missions',
    'collect': 'python tools/collect_export.py --level {n}',
    'interiors': 'python tools/interior_export.py --level {n}', 'interiors_gfx': 'python tools/interior_export.py --level {n}',
    'traffic': 'SHR_TEX_CAP256=1 SHR_SMALL_MIPS=1 SHR_LAYERS=1 python tools/traffic_export.py --level {n} --out build/levels/l{n}/traffic.shr',
    'roads': 'python tools/cartest/roads.py --level {n} --out build/sandbox/roads-l{n}.bin',
    'music': 'python tools/sound_export.py --level {n} --out build/levels/l{n}/audio', 'sfx': 'python tools/sound_export.py --level {n} --out build/levels/l{n}/audio',
    'ui': 'LEVEL={n} python tools/ui_export.py', 'homer': 'python tools/homer_export.py',
    'zonecam': 'python tools/zonecam_export.py --level {n}', 'fx': 'python tools/fx_pack.py --level {n}',
    'msnart': 'python tools/msnart_export.py --level {n}',
    'msncars': 'python tools/msncar_export.py --level {n}',
}


class Report:
    def __init__(self): self.rows = []
    def add(self, stage, status, what, detail=''):
        what, detail = (str(s).replace(str(ROOT) + '/', '') for s in (what, detail))   # пути — от корня проекта
        self.rows.append(dict(stage=stage, status=status, what=what, detail=str(detail)))
        print(f'  {stage:5} {status:4} {what}' + (f' — {detail}' if detail else ''), flush=True)
    def ok(self, st, w, d=''): self.add(st, 'PASS', w, d)
    def warn(self, st, w, d=''): self.add(st, 'WARN', w, d)
    def fail(self, st, w, d=''): self.add(st, 'FAIL', w, d)
    def check(self, st, cond, w, d=''): (self.ok if cond else self.fail)(st, w, d); return cond
    @property
    def failed(self): return any(r['status'] == 'FAIL' for r in self.rows)


# ---------------------------------------------------------------- данные диска
def disk_files(n):
    """Файлы уровня N на диске по ролям (как их берут экспортёры: psp_export l{N}_terra/r*/z*, interior_export l{N}i*)."""
    arts = sorted(p.name for p in ART.glob('*.p3d') if re.match(rf'l0?{n}[_a-z0-9]', p.name))
    return dict(
        terra=[a for a in arts if a == f'l{n}_terra.p3d'],
        regions=[a for a in arts if re.fullmatch(rf'l{n}r\d+[a-z_]*\.p3d', a)],
        zones=[a for a in arts if re.fullmatch(rf'l{n}z\d+\.p3d', a)],
        interiors=[a for a in arts if re.fullmatch(rf'l{n}i\d+\.p3d', a)],
        race_props=[a for a in arts if re.fullmatch(rf'l{n}_sr\d+p\.p3d', a)],
        fx=[a for a in arts if a == f'l0{n}_fx.p3d'],
        other=[a for a in arts if not re.fullmatch(rf'(l{n}_terra|l{n}r\d+[a-z_]*|l{n}z\d+|l{n}i\d+|l{n}_sr\d+p|l0{n}_fx)\.p3d', a)],
        mission_art=sorted(p.name for p in (ART / f'missions/level{n:02d}').glob('*.p3d')),
        scripts=sorted(p.name for p in (SCR / f'level{n:02d}').glob('*.mfk')),
    )


def chunk_ids(n, cache_f):
    """id чанков во всех p3d уровня N (art/l{N}*, art/l0{N}_fx, art/missions/level0N) — кэш по размеру/времени файла."""
    from p3d import read
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    files = [p for p in ART.glob('*.p3d') if re.match(rf'l0?{n}[_a-z0-9]', p.name)] + sorted((ART / f'missions/level{n:02d}').glob('*.p3d'))
    got = collections.Counter(); changed = False
    for f in files:
        st = f.stat(); key = f'{f.relative_to(ART)}:{st.st_size}:{int(st.st_mtime)}'
        if key not in cache:
            c = collections.Counter()
            def walk(ch):
                c[ch.id] += 1
                for k in ch.children: walk(k)
            walk(read(f)); cache[key] = {hex(k): v for k, v in c.items()}; changed = True
        for k, v in cache[key].items(): got[k] += v
    if changed: cache_f.parent.mkdir(parents=True, exist_ok=True); cache_f.write_text(json.dumps(cache))
    return got


def stage_disk(n, R, work):
    import mfk
    D = disk_files(n)
    R.check('disk', len(D['terra']) == 1, f'l{n}_terra.p3d', 'нет файла' if not D['terra'] else '')
    R.check('disk', len(D['regions']) > 0 and len(D['zones']) > 0, 'районы r* и зоны z*', f"r {len(D['regions'])}: {' '.join(D['regions'])}; z {len(D['zones'])}")
    R.check('disk', len(D['fx']) == 1, f'l0{n}_fx.p3d (эффекты уровня)')
    need = [ART / f'missions/level{n:02d}/level.p3d', SCR / f'level{n:02d}/level.mfk', SCR / f'level{n:02d}/leveli.mfk',
            ART / f'frontend/scrooby/resource/pure3d/l{n}hudmap.p3d', ART / f'frontend/scrooby/ingamel{n}.p3d',
            GAME / f'sound/music/l{n}_music.rms', GAME / f'sound/scripts/level{n}.spt']
    miss = [str(p.relative_to(GAME)) for p in need if not p.exists()]
    R.check('disk', not miss, 'level.p3d, level.mfk/leveli.mfk, радар l{N}hudmap, пауза ingamel{N}, музыка l{N}_music.rms, level{N}.spt',
            ('нет: ' + ', '.join(miss)) if miss else '')
    R.ok('disk', 'состав', f"комнаты {D['interiors']}, реквизит гонок {D['race_props']}, прочее {D['other']}, "
                           f"миссионный арт {len(D['mission_art'])}, скриптов {len(D['scripts'])}")
    # всё, что грузят скрипты уровня, есть на диске (без учёта регистра, пути как в скриптах)
    lower = {}
    for p in (GAME / 'art').rglob('*'):
        if p.is_file(): lower[str(p.relative_to(GAME)).lower().replace('/', '\\')] = p
    lv, _ = mfk.parse((SCR / f'level{n:02d}/level.mfk').read_text(errors='replace'))
    li, _ = mfk.parse((SCR / f'level{n:02d}/leveli.mfk').read_text(errors='replace'))
    loads = [str(c.args[0]) for c in lv + li if c.op in ('LoadP3DFile', 'LoadDisposableCar') and c.args]
    lm = sorted({f for f in loads if f.lower().replace('/', '\\') not in lower})
    R.check('disk', not lm, f'LoadP3DFile/LoadDisposableCar уровня: {len(loads)} путей на диске', ('нет: ' + ', '.join(lm)) if lm else '')
    zones = sorted({z for c in lv if c.op == 'AddTeleportDest' and len(c.args) > 4 for z in str(c.args[4]).split(';') if z})
    zm = [z for z in zones if not (ART / z).exists()]
    R.check('disk', not zm, f'зоны AddTeleportDest ({len(zones)}) есть в art/', ('нет: ' + ', '.join(zm)) if zm else '')
    ms = [str(c.args[0]) for c in lv if c.op == 'AddMission']; bms = [str(c.args[0]) for c in lv if c.op == 'AddBonusMission']
    R.ok('disk', 'миссии level.mfk', f"сюжет {ms}, бонус/гонки {bms}")
    # старт уровня: InitLevelPlayerVehicle -> локатор (tools/level_sweep.find_spawn)
    from level_sweep import find_spawn
    sp = find_spawn(n)
    R.check('disk', 'error' not in sp, f"старт {sp.get('locator')}: машина {sp.get('car')}", sp.get('error') or f"{sp.get('pos')} курс {sp.get('heading')}")
    # все команды скриптов уровня известны компилятору миссий (tools/missions/commands.py)
    ops = collections.Counter()
    for p in sorted((SCR / f'level{n:02d}').glob('*.mfk')):
        for c in mfk.parse(p.read_text(errors='replace'))[0]: ops[c.op] += 1
    src = (ROOT / 'tools/missions/commands.py').read_text()
    unknown = sorted(o for o in ops if o not in src)
    R.check('disk', not unknown, f'команды скриптов ({len(ops)} видов) известны компилятору', ('нет: ' + ', '.join(unknown)) if unknown else '')
    if n != 1:
        ops1 = collections.Counter()
        for p in sorted((SCR / 'level01').glob('*.mfk')):
            for c in mfk.parse(p.read_text(errors='replace'))[0]: ops1[c.op] += 1
        new = {o: ops[o] for o in sorted(set(ops) - set(ops1))}
        (R.warn if new else R.ok)('disk', 'команды, которых нет на уровне 1 (новые механики — движку)', new or 'нет')
    # чанки
    import tablo
    H = tablo.handlers(); ids = chunk_ids(n, work / 'chunk-ids.json')
    unh = sorted(k for k in ids if not H.get(k, 'нет').startswith(('обработчик', 'проигнорировано')))
    R.warn('disk', f'типы чанков без обработчика (docs/state/handlers.tsv): {len(unh)} из {len(ids)}', ' '.join(unh[:40]))
    if n != 1:
        ids1 = chunk_ids(1, work.parent.parent / 'l1' / 'chunk-ids.json')
        new = {k: ids[k] for k in sorted(set(ids) - set(ids1))}
        (R.warn if new else R.ok)('disk', 'типы чанков, которых нет на уровне 1', new or 'нет')
    return dict(files=D, spawn=sp, ops=dict(ops), missions=ms, bonus=bms, loads=len(loads))


# ---------------------------------------------------------------- level.shr
def parse_shr(path):
    """Только то, что нужно проверке: заголовок SHR7 (docs/FORMAT_SHR7.md), карта высот, счётчики COL1 и PVS1.
    (tools/level_sweep.parse_shr разбирает и текстуры по старой раскладке — на нынешних файлах падает.)"""
    import numpy as np
    d = Path(path).read_bytes()
    bb = struct.unpack_from('<6f', d, 12); spawn = struct.unpack_from('<4f', d, 36)
    hox, hoz, cell = struct.unpack_from('<3f', d, 56); W, H = struct.unpack_from('<II', d, 68)
    pvsoff, coloff = struct.unpack_from('<II', d, 88)
    if 104 + W * H * 8 > len(d): raise ValueError(f'карта высот {W}x{H} не помещается в файл')
    pw, ph, _ = struct.unpack_from('<III', d, pvsoff + 16)
    ent = np.frombuffer(d, '<u4', pw * ph * 2, pvsoff + 32).reshape(-1, 2)
    cW, cH, ntri, nbox, ncyl, nseg, nref = struct.unpack_from('<7I', d, coloff + 16)
    return dict(bbox=bb, spawn=spawn, hox=hox, hoz=hoz, cell=cell, W=W, H=H,
                hm=np.frombuffer(d, '<i2', W * H * 4, 104).reshape(H, W, 4),
                pvs=dict(cells_with_data=int((ent[:, 1] != 0xFFFFFFFF).sum())),
                col=dict(tris=ntri, boxes=nbox, cyls=ncyl, fences=nseg))


def ground_at(S, x, z):
    gx, gz = int((x - S['hox']) / S['cell']), int((z - S['hoz']) / S['cell'])
    if not (0 <= gx < S['W'] and 0 <= gz < S['H']): return None
    h = S['hm'][gz, gx]; return (h[h != -32768] * .01).tolist()


def stage_shr(n, R, shr, spawn):
    if not shr or not Path(shr).exists():
        R.fail('shr', 'level.shr уровня', f'нет файла; собрать: {HOW["shr"].format(n=n)}'); return None
    d = Path(shr).read_bytes()
    if not R.check('shr', d[:4] == b'SHR7' and len(d) > 104, f'заголовок SHR7 ({shr})', f'{len(d) / 2**20:.1f} МБ'): return None
    off = dict(zip(('pieces', 'ncell', 'cells', 'PVS1', 'COL1', 'PRP2', 'CAR1'), struct.unpack_from('<7I', d, 76)))
    bad = []
    for k in ('pieces', 'cells'):
        if not (104 < off[k] < len(d)): bad.append(f'{k}@{off[k]}')
    for k in ('PVS1', 'COL1', 'PRP2', 'CAR1'):
        if not (0 < off[k] < len(d) - 4) or d[off[k]:off[k] + 4] != k.encode(): bad.append(f'{k}@{off[k]}')
    if not R.check('shr', not bad and off['ncell'] > 0, 'секции PVS1 / COL1 / PRP2 / CAR1 на месте', ('битые: ' + ', '.join(bad)) if bad else f"клеток {off['ncell']}"):
        return None
    try:
        S = parse_shr(shr)
    except Exception as e:
        R.fail('shr', 'разбор level.shr', repr(e)); return None
    col = S['col'] or {}
    R.check('shr', col.get('tris', 0) + col.get('boxes', 0) > 0 and (S['pvs'] or {}).get('cells_with_data', 0) > 0,
            'коллизия и видимость не пустые', f"COL1 треуг. {col.get('tris')}, коробок {col.get('boxes')}, цилиндров {col.get('cyls')}; PVS клеток с данными {(S['pvs'] or {}).get('cells_with_data')}")
    # принадлежность уровню N: старт — из данных уровня N (локатор старта или точка телепорта level.mfk)
    sx, sy, sz, sh = S['spawn']
    cands = []
    if 'pos' in spawn: cands.append(('локатор ' + spawn['locator'], spawn['pos']))
    cands += [('телепорт ' + t[0], t[1:]) for t in spawn.get('teleports', [])]
    best = min(cands, key=lambda c: (c[1][0] - sx) ** 2 + (c[1][2] - sz) ** 2) if cands else None
    dist = ((best[1][0] - sx) ** 2 + (best[1][2] - sz) ** 2) ** .5 if best else 1e9
    R.check('shr', dist <= 1.5, 'старт в заголовке — из данных уровня', f'({sx:.1f}, {sy:.1f}, {sz:.1f}) курс {sh:.2f}; ближайшее: {best[0] if best else "—"}, {dist:.1f} м (допуск 1.5)')
    g = ground_at(S, sx, sz) or []
    R.check('shr', any(abs(v - sy) <= 1.0 for v in g), 'под стартом земля карты высот (±1 м)', f'слои {[round(v, 2) for v in g]}')
    tel = spawn.get('teleports', []); onground = 0
    for _, x, y, z in tel:
        gg = ground_at(S, x, z) or []
        if any(abs(v - y) <= 3.0 for v in gg): onground += 1
    R.check('shr', tel and onground >= 0.8 * len(tel), 'точки телепорта уровня стоят на земле этого файла (≥80%, ±3 м)', f'{onground} из {len(tel)}')
    return S


# ---------------------------------------------------------------- спутники
def stage_packs(n, R, paths, disk, S):
    def need(k, magic):
        p = paths.get(k)
        if not p or not Path(p).exists():
            R.fail('packs', f'{k}', f'нет файла; собрать: {HOW[k].format(n=n)}'); return None
        b = Path(p).read_bytes()
        if magic and b[:4] != magic:
            R.fail('packs', f'{k} {p}', f'магия {b[:4]!r}, ждём {magic!r}'); return None
        return b
    b = need('msn', b'MSN1')
    if b:
        ver, lvl = struct.unpack_from('<HH', b, 4); size, = struct.unpack_from('<I', b, 8)
        nmis, = struct.unpack_from('<I', b, 16 + 6 * 8 + 4); nstage, = struct.unpack_from('<I', b, 16 + 8 * 8 + 4)
        want = len(disk['missions']) + len(disk['bonus']) if disk else None
        R.check('packs', ver == 2 and lvl == n and size == len(b) and nmis > 0 and nstage > 0 and (want is None or nmis == want),
                f"миссии MSN1 ({paths['msn']})", f'версия {ver}, уровень {lvl}, миссий {nmis} (в level.mfk {want}), стадий {nstage}')
    b = need('collect', b'CLT1')
    if b:
        ver, lvl = struct.unpack_from('<II', b, 4)
        R.check('packs', lvl == n, f"карточки/осы/гэги CLT1 ({paths['collect']})", f'уровень {lvl}')
    b = need('interiors', b'SHI1')
    if b:
        nroom, ndoor, ver = struct.unpack_from('<3I', b, 4)
        want = len(disk['files']['interiors']) if disk else None
        R.check('packs', want is None or nroom == want, f"комнаты SHI1 ({paths['interiors']})", f'комнат {nroom} (файлов l{n}i*.p3d {want}), дверей {ndoor}')
    need('interiors_gfx', b'SHG1') and R.ok('packs', f"рисунок комнат SHG1 ({paths['interiors_gfx']})")
    if need('traffic', b'TRF1'):   # номера уровня в TRF1 нет — принадлежность по составу (tests/levels/traffic_level_check.py)
        import traffic_level_check as TLC
        bad = TLC.check(n, paths['traffic'])
        R.check('packs', not bad, f"трафик TRF1 ({paths['traffic']}): машины и пешеходы = leveli.mfk уровня", '; '.join(bad)[:300])
    b = need('roads', b'')
    if b is not None:
        import numpy as np
        ok = len(b) % 28 == 0 and len(b) > 0
        R_ = np.frombuffer(b[:len(b) - len(b) % 28], '<f4').reshape(-1, 7) if ok else None
        if ok and S is not None:
            mid = (R_[:, 0:3] + R_[:, 3:6]) / 2; hit = 0
            for x, y, z in mid:
                gg = ground_at(S, float(x), float(z)) or []
                if any(abs(v - y) <= 2.0 for v in gg): hit += 1
            R.check('packs', hit >= 0.9 * len(mid), f"дороги ботов ({paths['roads']}) лежат на земле level.shr (≥90%, ±2 м)", f'{hit} из {len(mid)}')
        else: R.check('packs', ok, f"дороги ботов ({paths['roads']})", f'{len(b)} Б, отрезков {len(b) // 28}')
    need('music', b'SAP1') and R.warn('packs', f"музыка SAP1 ({paths['music']})", 'номера уровня в файле нет; роли музыки — из композиции l<N>_music.rms (sound_export.music_table)')
    need('sfx', b'SAB1') and R.ok('packs', f"звуки SAB1 ({paths['sfx']})")
    if paths.get('music') and Path(paths['music']).exists() and paths.get('sfx') and Path(paths['sfx']).exists():
        import ambience_check as AC, sound_export as SE   # атмосфера: ворота уровня -> регионы ambience.rms (tests/levels/ambience_check.py)
        bad = AC.check(n, paths['music'], SE.ambience_map(), paths['sfx'])
        R.check('packs', not bad, 'атмосфера: все ворота уровня привязаны к дорожкам регионов ambience.rms', '; '.join(bad[:3])[:300])
    if need('ui', b'UIP1'):   # радар l<N>hudmap ложится на дороги уровня; фон паузы — PauseBgd.pag ingamel<N> (tests/levels/hud_level_check.py)
        R.ok('packs', f"интерфейс UIP1 ({paths['ui']})")
        if paths.get('roads') and Path(paths['roads']).exists():
            import hud_level_check as HLC
            bad = HLC.check(n, paths['ui'], paths['roads'])
            R.check('packs', not bad, 'интерфейс уровня: радарная карта на дорогах уровня, фон паузы из ingamel<N>', '; '.join(bad)[:300])
    need('zonecam', b'ZCM1') and R.ok('packs', f"камеры зон ZCM1 ({paths['zonecam']})")
    need('fx', b'FXP1') and R.ok('packs', f"частицы FXP1 ({paths['fx']})")
    need('msnart', b'MSA2') and R.ok('packs', f"значки и маркеры заданий MSA2 ({paths['msnart']})")
    need('homer', b'CHR1') and R.ok('packs', f"Гомер CHR1 ({paths['homer']})")


# ---------------------------------------------------------------- боты
def msn_missions(p):
    b = Path(p).read_bytes()
    so, sc = struct.unpack_from('<II', b, 16); bo, bc = struct.unpack_from('<II', b, 24); mo, mc = struct.unpack_from('<II', b, 16 + 6 * 8)
    def s(i):
        o = struct.unpack_from('<I', b, so + 4 * i)[0]; e = b.index(b'\0', bo + o); return b[bo + o:e].decode('utf-8', 'replace')
    return [s(struct.unpack_from('<I', b, mo + 32 * k)[0]) for k in range(mc)]


def stage_dir(n, paths, work):
    """Папка «как рядом с EBOOT»: world.c ищет спутники рядом с level.shr — traffic.shr и по номеру уровня из пакета миссий
    (MSN1 @6) collect-l<N>.shr, interiors-l<N>.bin (tools/bots/world.c bwLevel, с 29.09), машины миссий msncars-l<N>.shr и звук
    миссий audio/ (длины реплик, события музыки); здесь — ссылками. П1 30.09: без двух последних мир песочницы был не миром игры —
    машины миссий на кузовах трафика, разговоры по 1 с (m2 «провал» здесь и «пройдена» у tools/bots/missions.py)."""
    st = work / 'stage'; shutil.rmtree(st, ignore_errors=True); st.mkdir(parents=True)
    brk = os.environ.get('LEVEL_CHECK_BREAK_STAGE')   # отрицательный контроль гейта: папка без спутников миссий (как до 30.09)
    for name, k in (('level.shr', 'shr'), ('traffic.shr', 'traffic'), (f'collect-l{n}.shr', 'collect'), (f'interiors-l{n}.bin', 'interiors'),
                    (f'msncars-l{n}.shr', 'msncars')):
        if k == 'msncars' and brk: continue
        if paths.get(k) and Path(paths[k]).exists(): (st / name).symlink_to(Path(paths[k]).resolve())
    if not brk and paths.get('music') and Path(paths['music']).exists():   # audio/ = папка music.sap и sfx.sab
        (st / 'audio').symlink_to(Path(paths['music']).resolve().parent)
    return st


def run_mission(paths, st, idx, secs, out):
    r = subprocess.run(['nice', '-n', '10', str(BIN / 'missioner'), str(st / 'level.shr'), str(paths['homer']), str(paths['roads']), str(paths['msn']),
                        '--mission', str(idx), '--secs', str(secs), '--out', str(out)], capture_output=True, text=True)
    for l in r.stdout.splitlines():
        f = l.split('\t')
        if f[0] == 'M' and len(f) > 8:
            return dict(index=int(f[1]), id=f[2], title=f[3], result=f[4], why=f[5], time=float(f[6]), cls=f[15] if len(f) > 15 else '')
    return dict(index=idx, id='?', title='', result='нет итога', why=(r.stderr.strip().splitlines() or ['код %d' % r.returncode])[-1], time=0, cls='')


def baseline_file(n): return ROOT / f'tools/sandbox/baseline/l{n}.tsv'


def read_baseline(n):
    f = baseline_file(n)
    if not f.exists(): return {}
    return {l.split('\t')[0]: l.split('\t')[1] for l in f.read_text().splitlines() if l and not l.startswith('#') and '\t' in l}


def stage_bots(n, R, paths, work, a):
    for k in ('shr', 'msn', 'homer', 'roads'):
        if not paths.get(k) or not Path(paths[k]).exists():
            R.fail('bots', 'входы ботов', f'нет {k}'); return None
    if not (BIN / 'game_headless').exists() or not (BIN / 'missioner').exists():
        subprocess.run([str(ROOT / 'tools/bots/build.sh')], check=True, capture_output=True)
    st = stage_dir(n, paths, work)
    r = subprocess.run([str(BIN / 'game_headless'), str(st / 'level.shr'), str(paths['homer']), '--selftest', '--secs', '20', '--msn', str(paths['msn'])],
                       capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or r.stderr.strip().splitlines() or ['пусто'])
    R.check('bots', r.returncode == 0 and 'RESULT: OK' in r.stdout, 'игра без экрана: ввод дважды = мир побайтно, сохранить/загрузить',
            ' | '.join(x for x in tail if x.startswith(('трафик', 'RESULT', 'game_headless'))) or tail[-1])
    # П1 30.09: мир ботов = мир игры — спутники миссий, что лежат рядом с level.shr у EBOOT, нашлись и в папке песочницы
    # (LEVEL_CHECK_BREAK_STAGE=1 — отрицательный контроль: папка без них обязана дать FAIL)
    pk = next((x for x in tail if x.startswith('пакеты миссий')), '')
    m_ = re.search(r'кузовов машин (\d+), звук миссий (есть|нет)', pk)
    need_cars = bool(paths.get('msncars') and Path(paths['msncars']).exists()); need_audio = bool(paths.get('music') and Path(paths['music']).exists())
    ok_pk = bool(m_) and (not need_cars or int(m_.group(1)) > 0) and (not need_audio or m_.group(2) == 'есть')
    R.check('bots', ok_pk, 'мир ботов = мир игры: машины миссий (msncars) и звук миссий (audio/) рядом с уровнем',
            (pk or 'строки «пакеты миссий» нет') + f' (нужно: машины {"да" if need_cars else "нет файла"}, звук {"да" if need_audio else "нет файла"})')
    if a.missions == 'none': return dict(selftest=r.returncode == 0)
    ids = msn_missions(paths['msn']); base = read_baseline(n)
    if a.missions == 'all': want = list(range(len(ids)))
    elif a.missions == 'baseline': want = [i for i, m in enumerate(ids) if m in base]
    else: want = [i for i, m in enumerate(ids) if m in a.missions.split(',')]
    if not want:
        R.warn('bots', 'миссии', f'нечего гонять (база {baseline_file(n).relative_to(ROOT)} пуста; --missions all — все {len(ids)})'); return dict(missions=[])
    print(f'  bots  ..   миссионер: {[ids[i] for i in want]} по {a.secs:.0f} с игры, {a.procs} процессов (~5–10 мин на миссию)', flush=True)
    out = work / 'missions'; out.mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(a.procs) as ex:
        rows = list(ex.map(lambda i: run_mission(paths, st, i, a.secs, out), want))
    for m in rows:
        exp = base.get(m['id'])
        if exp == 'пройдена': R.check('bots', m['result'] == 'пройдена', f"миссия {m['id']} {m['title']} (база: пройдена)", f"{m['result']} {m['why']} {m['time']:.0f} с")
        else: R.warn('bots', f"миссия {m['id']} {m['title']} — до идеала", f"{m['result']} {m['why']} {m['cls']}")
    passed = sum(m['result'] == 'пройдена' for m in rows)
    R.ok('bots', 'идеал миссий', f'пройдено {passed} из {len(rows)} прогнанных; всего миссий в пакете {len(ids)}')
    if a.baseline_write:
        f = baseline_file(n); f.parent.mkdir(parents=True, exist_ok=True)
        old = read_baseline(n); old.update({m['id']: m['result'] for m in rows})
        f.write_text(f'# база миссий уровня {n} для tools/sandbox/level_check.py: «пройдена» обязана оставаться пройденной\n' +
                     ''.join(f'{k}\t{v}\n' for k, v in old.items()))
        print(f'  -> {f.relative_to(ROOT)}')
    return dict(missions=rows)


# ---------------------------------------------------------------- прогон
def resolve(n, a):
    paths, used = {}, {}
    for k, c in candidates(n).items():
        o = getattr(a, k, None)
        if o: paths[k] = Path(o).resolve(); continue
        paths[k] = next((p for p in c if p.exists()), c[0] if c else None)
    return paths


def check_level(n, a, tag=''):
    stamp = time.strftime('%Y%m%d-%H%M%S')
    work = BUILD / 'sandbox/level_check' / f'l{n}' / (stamp + tag); work.mkdir(parents=True, exist_ok=True)
    R = Report(); paths = resolve(n, a); stages = a.stages.split(',')
    print(f'== уровень {n}: стадии {stages}; отчёт {work.relative_to(ROOT)}', flush=True)
    disk = stage_disk(n, R, work.parent) if 'disk' in stages else None
    if disk is None and ('shr' in stages or 'packs' in stages):   # старт и миссии уровня нужны стадиям shr/packs и без отчёта disk
        import mfk
        from level_sweep import find_spawn
        lv, _ = mfk.parse((SCR / f'level{n:02d}/level.mfk').read_text(errors='replace'))
        disk = dict(spawn=find_spawn(n), missions=[c.args[0] for c in lv if c.op == 'AddMission'],
                    bonus=[c.args[0] for c in lv if c.op == 'AddBonusMission'], files=disk_files(n))
    S = stage_shr(n, R, paths['shr'], disk['spawn']) if 'shr' in stages else None
    if 'packs' in stages: stage_packs(n, R, paths, disk, S)
    bots = stage_bots(n, R, paths, work, a) if 'bots' in stages else None
    res = 'FAIL' if R.failed else 'PASS'
    cnt = collections.Counter(r['status'] for r in R.rows)
    (work / 'report.json').write_text(json.dumps(dict(level=n, result=res, paths={k: str(v) for k, v in paths.items()}, rows=R.rows, bots=bots),
                                                 ensure_ascii=False, indent=1, default=str))
    md = [f'# Песочница уровня {n} · {stamp}', '', f'Итог: **{res}** (PASS {cnt["PASS"]}, WARN {cnt["WARN"]}, FAIL {cnt["FAIL"]})', '',
          '| стадия | итог | что | подробно |', '|---|---|---|---|'] + \
         [f"| {r['stage']} | {r['status']} | {r['what']} | {r['detail'].replace('|', '/')} |" for r in R.rows]
    (work / 'report.md').write_text('\n'.join(md) + '\n')
    print(f'l{n}: {res} (PASS {cnt["PASS"]}, WARN {cnt["WARN"]}, FAIL {cnt["FAIL"]}) -> {(work / "report.md").relative_to(ROOT)}', flush=True)
    return res == 'PASS'


def corrupt(src, dst, how):
    b = bytearray(Path(src).read_bytes())
    if how == 'truncate': b = b[:len(b) // 3]
    elif how == 'col':   # магия и заголовок COL1 затёрты (битый файл уровня)
        o = struct.unpack_from('<I', b, 92)[0]; b[o:o + 64] = b'\0' * 64
    Path(dst).parent.mkdir(parents=True, exist_ok=True); Path(dst).write_bytes(bytes(b)); return dst


def gate(n, a):
    """Отрицательные контроли (обязаны дать FAIL), потом настоящий вход (обязан дать PASS)."""
    neg = BUILD / 'sandbox/level_check' / f'l{n}' / 'negative'; neg.mkdir(parents=True, exist_ok=True)
    real = resolve(n, a)
    other = next((m for m in range(1, 8) if m != n and ((BUILD / 'levels' / f'l{m}' / 'level.shr').exists())), None)
    cases = [('обрезанный level.shr', dict(shr=corrupt(real['shr'], neg / 'trunc.shr', 'truncate')), 'shr'),
             ('level.shr с затёртой коллизией COL1', dict(shr=corrupt(real['shr'], neg / 'col.shr', 'col')), 'shr,bots'),
             ('миссии чужого уровня', dict(msn=str(BUILD / 'missions' / f'level{(n % 7) + 1:02d}.msn')), 'packs')]
    if other: cases.append((f'level.shr уровня {other} под видом уровня {n}', dict(shr=str(BUILD / 'levels' / f'l{other}' / 'level.shr')), 'shr'))
    if read_baseline(n):   # регрессия миссий: база требует «пройдена», а на миссию дано 5 с игры — обязана не пройтись
        cases.append(('миссии базы с 5 с игры на миссию (регрессия)', dict(secs=5, missions='baseline', baseline_write=False), 'bots'))
    ok = True
    for i, (name, over, st) in enumerate(cases):
        b = argparse.Namespace(**{**vars(a), 'missions': 'none', **over, 'stages': st})
        print(f'\n-- отрицательный контроль: {name}', flush=True)
        r = check_level(n, b, f'-neg{i}')
        print(f'GATE {"RED OK" if not r else "НЕ ПОКРАСНЕЛ"}: {name}'); ok &= not r
    print('\n-- настоящий вход', flush=True)
    g = check_level(n, a)
    print(f'GATE {"GREEN OK" if g else "КРАСНЫЙ"}: уровень {n} как есть'); ok &= g
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, required=True, choices=range(1, 8))
    ap.add_argument('--stages', default='disk,shr,packs,bots')
    ap.add_argument('--missions', default='baseline', help='baseline | all | none | m0,sr1,...')
    ap.add_argument('--secs', type=float, default=600, help='секунд игры на миссию')
    ap.add_argument('--procs', type=int, default=max(1, (os.cpu_count() or 4) - 4))
    ap.add_argument('--gate', action='store_true'); ap.add_argument('--baseline-write', action='store_true')
    for k in candidates(1): ap.add_argument('--' + k.replace('_', '-'), dest=k)
    a = ap.parse_args()
    ok = gate(a.level, a) if a.gate else check_level(a.level, a)
    print('RESULT: ' + ('PASS' if ok else 'FAIL')); return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
