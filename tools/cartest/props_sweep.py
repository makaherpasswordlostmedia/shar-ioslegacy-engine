#!/usr/bin/env python3
"""Каждый предмет уровня под ударом (пункт 10а): tools/cartest/props_sweep.c в 6 процессах, сводка по типам
«как в данных / отличие / аномалия» -> build/sandbox/props-sweep.json. Без AI и сети.
  python3 tools/cartest/props_sweep.py            сводка
  python3 tools/cartest/props_sweep.py --gate     + отрицательный контроль оракула (подложенные ошибки обязаны найтись)
  python3 tools/cartest/props_sweep.py --plant-kick 4 --out X   контроль аномалии удара: разгон × 4 обязан найтись
Оракул (данные игры): PRP1 — «ломается» = у типа есть объект-обломок SPR1 с кусками из данных уровня (BreakableObject,
таблица dynBreak, spBreakOf; обломок без кусков — только эффект, предмет остаётся); колонка ATC в PRP2 @44 (частицы, эффект BreakablesEnum) — эффект удара, его играет main.c onPropKick,
исчезновение предмета она не задаёт (гидрант: вода бьёт, сам предмет отлетает). Аномалия — предмет разогнан сильнее, чем
может удар (пик скорости > 2 × пик машины + 3 м/с) или машина упирается в предмет (без него проходит); стейтпропы — машины состояний, docs/gameplay.md §2: ящик от машины сразу 30 монет,
автомат 15, будка 1 и снимает коллизию, забор/сено/забор туннеля/томако исчезают без монет, куст-шар (класс 2) насквозь.
Имена типов SPR1 — из tools/prp2_export.py (порядок сверяется с level.shr по kind/bindex/cls), PRP1 — из
tools/psp_export.py prop_entities (тот же порядок, что dynBreak)."""
import argparse, collections, concurrent.futures, json, struct, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
SP_ORACLE = {  # docs/gameplay.md §2 (машины состояний, сверено по данным)
    'l1_crate_Shape': dict(coins=30, gone=None), 'l1_vending_Shape': dict(coins=15, gone=None),
    'l1_phonestop_Shape': dict(coins=1, colOff=True), 'l1_fence_Shape': dict(coins=0, gone=True),
    'l1_haybale_Shape': dict(coins=0, gone=True), 'l1_tunnelfence_Shape': dict(coins=0, gone=True),
    'l1r6_tomaccostand_Shape': dict(coins=0, gone=True), 'l1_shrubround_Shape': dict(coins=0, passThrough=True)}


def prp_verdict(kick, broke, exp_break, brk, flew, stuck):
    """exp_break — у типа есть обломок SPR1 (данные уровня); brk — номер типа-обломка; flew — заездов, где предмет
    разогнан сильнее удара"""
    verdict, why = 'как в данных', []
    if kick < 0.8: verdict = 'отличие'; why.append('удар машиной засчитан в %.0f%% заездов 50/90 км/ч, где машина дошла до предмета' % (kick * 100))
    if exp_break and broke < 0.8: verdict = 'отличие'; why.append('обломок SPR1 %d в данных, сломался в %.0f%%' % (brk, broke * 100))
    if not exp_break and broke > 0: verdict = 'отличие'; why.append('обломка SPR1 нет, а предмет исчез в %.0f%%' % (broke * 100))
    if flew: verdict = 'аномалия'; why.append('разогнан сильнее удара (> 2 × машина + 3 м/с) в %d заездах' % flew)
    if stuck > 0.25: verdict = 'аномалия'; why.append('машина упёрлась в предмет в %.0f%% заездов' % (stuck * 100))
    return verdict, why


def sp_verdict(O, hit, coins, gone, coloff, stuck):
    if O is None:
        return 'нет в оракуле', []
    verdict, why = 'как в данных', []
    if O.get('passThrough'):
        if stuck > 0.1: verdict = 'отличие'; why.append('куст-шар должен пропускать, машина упёрлась в %.0f%%' % (stuck * 100))
    elif not hit:
        verdict = 'отличие'; why.append('на удар машиной не отозвался ни разу')
    else:
        if coins and max(coins, key=coins.get) != O['coins']: verdict = 'отличие'; why.append('монет за удар машиной %s, по данным %d' % (dict(coins), O['coins']))
        if O.get('gone') and gone < hit: verdict = 'отличие'; why.append('исчез в %d из %d' % (gone, hit))
        if O.get('colOff') and coloff < hit: verdict = 'отличие'; why.append('коллизия снята в %d из %d' % (coloff, hit))
    return verdict, why


def data_oracle(T):
    """Исход удара машиной по машине состояний SPR1 из данных (tools/prp2_export.py StateProps): из состояния 0 первое
    событие, которое оно обрабатывает, в порядке VEHICLE_HIT -> HIT -> DESTROYED (правило порта §6, как viewer/stateprops.c),
    дальше вызовы нового состояния и его авто-переходы. -> dict(reacts, coins, gone, colOff, colOffAtStart)"""
    import prp2_export as P
    st = T['states']; calls0 = [c[0] for c in st[0]['calls']]
    O = dict(reacts=False, coins=0, gone=False, colOff=False, colOffAtStart=P.OP_COLOFF in calls0)
    ev = next((to for want in (11, 8, 7) for e, to in st[0]['events'] if e == want), None)
    if ev is None: return O
    O['reacts'] = True; seen = set(); s_ = ev
    while s_ is not None and s_ < len(st) and s_ not in seen:
        seen.add(s_)
        for op, arg, _ in st[s_]['calls']:
            if op in (P.OP_COINS, P.OP_COINS_Z): O['coins'] += arg
            elif op == P.OP_REMOVE: O['gone'] = True
            elif op == P.OP_COLOFF: O['colOff'] = True
        s_ = st[s_]['auto'] if st[s_]['auto'] != 0xFF else None
    return O


def data_verdict(D, rs_fast, coins, gone, coloff):
    note = 'оракул из данных: %s' % ('в свободной езде не реагирует' + (', коллизия снята с начала' if D['colOffAtStart'] else '') if not D['reacts'] else
            'удар машиной -> монет %d%s%s' % (D['coins'], ', исчезает' if D['gone'] else '', ', коллизия снимается' if D['colOff'] else ''))
    why = [note]
    if not rs_fast: return 'нет заездов', why
    changed = [r for r in rs_fast if r[10] != r[9] or r[11] == '0']
    mode = max(coins, key=coins.get) if coins else 0
    if not D['reacts']:
        ok = not changed and mode == 0
    else:
        n = len(rs_fast); ok = len(changed) >= 0.8 * n and mode == D['coins'] and (not D['gone'] or gone >= 0.8 * len(changed)) and (not D['colOff'] or coloff >= 0.8 * len(changed))
    if not ok: why.append('наблюдение: состояние сменилось в %d из %d, монет чаще %d, исчез %d, коллизия снята %d' % (len(changed), len(rs_fast), mode, gone, coloff))
    return ('как в данных' if ok else 'отличие'), why


def names():
    import prp2_export as P, psp_export as PE
    art = ROOT / 'hit-and-run-web/source/game/art'
    sp = P.StateProps(1, art, lambda f, m: [], lambda f, s: -1, verbose=False)
    prp = list(PE.prop_entities([p.stem for p in P.level_files(art, 1)], art)) + ['coinShape_000']
    global DATA_ORACLE
    DATA_ORACLE = {t['name']: data_oracle(t) for t in sp.types if t.get('states')}
    return [(t['name'], t.get('kind', 0), t.get('bindex', 0), t.get('cls', 0)) for t in sp.types], prp


def atc(level):
    b = level.read_bytes(); po = struct.unpack_from('<I', b, 96)[0]
    ntype = struct.unpack_from('<I', b, po + 8)[0]; off, n = struct.unpack_from('<2I', b, po + 44)
    return [(b[po + off + 2 * t], b[po + off + 2 * t + 1]) for t in range(min(n, ntype))], ntype


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--gate', action='store_true'); ap.add_argument('--level', type=Path, default=ROOT / 'build/level.shr')
    ap.add_argument('--out', type=Path, default=ROOT / 'build/sandbox/props-sweep.json')
    ap.add_argument('--plant-kick', type=float, default=0, help='отрицательный контроль: скорость предмета в кадр удара × K')
    ap.add_argument('--bin', type=Path, help='готовый бинарник (замороженный ночью ботов, Т1.1); нет файла — собрать в этот путь')
    ap.add_argument('--build-only', action='store_true', help='только собрать бинарник (--bin) и выйти')
    a = ap.parse_args()
    B = a.bin or a.out.with_suffix('.bin')   # свой бинарник на прогон: станок ботов и ночь полигона не перезаписывают друг другу исполняемый файл
    if not (a.bin and a.bin.exists()): subprocess.run(['cc', '-std=c11', '-O2', '-DSKIN_HOST', '-I', str(ROOT / 'viewer'), str(ROOT / 'tools/cartest/props_sweep.c')] +
                   [str(ROOT / 'viewer' / f) for f in ('car.c', 'col.c', 'props.c', 'stateprops.c', 'coins.c')] + ['-lm', '-o', str(B)], check=True)
    if a.build_only: return 0
    with concurrent.futures.ThreadPoolExecutor(6) as ex:
        out = ''.join(ex.map(lambda k: subprocess.run([str(B), str(a.level), str(k), '6'] + (['--plant-kick', str(a.plant_kick)] if a.plant_kick else []), capture_output=True, text=True, check=True).stdout, range(6)))
    rows = [l.split('\t') for l in out.splitlines() if l]
    sp_names, prp_names = names()
    Ts = [r for r in rows if r[0] == 'T']
    order_ok = len(Ts) == len(sp_names) and all((int(t[2]), int(t[3]), int(t[4])) == (k, bi, c) for t, (_, k, bi, c) in zip(Ts, sp_names))
    fx, nprp = atc(a.level)
    if len(prp_names) != nprp:
        prp_names = prp_names[:nprp] + ['type%d' % i for i in range(len(prp_names), nprp)]
    res = dict(prp1={}, spr1={})
    # PRP1
    P = collections.defaultdict(list); R = collections.defaultdict(list)
    spb = {int(r[1]): int(r[2]) if int(r[3]) > 0 else -1 for r in rows if r[0] == 'B'}   # тип PRP1 -> обломок SPR1 с кусками (-1: нет или только эффект)
    for r in rows:
        if r[0] == 'P': P[int(r[2])].append(r)
        if r[0] == 'R': R[(r[1], int(r[3]))].append(r)
    for t, rs in sorted(P.items()):
        part, brk = fx[t] if t < len(fx) else (0, 0xFF)
        # только заезды 50/90 км/ч, где кузов дошёл до предмета (центр ближе 3 м); «упёрлась» — только если без
        # предмета тот же заезд проходит (иначе держит окружение: дом, забор)
        fast = [r for r in rs if r[4] in ('50', '90') and float(r[15]) <= 3.0 and r[14] != '-1']   # -1 — нет земли под стартом, заезда не было
        kick = sum(r[5] == '1' for r in fast) / max(1, len(fast)); broke = sum(r[6] == '1' for r in fast) / max(1, len(fast))
        # аномалия удара — по горизонтали (падение с высоты или в дыру разгоняет по вертикали, это не удар); отдельно:
        # предмет упал в дыру (ушёл ниже места больше 5 м и под ним нет земли коллизии) — пункт 11.3
        flew = sum(float(r[19] if len(r) > 19 else r[17]) > 2 * float(r[18]) + 3 for r in rs); stuck = sum(r[14] == '1' and r[16] == '0' for r in rs) / max(1, len(rs))
        void = sum(len(r) > 21 and float(r[20]) > 5 and r[21] == '1' for r in rs)
        maxMoved = max(float(r[7]) for r in rs)
        back = [x for x in R[('P', t)] if x[4] == '1']; backok = sum(x[5] == '1' for x in back) / max(1, len(back)) if back else None
        sb = spb.get(t, -1); exp_break = sb >= 0
        verdict, why = prp_verdict(kick, broke, exp_break, sb, flew, stuck)
        if not fast: verdict, why = 'недосягаем с земли', ['ни в одном заезде 50/90 км/ч кузов не перекрыл предмет по высоте и месту (стоит выше, на сооружении)']
        res['prp1'][prp_names[t]] = dict(type=t, instances=len(rs) // 25, reachedFast=len(fast), maxMovedM=round(maxMoved, 1),
                                        sprDebris=sb, peakPropV=round(max(float(r[17]) for r in rs), 1),
                                        atc=dict(particles=part, debris=None if brk == 0xFF else brk),
                                        kicked=round(kick, 2), broke=round(broke, 2), flew=flew, fellIntoHole=void, carStuck=round(stuck, 2),
                                        respawn=None if backok is None else round(backok, 2), verdict=verdict, why=why)
    # SPR1
    S = collections.defaultdict(list)
    for r in rows:
        if r[0] == 'S': S[int(r[2])].append(r)
    for t, rs in sorted(S.items()):
        nm = sp_names[t][0] if t < len(sp_names) else 'type%d' % t; O = SP_ORACLE.get(nm)
        rs_fast = [r for r in rs if r[4] in ('50', '90') and float(r[15]) <= 3.0]   # дошла до предмета на 50/90 км/ч
        hit = [r for r in rs_fast if r[10] != r[9] or r[11] == '0' or r[12] == '0' or int(r[13]) > 0]   # предмет отозвался
        coins = collections.Counter(int(r[13]) for r in hit); gone = sum(r[11] == '0' for r in hit); coloff = sum(r[12] == '0' for r in hit)
        stuck = sum(r[14] == '1' and r[16] == '0' for r in rs) / max(1, len(rs))
        back = [x for x in R[('S', t)] if x[4] == '1']; backok = sum(x[5] == '1' for x in back) / max(1, len(back)) if back else None
        verdict, why = sp_verdict(O, len(hit), coins, gone, coloff, stuck)
        D = DATA_ORACLE.get(nm) if O is None else None
        if D is not None:   # оракул из машины состояний в данных (нет в таблице docs/gameplay.md §2)
            verdict, why = data_verdict(D, rs_fast, coins, gone, coloff)
        res['spr1'][nm] = dict(type=t, instances=len(rs) // 25, reachedFast=len(rs_fast), responded=len(hit), coinsPerHit={str(k): v for k, v in coins.items()}, gone=gone, colOff=coloff,
                               carStuck=round(stuck, 2), respawn=None if backok is None else round(backok, 2), verdict=verdict, why=why)
    res['typeOrderMatchesExporter'] = order_ok
    res['note'] = 'наблюдения ботов на Mac; отличия от данных -> новые пункты очереди, общими правилами'
    # отрицательный контроль оракула: подложить ящику +10 монет и стеклу «без обломка» -> обязаны найтись
    gate = None
    if a.gate:   # те же функции вердикта на подложенных ошибках
        crate = res['spr1'].get('l1_crate_Shape'); glass = next((v for v in res['prp1'].values() if v['atc']['debris'] == 19 and v['sprDebris'] >= 0), None)
        c_real = crate and crate['verdict']; g_real = glass and glass['verdict']
        cc = collections.Counter({int(k) + 10: v for k, v in (crate or {}).get('coinsPerHit', {}).items()})
        c_plant, _ = sp_verdict(SP_ORACLE['l1_crate_Shape'], crate['responded'] if crate else 0, cc, 0, 0, 0.0)
        g_plant, _ = prp_verdict(glass['kicked'], 0.0, True, glass['sprDebris'], 0, 0.0) if glass else ('нет стекла', [])
        # лишняя энергия — через настоящую симуляцию: часть предметов (1/6) с разгоном ×4 в кадр удара, те же строки P и та же формула
        pr = subprocess.run([str(B), str(a.level), '0', '6', '--plant-kick', '4'], capture_output=True, text=True).stdout
        pl = [l.split('\t') for l in pr.splitlines() if l.startswith('P\t')]
        n_pl = sum(len(r) > 19 and float(r[19]) > 2 * float(r[18]) + 3 for r in pl)
        e_plant = 'аномалия' if n_pl else 'как в данных'   # {n_pl} заездов из {len(pl)} с подложенным разгоном
        gp = DATA_ORACLE.get('l1_gaspump_Shape'); gp_rows = [r for r in rows if r[0] == 'S' and int(r[2]) < len(sp_names) and sp_names[int(r[2])][0] == 'l1_gaspump_Shape' and r[4] in ('50', '90') and float(r[15]) <= 3.0]
        d_plant, _ = data_verdict(dict(gp, coins=gp['coins'] + 5), gp_rows, collections.Counter(int(r[13]) for r in gp_rows), 0, sum(r[12] == '0' for r in gp_rows)) if gp else ('нет колонки', [])
        gate = dict(crateExtra10=c_plant, glassNoDebris=g_plant, realCrate=c_real, realGlass=g_real, energyPlant=e_plant, gaspumpPlus5=d_plant,
                    energyPlantRuns=n_pl, crateExtra10Caught=c_plant == 'отличие', glassNoDebrisCaught=g_plant == 'отличие', energyCaught=e_plant == 'аномалия',
                    dataOracleCaught=d_plant == 'отличие')
    res['gate'] = gate
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    n = collections.Counter(v['verdict'] for part in ('prp1', 'spr1') for v in res[part].values())
    print('заездов %d; типов PRP1 %d, стейтпропов %d; порядок типов с экспортёром: %s; вердикты %s' % (
        sum(1 for r in rows if r[0] in 'PS'), len(res['prp1']), len(res['spr1']), order_ok, dict(n)))
    for part in ('prp1', 'spr1'):
        for k, v in res[part].items():
            if v['verdict'] != 'как в данных':
                print('  %s %-26s %-13s %s' % (part, k, v['verdict'], '; '.join(v['why'])))
    if gate:
        ok = gate['crateExtra10Caught'] and gate['glassNoDebrisCaught'] and gate['energyCaught'] and gate['dataOracleCaught']
        print('гейт оракула: ящик +10 пойман %s, стекло без обломка поймано %s, лишняя энергия поймана %s, колонка +5 монет (оракул из данных) поймана %s -> %s' % (
              gate['crateExtra10Caught'], gate['glassNoDebrisCaught'], gate['energyCaught'], gate['dataOracleCaught'], 'PASS' if ok else 'FAIL'))
        return 0 if ok else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
