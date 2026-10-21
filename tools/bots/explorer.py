#!/usr/bin/env python3
"""Каскадёр и пешеход на всех ядрах (пункт Б3): tools/bots/explorer в N процессах с низким приоритетом, сводка «что достижимо
с дороги, за сколько, по какой цепочке» и кластеры событий (Гомер застрял, провал сквозь землю). Без AI и сети.
  python3 tools/bots/explorer.py [--procs 3] [--secs 600] [--seed 1]     -> build/bots/runs/explore/<время>/explore.md
  python3 tools/bots/explorer.py --gate                                  гейты Б3 (красный контроль, потом зелёный)
Каждая засчитанная цель и каждый кластер проверяются повтором в отдельном процессе: build/bots/game_headless с тем же
стартом и нажатиями обязан закончить в цели по тем же правилам, что у исследователя (монета — собрана именно эта,
стекло — разбито именно это, крыша — стоит на площадке, трамплин — на кромке на скорости). Старты только с дороги
(естественные): спавн, узлы дорог, разгон на трамплины; стресс-стартов здесь нет."""
import argparse, collections, concurrent.futures, hashlib, json, math, os, re, shutil, subprocess, sys, time
from pathlib import Path
from clusterkey import cluster_key
ROOT = Path(os.environ.get('BOTS_ROOT') or Path(__file__).resolve().parents[2])   # ночь запускает замороженную копию скрипта (Т1.1)
IN = Path(os.environ.get('BOTS_IN') or ROOT / 'build')   # входы: общие build/ или замороженный комплект ночи
BIN = Path(os.environ.get('BOTS_BIN', ROOT / 'build/bots'))   # ночь играет своей копией бинарников (дневная пересборка их не трогает)
LVL, HOM, RDS = IN / 'level.shr', IN / 'homer.shr', IN / 'sandbox/roads-l1.bin'
TGT, ROUTES = IN / 'bots/targets-l1.tsv', IN / 'sandbox/routes-l1.tsv'


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def rel(p):   # путь от корня проекта (или полный, если папка вне проекта)
    p = Path(p).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def targets():
    T = {}
    for l in TGT.read_text().splitlines():
        f = l.split()
        if len(f) == 10: T[f[1]] = dict(kind=f[0], x=float(f[2]), y=float(f[3]), z=float(f[4]), r=float(f[5]), box=[float(v) for v in f[6:10]])
    return T


def run_explorer(binp, out, seed, secs, plant=True):
    out.mkdir(parents=True, exist_ok=True)
    cmd = ['nice', '-n', '10', str(binp), str(LVL), str(HOM), str(RDS), str(TGT), '--secs', str(secs), '--seed', str(seed), '--out', str(out), '--routes', str(ROUTES)]
    if plant: cmd.append('--plant-sky')
    r = subprocess.run(cmd, capture_output=True, text=True)
    (out / 'stdout.tsv').write_text(r.stdout); (out / 'stderr.txt').write_text(r.stderr)
    return r.stdout


def parse(stdout):
    T, E, S = {}, [], None
    for l in stdout.splitlines():
        f = l.split('\t')
        if f[0] == 'T':
            T[f[2]] = dict(kind=f[1], x=float(f[3]), y=float(f[4]), z=float(f[5]), reached=f[6] == '1', t=float(f[7]))
            if len(f) >= 14: T[f[2]]['near'] = dict(d=float(f[8]), h=float(f[9]), at=[float(f[10]), float(f[11]), float(f[12])], foot=int(f[13]))   # лучший подход
        elif f[0] == 'E': E.append(dict(kind=f[1], x=float(f[2]), y=float(f[3]), z=float(f[4]), n=int(f[5]), t=float(f[6]), file=f[7],
                                        layer=int(f[8]) if len(f) > 9 else 0, obj=f[9] if len(f) > 9 else '-'))   # слой и объект — Т1.1
        elif f[0] == 'S': S = dict(macros=int(f[1]), frames=int(f[2]), cells=int(f[3]), cap=int(f[4]) if len(f) > 4 else 0)
    return T, E, S


def replay(path):
    """Проиграть .in исследователя отдельным процессом game_headless -> состояние в последнем кадре."""
    s = re.search(r'--start ([-0-9.e ]+) --input', path.read_text().split('\n', 1)[0]).group(1).split()
    o = subprocess.run([str(BIN / 'game_headless'), str(LVL), str(HOM), '--input', str(path), '--start', *s], capture_output=True, text=True).stdout
    m = re.search(r'пешком (\d)', o); p = re.search(r'игрок ([-0-9.]+) ([-0-9.]+) ([-0-9.]+); на земле (\d); скорость ([-0-9.]+)', o)
    coins = re.search(r'монеты мира собраны:([ 0-9]*)', o).group(1).split(); hid = re.search(r'предметы спрятаны:([ 0-9]*)', o).group(1).split()
    return dict(foot=int(m.group(1)), x=float(p.group(1)), y=float(p.group(2)), z=float(p.group(3)), grounded=int(p.group(4)), v=float(p.group(5)),
                coins={int(c) for c in coins}, hidden={int(c) for c in hid}, frames=int(re.search(r'кадров (\d+)', o).group(1)))


def hit(name, t, st):
    """Те же правила, что checkTargets() в explorer.c."""
    k, x, y, z = t['kind'], st['x'], st['y'], st['z']
    if k == 'roof':
        x0, z0, x1, z1 = t['box']; return x0 <= x <= x1 and z0 <= z <= z1 and t['y'] - .5 <= y <= t['y'] + 3 and st['grounded'] == 1
    if k == 'ramp': return not st['foot'] and math.hypot(x - t['x'], z - t['z']) < t['r'] and abs(y - t['y']) < 2 and st['v'] > 6
    if k == 'coin': return int(name[4:]) in st['coins']
    if k == 'glass': return int(name[5:]) in st['hidden']
    return math.hypot(x - t['x'], z - t['z']) < t['r'] and abs(y - t['y']) < 2.5


def campaign(binp, out, procs, secs, seed):
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(procs) as ex:
        outs = list(ex.map(lambda k: run_explorer(binp, out / f'p{k}', seed + k, secs), range(procs)))
    TG = targets(); best, events, stats, near = {}, {}, [], {}
    for k, o in enumerate(outs):
        T, E, S = parse(o); stats.append(S)
        for n, t in T.items():
            if t['reached'] and (n not in best or t['t'] < best[n]['t']): best[n] = dict(t, proc=k)
            a = t.get('near')
            if a and a['d'] >= 0 and (n not in near or a['d'] + 2 * a['h'] < near[n]['d'] + 2 * near[n]['h']): near[n] = a
        for e in E:
            key = cluster_key(e['kind'], e['x'], e['z'], e['layer'], e['obj'])
            if key not in events: events[key] = dict(e, proc=k, n=0)
            elif e['t'] < events[key]['t']: events[key].update(e, proc=k, n=events[key]['n'])
            events[key]['n'] += e['n']
    rep = out / 'repro'; rep.mkdir(exist_ok=True)
    rows = []
    for n, b in sorted(best.items()):
        src = out / f"p{b['proc']}" / f'{n}.in'; dst = rep / f'{n}.in'; shutil.copy(src, dst)
        st = replay(dst); t = TG.get(n)
        ok = hit(n, t, st) if t else False   # подложенной крыши нет в данных: её «достижение» — всегда дефект
        rows.append(dict(name=n, kind=b['kind'], t=b['t'], foot=st['foot'], replay=bool(ok), repro=rel(dst)))
    evrows = []
    for key, e in sorted(events.items(), key=lambda kv: -kv[1]['n']):
        src = out / f"p{e['proc']}" / f"{e['file']}.in"; dst = rep / f"{e['file']}.in"; shutil.copy(src, dst)
        st = replay(dst); ok = math.dist((st['x'], st['y'], st['z']), (e['x'], e['y'], e['z'])) < 1.0
        evrows.append(dict(kind=e['kind'], x=e['x'], y=e['y'], z=e['z'], layer=e['layer'], obj=e['obj'], key=key, n=e['n'], t=e['t'], replay=ok, repro=rel(dst)))
    kinds = collections.Counter(t['kind'] for t in TG.values()); got = collections.Counter(r['kind'] for r in rows if r['kind'] != 'roof' or r['name'] != 'planted_roof')
    frames = sum(s['frames'] for s in stats if s)
    res = dict(levelSha=sha(LVL), binarySha=sha(binp), procs=procs, secs=secs, seed=seed, wallSeconds=round(time.time() - t0, 1),
               gameMinutes=round(frames / 3600, 1), cells=sum(s['cells'] for s in stats if s),
               capReached=any(s and s.get('cap') and s['cells'] >= s['cap'] for s in stats),   # архив ячеек полон: «не достигнуто» отчасти потолок архива
               reach={k: [got.get(k, 0), kinds[k]] for k in sorted(kinds)}, plantedRoof='planted_roof' in best,
               replayOk=sum(r['replay'] for r in rows), reached=len(rows), rows=rows, events=evrows,
               unreached=sorted(n for n in TG if n not in best),
               approach={n: near[n] for n in TG if n not in best and n in near})   # недостигнутые: лучший подход
    return res


def write(out, res, title):
    (out / 'explore.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
    foot = sum(r['foot'] for r in res['rows'])
    L = [f'# {title}', '', f"{res['procs']} процессов × {res['secs']} с, {res['gameMinutes']} мин игры, ячеек {res['cells']}" + (' (архив полон — «не достигнуто» отчасти его потолок)' if res.get('capReached') else '') + f"; уровень {res['levelSha']}, бинарник {res['binarySha']}",
         f"Достигнуто {res['reached']} целей (пешком {foot}), повтор отдельным процессом сошёлся у {res['replayOk']}; подложенная крыша: {'ДОСТИГНУТА' if res['plantedRoof'] else 'не достигнута'}", '',
         '| что | достигнуто из | ', '|---|---|'] + [f'| {k} | {a} из {b} |' for k, (a, b) in res['reach'].items()] + [
         '', '## Кластеры событий (клетка 8 м, первый случай — повтор)', '',
         '| событие | место | раз | повтор |', '|---|---|---|---|'] + [
         f"| {e['kind']} | {e['x']:.0f} {e['y']:.1f} {e['z']:.0f} | {e['n']} | {'сошёлся' if e['replay'] else 'РАЗОШЁЛСЯ'} `{Path(e['repro']).name}` |" for e in res['events'][:20]] + [
         '', '## Достигнутые цели', '', '| цель | за, с игры | пешком | повтор |', '|---|---|---|---|'] + [
         f"| {r['name']} | {r['t']:.1f} | {'да' if r['foot'] else ''} | {'сошёлся' if r['replay'] else 'РАЗОШЁЛСЯ'} |" for r in res['rows']] + [
         '', f"Не достигнуто за прогон ({len(res['unreached'])}): " + ', '.join(res['unreached'][:60]) + (' …' if len(res['unreached']) > 60 else '')]
    (out / 'explore.md').write_text('\n'.join(L) + '\n')
    return L


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--procs', type=int, default=3); ap.add_argument('--secs', type=float, default=600); ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--gate', action='store_true'); ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    if not os.environ.get('BOTS_NO_BUILD'): subprocess.run([str(ROOT / 'tools/bots/build.sh')], check=True, capture_output=True)   # ночь собирает один раз сама
    os.environ['BW_FRAMES'] = '1'
    stamp = time.strftime('%Y%m%d-%H%M%S'); out = a.out or ROOT / 'build/bots/runs/explore' / (stamp + ('-gate' if a.gate else '')); out.mkdir(parents=True, exist_ok=True)
    if not a.gate:
        res = campaign(BIN / 'explorer', out, a.procs, a.secs, a.seed); L = write(out, res, f'Каскадёр и пешеход {stamp}')
        print('\n'.join(L[2:4])); print('->', out / 'explore.md'); return 0
    # гейт: (1) контроль — проверка крыши сломана нарочно (без высоты и опоры): подложенная крыша обязана «достигнуться» -> красный
    env = dict(os.environ, BINS='explorer', SUF='_broken')
    subprocess.run([str(ROOT / 'tools/bots/build.sh'), '-DEXP_BREAK_ROOF=1'], check=True, capture_output=True, env=env)
    bad = campaign(ROOT / 'build/bots/explorer_broken', out / 'broken', 1, 60, a.seed)
    def verdict(r):
        why = []
        if r['plantedRoof']: why.append('подложенная крыша достигнута')
        if 'jumpzone16' not in {x['name'] for x in r['rows']}: why.append('jumpzone16 не достигнут')
        if r['replayOk'] < r['reached'] - (1 if r['plantedRoof'] else 0): why.append(f"повторов разошлось {r['reached'] - r['replayOk']}")
        if any(not e['replay'] for e in r['events']): why.append('повтор события разошёлся')
        return why
    wb = verdict(bad)
    good = campaign(BIN / 'explorer', out / 'good', 2, 150, a.seed); wg = verdict(good)
    write(out / 'good', good, f'Гейт Б3 {stamp}, рабочая сборка')
    lines = [f"контроль (проверка крыши сломана): {'КРАСНЫЙ — ' + '; '.join(wb) if wb else 'зелёный — ГЕЙТ НЕ ЛОВИТ'}",
             f"рабочая сборка: {'КРАСНЫЙ — ' + '; '.join(wg) if wg else 'зелёный'}; целей {good['reached']}, повторов сошлось {good['replayOk']}, "
             f"кластеров событий {len(good['events'])}; jumpzone16 {'да' if 'jumpzone16' in {x['name'] for x in good['rows']} else 'нет'}"]
    ok = bool(wb) and 'подложенная крыша достигнута' in wb and not wg
    lines.append(f"RESULT: {'OK' if ok else 'FAIL'}")
    (out / 'gate.txt').write_text('\n'.join(lines) + '\n'); print('\n'.join(lines)); print('->', out)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
