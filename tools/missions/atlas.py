#!/usr/bin/env python3
"""Атлас миссий уровня (правка 332, слово Роба 05.10: «как научиться понимать из оригинала последовательность и логику миссий»).

  python3 tools/missions/atlas.py [--level 1] [--run-bots [--procs 4] [--secs 900]] [--bots DIR] [--ps2 DIR ...] [--out DIR]

Одна страница: миссия → этапы, у каждого этапа три слоя рядом.
  1. СКРИПТ [диск] — скрипты миссий диска, собранные тем же компилятором, что пакет level0N.msn (tools/missions/compile.py):
     фаза 0 (вступление / прогулка, mXsd) и фаза 1 (миссия); цель этапа человеческим языком, текст задания из текстовой
     библии, значок, персонажи, машины, точки (код места как на паузе), условия провала, таймеры, разговоры (реплики и длина
     по файлам диска), что грузится (mXsdl / mXl / level.mfk, зоны SetDynaLoadData, карточка SetPresentationBitmap).
  2. ПОРТ [порт] — тот же порядок по факту: журнал бота-миссионера (tools/bots/missioner.c -v: «стадия ф.э t=…», провалы, итог)
     — пройден / застрял / провал / не дошёл, время этапа; что порт НЕ делает на этом этапе — строки переписи
     tools/missions/census.py («нет / частично») и команды, которые игра пропускает (tools/missions/coverage.py «ignored»).
  3. ОРИГИНАЛ [PS2] — прогоны оригинала tools/twins/msn_timeline.py (память PS2: текущий этап, тип цели, номер текста, значок —
     адреса в docs/МИССИИ_КАК_ЧИТАТЬ_ОРИГИНАЛ.md) и запись PS2 (build/ps2ref/external/yt-bziOipI4gDI.mp4: отрезок миссии по каталогу
     tools/ps2ref/CATALOG_L1.md). Где оригинал не снят — серым «не наблюдалось».
Цвет — расхождение: зелёный совпало / пройдено, жёлтый частично (порт чего-то не делает, этап закрылся мгновенно), красный провал
или противоречие, серый — нет данных. Метки происхождения у каждого утверждения: [диск] [порт] [PS2] [запись PS2] [правило порта].

Выход (по умолчанию build/АТЛАС_МИССИЙ_L<N>/ основной папки данных): index.html (открывается двойным кликом, без сети),
atlas.json (всё, из чего собрана страница), level0N.json (скрипт после компилятора). Бот: --run-bots собирает свой missioner в
<выход>/bots/bin и гоняет все миссии уровня (не больше --procs процессов) в <выход>/bots/<время>/; без ключа берётся последний
такой прогон (или --bots ПАПКА с m*.log). Оригинал: --ps2 папки прогонов msn_timeline.py (по умолчанию <выход>/ps2/*)."""
import argparse, html, json, math, os, re, struct, subprocess, sys, time
from collections import defaultdict, Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools')); sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tools/twins'))
GAME = ROOT / 'hit-and-run-web/source/game'


def data_root():
    """основная папка данных (build/ общий у рабочих копий): по git common dir, как tools/twins/common.py"""
    try:
        cd = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--git-common-dir'], capture_output=True, text=True, check=True).stdout.strip()
        p = (Path(cd) if os.path.isabs(cd) else ROOT / cd).resolve().parent
        return p if (p / 'build').exists() else ROOT
    except (OSError, subprocess.CalledProcessError):
        return ROOT


DATA = data_root()


def clock(): return subprocess.check_output(['date', '+%Y-%m-%d %H:%M'], text=True).strip()
def stamp(): return subprocess.check_output(['date', '+%Y%m%d-%H%M%S'], text=True).strip()
def E(s): return html.escape(str(s), quote=True)


ACTOR = {'hom': 'Гомер', 'mrg': 'Мардж', 'brt': 'Барт', 'lis': 'Лиза', 'apu': 'Апу', 'skn': 'Скиннер', 'smi': 'Смитерс', 'bur': 'Бёрнс',
         'cle': 'Клетус', 'lou': 'Луи', 'mil': 'Милхаус', 'nel': 'Нельсон', 'ral': 'Ральф', 'bar': 'Барни', 'len': 'Ленни', 'car': 'Карл',
         'wil': 'Вилли', 'mrn': 'Мардж', 'brn': 'Барни', 'oto': 'Отто', 'kru': 'Красти', 'mol': 'Мэн-крот', 'gil': 'Гил'}
NAV = {'nearest road': 'стрелки по ближайшей дороге', 'both': 'стрелки и маркер', 'neither': 'без стрелок', 'niether': 'без стрелок',
       'intersection': 'стрелки до перекрёстка'}
DRAW = {'carsphere': 'сфера для машины', 'triggersphere': 'сфера'}
FLAG_RU = [(1, 'последний этап (final)'), (2, 'чекпоинт: повтор миссии отсюда (RESET_TO_HERE)'), (4, 'закрыт до покупки (locked)'),
           (8, 'надпись «STAGE COMPLETE»'), (16, 'нужно нажать действие (MustActionTrigger)'), (32, 'без окна «иди к…» (TurnGotoDialogOff)'),
           (64, 'время вверх (UseElapsedTime)'), (128, 'музыка этапа всегда (SetStageMusicAlwaysOn)')]
OBJ_ORIG = {1: 'goto', 7: 'talkto', 8: 'dialogue', 9: 'getin'}   # тип цели в памяти PS2 (msn_timeline.py, наблюдение 05.10) — дополняется


# ------------------------------------------------------------------ слой 1: скрипт
def rsd_seconds(path):
    """длина реплики по файлу диска: RSD4VAG, моно, частота в заголовке, VAG 16 байт → 28 отсчётов, данные с 0x800"""
    try:
        b = path.read_bytes()
        if b[:4] != b'RSD4': return None
        ch, _, rate = struct.unpack_from('<III', b, 8)
        return (len(b) - 0x800) / 16 * 28 / max(1, rate) / max(1, ch)
    except OSError:
        return None


def load_script(level, out_dir):
    import compile as MC
    c = MC.Compiler(level); c.compile(); P = c.pack
    jp = out_dir / f'level{level:02d}.json'
    MC.dump_json(P, jp)
    J = json.loads(jp.read_text())
    S = lambda i: P.strings[i]
    info = {S(m[0]): S(m[2]) for m in P.missions}
    lf, lc, inf, inc = P.level[:4]
    def flat(a, n):
        out = []
        for k in range(a, a + n):
            op, cnt, _, a0, line, f = P.cmds[k]
            args = [S(v) if t in (MC.ARG_STR, MC.ARG_BARE) else v for t, _, v in P.args[a0:a0 + cnt]]
            out.append(dict(op=MC.CMD.SPECS[op - 1].name, args=args, src=f'{S(P.files[f])}:{line}'))
        return out
    J['level_cmds'] = flat(lf, lc); J['leveli_cmds'] = flat(inf, inc); J['info'] = info
    J['warnings'] = c.warn; J['texts'] = dict(P.texts)
    durs = {}
    for key, clips in J['conversations'].items():
        durs[key] = [(Path(cp).name, rsd_seconds(GAME / cp)) for cp in clips]
    J['conv_durs'] = durs
    return J


def place(pos):
    try:
        import place as PL
    except Exception:
        return ''
    if pos is None: return ''
    if pos[1] < -10: return 'комната'
    return PL.code(pos[0], pos[2])


def loc_txt(a):
    if isinstance(a, dict):
        nm = a.get('loc') or a.get('v'); p = a.get('pos')
        code = place(p)
        return f"{nm} ({code})" if code else str(nm)
    return str(a)


def plain(a): return a.get('v') if isinstance(a, dict) else a
def g(a, i): return a[i] if len(a) > i else ''
def ga(c, i): return g(c['args'], i)


def conv_lookup(J, conv, mission):
    conv = str(conv).lower(); d = J['conv_durs']
    for k in (f'{conv}/{mission}', f'{conv}/'):
        if k in d: return k, d[k]
    ks = [k for k in d if k.split('/')[0] == conv]
    return (ks[0], d[ks[0]]) if ks else (None, [])


def conv_txt(J, conv, mission):
    key, lines = conv_lookup(J, conv, mission)
    if not lines: return f'«{conv}» — реплик на диске нет'
    who = []
    for nm, _ in lines:
        m = re.match(r'c_.+?_\d+_[a-z]+_([a-z0-9]+)_', nm)
        who.append(ACTOR.get(m.group(1), m.group(1)) if m else '?')
    sec = sum(s or 0 for _, s in lines)
    order = ' → '.join(dict.fromkeys(who))
    return f'«{conv}»: {len(lines)} репл. ({order}), {sec:.1f} с'


def human_stage(st, mission, J, cov):
    """этап компилятора → сведения человеческим языком (всё с метками [диск])"""
    obj = st['obj']; cmds = st['cmds']; mode = []
    D = defaultdict(list)
    goal = ''
    by = defaultdict(list)
    for c in cmds: by[c['op']].append(c)
    objc = next((c for c in cmds if c['op'] == 'AddObjective'), None)
    if objc: mode = [str(x) for x in objc['args'][1:]]
    nav = ', '.join(NAV.get(m.lower(), m) for m in mode if m.lower() in NAV)
    dest = by.get('SetDestination', [])
    def dest_txt(c):
        a = c['args']; dr = str(g(a, 1)) if len(a) > 1 else ''
        what = DRAW.get(dr.lower(), 'дверь (вход в здание)' if 'doorstar' in dr.lower() else f'предмет «{dr}»' if dr else 'точка')
        return f"{loc_txt(g(a, 0))} — {what}"
    npcs = [f"{plain(ga(c, 0))} на {loc_txt(ga(c, 1))}" for c in by.get('AddNPC', []) if len(c['args']) > 1]
    coll = [c['args'] for c in by.get('AddCollectible', [])]
    tgt = [plain(ga(c, 0)) for c in by.get('SetObjTargetVehicle', []) if c['args']]
    if obj in ('goto', 'interior', 'gooutside'):
        goal = {'goto': 'Доехать / дойти', 'interior': 'Войти в здание', 'gooutside': 'Выйти из здания'}[obj] + \
               (': ' + '; '.join(dest_txt(c) for c in dest) if dest else '')
    elif obj == 'talkto':
        t = by.get('SetTalkToTarget', [])
        goal = 'Подойти и поговорить (△): ' + (', '.join(str(plain(ga(c, 0))) for c in t) if t else '?')
    elif obj == 'dialogue':
        goal = 'Разговор-сценка'
    elif obj == 'getin':
        goal = 'Сесть в машину' + (f" ({', '.join(map(str, tgt))})" if tgt else '')
    elif obj == 'race':
        laps = [ga(c, 0) for c in by.get('SetRaceLaps', [])]
        opp = [plain(ga(c, 0)) for c in by.get('SetCondTargetVehicle', [])] + [plain(ga(c, 0)) for c in by.get('ActivateVehicle', [])]
        goal = f"Гонка: {len(coll)} контр. точек" + (f", кругов {laps[0]}" if laps else '') + (f"; соперники {', '.join(dict.fromkeys(map(str, opp)))}" if opp else ' (на время)')
    elif obj in ('delivery', 'pickupitem'):
        models = Counter(str(g(a, 1)) for a in coll if len(a) > 1)
        goal = (f"Собрать {len(coll)} предм. ({', '.join(f'{k}×{v}' for k, v in models.items())})" if models else
                f"Цель — {len(coll)} объектов мира на точках (своего предмета нет: ломаются / подбираются объекты уровня)")
    elif obj == 'dump':
        goal = f"Таранить {', '.join(map(str, tgt)) or 'машину'} и подбирать выпавшее ({len(coll)})"
    elif obj == 'destroy':
        goal = f"Разбить {', '.join(map(str, tgt)) or 'машину'}"
    elif obj == 'follow':
        goal = f"Ехать за {', '.join(map(str, tgt)) or 'машиной'}, не отставая"
    elif obj == 'losetail':
        goal = f"Оторваться от {', '.join(map(str, tgt)) or 'погони'}"
    elif obj == 'timer':
        goal = 'Пауза-постановка'
    elif obj == 'buycar':
        goal = f"Купить машину {' '.join(mode)}"
    elif obj == 'buyskin':
        goal = f"Купить костюм {' '.join(mode)}"
    elif obj == 'coins':
        goal = f"Заплатить монеты (ставка) {' '.join(mode)}"
    elif obj == 'fmv':
        goal = 'Ролик'
    elif obj == 'destroyboss':
        goal = 'Поразить босса'
    else:
        goal = obj
    if nav: goal += f' · {nav}'
    if npcs: D['персонажи'] += npcs
    for c in by.get('AddObjectiveNPCWaypoint', []): D['персонажи'].append(f"{plain(ga(c, 0))} идёт к {loc_txt(ga(c, 1))}")
    for c in by.get('AddStageCharacter', []): D['персонажи'].append('игрок: ' + ' '.join(str(plain(x)) for x in c['args']))
    for c in by.get('RemoveNPC', []): D['персонажи'].append(f"убрать {plain(ga(c, 0))}")
    for c in by.get('SetDialogueInfo', []):
        a = c['args']; D['разговоры'].append(f"{plain(g(a, 0))} ↔ {plain(g(a, 1))}: " + conv_txt(J, plain(g(a, 2)), mission))
    for c in by.get('SetCompletionDialog', []):
        a = c['args']; D['разговоры'].append('после этапа: ' + conv_txt(J, plain(g(a, 0)), mission) + (f' ({plain(g(a, 1))})' if len(a) > 1 else ''))
    for c in by.get('AddStageVehicle', []):
        a = c['args']; drv = f", водитель {g(a, 4)}" if len(a) > 4 and str(g(a, 4)).lower() != 'null' else ''
        D['машины'].append(f"{plain(g(a, 0))} на {loc_txt(g(a, 1))}, режим {plain(g(a, 2))}{drv}")
    for c in by.get('ActivateVehicle', []):
        a = c['args']; D['машины'].append(f"включить {plain(g(a, 0))}: " + ' '.join(str(plain(x)) for x in a[1:]))
    for op in ('MoveStageVehicle', 'RemoveStageVehicle', 'PlacePlayerCar', 'SetForcedCar', 'ResetToThisStage', 'SetVehicleAIParams', 'SetStageAIRaceCatchupParams',
               'SetStageAIEvadeCatchupParams', 'SetStageAITargetCatchupParams'):
        for c in by.get(op, []): D['машины'].append(op + '(' + ', '.join(loc_txt(x) for x in c['args']) + ')')
    wps = [loc_txt(ga(c, 0)) for c in by.get('AddStageWaypoint', [])]
    if wps: D['машины'].append('путь соперника: ' + ' → '.join(wps))
    if dest: D['точки'] += [dest_txt(c) for c in dest]
    if coll: D['точки'].append('предметы / контрольные точки: ' + ', '.join(loc_txt(g(a, 0)) + (f' [{g(a, 1)}]' if len(a) > 1 else '') for a in coll[:12]) + (f' … ещё {len(coll) - 12}' if len(coll) > 12 else ''))
    for c in by.get('SetStageTime', []): D['таймер'].append(f"время этапа {ga(c, 0)} с (SetStageTime)")
    for c in by.get('AddStageTime', []): D['таймер'].append(f"+{ga(c, 0)} с к общему таймеру (AddStageTime)")
    for c in by.get('SetParTime', []): D['таймер'].append(f"пар-время {ga(c, 0)} с (ставка)")
    if st['flags'] & 64: D['таймер'].append('время идёт вверх (UseElapsedTime)')
    # условия провала
    cur = None
    for c in cmds:
        if c['op'] == 'AddCondition':
            t = str(ga(c, 0)).lower(); cur = len(D['провал']); D['провал'].append(COND_RU.get(t, t))
        elif c['op'] == 'SetCondTime' and cur is not None: D['провал'][cur] += f" ({ga(c, 0)} с)"
        elif c['op'] == 'SetCondMinHealth' and cur is not None: D['провал'][cur] += f" (здоровье < {ga(c, 0)})"
        elif c['op'] == 'SetCondTargetVehicle' and cur is not None: D['провал'][cur] += f": {plain(ga(c, 0))}"
        elif c['op'] == 'SetFollowDistances' and cur is not None: D['провал'][cur] += f" ({', '.join(map(str, c['args']))} м)"
        elif c['op'] == 'SetConditionPosition' and cur is not None: D['провал'][cur] += f" (хуже {ga(c, 0)}-го)"
        elif c['op'] == 'CloseCondition': cur = None
    for c in by.get('SetPresentationBitmap', []): D['грузит'].append(f"карточка миссии {Path(str(ga(c, 0))).stem}")
    for c in by.get('StreetRacePropsLoad', []): D['грузит'].append(f"пропы гонки {ga(c, 0)}")
    for c in by.get('SetCollectibleEffect', []): D['эффекты'].append(f"эффект подбора {ga(c, 0)}")
    for c in by.get('SetMaxTraffic', []): D['мир'].append(f"трафик ≤ {ga(c, 0)}")
    for c in by.get('AddStageMusicChange', []): D['мир'].append('смена музыки')
    fl = [t for b, t in FLAG_RU if st['flags'] & b]
    known = {'AddStage', 'CloseStage', 'AddObjective', 'CloseObjective', 'AddCondition', 'CloseCondition', 'SetDestination', 'AddNPC', 'AddCollectible',
             'SetObjTargetVehicle', 'SetTalkToTarget', 'SetRaceLaps', 'SetCondTargetVehicle', 'ActivateVehicle', 'AddObjectiveNPCWaypoint', 'AddStageCharacter',
             'RemoveNPC', 'SetDialogueInfo', 'SetCompletionDialog', 'AddStageVehicle', 'MoveStageVehicle', 'RemoveStageVehicle', 'PlacePlayerCar',
             'SetForcedCar', 'ResetToThisStage', 'SetVehicleAIParams', 'SetStageAIRaceCatchupParams', 'SetStageAIEvadeCatchupParams',
             'SetStageAITargetCatchupParams', 'AddStageWaypoint', 'SetStageTime', 'AddStageTime', 'SetParTime', 'UseElapsedTime', 'SetCondTime',
             'SetCondMinHealth', 'SetFollowDistances', 'SetConditionPosition', 'SetPresentationBitmap', 'StreetRacePropsLoad', 'SetCollectibleEffect',
             'SetMaxTraffic', 'AddStageMusicChange', 'SetStageMessageIndex', 'SetHUDIcon', 'RESET_TO_HERE', 'ShowStageComplete', 'MustActionTrigger',
             'TurnGotoDialogOff', 'SetStageMusicAlwaysOn'}
    other = Counter(c['op'] for c in cmds if c['op'] not in known)
    if other: D['прочее'].append(', '.join(f'{k}×{v}' if v > 1 else k for k, v in other.items()))
    ign = sorted({c['op'] for c in cmds if cov.get(c['op']) == 'ignored'})
    src = cmds[0]['src'] if cmds else ''
    return dict(goal=goal, details={k: v for k, v in D.items() if v}, flags=fl, ignored=ign, src=src)


COND_RU = {'timeout': 'время вышло', 'outofvehicle': 'слишком долго без машины', 'damage': 'машина разбита', 'position': 'плохое место в гонке',
           'race': 'соперник первым у финиша', 'followdistance': 'слишком отстал / приблизился', 'keepbarrel': 'потерян груз'}
OBJ_RU = {'goto': 'доехать / дойти', 'getin': 'сесть в машину', 'talkto': 'поговорить', 'dialogue': 'разговор', 'interior': 'войти',
          'gooutside': 'выйти', 'race': 'гонка', 'follow': 'слежка', 'losetail': 'оторваться', 'delivery': 'собрать', 'dump': 'таран + подбор',
          'destroy': 'разбить', 'pickupitem': 'подобрать', 'destroyboss': 'босс', 'timer': 'пауза', 'fmv': 'ролик', 'buycar': 'купить машину',
          'buyskin': 'купить костюм', 'coins': 'ставка', 'dummy': 'пустышка'}


def human_phase(ph, J):
    """фаза: что грузится при её старте и как ставится игрок [диск]"""
    loads, setup = [], []
    for c in ph['load']:
        a = c['args']
        if c['op'] == 'LoadP3DFile':
            p = str(g(a, 0)).replace('\\', '/'); nm = Path(p).stem
            kind = 'значок' if '/msnicons/' in p.lower() else 'камера' if 'cam' in nm.lower() else 'карточка' if '/images/' in p.lower() else 'модель'
            loads.append(f'{kind} {nm}')
        elif c['op'] == 'LoadDisposableCar':
            loads.append(f"машина {g(a, 1)} ({g(a, 2) if len(a) > 2 else ''})")
        else:
            loads.append(c['op'] + ' ' + ' '.join(map(str, a)))
    for c in ph['setup']:
        a = c['args']; op = c['op']
        if op == 'SelectMission': continue
        if op == 'SetMissionResetPlayerInCar': setup.append(f"старт / повтор: Гомер в машине на {loc_txt(g(a, 0))}")
        elif op == 'SetMissionResetPlayerOutCar': setup.append(f"старт / повтор: Гомер на {loc_txt(g(a, 0))}, машина на {loc_txt(g(a, 1))}")
        elif op == 'SetDynaLoadData': setup.append('зоны города: ' + str(g(a, 0)).replace('.p3d', '').strip(';').replace(';', ', '))
        elif op == 'UsePedGroup': setup.append(f'группа пешеходов {g(a, 0)}')
        elif op in ('SetMissionStartCameraName', 'SetAnimatedCameraName'): setup.append(f'камера старта {g(a, 0)}')
        elif op in ('SetMissionStartMulticontName', 'SetAnimCamMulticontName'): continue
        elif op == 'SetInitialWalk': setup.append(f'Гомер сам идёт к {loc_txt(g(a, 0))}')
        elif op == 'SetForcedCar': setup.append(f'машина миссии {g(a, 0)} (SetForcedCar)')
        else: setup.append(op + '(' + ', '.join(loc_txt(x) for x in a) + ')')
    return dict(loads=list(dict.fromkeys(loads)), setup=list(dict.fromkeys(setup)))


# ------------------------------------------------------------------ слой 2: порт
def build_missioner(out):
    b = out / 'bin'; b.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(ROOT / 'tools/bots/build.sh')], check=True, capture_output=True, cwd=str(ROOT),
                   env=dict(os.environ, OUT_DIR=str(b), BINS='missioner'))
    return b / 'missioner'


def run_bots(level, out, procs, secs, n_missions):
    if level != 1: raise SystemExit('бот-миссионер — пока только уровень 1 (roads-l1.bin, level.shr)')
    exe = build_missioner(out); run = out / stamp(); run.mkdir(parents=True)
    B = DATA / 'build'
    args = [str(B / 'level.shr'), str(B / 'homer.shr'), str(B / 'sandbox/roads-l1.bin'), str(B / f'missions/level{level:02d}.msn')]
    import concurrent.futures
    def one(m):
        with open(run / f'm{m}.log', 'w') as fo:
            subprocess.run(['nice', '-n', '10', str(exe), *args, '--mission', str(m), '--secs', str(secs), '-v', '--out', str(run)],
                           stdout=fo, stderr=subprocess.STDOUT, env=dict(os.environ, BW_FRAMES='1'))
        return m
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(procs) as ex:
        for m in ex.map(one, range(n_missions)): print(f'  бот: миссия {m} готова ({time.time() - t0:.0f} с)')
    (run / 'run.json').write_text(json.dumps(dict(started=clock(), secs=secs, procs=procs, inputs=args), ensure_ascii=False, indent=1))
    return run


STAGE_RE = re.compile(r'^  стадия (\d+)\.(\d+) t=([\d.]+): (.*)$')
FAIL_RE = re.compile(r'^  провал стадии (\d+)\.(\d+) t=([\d.]+): ([^;]+);(.*)$')


def parse_bots(run):
    out = {}
    if not run: return out
    for p in sorted(Path(run).glob('m*.log')):
        st, fails, M = [], [], None
        for ln in p.read_text(errors='replace').splitlines():
            m = STAGE_RE.match(ln)
            if m: st.append(dict(ph=int(m.group(1)), st=int(m.group(2)), t=float(m.group(3)), info=m.group(4))); continue
            m = FAIL_RE.match(ln)
            if m: fails.append(dict(ph=int(m.group(1)), st=int(m.group(2)), t=float(m.group(3)), why=m.group(4).strip(), more=m.group(5).strip())); continue
            if ln.startswith('M\t'):
                f = ln.split('\t')
                M = dict(index=int(f[1]), id=f[2], result=f[4], why=f[5], t=float(f[6]), margin=float(f[7]), damage=float(f[8]),
                         stages=int(f[9]), attempts=int(f[10]), place=[float(f[12]), float(f[13])], cls=f[15] if len(f) > 15 else '')
        if M: out[M['id']] = dict(stages=st, fails=fails, result=M, log=p.name)
    return out


def latest_bot_run(out):
    runs = sorted(d for d in (out / 'bots').glob('2*') if d.is_dir() and list(d.glob('m*.log'))) if (out / 'bots').exists() else []
    return runs[-1] if runs else None


def census_rows(level):
    import census as CS
    C = CS.Census(ROOT, []); C.level(level)
    rows = defaultdict(list); loads = {}
    for r in C.rows:
        if r['cmd'] == 'LoadP3DFile': loads[str(r['res']).lower()] = (r['ok'], r['ev'])
        if r['ok'] == 'есть': continue
        rows[(r['mission'], r['phase'], str(r['stage']))].append(r)
    return rows, loads


def coverage_map():
    import coverage as CV
    try:
        return CV.classify(ROOT / 'viewer', ROOT / 'tools')
    except Exception as e:   # не мешает атласу: просто без колонки «пропускает»
        print('coverage.py:', e); return {}


# ------------------------------------------------------------------ слой 3: оригинал
def recording(level, J):
    """отрезки миссий в записи PS2 по каталогу (tools/level/acceptance.py timeline) + строки каталога в отрезке"""
    cat = ROOT / f'tools/ps2ref/CATALOG_L{level}.md'
    if not cat.exists(): return {}, []
    sys.path.insert(0, str(ROOT / 'tools/level'))
    import acceptance as AC
    P = dict(missions=[dict(id=m['id'], title=m['title'],
                            objs={s['obj'] for ph in m['phases'] for s in ph['stages']},
                            kind='бонус' if m['flags'] & 1 else 'сюжет') for m in J['missions']])
    start, total, prob = AC.timeline(P, cat, None)
    rows = AC.md_rows(cat)
    out = {}
    order = sorted(start.items(), key=lambda kv: kv[1])
    for k, (mid, t0) in enumerate(order):
        t1 = order[k + 1][1] if k + 1 < len(order) else total
        notes = []
        for sec, c in rows:
            if len(c) < 2: continue
            for part in re.split(r'[;,]\s*', c[1]):
                ts = AC.times(part)
                if ts and t0 <= ts[0] < t1: notes.append(f'{AC.mmss(ts[0])} {c[0]}')
        out[mid] = dict(t0=AC.mmss(t0), t1=AC.mmss(t1), notes=list(dict.fromkeys(notes))[:10])
    return out, prob


def ps2_runs(dirs, J):
    """прогоны msn_timeline.py: stages.tsv + снимки на сменах этапа → по миссии список наблюдённых этапов"""
    res = []
    try:
        import msn_timeline as T
    except Exception as e:
        print('msn_timeline:', e); return res
    get = None
    try:
        import compile as MC
        get = MC.bible()
    except Exception:
        pass
    for d in dirs:
        d = Path(d)
        tl = d / 'timeline.json'
        if tl.exists():
            res.append(json.loads(tl.read_text())); continue
        if not (d / 'stages.tsv').exists(): continue
        res.append(T.timeline(d, get))
    return res


def import_ps2(src, out, mission):
    """прогон оригинала (папка msn_timeline.py run со снимками .p2s) → лёгкая копия в атлас: timeline.json + кадры этапов JPEG"""
    import msn_timeline as T, compile as MC
    from PIL import Image
    dst = out / 'ps2' / src.name; (dst / 'frames').mkdir(parents=True, exist_ok=True)
    TL = T.timeline(src, MC.bible(), mission)
    def shot_for(r):
        """кадр экрана этапа: первый кадр игры (экран 1) после начала этапа + 60 (окно задания уже на экране), шаг кадров png — 50"""
        scr = r.get('screens') or [(r['frame'], r.get('screen'))]
        f7 = next((f for f, x in scr if x == 7), None)   # этап с экраном «Start Mission» — показать его
        f0 = f7 + 10 - 60 if f7 is not None else next((f for f, x in scr if x == 1), scr[0][0])
        for f in range((f0 + 60 + 49) // 50 * 50, f0 + 400, 50):
            if (src / 'png' / f'f{f:05d}.png').exists(): return f, src / 'png' / f'f{f:05d}.png'
        return None, None
    for lst in (TL['stages'], TL['changes']):
        for r in lst:
            r.pop('png', None)
            f, png = shot_for(r)
            if png:
                nm = f"f{f:05d}.jpg"
                if not (dst / 'frames' / nm).exists():
                    Image.open(png).convert('RGB').resize((320, 240)).save(dst / 'frames' / nm, quality=82)
                r['shot'] = f'ps2/{src.name}/frames/{nm}'; r['shot_frame'] = f
    for nm in ('stages.tsv', 'events.tsv', 'run.json', 'trace.tsv', 'log.txt'):   # log.txt — журнал эмулятора (с --cdvd: чтения диска с кадром)
        if (src / nm).exists(): (dst / nm).write_bytes((src / nm).read_bytes())
    (dst / 'snaps').mkdir(exist_ok=True)   # снимки на сменах этапа (через 10 кадров) — для гейта msn_timeline.py gate <атлас>/ps2/<прогон>
    for r in TL['changes']:
        sp = src / f"snap_{r['frame'] + 10:05d}.p2s"
        if sp.exists() and not (dst / 'snaps' / sp.name).exists(): (dst / 'snaps' / sp.name).write_bytes(sp.read_bytes())
    (dst / 'timeline.json').write_text(json.dumps(TL, ensure_ascii=False, indent=1))
    print(f'  оригинал: {src.name} → {dst} (этапов {len(TL["stages"])}, чтений {len(TL["reads"])})')
    return dst


def port_have(cen_loads=None):
    """что из прочитанного оригиналом есть у порта: звук/персонажи/гэги/мир (tools/twins/b2_compare.py), модели и значки миссий —
    записи msnart.shr (tools/missions/census.py), скрипты — компилятор миссий"""
    try:
        import b2_compare as B, census as CS
        have = B.port_sets(); M = CS.Packs(ROOT, []).get('msnart.shr', CS.rd_msnart) or {}
    except Exception as e:
        print('сверка чтений с портом недоступна:', e); return lambda p: ('?', None, str(e))
    def judge(path):
        inner = (path.split(':', 1)[1] if ':' in path else path).lower()
        if inner.startswith('scripts/missions/') and inner.endswith('.mfk'): return 'скрипт', True, 'tools/missions/compile.py → missions.shr'
        if inner.startswith(('art/missions/', 'art/frontend/dynaload/')) and inner.endswith('.p3d'):
            if inner in M: return 'модель/значок миссии', True, 'msnart.shr (census.py rd_msnart)'
            ok, ev = (cen_loads or {}).get(inner, (None, ''))
            return 'модель/значок миссии', True if ok == 'есть' else False if ok == 'нет' else None, ev or 'не проверено'
        return B.judge(path, have)
    return judge


def findings():
    """наблюдения оригинала с уликами (tools/missions/atlas_findings.tsv): (миссия, этап) → [(цвет, текст, улика)]"""
    out = defaultdict(list); f = HERE / 'atlas_findings.tsv'
    if not f.exists(): return out
    for ln in f.read_text().splitlines():
        if not ln.strip() or ln.startswith('#'): continue
        c = ln.split('\t')
        if len(c) >= 5: out[(c[0], c[1])].append((c[2], c[3], c[4]))
    return out


def match_ps2(J, runs):
    """наблюдения оригинала → этап скрипта: по номеру текста и типу цели в порядке этапов миссии"""
    obs = defaultdict(dict)   # (mission, phase_i, stage_i) -> наблюдение
    for r in runs:
        mid = r.get('mission'); m = next((x for x in J['missions'] if x['id'] == mid), None)
        if not m: continue
        seq = [(pi, si, s) for pi, ph in enumerate(m['phases']) for si, s in enumerate(ph['stages'])]
        k = 0
        st_frames = [x['frame'] for x in r['stages']] + [10 ** 9]
        for n_, o in enumerate(r['stages']):
            o = dict(o, reads=[x for x in r.get('reads', []) if st_frames[n_] <= x['frame'] < st_frames[n_ + 1]])
            if o.get('screen') not in (1, None) and o.get('msg') is None and o.get('obj') is None: continue
            for j in range(k, len(seq)):
                pi, si, s = seq[j]
                want_msg = s['msg'] if s['msg'] != 65535 else None
                if o.get('obj_name') == s['obj'] and (o.get('msg') == want_msg):
                    o = dict(o, run=r.get('run'), matched=True)
                    obs[(mid, pi, si)] = o; k = j + 1; break
    return obs


# ------------------------------------------------------------------ сборка
def port_status(m, bots):
    """этапы скрипта → статус порта по журналу миссионера"""
    b = bots.get(m['id'])
    seq = [(pi, si) for pi, ph in enumerate(m['phases']) for si, _ in enumerate(ph['stages'])]
    has_intro = len(m['phases']) > 1
    def key_of(e): return (e['ph'] if has_intro else e['ph'] - 1, e['st'])
    res = {}
    if not b:
        for k in seq: res[k] = dict(state='нет', text='бот не гонял')
        return res, None
    first, count = {}, Counter()
    for e in b['stages']:
        k = key_of(e); count[k] += 1
        first.setdefault(k, e)
    order = [k for k in seq if k in first]
    last = order[-1] if order else None
    R = b['result']
    for i, k in enumerate(seq):
        if k not in first:
            res[k] = dict(state='нет', text='не дошёл'); continue
        e = first[k]; nxt = next((first[q] for q in seq[seq.index(k) + 1:] if q in first), None)
        dur = (nxt['t'] - e['t']) if nxt else (R['t'] - e['t'])
        fl = [f for f in b['fails'] if key_of(f) == k]
        fails = Counter(FAIL_RU.get(f['why'], f['why']) for f in fl)
        ftxt = '; '.join(f'{w} ×{n}' if n > 1 else w for w, n in fails.items())
        if nxt or (k == last and R['result'] == 'пройдена'):
            st = 'ок'; text = f"пройден за {dur:.1f} с (с {e['t']:.1f} с)"
            if fl: text += f"; провалы до прохода: {ftxt}"
        elif R['result'] == 'провал':
            st = 'провал'; text = f"провал: {R['why']}" + (f" — {ftxt}" if ftxt else '')
        else:
            st = 'застрял'; text = f"{R['result']}: {R['why']}" + (f" (место {R['place'][0]:.0f} {R['place'][1]:.0f}, код {place([R['place'][0], 0, R['place'][1]])})" if R['place'] != [0.0, 0.0] else '')
        res[k] = dict(state=st, text=text, t=e['t'], dur=dur, n=count[k], info=e['info'], fails=ftxt)
    return res, R


FAIL_RU = {'timeout': 'время вышло', 'damage': 'машина разбита', 'race': 'соперник первым', 'position': 'плохое место', 'outofvehicle': 'долго без машины',
           'followdistance': 'отстал от цели', 'keepbarrel': 'потерян груз', 'partime': 'не уложился в пар', 'hitnrun': 'Hit & Run', 'abort': 'отмена'}
SCREEN_RU = {1: 'игра', 7: '«Start Mission / Cancel», идёт разговор', 6: 'переход', 5: 'карточка миссии'}
INSTANT_OBJ = {'goto', 'interior', 'gooutside', 'talkto', 'getin', 'race', 'delivery', 'dump', 'destroy', 'follow', 'losetail'}


def build(level, out, bot_run, ps2_dirs):
    out.mkdir(parents=True, exist_ok=True)
    print('1/5 скрипт (компилятор)…'); J = load_script(level, out)
    print('2/5 перепись порта (census, coverage)…'); cen, cen_loads = census_rows(level); cov = coverage_map()
    print('3/5 журнал бота…'); bots = parse_bots(bot_run)
    print('4/5 оригинал: запись и прогоны PS2…'); rec, rec_prob = recording(level, J); runs = ps2_runs(ps2_dirs, J); obs = match_ps2(J, runs)
    judge = port_have(cen_loads)
    for r in runs:
        for x in r.get('reads', []):
            cat, ok, ev = judge(x['file']); x.update(cat=cat, port=ok, ev=ev)
    for o in obs.values():
        for x in o.get('reads', []):
            cat, ok, ev = judge(x['file']); x.update(cat=cat, port=ok, ev=ev)
    FND = findings()
    print('5/5 страница…')
    missions = []
    top = []
    for m in J['missions']:
        pst, R = port_status(m, bots)
        M = dict(id=m['id'], title=m['title'], info=J['info'].get(m['id'], ''), flags=m['flags'], phases=[], rec=rec.get(m['id']),
                 bot=R, bot_log=bots.get(m['id'], {}).get('log'))
        for pi, ph in enumerate(m['phases']):
            intro = len(m['phases']) > 1 and pi == 0
            H = human_phase(ph, J)
            cph = cen.get((m['id'], ph['name'], 'загрузка'), []) + cen.get((m['id'], ph['name'], 'миссия'), [])
            P = dict(name=ph['name'], file=ph['file'], kind='фаза 0 · вступление / прогулка' if intro else 'фаза 1 · миссия', loads=H['loads'], setup=H['setup'],
                     census=[f"{r['cmd']} {r['res']}: {r['miss']}" for r in cph], stages=[])
            for si, st in enumerate(ph['stages']):
                hs = human_stage(st, m['id'], J, cov)
                cs = cen.get((m['id'], ph['name'], str(si)), [])
                ps = pst.get((pi, si), dict(state='нет', text='—'))
                notes = []
                if ps.get('state') == 'ок' and ps.get('dur', 9) < 0.5 and st['obj'] in INSTANT_OBJ:
                    notes.append(('жёлтый', f"[порт] этап закрылся за {ps['dur']:.1f} с — цель уже рядом с точкой, где бот начал миссию (бот стартует миссию сразу, без дороги от прошлой — [правило порта] стенда); в игре сюда приходят от места прошлой миссии — сверить нельзя"))
                o = obs.get((m['id'], pi, si))
                fnd = FND.get((m['id'], f"{ph['name']}.{si}"), [])
                S = dict(num=st['num'], obj=st['obj'], findings=fnd, obj_ru=OBJ_RU.get(st['obj'], st['obj']), text=st['text'], msg=st['msg'], icon=st['icon'],
                         conds=st['conds'], human=hs, census=[dict(cmd=r['cmd'], res=r['res'], miss=r['miss'], fam=r['fam']) for r in cs],
                         port=ps, ps2=o, notes=notes)
                P['stages'].append(S)
            M['phases'].append(P)
        missions.append(M)
    # топ расхождений
    for M in missions:
        R = M['bot']
        if R and R['result'] != 'пройдена':
            stg = next(((P['name'], i, S) for P in M['phases'] for i, S in enumerate(P['stages']) if S['port'].get('state') in ('застрял', 'провал')), None)
            where = f"этап {stg[0]}.{stg[1]} «{stg[2]['text'] or stg[2]['obj_ru']}»" if stg else ''
            top.append(dict(level='красный' if R['result'] == 'провал' else 'жёлтый', mission=M['id'], title=M['title'],
                            text=f"[порт] бот: {R['result']} — {R['why']}; {where}"))
    for M in missions:
        for P in M['phases']:
            for i, S in enumerate(P['stages']):
                for col, txt, ev in S['findings']:
                    if col in ('красный', 'жёлтый'):
                        top.insert(0 if col == 'красный' else len(top), dict(level=col, mission=M['id'], title=M['title'], text=f"этап {P['name']}.{i}: {txt}"))
    fam = Counter()
    for M in missions:
        for P in M['phases']:
            for S in P['stages']:
                for c in S['census']: fam[(M['id'], c['fam'])] += 1
            for c in P['census']: fam[(M['id'], 'загрузка')] += 1
    def relp(x):
        try: return str(Path(x).resolve().relative_to(out.resolve()))
        except ValueError: return str(x)
    data = dict(level=level, made=clock(), bot_run=relp(bot_run) if bot_run else None, ps2=[r.get('run') for r in runs], rec_problems=rec_prob,
                missions=missions, top=top, census_by_mission={f'{a}|{b}': n for (a, b), n in fam.items()},
                level_loads=[c['args'][0] for c in J['level_cmds'] if c['op'] == 'LoadP3DFile'], ps2_runs=runs)
    (out / 'atlas.json').write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str))
    (out / 'index.html').write_text(render(data))
    print('готово:', (out / 'index.html').resolve())
    return data


# ------------------------------------------------------------------ HTML
CSS_TOKENS = ''':root{
  --nh:80;--brand-hue:182;
  --bg:#f6f5f2;--side:rgba(246,245,242,.86);--card:#ecebe6;--field:#ffffff;--stage:#ffffff;
  --ink:#1a1a1a;--ink2:#3d3c39;--ink3:#5c5b57;--on-ink:#ffffff;--on-ink-muted:rgba(255,255,255,.72);--knob:#ffffff;
  --fill:rgba(26,26,26,.07);--fill-hover:rgba(26,26,26,.10);--fill-strong:rgba(26,26,26,.15);--fill-active:rgba(26,26,26,.24);--line-strong:rgba(26,26,26,.28);
  --line:rgba(26,26,26,.14);--line-ctl:rgba(26,26,26,.28);--hair:rgba(26,26,26,.10);--hover:rgba(26,26,26,.055);
  --sel:oklch(.49 .08 var(--brand-hue));--selfg:#ffffff;--ring:oklch(.49 .08 var(--brand-hue));--seg-on:#ffffff;--track-s:.02em;
  --m-wait:oklch(.76 .12 78);--m-work:oklch(.52 .085 var(--brand-hue));--m-pause:#b9b8b2;--m-done:#d9d8d2;
  --st-ok:oklch(.6 .09 145);--st-run:oklch(.55 .09 var(--brand-hue));--st-wait:oklch(.74 .13 75);--st-bad:oklch(.56 .15 40);--st-sched:oklch(.6 .05 230);--st-info:oklch(.66 .07 205);
  --t-bad:oklch(.52 .12 45);--t-wait:oklch(.5 .09 70);--on-wait:oklch(.26 .05 75);
  --scrim:rgba(20,20,20,.36);--shadow:rgba(20,20,20,.28);--shadow-s:rgba(20,20,20,.10);
  --bt:.24;--btc:.03;
  --ground-light:#ffffff;--ground-light-muted:rgba(0,0,0,.55);--ground-dark:#141414;--ground-dark-muted:rgba(255,255,255,.62);
  --sans:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display","Inter","Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  --display:"Inter Tight",-apple-system,BlinkMacSystemFont,"SF Pro Display",system-ui,sans-serif;
  --t1:11.67px;--t2:14px;--t3:16.8px;--t4:20.16px;--t5:24.19px;--t6:29.03px;--t7:34.84px;--t8:41.8px;
  --r-ctl:4px;--r:6px;--r-card:6px;--r-pill:999px;--ease:cubic-bezier(.23,1,.32,1);--dur-press:140ms;--dur-pop:180ms;
  box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);color-scheme:light;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#161615;--side:rgba(22,22,21,.86);--card:#21211f;--field:#2b2b29;--stage:#2b2b29;
  --ink:#ecebe6;--ink2:#cfcec8;--ink3:#a6a59f;--on-ink:#161615;--on-ink-muted:rgba(22,22,21,.68);--knob:#ecebe6;
  --fill:rgba(255,255,255,.07);--fill-hover:rgba(255,255,255,.10);--fill-strong:rgba(255,255,255,.16);--fill-active:rgba(255,255,255,.26);--line-strong:rgba(255,255,255,.30);
  --line:rgba(255,255,255,.14);--line-ctl:rgba(255,255,255,.30);--hair:rgba(255,255,255,.10);--hover:rgba(255,255,255,.06);
  --sel:oklch(.78 .09 var(--brand-hue));--selfg:#161615;--ring:oklch(.78 .09 var(--brand-hue) / .7);--seg-on:#3d3d3a;--track-s:.025em;
  --m-wait:oklch(.78 .12 78);--m-work:oklch(.74 .09 var(--brand-hue));--m-pause:#5d5c57;--m-done:#3b3b38;
  --st-ok:oklch(.76 .08 145);--st-run:oklch(.78 .09 var(--brand-hue));--st-wait:oklch(.8 .12 78);--st-bad:oklch(.72 .13 45);--st-sched:oklch(.72 .05 230);--st-info:oklch(.76 .07 205);
  --t-bad:oklch(.74 .11 50);--t-wait:oklch(.82 .1 78);--on-wait:oklch(.22 .04 75);
  --scrim:rgba(0,0,0,.55);--shadow:rgba(0,0,0,.5);--shadow-s:rgba(0,0,0,.3);
  --bt:.95;--btc:.012;color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#161615;--side:rgba(22,22,21,.86);--card:#21211f;--field:#2b2b29;--stage:#2b2b29;
  --ink:#ecebe6;--ink2:#cfcec8;--ink3:#a6a59f;--on-ink:#161615;--on-ink-muted:rgba(22,22,21,.68);--knob:#ecebe6;
  --fill:rgba(255,255,255,.07);--fill-hover:rgba(255,255,255,.10);--fill-strong:rgba(255,255,255,.16);--fill-active:rgba(255,255,255,.26);--line-strong:rgba(255,255,255,.30);
  --line:rgba(255,255,255,.14);--line-ctl:rgba(255,255,255,.30);--hair:rgba(255,255,255,.10);--hover:rgba(255,255,255,.06);
  --sel:oklch(.78 .09 var(--brand-hue));--selfg:#161615;--ring:oklch(.78 .09 var(--brand-hue) / .7);--seg-on:#3d3d3a;--track-s:.025em;
  --m-wait:oklch(.78 .12 78);--m-work:oklch(.74 .09 var(--brand-hue));--m-pause:#5d5c57;--m-done:#3b3b38;
  --st-ok:oklch(.76 .08 145);--st-run:oklch(.78 .09 var(--brand-hue));--st-wait:oklch(.8 .12 78);--st-bad:oklch(.72 .13 45);--st-sched:oklch(.72 .05 230);--st-info:oklch(.76 .07 205);
  --t-bad:oklch(.74 .11 50);--t-wait:oklch(.82 .1 78);--on-wait:oklch(.22 .04 75);
  --scrim:rgba(0,0,0,.55);--shadow:rgba(0,0,0,.5);--shadow-s:rgba(0,0,0,.3);
  --bt:.95;--btc:.012;color-scheme:dark}'''   # домашний стиль «Полевой журнал» (~/Claude/Projects/_arsenal/house/house.tokens.css, v2 04.10), офлайн: шрифт Inter Tight — если стоит в системе


def chip(state):
    cls = {'ок': 'ok', 'застрял': 'wait', 'провал': 'bad', 'нет': 'none', 'жёлтый': 'wait', 'красный': 'bad', 'зелёный': 'ok'}.get(state, 'none')
    return cls


def render(D):
    L = D['level']; ms = D['missions']
    def li(xs): return ''.join(f'<li>{x}</li>' for x in xs)
    def kv(d):
        return ''.join(f'<div class="kv"><span class="k">{E(k)}</span><span class="v">{"<br>".join(E(x) for x in v)}</span></div>' for k, v in d.items())
    # сводка
    rows = []
    for M in ms:
        n = sum(len(P['stages']) for P in M['phases'])
        R = M['bot']; res = R['result'] if R else 'нет данных'
        okn = sum(1 for P in M['phases'] for S in P['stages'] if S['port'].get('state') == 'ок')
        ps2n = sum(1 for P in M['phases'] for S in P['stages'] if S['ps2'])
        cen = sum(len(S['census']) for P in M['phases'] for S in P['stages']) + sum(len(P['census']) for P in M['phases'])
        st = 'ok' if res == 'пройдена' else 'bad' if res == 'провал' else 'wait' if R else 'none'
        rec = f"{M['rec']['t0']}–{M['rec']['t1']}" if M['rec'] else 'в записи нет'
        rows.append(f'<tr><td><a href="#{E(M["id"])}">{E(M["id"])}</a></td><td>{E(M["title"])}</td><td class="num">{n}</td>'
                    f'<td><span class="dot {st}"></span>{E(res)}</td><td class="num">{okn}/{n}</td><td class="num">{cen or "—"}</td>'
                    f'<td class="num">{ps2n or "—"}</td><td class="mono">{E(rec)}</td></tr>')
    toc = ''.join(f'<a class="pill" href="#{E(M["id"])}"><span class="mono">{E(M["id"])}</span></a>' for M in ms)
    top = ''.join(f'<li><span class="dot {chip(t["level"])}"></span><b>{E(t["mission"])}</b> {E(t["title"])} — {E(t["text"])}</li>' for t in D['top'])
    body = []
    for M in ms:
        R = M['bot']
        head = (f'<section id="{E(M["id"])}" class="msn"><div class="sechead"><span class="mono n">{E(M["id"])}</span>'
                f'<h2>{E(M["title"])}</h2><span class="sub">{E(M["info"])}</span></div>')
        meta = []
        if R: meta.append(f'<span class="dot {chip("ок" if R["result"] == "пройдена" else "провал" if R["result"] == "провал" else "застрял")}"></span>[порт] бот: {E(R["result"])}'
                          + (f' — {E(R["why"])}' if R['why'] else '') + f', {R["t"]:.0f} с игры, этапов {R["stages"]}, попыток {R["attempts"]}')
        if M['rec']: meta.append(f'[запись PS2] {E(M["rec"]["t0"])}–{E(M["rec"]["t1"])}: ' + E('; '.join(M['rec']['notes'][:6])))
        else: meta.append('[запись PS2] в записи нет')
        body.append(head + '<div class="meta">' + '<br>'.join(meta) + '</div>')
        for P in M['phases']:
            ph = (f'<div class="phase"><div class="phhead"><b>{E(P["kind"])}</b> <span class="mono">{E(P["name"])} · {E(P["file"])}</span></div>'
                  f'<div class="phgrid"><div><div class="lbl">грузит при старте фазы [диск]</div><div class="small">{E(", ".join(P["loads"]) or "—")}</div></div>'
                  f'<div><div class="lbl">как ставится [диск]</div><div class="small">{E("; ".join(P["setup"]) or "—")}</div></div>'
                  + (f'<div><div class="lbl">у порта нет / частично [порт]</div><div class="small warn">{E("; ".join(P["census"]))}</div></div>' if P['census'] else '')
                  + '</div>')
            st_rows = []
            for i, S in enumerate(P['stages']):
                h = S['human']; p = S['port']; o = S['ps2']
                pc = chip(p.get('state', 'нет'))
                if S['census'] and pc == 'ok': pc = 'wait'
                for lvl, _ in S['notes']:
                    if lvl == 'жёлтый' and pc == 'ok': pc = 'wait'
                txt = f'<div class="stxt">«{E(S["text"])}»</div>' if S['text'] else ''
                icon = f'<span class="tag">значок {E(S["icon"])}</span>' if S['icon'] else ''
                c1 = (f'<div class="goal">{E(h["goal"])}</div>{txt}<div class="tags"><span class="tag">{E(S["obj"])}</span>{icon}'
                      + ''.join(f'<span class="tag">{E(f)}</span>' for f in h['flags']) + '</div>' + kv(h['details'])
                      + f'<div class="src mono">{E(h["src"])}</div>')
                c2 = f'<div class="status"><span class="dot {pc}"></span>{E(p.get("text", "—"))}</div>'
                if p.get('n', 1) > 1: c2 += f'<div class="small">заходов в этап: {p["n"]} (повтор с чекпоинта)</div>'
                if S['census']:
                    c2 += '<div class="lbl">порт не делает (перепись)</div><ul class="small warn">' + li(E(f"{c['cmd']} {c['res']}: {c['miss']}") for c in S['census']) + '</ul>'
                if h['ignored']: c2 += '<div class="lbl">команды, которые игра пропускает (coverage)</div><div class="small warn">' + E(', '.join(h['ignored'])) + '</div>'
                for lvl, n in S['notes']: c2 += f'<div class="small warn">{E(n)}</div>'
                o3 = 'none'
                if o:
                    miss = [x for x in o.get('reads', []) if x.get('port') is False]
                    oc = 'wait' if miss else 'ok'
                    c3 = (f'<div class="status"><span class="dot {oc}"></span>[PS2] этап начался на кадре {o.get("frame")} ({o.get("frame", 0) / 50:.1f} с от загрузки состояния)'
                          f'</div><div class="small">в памяти: тип цели {E(o.get("obj_name") or o.get("obj"))}, текст ' + (f'№{o["msg"]}' if o.get('msg') is not None else 'нет')
                          + (f', значок {E(o["icon"])}' if o.get('icon') else '') + (f', персонаж {E(o["npc"])} @ {E(o["loc"])}' if o.get('npc') else '')
                          + ' — совпадает со скриптом</div>')
                    scr = o.get('screens') or []
                    if len(scr) > 1 or (scr and scr[0][1] != 1):
                        c3 += '<div class="small">экран: ' + E(' → '.join(f'{f}: {SCREEN_RU.get(x, x)}' for f, x in scr)) + '</div>'
                    rd = o.get('reads', [])
                    if rd:
                        c3 += '<div class="lbl">читает с диска в этом этапе [PS2]</div><ul class="small">' + li(
                            ('<span class="warn">' if x.get('port') is False else '<span>') + E(f"{x['frame']}: {x['file'].split(':', 1)[-1]} {x['kb']} КБ")
                            + (' — у порта нет' if x.get('port') is False else '') + '</span>' for x in rd[:14]) + (f'<li>… ещё {len(rd) - 14}</li>' if len(rd) > 14 else '') + '</ul>'
                    if o.get('shot'): c3 += f'<img loading="lazy" src="{E(o["shot"])}" alt="кадр оригинала {o.get("shot_frame")}"><div class="src mono">кадр экрана {o.get("shot_frame")}</div>'
                    o3 = 'wait' if miss else 'ok'
                else:
                    c3 = '<div class="status"><span class="dot none"></span>не наблюдалось</div>' if not S['findings'] else ''
                    if M['rec']: c3 += f'<div class="small">смотреть запись PS2 {E(M["rec"]["t0"])}–{E(M["rec"]["t1"])}</div>'
                for col, txt, ev in S['findings']:
                    c3 += f'<div class="find"><span class="dot {chip(col)}"></span>{E(txt)}<div class="src mono">{E(ev)}</div></div>'
                    if col == 'красный': o3 = 'bad'
                    elif col == 'жёлтый' and o3 in ('ok', 'none'): o3 = 'wait'
                    elif col == 'зелёный' and o3 == 'none': o3 = 'ok'
                st_rows.append(f'<div class="stage"><div class="snum"><span class="mono">{E(P["name"])}.{i}</span></div>'
                               f'<div class="c c1">{c1}</div><div class="c c2 s-{pc}">{c2}</div><div class="c c3 s-{o3}">{c3}</div></div>')
            body.append(ph + '<div class="stages"><div class="stage hdr"><div></div><div>1 · СКРИПТ [диск]</div><div>2 · ПОРТ [порт]</div><div>3 · ОРИГИНАЛ [PS2]</div></div>'
                        + ''.join(st_rows) + '</div></div>')
        body.append('</section>')
    runs = ''
    for r in D.get('ps2_runs') or []:
        ev = ''.join(f'<li><span class="mono">{E(e[0])}</span> {E(e[1])}</li>' for e in r.get('events', []))
        sts, prev = '', None
        for s in r.get('changes') or r['stages']:
            new = s.get('ptr') != prev; prev = s.get('ptr')
            sts += (f'<tr><td class="mono">{s["frame"]}</td><td class="mono">{s["frame"] / 50:.1f}</td>'
                    + (f'<td>{E(s.get("obj_name") or s.get("obj") or "—")}</td><td>{E(s.get("text") or "—")}</td><td>{E(s.get("icon") or "—")}</td>' if new else '<td colspan="3" class="small">тот же этап</td>')
                    + f'<td>{E(s.get("screen_ru") or s.get("screen"))}</td></tr>')
        reads = ''.join(f'<tr><td class="mono">{E(x["frame"])}</td><td class="mono">{E(x["file"])}</td><td class="num">{E(x["kb"])}</td><td>{E(x.get("stage", ""))}</td>'
                        f'<td>{"<span class=warn>нет</span>" if x.get("port") is False else "есть" if x.get("port") else "не проверено"}</td></tr>'
                        for x in r.get('reads', [])[:120])
        runs += (f'<div class="card"><div class="lbl">прогон {E(r.get("run"))} · {E(r.get("plan"))} · {E(r.get("made", ""))}</div>'
                 f'<div class="grid2"><div><div class="lbl">что делал бот</div><ul class="small">{ev}</ul></div>'
                 f'<div><div class="lbl">смены этапа и экрана в памяти PS2</div><table class="t small"><tr><th>кадр</th><th>с</th><th>цель</th><th>текст</th><th>значок</th><th>экран</th></tr>{sts}</table></div></div>'
                 + (f'<div class="lbl">что оригинал читал с диска (первое чтение файла)</div><table class="t small"><tr><th>кадр</th><th>файл</th><th>КБ</th><th>этап</th><th>у порта</th></tr>{reads}</table>' if reads else '')
                 + '</div>')
    loads = ', '.join(Path(str(x)).stem for x in D['level_loads'])
    return PAGE.format(level=L, made=E(D['made']), toc=toc, rows=''.join(rows), top=top or '<li>нет данных бота</li>', body=''.join(body),
                       runs=runs or '<p class="small">прогонов оригинала нет: tools/twins/msn_timeline.py run --plan m0 --out …</p>',
                       loads=E(loads), bot=E(D['bot_run'] or 'нет'), tokens=CSS_TOKENS)


PAGE = '''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Атлас миссий L{level}</title>
<style>
/* house:tokens begin */
{tokens}
/* house:tokens end */
*{{box-sizing:border-box}}
a{{color:var(--ink);text-decoration-color:var(--line-strong);text-underline-offset:2px}} a:hover{{text-decoration-color:var(--ink)}}
body{{margin:0;background:var(--bg);color:var(--ink);font:var(--t2)/1.45 var(--sans);-webkit-font-smoothing:antialiased}}
main{{max-width:1440px;margin:0 auto;padding:32px 24px 80px}}
h1{{font:600 var(--t8)/1.1 var(--display);letter-spacing:-.01em;margin:0 0 8px}}
h2{{font:600 var(--t5)/1.2 var(--display);margin:0}}
.lead{{color:var(--ink2);max-width:980px;margin:0 0 24px}}
.mono{{font-family:var(--mono)}}
.small{{font-size:var(--t1);color:var(--ink2);letter-spacing:var(--track-s)}}
.lbl{{font-size:var(--t1);text-transform:uppercase;letter-spacing:.07em;color:var(--ink3);margin:10px 0 4px}}
.sechead{{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:20px;margin-top:40px}}
.sechead .n{{font-size:var(--t1);color:var(--ink3)}} .sechead .sub{{color:var(--ink3);font-size:var(--t1);max-width:720px}}
.toc{{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 24px}}
.pill{{display:inline-block;padding:4px 10px;border-radius:var(--r-pill);background:var(--fill);color:var(--ink);text-decoration:none;font-size:var(--t1)}}
.pill:hover{{background:var(--fill-hover)}}
.card{{background:var(--card);border-radius:var(--r-card);padding:16px;margin:12px 0;overflow-x:auto}}
table.t{{border-collapse:collapse;width:100%}} .t td{{overflow-wrap:anywhere}} .t th,.t td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--hair);vertical-align:top}}
.t th{{font-size:var(--t1);text-transform:uppercase;letter-spacing:.07em;color:var(--ink3);font-weight:500}}
.num{{font-family:var(--mono);text-align:right}}
.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:1px;background:var(--m-pause)}}
.dot.ok{{background:var(--st-ok)}} .dot.wait{{background:var(--st-wait)}} .dot.bad{{background:var(--st-bad)}} .dot.none{{background:var(--m-pause)}}
.meta{{color:var(--ink2);font-size:var(--t1);margin:8px 0 12px;letter-spacing:var(--track-s)}}
.phase{{margin:16px 0 8px}} .phhead{{margin:8px 0}} .phhead .mono{{color:var(--ink3);font-size:var(--t1)}}
.phgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;background:var(--card);border-radius:var(--r-card);padding:8px 16px 12px}}
.stages{{border-radius:var(--r-card);overflow:hidden;margin-top:8px}}
.stage{{display:grid;grid-template-columns:72px 1.25fr 1fr 1fr;gap:0;border-bottom:1px solid var(--hair);background:var(--stage)}}
.stage.hdr{{background:var(--card);font-size:var(--t1);text-transform:uppercase;letter-spacing:.07em;color:var(--ink3)}}
.stage.hdr>div{{padding:8px 12px}}
.stage>.c{{padding:10px 12px;border-left:1px solid var(--hair);min-width:0;overflow-wrap:anywhere}}
.snum{{padding:10px 8px;font-size:var(--t1);color:var(--ink3)}}
.c.s-wait{{background:color-mix(in oklch,var(--st-wait) 10%,transparent)}}
.c.s-bad{{background:color-mix(in oklch,var(--st-bad) 12%,transparent)}}
.c.s-ok{{background:color-mix(in oklch,var(--st-ok) 8%,transparent)}}
.goal{{font-weight:600}} .stxt{{font-family:var(--mono);font-size:var(--t1);margin:2px 0 4px}}
.tags{{display:flex;flex-wrap:wrap;gap:4px;margin:4px 0}} .tag{{font-size:var(--t1);padding:1px 8px;border-radius:var(--r-pill);background:var(--fill);color:var(--ink2)}}
.kv{{display:grid;grid-template-columns:96px 1fr;gap:8px;font-size:var(--t1);padding:2px 0;color:var(--ink2)}} .kv .k{{color:var(--ink3)}}
.src{{font-size:var(--t1);color:var(--ink3);margin-top:6px}}
.warn{{color:var(--t-wait)}}
.status{{font-weight:500}} .find{{font-size:var(--t1);margin:8px 0;color:var(--ink2)}}

ul{{margin:4px 0;padding-left:18px}} li{{margin:2px 0}}
img{{max-width:100%;border-radius:var(--r);margin-top:6px;display:block}}
.grid2{{display:grid;grid-template-columns:1fr 1.4fr;gap:16px}}
@media (max-width:900px){{.stage{{grid-template-columns:1fr}} .stage>.c{{border-left:0;border-top:1px solid var(--hair)}} .stage.hdr{{display:none}} .grid2{{grid-template-columns:1fr}} main{{padding:20px 16px 60px}} h1{{font-size:var(--t7)}}}}
</style></head><body><main>
<div class="small mono">SHAR → PSP · уровень {level} · собрано {made} · tools/missions/atlas.py</div>
<h1>Атлас миссий L{level}</h1>
<p class="lead">Каждый этап каждой миссии в трёх слоях рядом: <b>скрипт</b> диска (что задумано), <b>порт</b> по факту (что делает наш бот-миссионер в той же игре) и <b>оригинал</b> по факту (память PS2 и запись). Цвет строки — расхождение: зелёный пройдено, жёлтый частично (порт чего-то не делает или этап закрылся мгновенно), красный провал, серый — нет данных. Метки: [диск] [порт] [PS2] [запись PS2] [правило порта].</p>
<div class="toc">{toc}</div>
<div class="sechead"><span class="mono n">01</span><h2>Сводка</h2><span class="sub">бот: {bot}</span></div>
<div class="card"><table class="t"><tr><th>миссия</th><th>название</th><th>этапов</th><th>бот [порт]</th><th>пройдено этапов</th><th>строк «нет» переписи</th><th>этапов снято с PS2</th><th>запись PS2</th></tr>{rows}</table></div>
<div class="sechead"><span class="mono n">02</span><h2>Где порт расходится</h2><span class="sub">по итогу бота; подробности — в строках этапов</span></div>
<div class="card"><ul>{top}</ul></div>
<div class="sechead"><span class="mono n">03</span><h2>Оригинал по факту</h2><span class="sub">прогоны своей PCSX2 без окна и звука: что нажимал бот, когда менялся этап в памяти, что читалось с диска</span></div>
{runs}
<div class="sechead"><span class="mono n">04</span><h2>Что грузит уровень всегда</h2><span class="sub">level.mfk [диск]</span></div>
<div class="card small">{loads}</div>
<div class="sechead"><span class="mono n">05</span><h2>Миссии по этапам</h2><span class="sub">фаза 0 — вступление (прогулка до разговора), фаза 1 — сама миссия</span></div>
{body}
</main></body></html>'''


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--out', help='папка атласа (по умолчанию <данные>/build/АТЛАС_МИССИЙ_L<N>)')
    ap.add_argument('--run-bots', action='store_true'); ap.add_argument('--procs', type=int, default=4); ap.add_argument('--secs', type=float, default=900)
    ap.add_argument('--bots', help='готовый прогон миссионера (папка с m*.log)')
    ap.add_argument('--ps2', nargs='*', help='папки прогонов tools/twins/msn_timeline.py (по умолчанию <атлас>/ps2/*)')
    ap.add_argument('--import-ps2', nargs='*', help='прогон msn_timeline.py (со снимками) → <атлас>/ps2/<имя>/: timeline.json и кадры этапов (без снимков)')
    ap.add_argument('--ps2-mission', default='m0', help='какая миссия в импортируемом прогоне (план m0 → m0, sr3 → sr3)')
    a = ap.parse_args()
    out = Path(a.out) if a.out else DATA / f'build/АТЛАС_МИССИЙ_L{a.level}'
    out.mkdir(parents=True, exist_ok=True)
    bot_run = Path(a.bots) if a.bots else None
    if a.import_ps2:
        for d in a.import_ps2: import_ps2(Path(d), out, a.ps2_mission)
    if a.run_bots:
        import compile as MC
        c = MC.Compiler(a.level); c.compile()
        bot_run = run_bots(a.level, out / 'bots', min(4, a.procs), a.secs, len(c.pack.missions))
    if bot_run is None: bot_run = latest_bot_run(out)
    ps2 = a.ps2 if a.ps2 is not None else sorted(str(d) for d in (out / 'ps2').glob('*') if d.is_dir()) if (out / 'ps2').exists() else []
    build(a.level, out, bot_run, ps2)


if __name__ == '__main__':
    main()
