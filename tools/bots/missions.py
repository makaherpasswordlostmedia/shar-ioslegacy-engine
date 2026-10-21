#!/usr/bin/env python3
"""Миссионер на всех ядрах (пункт Б2): tools/bots/missioner по каждой миссии уровня в своём процессе (nice), таблица итогов
и места тупиков с объектом коллизии. Без AI и сети.
  python3 tools/bots/missions.py [--secs 600] [--procs 6]      -> build/bots/runs/mission/<время>/missions.md, missions.json
  python3 tools/bots/missions.py --gate                          гейт Б2: невозможный таймер (sr1) -> «провал»; m0 -> «пройдена»
Повтор миссии: build/bots/game_headless build/level.shr build/homer.shr --msn build/missions/level01.msn --mission N --input <папка>/mN.in"""
import argparse, concurrent.futures, json, os, subprocess, sys, time
from pathlib import Path
ROOT = Path(os.environ.get('BOTS_ROOT') or Path(__file__).resolve().parents[2])   # ночь запускает замороженную копию скрипта (Т1.1)
IN = Path(os.environ.get('BOTS_IN') or ROOT / 'build')   # входы: общие build/ или замороженный комплект ночи
BIN = Path(os.environ.get('BOTS_BIN', ROOT / 'build/bots'))   # ночь играет своей копией бинарников (дневная пересборка их не трогает)
ARGS = [str(IN / p) for p in ('level.shr', 'homer.shr', 'sandbox/roads-l1.bin', 'missions/level01.msn')]


def run(m, secs, out, extra=()):
    r = subprocess.run(['nice', '-n', '10', str(BIN / 'missioner'), *ARGS, '--mission', str(m), '--secs', str(secs), '--out', str(out), *extra],
                       capture_output=True, text=True)
    fr = sum(int(l.split('\t')[1]) for l in r.stdout.splitlines() if l.startswith('F\t'))
    for l in r.stdout.splitlines():
        f = l.split('\t')
        if f[0] == 'M':
            return dict(frames=fr, index=int(f[1]), id=f[2], title=f[3], result=f[4], why=f[5], time=float(f[6]), timerLeft=float(f[7]), damage=float(f[8]),
                        stages=int(f[9]), attempts=int(f[10]), place=[float(f[12]), float(f[13])], wall=int(f[14]),
                        cls=f[15] if len(f) > 15 else '', nav=int(f[16]) if len(f) > 16 else 0, second=int(f[17]) if len(f) > 17 else 0)   # Т1.5: класс итога
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--secs', type=float, default=600); ap.add_argument('--procs', type=int, default=max(1, (os.cpu_count() or 4) - 4)); ap.add_argument('--gate', action='store_true'); ap.add_argument('--out', type=Path)
    ap.add_argument('--only', type=int, nargs='*', help='номера миссий (0 m0 … 7 m7, 8 sr1, 9 sr2, 10 sr3, 11 gr1, 12 bm1)')
    a = ap.parse_args()
    if not os.environ.get('BOTS_NO_BUILD'): subprocess.run([str(ROOT / 'tools/bots/build.sh')], check=True, capture_output=True)   # ночь собирает один раз сама
    os.environ['BW_FRAMES'] = '1'
    stamp = time.strftime('%Y%m%d-%H%M%S'); out = a.out or ROOT / 'build/bots/runs/mission' / (stamp + ('-gate' if a.gate else '')); out.mkdir(parents=True, exist_ok=True)
    names = json.loads((IN / 'sandbox/colnames-l1.json').read_text())
    def wall(w):
        if w < 0: return '-'
        t, i = divmod(w, 100000)
        return {1: lambda: names['box'][i][0], 2: lambda: names['cyl'][i][0]}.get(t, lambda: 'забор-граница' if t == 3 else 'земля')()
    if a.gate:
        imp, m0 = run(8, 300, out, ('--impossible-timer',)), run(0, a.secs, out)
        ok = imp and imp['result'] == 'провал' and m0 and m0['result'] == 'пройдена'
        (out / 'gate.json').write_text(json.dumps(dict(impossibleTimer=imp, m0=m0, ok=ok), ensure_ascii=False, indent=1))
        print(f"гейт Б2: sr1 с таймером 1 с -> «{imp and imp['result']}»; m0 -> «{m0 and m0['result']}» ({m0 and m0['why']}; место {m0 and m0['place']}, {m0 and wall(m0['wall'])}) -> {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1
    with concurrent.futures.ThreadPoolExecutor(a.procs) as ex:
        rows = [r for r in ex.map(lambda m: run(m, a.secs, out), a.only if a.only else range(13)) if r]
    for r in rows: r['object'] = wall(r['wall'])
    (out / 'missions.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    L = [f'# Миссионер {stamp}', '', 'Итог: пройдена / провал / не покрыто (нет в движке) / застрял. Класс (Т1.5): игра — два независимых водителя не доехали; '
         'водитель — второй доехал; нет данных; намеренно — провал правилом миссии', '',
         '| миссия | итог | класс | почему | время, с | стадий | отрезков навигатором | место тупика | объект коллизии |', '|---|---|---|---|---|---|---|---|---|'] + [
         f"| {r['id']} {r['title']} | {r['result']} | {r.get('cls', '')} | {r['why']} | {r['time']:.0f} | {r['stages']} | {r.get('nav', 0)} | {r['place'][0]:.0f} {r['place'][1]:.0f} | {r['object']} |" for r in rows]
    (out / 'missions.md').write_text('\n'.join(L) + '\n'); print('\n'.join(L)); return 0


if __name__ == '__main__':
    sys.exit(main())
