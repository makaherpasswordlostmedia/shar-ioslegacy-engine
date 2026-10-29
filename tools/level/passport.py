#!/usr/bin/env python3
"""Паспорт уровня N (канон docs/КАНОН_УРОВНЯ.md §1 Ф0.2, §3): что в уровне есть — из данных диска Роба, до первой строки кода.

  python3 tools/level/passport.py N                 паспорт -> docs/levels/LN_ПАСПОРТ.md (≤ 10 КБ) + build/level/lN/passport.json
  python3 tools/level/passport.py N --check         + сверка: известные числа (tools/level/known.tsv) и пакеты уровня (build/)
  python3 tools/level/passport.py 1 --gate          гейт «сначала красный»: чужой уровень и испорченное число обязаны дать FAIL,
                                                    настоящий уровень — PASS (журнал build/gates/level/passport-lN.log)
  --data-level M   данные уровня M под номером N (так делается отрицательный контроль «чужой уровень»)
  --plant КЛЮЧ=ЧИСЛО   испортить число паспорта (отрицательный контроль «испорченное число»), например cards=8
  --out / --json   куда писать (по умолчанию как выше); --no-write — только проверка

Источники (только чтение диска; парсеры проекта, ничего нового): скрипты level0N/*.mfk (tools/missions/mfk.py, компилятор
миссий tools/missions/compile.py — названия, этапы, таймеры, условия провала, старты), локаторы уровня (tools/collect_export.py
all_locators: карточки CollectorCard, осы w_*, будки SummonVehiclePhone, ключи Wrench, монеты — локаторы вида 14, двери
комнат — вида 7), гэги (collect_export.parse_gags), осы (parse_wasps), лавка и будка (tools/shop_export.py), костюмы
(tools/skins_export.py), машина (.con: tools/con2h.py; старт: tools/level_sweep.find_spawn), атмосфера (tools/sound_export.py:
регион с наибольшим числом объёмов ворот — карта и время суток), новое против уровня 1 (tools/sandbox/level_check.py: команды,
типы чанков, docs/state/handlers.tsv), коды мест (tools/place.py). Параметры, которые движок держит числом уровня 1 (риски
уровня N), — таблица L1_WIRED ниже: место в viewer/ и значение, которое там прошито.

Проверка принадлежности (любой уровень, без таблицы известных): номера карточек = N·10+k, миссии из level0N, ключи названий
MISSION_TITLE_L{N}, локатор старта level{N}_carstart. Сверка с пакетами — другой путь от того же диска (экспортёры): CLT1
(карточки, осы, гэги), MSN1 (миссии, этапы), SHI1 (комнаты), PRP2 в level.shr (монеты), CAR1 (машина)."""
import argparse, collections, json, math, re, struct, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / 'hit-and-run-web/source/game'
ART, SCR = GAME / 'art', GAME / 'scripts/missions'
for p in ('tools', 'tools/missions', 'tools/sandbox', 'hit-and-run-web/tools'):
    sys.path.insert(0, str(ROOT / p))
KNOWN = ROOT / 'tools/level/known.tsv'
ROOMS = {0: 'школа (SpringfieldElementary)', 1: 'Kwik-E-Mart', 2: 'дом Симпсонов', 3: 'DMV', 4: "Moe's", 5: "Android's Dungeon",
         6: 'Обсерватория', 7: 'комната Барта'}
MAP_OF = {'suburbs': 'Evergreen Terrace (пригород)', 'city': 'центр города', 'seaside': 'Squidport (набережная)',
          'halloween': 'Evergreen Terrace, Хэллоуин'}
# Параметры уровня, которые движок сейчас держит значением уровня 1 (grep по viewer/, 30.09): на уровне N с другим числом — риск
L1_WIRED = [
    ('hnr_decay', 'viewer/main.c', r'gameHnrRate\(&G, dt, inR \? 10\.f : G\.hnrLatched \? 6\.f : 3\.f\)', 'спад Hit & Run 3/с'),
    ('chase_cars', 'viewer/msn_view.c', r'#define HNR_CHASE_CARS 1\b', 'машин погони 1'),
    ('chase_con', 'viewer/msn_view.c', r'Pursuit\\\\L1cop\.con', 'полиция Pursuit\\L1cop.con'),
    ('chase_car', 'viewer/msn_view.c', r'"cPolice"', 'машина погони cPolice'),
]
TYPE_RU = {'goto_timed': 'доехать на время', 'race': 'гонка', 'destroy': 'таран', 'follow': 'слежка', 'delivery': 'сбор', 'dump': 'сбор выпавшего',
           'buycar': 'покупка машины', 'coins': 'ставка', 'fmv': 'ролик', 'timer': 'таймер', 'goto': 'доехать',
           'talkto': 'разговор', 'interior': 'комната', 'getin': 'сесть', 'losetail': 'оторваться', 'loseTail': 'оторваться',
           'pickupitem': 'подобрать', 'dialogue': 'разговор', 'gooutside': 'выйти'}
MAIN_OBJ = ('race', 'destroy', 'follow', 'losetail', 'loseTail', 'delivery', 'dump', 'pickupitem', 'coins', 'buycar', 'fmv', 'timer')   # приоритет
COND_RU = {'timeout': 'таймер', 'outofvehicle': 'вне машины', 'damage': 'урон', 'race': 'проиграл', 'position': 'место',
           'followdistance': 'отстал', 'hitandrun': 'арест', 'keepbarrier': 'барьер'}


def rel(p): return str(p).replace(str(ROOT) + '/', '')


def sh(cmd):
    try: return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception: return ''


# ---------------------------------------------------------------- сбор данных уровня
def calls(n, name):
    import mfk
    p = SCR / f'level{n:02d}' / name
    return mfk.parse(p.read_text(errors='replace'))[0] if p.exists() else []


def mission_json(n, work):
    """Компилятор миссий в память (build/ не трогается): его JSON-дамп — миссии, фазы, этапы, команды с локаторами."""
    import compile as MC
    c = MC.Compiler(n); c.compile()
    work.mkdir(parents=True, exist_ok=True); f = work / f'level{n:02d}.msn.json'
    MC.dump_json(c.pack, f)
    return json.loads(f.read_text()), c


def loc_of(args):
    for a in args:
        if isinstance(a, dict) and 'pos' in a: return a['loc'], a['pos']
    return None, None


def missions(n, work):
    import place
    d, comp = mission_json(n, work)
    out = []
    for m in d['missions']:
        fl = m['flags']
        kind = 'сюжет' if not fl & 1 else ('гонка' if fl & 2 else 'ставка' if fl & 4 else 'бонус' if fl & 8 else 'бонус')
        if fl & 256: kind = 'переход'
        if fl & 16: kind += ', без скрипта'
        objs, conds, stime, addt, par, forced, start, reset = [], collections.Counter(), [], [], None, [], None, None
        for p in m['phases']:
            for x in p['setup']:
                if x['op'].startswith('SetMissionResetPlayer') and reset is None:
                    nm, pos = loc_of(x['args']); reset = (nm, pos) if pos else None
                if x['op'] == 'InitLevelPlayerVehicle': forced.append(str(x['args'][0]))
                if x['op'] == 'SetForcedCar': forced.append('SetForcedCar')
            for k, s in enumerate(p['stages']):
                objs.append(s['obj'])
                for cn in s['conds']: conds[cn] += 1
                for x in s['cmds']:
                    if x['op'] == 'SetStageTime' and x['args']: stime.append(float(x['args'][0]))
                    if x['op'] == 'AddStageTime' and x['args'] and float(x['args'][0]) > 0: addt.append(float(x['args'][0]))
                    if x['op'] == 'SetParTime' and x['args']: par = float(x['args'][0])
                if start is None and k == 0:   # старт миссии: цель первого этапа первой фазы (SetDestination, иначе NPC)
                    for op in ('SetDestination', 'AddNPC', 'SetTalkToTarget'):
                        hit = [loc_of(x['args']) for x in s['cmds'] if x['op'] == op]
                        hit = [h for h in hit if h[1]]
                        if hit: start = hit[0]; break
        if start is None: start = reset
        stime_real = [t for t in stime if t > 1]
        main = next((o for o in MAIN_OBJ if o in objs), 'goto_timed' if stime_real else 'goto')
        timer = (f'{int(sum(stime_real))} с' if stime_real else '') + (f' +{int(addt[0])}×{len(addt)}' if addt else '') + \
                (f' пар {int(par)} с' if par else '')
        out.append(dict(id=m['id'], title=m['title'], kind=kind, flags=fl, stages=len(objs), main=main, objs=objs,
                        timer=timer.strip() or '—', stage_time=stime_real, add_time=addt, par_time=par,
                        fails=dict(conds), forced=[f for f in forced if f != 'SetForcedCar'] if 'SetForcedCar' in forced else [],
                        forced_cmd='SetForcedCar' in forced,
                        start=dict(loc=start[0], pos=[round(v, 2) for v in start[1]], code=place.code(start[1][0], start[1][2])) if start else None))
    st = dict(stages=len(comp.pack.stages), phases=len(comp.pack.phases), warnings=len(comp.warn), errors=len(comp.err))
    return out, st


def level_locators(n):
    import collect_export as CE
    files = [ART / f'l{n}_terra.p3d', *sorted(ART.glob(f'l{n}[rzi]*.p3d')), *sorted((ART / f'missions/level0{n}').glob('*.p3d'))]
    return CE.all_locators([f for f in files if f.exists()])


def collectibles(n, locs):
    import collect_export as CE, place
    cards, act, coins, doors, wcars = [], collections.defaultdict(list), [], [], []
    cars = {p.stem.lower() for p in (GAME / 'scripts/cars').glob('*.con')}
    for nm, Ls in locs.items():
        for L in Ls:
            if L['kind'] == 14: coins.append(L['pos'])
            if L['kind'] == 3 and L['file'].startswith(f'l{n}') and (nm.lower() + '_v') in cars:   # машина мира (CarStart с именем машины)
                wcars.append(dict(name=nm, car=nm.lower() + '_v', pos=[round(v, 2) for v in L['pos']], code=place.code(L['pos'][0], L['pos'][2]), file=L['file']))
            if L['kind'] == 7 and L['file'].startswith(f'l{n}'): doors.append(dict(name=nm, pos=L['pos'], room=L['strs'][0] if L['strs'] else nm))
            if L['kind'] != 9: continue
            ev = [s for s in L['strs'] if s[:1].isupper()]
            key = ev[-1] if ev else '?'
            act[key].append(dict(name=nm, pos=L['pos'], file=L['file']))
            if 'CollectorCard' in L['strs']:
                cid = L['strs'][0]; m = re.fullmatch(r'card(\d)(\d)', cid)
                cards.append(dict(locator=nm, data=cid, level=int(m.group(1)) if m else None, k=int(m.group(2)) if m else None,
                                  pos=[round(v, 2) for v in L['pos']], code=place.code(L['pos'][0], L['pos'][2]), file=L['file']))
    cards.sort(key=lambda c: c['data'])
    icalls, lcalls = calls(n, 'leveli.mfk'), calls(n, 'level.mfk')
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        wasps, prealloc = CE.parse_wasps(icalls, locs)
        gags = CE.parse_gags(lcalls, locs)
    wl = sorted(nm for nm in locs if nm.lower().startswith('w_') and any('wasps' in L['file'] for L in locs[nm]))
    spawned = {w['loc'].lower() for w in wasps}
    booths = act.get('SummonVehiclePhone', [])
    return dict(
        cards=cards, card_locator_names=len({c['locator'] for c in cards}),
        wasps=[dict(name=w['name'], loc=w['loc'], pos=[round(v, 2) for v in w['pos']], code=place.code(w['pos'][0], w['pos'][2]),
                    static=w['static']) for w in wasps],
        wasp_locators=len(wl), wasp_unspawned=[x for x in wl if x.lower() not in spawned], wasp_prealloc=prealloc,
        gags=len(gags), gags_rooms=sum(g['interior'] >= 0 for g in gags), gags_fmv=sum(bool(g['fmv']) for g in gags),
        gags_coins=sum(g['coins'] > 0 for g in gags), gags_action=sum(g['trigKind'] for g in gags),
        coins=len(coins), wrenches=len(act.get('Wrench', [])),
        booths=[dict(name=b['name'], pos=[round(v, 2) for v in b['pos']], code=place.code(b['pos'][0], b['pos'][2]), file=b['file']) for b in booths],
        skin_spots=[dict(name=b['name'], file=b['file']) for b in act.get('PurchaseSkin', [])], world_cars=wcars,
        actions={k: len(v) for k, v in sorted(act.items())}, doors=doors)


def shops(n):
    import shop_export as SH, skins_export as SK
    return dict(forsale=[dict(car=c, price=p, seller=s) for c, p, s in SH.forsale_file_order(n)],
                rewards=[dict(car=c, how=q) for c, q in SH.level_cars(n)],
                booth_gallery=[c for c, _, _ in SH.phone_cars(n)],
                skins=[dict(name=a, model=m, price=p) for a, m, p in SK.skins(n)])


def rooms(n, doors):
    import place
    files = sorted(p.name for p in ART.glob(f'l{n}i*.p3d') if re.fullmatch(rf'l{n}i\d+\.p3d', p.name))
    out = []
    names = {'SpringfieldElementary': 0, 'KwikEMart': 1, 'SimpsonsHouse': 2, 'DMV': 3, 'Moes': 4, 'AndroidsDungeon': 5,
             'Observatory': 6, 'BartRoom': 7}
    for f in files:
        k = int(re.search(r'i(\d+)', f).group(1))
        nm = next((a for a, b in names.items() if b == k), f)
        dr = [d for d in doors if d['room'] == nm or d['name'].lower().startswith(nm.lower())]
        out.append(dict(file=f, index=k, name=nm, ru=ROOMS.get(k, nm),
                        door=dict(pos=[round(v, 2) for v in dr[0]['pos']], code=place.code(dr[0]['pos'][0], dr[0]['pos'][2])) if dr else None))
    return out


def world(n):
    ic = calls(n, 'leveli.mfk'); lc = calls(n, 'level.mfk')
    g = lambda op: [c.args for c in ic + lc if c.op == op]
    chase = g('CreateChaseManager')
    return dict(driver=str(g('AddCharacter')[0][0]) if g('AddCharacter') else '?',
                traffic=[str(a[0]) for a in g('AddTrafficModel')], peds=len(g('AddPed')), ped_groups=len(g('CreatePedGroup')),
                ambient_chars=len(g('AddAmbientCharacter')), bonus_givers=len(g('AddNPCCharacterBonusMission')),
                chase_car=str(chase[0][0]) if chase else '', chase_con=str(chase[0][1]) if chase and len(chase[0]) > 1 else '',
                chase_cars=int(float(g('SetNumChaseCars')[0][0])) if g('SetNumChaseCars') else None,
                hnr_decay=float(g('SetHitAndRunDecay')[0][0]) if g('SetHitAndRunDecay') else None,
                tutorial=str(g('EnableTutorialMode')[0][0]) if g('EnableTutorialMode') else '',
                teleports=[str(a[0]) for a in g('AddTeleportDest')], disposable=[str(a[0]) for a in g('LoadDisposableCar')],
                booth_select=[str(a[1]) if len(a) > 1 else str(a[0]) for a in g('AddVehicleSelectInfo')],
                gag_bindings=len(g('AddGagBinding')), suppress_driver=len(g('SuppressDriver')))


def ambience(n):
    import sound_export as SE
    amb = SE.ambience_map(); w = collections.Counter()
    for f, nm, kind, d, pos, vols in SE.locators(n):
        if kind != 0 or len(d) < 4: continue
        ev, = struct.unpack_from('<I', d, 0)
        if ev in amb and amb[ev]['file']: w[amb[ev]['region'].replace('_region', '')] += len(vols)
    return w.most_common(4)


def car_info(n, car):
    import con2h
    p = GAME / f'scripts/cars/{car}.con'
    if not p.exists(): return dict(car=car)
    v = con2h.parse(p)
    return dict(car=car, mass=v.get('SetMass'), top=v.get('SetTopSpeedKmh'))


def new_vs_l1(n, work):
    """Команды скриптов и типы чанков, которых нет на уровне 1 (как level_check disk), плюс есть ли у команды исполнитель
    в движке (case MSN_OP_* в viewer/ — упоминание, не доказательство исполнения)."""
    import mfk, level_check as LC, tablo
    def ops(k):
        c = collections.Counter()
        for p in sorted((SCR / f'level{k:02d}').glob('*.mfk')):
            for x in mfk.parse(p.read_text(errors='replace'))[0]: c[x.op] += 1
        return c
    o, o1 = ops(n), ops(1)
    src = '\n'.join(p.read_text(errors='replace') for p in list((ROOT / 'viewer').glob('*.c')) + list((ROOT / 'viewer/mission').glob('*.c')))
    cmds = [dict(op=k, n=o[k], engine=bool(re.search(r'case MSN_OP_' + k.upper() + r'\b', src))) for k in sorted(set(o) - set(o1))]
    H = tablo.handlers()
    cache = ROOT / 'build/level/chunk-ids.json'   # общий кэш по файлам диска (ключ — файл, размер, время)
    ids = LC.chunk_ids(n, cache); ids1 = LC.chunk_ids(1, cache)
    chunks = [dict(id=k, n=ids[k], fate=H.get(k, 'нет')) for k in sorted(set(ids) - set(ids1))]
    unh = sorted(k for k in ids if not H.get(k, 'нет').startswith(('обработчик', 'проигнорировано')))
    return dict(commands=cmds, chunks=chunks, chunks_total=len(ids), chunks_unhandled=len(unh))


def l1_wired():
    out = {}
    for key, f, rx, what in L1_WIRED:
        p = ROOT / f; txt = p.read_text(errors='replace') if p.exists() else ''
        m = re.search(rx, txt)
        out[key] = dict(file=f, line=txt[:m.start()].count('\n') + 1 if m else None, what=what, wired=bool(m))
    return out


def collect(n, data_level=None, work=None):
    """Весь паспорт уровня n (данные уровня data_level, если задан — отрицательный контроль) -> dict"""
    import place
    from level_sweep import find_spawn
    dl = data_level or n
    work = work or ROOT / f'build/level/l{n}'
    locs = level_locators(dl)
    col = collectibles(dl, locs)
    ms, mst = missions(dl, work)
    sp = find_spawn(dl)
    W = world(dl)
    P = dict(level=n, data_level=dl, generated=time.strftime('%Y-%m-%d %H:%M'), commit=sh(['git', 'rev-parse', '--short', 'HEAD']),
             driver=W['driver'], car=car_info(dl, sp.get('car', '?')),
             start=dict(locator=sp.get('locator'), pos=sp.get('pos'), heading=sp.get('heading'),
                        code=place.code(sp['pos'][0], sp['pos'][2]) if sp.get('pos') else '--'),
             ambience=ambience(dl), missions=ms, msn_stats=mst, collect=col, shops=shops(dl), rooms=rooms(dl, col['doors']),
             world=W, new=new_vs_l1(dl, work) if dl != 1 else None, wired=l1_wired(),
             zones=len([p for p in ART.glob(f'l{dl}z*.p3d')]), regions=len([p for p in ART.glob(f'l{dl}r*.p3d')]))
    top = P['ambience'][0][0] if P['ambience'] else ''
    fam = next((k for k in MAP_OF if top.startswith(k)), '')
    P['map'] = MAP_OF.get(fam, top); P['daytime'] = 'Хэллоуин (ночь)' if fam == 'halloween' else 'ночь' if 'night' in top else 'день' if 'day' in top else '?'
    # та же карта: общие названия телепортов с другими уровнями
    same = []
    for k in range(1, 8):
        if k == dl: continue
        t = {str(c.args[0]) for c in calls(k, 'level.mfk') if c.op == 'AddTeleportDest'}
        if t and len(t & set(W['teleports'])) >= 0.6 * max(1, len(W['teleports'])): same.append(k)
    P['same_map'] = same
    return P


# ---------------------------------------------------------------- числа паспорта (для сверки)
def numbers(P):
    c = P['collect']
    return dict(missions=len(P['missions']), story=sum(m['kind'].startswith('сюжет') for m in P['missions']),
                bonus=sum(not m['kind'].startswith('сюжет') for m in P['missions']), stages=P['msn_stats']['stages'],
                cards=len(c['cards']), card_locator_names=c['card_locator_names'], wasps=len(c['wasps']),
                wasp_locators=c['wasp_locators'], wasp_prealloc=c['wasp_prealloc'], gags=c['gags'], coins=c['coins'],
                wrenches=c['wrenches'], booths=len(c['booths']), rooms=len(P['rooms']), skins=len(P['shops']['skins']),
                forsale=len(P['shops']['forsale']), teleports=len(P['world']['teleports']), car=P['car']['car'], driver=P['driver'])


def ownership(P):
    """Принадлежность уровню P['level'] по самим данным (без таблицы): -> [(ok, что, подробно)]"""
    n = P['level']; rows = []
    bad = [c['data'] for c in P['collect']['cards'] if c['level'] != n]
    rows.append((not bad and P['collect']['cards'], f'номера карточек card{n}k (уровень {n})', ', '.join(c['data'] for c in P['collect']['cards'])))
    rows.append((P['start']['locator'] == f'level{n}_carstart', f'локатор старта level{n}_carstart', str(P['start']['locator'])))
    rows.append((P['data_level'] == n, f'скрипты миссий level{n:02d}', f"данные уровня {P['data_level']}"))
    return rows


def packs(P):
    """Те же числа из собранных пакетов уровня (другой путь от диска: экспортёры) -> {ключ: (число, файл)}"""
    n, B = P['level'], ROOT / 'build'
    L = B / 'levels' / f'l{n}'
    first = lambda *ps: next((p for p in ps if p.exists()), None)
    out = {}
    f = first(B / f'collect-l{n}.shr', L / f'collect-l{n}.shr')
    if f:
        b = f.read_bytes()
        if b[:4] == b'CLT1':
            lvl, = struct.unpack_from('<I', b, 8); nc, = struct.unpack_from('<I', b, 28); nw, = struct.unpack_from('<I', b, 36); ng, = struct.unpack_from('<I', b, 44)
            out.update(cards=(nc, f), wasps=(nw, f), gags=(ng, f), clt_level=(lvl, f))
    f = first(*( [B / 'missions/level01.msn'] if n == 1 else []), L / f'missions/level{n:02d}.msn', L / f'level{n:02d}.msn')
    if f:
        b = f.read_bytes()
        if b[:4] == b'MSN1':
            lvl, = struct.unpack_from('<H', b, 6); nm, = struct.unpack_from('<I', b, 16 + 6 * 8 + 4); ns, = struct.unpack_from('<I', b, 16 + 8 * 8 + 4)
            out.update(missions=(nm, f), stages=(ns, f), msn_level=(lvl, f))
    f = first(B / f'interiors-l{n}.bin', L / f'interiors-l{n}.bin')
    if f:
        b = f.read_bytes()
        if b[:4] == b'SHI1': out['rooms'] = (struct.unpack_from('<I', b, 4)[0], f)
    f = first(*([B / 'level.shr'] if n == 1 else []), L / 'level.shr')
    if f:
        with open(f, 'rb') as fh: head = fh.read(104)
        if head[:4] == b'SHR7':
            po, co = struct.unpack_from('<II', head, 96)
            with open(f, 'rb') as fh:
                fh.seek(po); pr = fh.read(64)
                if pr[:4] in (b'PRP1', b'PRP2'): out['coins'] = (struct.unpack_from('<I', pr, 28)[0], f)
                fh.seek(co); cr = fh.read(32)
                if cr[:4] == b'CAR1':   # версия 2: pad[0] @24 — смещение блока машины, в нём char car[16] (docs/FORMAT_SHR7.md)
                    ver, = struct.unpack_from('<I', cr, 4); boff, = struct.unpack_from('<I', cr, 24)
                    if ver >= 2 and boff:
                        fh.seek(co + boff); nm = fh.read(16).split(b'\0')[0].decode('latin1', 'replace')
                        if nm: out['car'] = (nm, f)
    return out


def known_rows(n):
    rows = []
    if KNOWN.exists():
        for l in KNOWN.read_text().splitlines():
            if not l.strip() or l.startswith('#'): continue
            p = l.split('\t')
            if len(p) != 5 or p[3] not in ('равно', 'справка'):   # битая строка таблицы — не молчать (так было 30.09: слипся режим)
                raise SystemExit(f'{rel(KNOWN)}: строка не «уровень ключ значение равно|справка источник»: {l[:80]}')
            if int(p[0]) == n: rows.append(dict(key=p[1], value=p[2], mode=p[3], source=p[4]))
    return rows


def check(P, R):
    """Сверка паспорта: принадлежность уровню, пакеты, известные числа. R.add(status, что, подробно)"""
    N = numbers(P)
    for ok, what, det in ownership(P): R.check(bool(ok), 'принадлежность: ' + what, det)
    pk = packs(P)
    if not pk: R.warn('пакеты уровня', 'нет собранных пакетов в build/ — сверка только с таблицей известных')
    for k, (v, f) in pk.items():
        if k in ('clt_level', 'msn_level'):
            R.check(int(v) == P['level'], f'пакет {k}', f'{rel(f)}: уровень {v}'); continue
        R.check(str(v) == str(N.get(k)), f'пакет: {k}', f'паспорт {N.get(k)}, {rel(f)} {v}')
    for r in known_rows(P['level']):
        got = N.get(r['key'])
        if r['mode'] == 'равно':
            R.check(str(got) == r['value'], f"известное: {r['key']} = {r['value']}", f"паспорт {got}; {r['source']}")
        else:   # справка «ключ/объясняющий»: число другого источника обязано совпасть с объясняющим числом паспорта
            key, _, why = r['key'].partition('/')
            got, alt = N.get(key), N.get(why)
            R.check(str(alt) == r['value'], f"известное (справка): {key} {r['value']}",
                    f"паспорт {key} {got}; {r['value']} = {why} {alt}; {r['source']}")
    return N


class Rep:
    def __init__(self, quiet=False): self.rows = []; self.quiet = quiet
    def add(self, st, what, det=''):
        self.rows.append((st, what, det))
        if not self.quiet: print(f'  {st:4} {what}' + (f' — {det}' if det else ''), flush=True)
    def check(self, ok, what, det=''): self.add('PASS' if ok else 'FAIL', what, det); return ok
    def warn(self, what, det=''): self.add('WARN', what, det)
    @property
    def failed(self): return any(s == 'FAIL' for s, _, _ in self.rows)


# ---------------------------------------------------------------- паспорт в markdown (≤ 10 КБ)
def fmt_md(P, chk=None):
    n, c, S, W = P['level'], P['collect'], P['shops'], P['world']
    L = [f'# Уровень {n} · паспорт (Ф0, данные диска)',
         '',
         f"Сгенерирован `tools/level/passport.py {n}` {P['generated']} (код {P['commit']}); полные данные — `build/level/l{n}/passport.json`."
         ' Источник каждого числа — диск Роба (скрипты, локаторы, .con); код места — `tools/place.py`.',
         '']
    car = P['car']
    L += ['## Водитель, машина, карта',
          f"- Водитель **{P['driver']}**, машина **{car['car']}** ({int(car.get('mass') or 0)} кг, {int(car.get('top') or 0)} км/ч по .con); "
          f"старт `{P['start']['locator']}` {P['start']['code']}",
          f"- Карта: {P['map']}, {P['daytime']} (атмосфера: {', '.join(f'{r} {k}' for r, k in P['ambience'][:3])}); районов {P['regions']}, зон {P['zones']}, "
          f"телепортов {len(W['teleports'])}" + (f"; та же карта у уровней {', '.join(map(str, P['same_map']))}" if P['same_map'] else ''),
          f"- Машины миссий: " + (', '.join(f"{m['id']} {'/'.join(m['forced']) or '—'}" for m in P['missions'] if m['forced_cmd']) or 'нет SetForcedCar')
          + (f"; разовая машина {', '.join(W['disposable'])}" if W['disposable'] else ''),
          '']
    L += [f"## Миссии: {len(P['missions'])} ({sum(m['kind'] == 'сюжет' for m in P['missions'])} сюжет + "
          f"{sum(m['kind'] != 'сюжет' for m in P['missions'])} бонус), этапов {P['msn_stats']['stages']}",
          '', '| миссия | тип | этапов | таймер | провал | старт |', '|---|---|---|---|---|---|']
    for m in P['missions']:
        fails = ', '.join(COND_RU.get(k, k) for k in m['fails']) or '—'
        L.append(f"| {m['id']} {m['title']} | {m['kind']}: {TYPE_RU.get(m['main'], m['main'])} | {m['stages']} | {m['timer']} | {fails} | "
                 f"{m['start']['code'] if m['start'] else '--'} |")
    L.append('')
    wl = c['wasp_locators']
    L += ['## Коллекции и объекты',
          f"- Карточки **{len(c['cards'])}**: " + ', '.join(f"{x['data']} {x['code']}" + ('' if x['locator'] == x['data'] else f" (локатор {x['locator']})") for x in c['cards']),
          f"- Осы **{len(c['wasps'])}** (AddSpawnPointByLocatorScript; живых сразу {c['wasp_prealloc']}), локаторов w_* в wasps.p3d {wl}"
          + (f"; без точки появления: {', '.join(c['wasp_unspawned'])}" if c['wasp_unspawned'] else ''),
          f"- Гэги **{c['gags']}**: в комнатах {c['gags_rooms']}, по △ {c['gags_action']}, с монетами {c['gags_coins']}, с роликом {c['gags_fmv']}"
          + (f"; AddGagBinding {W['gag_bindings']}" if W['gag_bindings'] else ''),
          f"- Монеты **{c['coins']}** (локаторы вида 14), гаечные ключи {c['wrenches']}, будки {len(c['booths'])} (SummonVehiclePhone)"
          + (f"; машины мира: {', '.join(x['car'] + ' ' + x['code'] for x in c['world_cars'])}" if c['world_cars'] else ''),
          f"- Прочие △-события: " + ', '.join(f'{k} {v}' for k, v in c['actions'].items() if k not in ('CollectorCard', 'SummonVehiclePhone', 'Wrench')),
          '']
    L += ['## Лавка, будка, костюмы',
          f"- Продаются: " + (', '.join(f"{x['car']} {x['price']} ({x['seller']})" for x in S['forsale']) or 'нет'),
          f"- Награды-машины уровня: " + ', '.join(f"{x['car']} ({x['how']})" for x in S['rewards']),
          f"- Галерея будки: {', '.join(S['booth_gallery'])}",
          f"- Костюмы {len(S['skins'])}: " + ', '.join(f"{x['name']} {x['price'] or 'свой'}" for x in S['skins'])
          + f"; места выбора {len(c['skin_spots'])} ({', '.join(x['file'] for x in c['skin_spots'])})",
          '']
    L += [f"## Комнаты: {len(P['rooms'])}",
          '- ' + '; '.join(f"{r['ru']} `{r['file']}` дверь {r['door']['code'] if r['door'] else '—'}" for r in P['rooms']),
          '']
    hn = f"спад SetHitAndRunDecay {W['hnr_decay']}, машин погони {W['chase_cars']} ({W['chase_car']}, {W['chase_con']})"
    L += ['## Живой мир',
          f"- Трафик: {', '.join(W['traffic'])}; пешеходов AddPed {W['peds']} в {W['ped_groups']} группах; фоновых персонажей {W['ambient_chars']}; "
          f"выдают бонусы {W['bonus_givers']}",
          f"- Hit & Run: {hn}; обучение (подсказки Барта, EnableTutorialMode): {'да' if W['tutorial'] in ('1', 'true') else 'нет'}",
          '']
    if P['new']:
        nw = P['new']
        L += ['## Новое против уровня 1',
              '- Команды: ' + (', '.join(f"{x['op']} {x['n']}" + ('' if x['engine'] else ' (нет case в viewer/)') for x in nw['commands']) or 'нет'),
              '- Типы чанков: ' + (', '.join(f"{x['id']} ×{x['n']}" + ('' if x['fate'].startswith(('обработчик', 'проигнорировано')) else ' (нет судьбы)') for x in nw['chunks']) or 'нет')
              + f"; без обработчика всего {nw['chunks_unhandled']} из {nw['chunks_total']}",
              '']
    L += ['## Риски (из данных)'] + [f'- {r}' for r in risks(P)] + ['']
    if chk is not None:
        cnt = collections.Counter(s for s, _, _ in chk.rows)
        grp = collections.Counter(w.split(':')[0].split(' (')[0] for s, w, _ in chk.rows if s == 'PASS')
        L += ['## Сверка (passport.py --check)',
              f"- Итог **{'FAIL' if chk.failed else 'PASS'}**: PASS {cnt['PASS']}, WARN {cnt['WARN']}, FAIL {cnt['FAIL']} — "
              + ', '.join(f'{k} {v}' for k, v in grp.items())]
        for st, what, det in chk.rows:
            if st != 'PASS' or 'справка' in what: L.append(f"- {st} {what}: {det}")
        L.append('')
    return '\n'.join(L) + '\n'


def risks(P):
    n, W, c, out = P['level'], P['world'], P['collect'], []
    wired = P['wired']; base = collect_base()
    diff = [('hnr_decay', W['hnr_decay'], base.get('hnr_decay')), ('chase_cars', W['chase_cars'], base.get('chase_cars')),
            ('chase_con', W['chase_con'], base.get('chase_con')), ('chase_car', W['chase_car'], base.get('chase_car'))]
    for key, v, v1 in diff:
        w = wired[key]
        if w['wired'] and str(v) != str(v1):
            out.append(f"{w['what']} прошито в `{w['file']}:{w['line']}` (уровень 1), у уровня {n} — {v}")
        elif w['wired'] and n == 1:
            out.append(f"{w['what']} прошито в `{w['file']}:{w['line']}` — для уровней 2–7 брать из данных")
    if P['daytime'] != 'день':
        out.append(f"{P['daytime']}: свет машины и персонажей — константы порта (`psp_export.py` CAR_AMB/CAR_DIF), не свет уровня 0x13000")
    if P['driver'] != 'homer':
        out.append(f"водитель {P['driver']}: у порта пешком всегда Гомер (РЕЦЕПТ §10 «водитель 2–6 — отдельный пункт»)")
    if P['new']:
        miss = [x['op'] for x in P['new']['commands'] if not x['engine']]
        if miss: out.append(f"команд без case в движке: {len(miss)} ({', '.join(miss)}) — исполнитель или «не покрыто»")
        nf = [x['id'] for x in P['new']['chunks'] if not x['fate'].startswith(('обработчик', 'проигнорировано'))]
        if nf: out.append(f"новых типов чанков без судьбы в handlers.tsv: {len(nf)} ({', '.join(nf)})")
    if c['wasp_unspawned']:
        out.append(f"локаторов ос без точки появления {len(c['wasp_unspawned'])} — не цели ботов и не осы игры")
    if c['card_locator_names'] != len(c['cards']):
        out.append(f"имя локатора карточки ≠ номер в данных ({', '.join(x['locator'] + '→' + x['data'] for x in c['cards'] if x['locator'] != x['data'])}): "
                   "счёт по именам теряет карточку")
    forced = [m['id'] for m in P['missions'] if m['forced_cmd']]
    if forced: out.append(f"SetForcedCar в {', '.join(forced)}: машина миссии вместо своей — что запрещает оригинал, сверить (GAPS)")
    races = [m['id'] for m in P['missions'] if m['main'] == 'race' or m['kind'] == 'гонка']
    if races: out.append(f"гонки {len(races)} ({', '.join(races)}): таймер и соперники — боты упираются в правило миссии, «время вышло» сначала сверить скорость машины с оригиналом")
    return out


_BASE = {}
def collect_base():
    """числа уровня 1 для сравнения (без полного паспорта L1)"""
    if not _BASE: _BASE.update({k: v for k, v in world(1).items() if k in ('hnr_decay', 'chase_cars', 'chase_con', 'chase_car')})
    return _BASE


# ---------------------------------------------------------------- гейт
def gate(n):
    log = ROOT / f'build/gates/level/passport-l{n}.log'; log.parent.mkdir(parents=True, exist_ok=True)
    lines, ok_all = [], True
    other = 2 if n != 2 else 3
    cases = [('RED', f'чужой уровень: данные уровня {other} под номером {n}', dict(data_level=other), None),
             ('RED', 'испорченное число: карточек +1', dict(), ('cards', 1)),
             ('RED', 'испорченное число: миссий −1', dict(), ('missions', -1)),
             ('GREEN', f'настоящий уровень {n}', dict(), None)]
    for want, what, kw, plant in cases:
        P = collect(n, **kw)
        if plant:
            k, dv = plant
            if k == 'cards': P['collect']['cards'].append(dict(P['collect']['cards'][-1], data='card%d9' % n))
            if k == 'missions': P['missions'] = P['missions'][:-1]
        R = Rep(quiet=True); check(P, R)
        fails = [w for s, w, _ in R.rows if s == 'FAIL']
        good = (want == 'RED') == bool(fails)
        ok_all &= good
        s = f"{want:5} {'OK ' if good else 'BAD'} {what}: FAIL {len(fails)}" + (f" ({'; '.join(fails[:4])})" if fails else '') + f", PASS {sum(1 for x in R.rows if x[0] == 'PASS')}"
        print(s, flush=True); lines.append(s)
    lines.append('RESULT: ' + ('PASS' if ok_all else 'FAIL'))
    log.write_text(time.strftime('%Y-%m-%d %H:%M') + f' passport.py {n} --gate\n' + '\n'.join(lines) + '\n')
    print(lines[-1], '->', rel(log))
    return 0 if ok_all else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('level', type=int)
    ap.add_argument('--check', action='store_true'); ap.add_argument('--gate', action='store_true')
    ap.add_argument('--data-level', type=int); ap.add_argument('--plant')
    ap.add_argument('--out'); ap.add_argument('--json'); ap.add_argument('--no-write', action='store_true')
    a = ap.parse_args()
    if a.gate: return gate(a.level)
    P = collect(a.level, a.data_level)
    if a.plant:
        k, v = a.plant.split('=')
        if k == 'cards':
            while len(P['collect']['cards']) < int(v): P['collect']['cards'].append(dict(P['collect']['cards'][-1], data='card%d9' % a.level))
        elif k == 'missions': P['missions'] = P['missions'][:int(v)]
        else: raise SystemExit(f'--plant: cards=N или missions=N')
    R = None
    if a.check or a.data_level or a.plant:
        print(f'== сверка паспорта уровня {a.level}' + (f' (данные уровня {a.data_level})' if a.data_level else ''))
        R = Rep(); check(P, R)
    if not a.no_write and not a.data_level and not a.plant:
        js = Path(a.json) if a.json else ROOT / f'build/level/l{a.level}/passport.json'
        js.parent.mkdir(parents=True, exist_ok=True); js.write_text(json.dumps(P, ensure_ascii=False, indent=1, default=str))
        md = fmt_md(P, R)
        out = Path(a.out) if a.out else ROOT / f'docs/levels/L{a.level}_ПАСПОРТ.md'
        out.parent.mkdir(parents=True, exist_ok=True); out.write_text(md)
        size = len(md.encode())
        print(f'паспорт -> {rel(out)} ({size} Б{", БОЛЬШЕ 10 КБ" if size > 10240 else ""}), данные -> {rel(js)}')
        if size > 10240: return 1
    if R is not None:
        print('RESULT:', 'FAIL' if R.failed else 'PASS')
        return 1 if R.failed else 0
    return 0


if __name__ == '__main__':
    sys.exit(main())
