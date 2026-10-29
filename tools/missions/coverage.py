#!/usr/bin/env python3
"""Команды скриптов миссий, которые компилятор принимает, а игра не исполняет — по уровням 1–7, из пакетов и кода.

  python3 tools/missions/coverage.py [--msn-dir DIR] [--src viewer] [--tools tools] [--write docs/state/msn_coverage.tsv]
                                     [--check tests/levelmech/coverage_expected.tsv]

Откуда что (ничего не задано руками — всё читается):
  * вызовы — секция CMDS пакетов levelNN.msn (tools/missions/compile.py: в пакете только то, что играет — level.mfk,
    leveli.mfk, награды уровня и миссии AddMission/AddBonusMission; демо e3*, level-d, ss* туда не входят);
  * кто исполняет — код игры:
      runtime   маршрут 'rt' в tools/missions/commands.py (этапы, цели, условия читает viewer/mission/msn_run.c);
      engine    типизированная команда (viewer/mission/msn_game.c on_command: CALL(группа, функция)), и эту функцию
                ставит игра (viewer/game_msn.c `api.группа.функция =`, viewer/msn_view.c `v.группа.функция =`),
                или сквозная команда, которую код игры (viewer/*.c вне viewer/mission) упоминает по MSN_OP_<ИМЯ>;
      offline   команду читает экспортёр данных (tools/*.py: имя команды в кавычках) — трафик, осы, гэги, частицы;
      ignored   ни то, ни другое: команда доходит до игры и пропадает («не покрыто»).
    Для runtime-команд, которым нужен сигнал движка (msn_notify), он проверяется отдельно: destroyboss ждёт
    MSN_IN_BOSS_HIT, keepbarrel — MSN_IN_CARGO_LOST (колонка «ждёт»).
Проверка (--check): статус каждой команды пакетов = записанному в таблице ожиданий; иначе FAIL (новая «ignored» —
регрессия, новая «engine» — таблицу обновить сознательно). Гейт — tests/levelmech/coverage.sh (подложенный вход красный).
"""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[2]/"tools"))
from main_source import read_main
import argparse, re, struct, sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/missions'))
import commands as CMD   # noqa: E402

LEVELS = range(1, 8)
SEC_CMDS = 5   # msn_format.h: MSN_SEC_CMDS
# сигналы движка, которых ждут runtime-команды (msn_run.c: flag_boss / flag_cargo_lost)
NEEDS = {'SetObjTargetBoss': 'MSN_IN_BOSS_HIT', 'SetPickupTarget': 'MSN_IN_CARGO_LOST'}


def pack_ops(path):
    """levelNN.msn -> Counter(opcode) по секции CMDS (MsnCmd 12 Б: u16 op, ...)."""
    b = path.read_bytes()
    if b[:4] != b'MSN1': raise ValueError(f'{path}: не MSN1')
    level, = struct.unpack_from('<H', b, 6)
    off, cnt = struct.unpack_from('<II', b, 16 + SEC_CMDS * 8)
    c = Counter(struct.unpack_from('<H', b, off + 12 * i)[0] for i in range(cnt))
    return level, c


def typed_calls(src):
    """msn_game.c on_command: опкод -> набор (группа, функция), которые он зовёт."""
    t = (src / 'mission/msn_game.c').read_text()
    body = t[t.index('static void on_command'):t.index('/* ------------------------------------------------------------------ host: events')]
    sw = body[body.index('switch (op)', body.index('default: g->n_none++')):]
    out, pend = {}, []
    for part in re.split(r'(case MSN_OP_\w+:)', sw)[1:]:
        m = re.match(r'case MSN_OP_(\w+):', part)
        if m: pend.append(m.group(1)); continue
        calls = set(re.findall(r'CALL0?\((\w+),\s*(\w+)', part))
        if 'swap_mask |= 8' in part or 'swap_mask |=' in part: calls.add(('player', 'swap_default_car'))
        if 'BINDREWARD' in ''.join(pend) or 'msn_reward_get' in part: calls.add(('shop', 'reward_table'))
        for o in pend: out.setdefault(o, set()).update(calls)
        if re.search(r'\bbreak;', part) or 'return' in part: pend = []
    return out


def installed(src):
    """Функции интерфейса MsnGameApi, которые игра ставит: {(группа, функция)}."""
    have = set()
    for fn in ('game_msn.c', 'msn_view.c'):
        t = (src / fn).read_text()
        have |= set(re.findall(r'\b(?:api|v)\.(\w+)\.(\w+)\s*=\s*\w', t))
    return have


def engine_mentions(src):
    """Сквозные команды, которые код игры (вне viewer/mission) разбирает по имени опкода."""
    ops = set()
    for f in sorted(src.glob('*.c')):
        if re.search(r'_v\d+\.c$', f.name): continue
        ops |= set(re.findall(r'MSN_OP_(\w+)', read_main(f, errors='replace')))
    return ops


def offline_readers(tools):
    """Имя команды -> экспортёры tools/*.py, где оно стоит в кавычках (кроме компилятора и реестра команд)."""
    skip = {'commands.py', 'compile.py', 'catalog.py', 'coverage.py', 'mfk.py'}
    text = {}
    for f in sorted(tools.glob('*.py')) + sorted((tools / 'cartest').glob('*.py')):
        if f.name in skip: continue
        text[f.relative_to(tools.parent)] = f.read_text(errors='replace')
    out = {}
    for s in CMD.SPECS:
        pat = re.compile(r'''['"]%s['"]''' % re.escape(s.name))
        who = [str(p) for p, t in text.items() if pat.search(t)]
        if who: out[s.name] = who
    return out


def classify(src, tools):
    typed, have, ment, off = typed_calls(src), installed(src), engine_mentions(src), offline_readers(tools)
    have_names = {n for _, n in have}
    res = {}
    for s in CMD.SPECS:
        up = s.name.upper()
        st, where = [], []
        if s.route in ('rt', 'both'): st.append('runtime')
        if s.route in ('eng', 'both'):
            calls = typed.get(up)
            if calls:
                ok = [f'{g}.{fn}' for g, fn in sorted(calls) if (g, fn) in have or (g == 'shop' and fn == 'reward_table' and 'msn_reward_get' in ''.join(read_main(src / x) for x in ('game_msn.c', 'msn_view.c', 'main.c')))]
                if ok: st.append('engine'); where += ok
                else: where += ['нет ' + '/'.join(f'{g}.{fn}' for g, fn in sorted(calls))]
            elif up in ment:
                st.append('engine'); where.append('MSN_OP_' + up)
            if s.name in off and 'engine' not in st:
                st.append('offline'); where += off[s.name]
        if not st: st = ['ignored']
        elif st == ['runtime'] and s.route == 'both': st.append('ignored-engine')
        res[s.op] = dict(name=s.name, status='+'.join(st), where=', '.join(where), feature=s.feature, route=s.route,
                         needs=NEEDS.get(s.name, ''), ru=s.ru)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--msn-dir', default=str(ROOT / 'build/lm/msn'), help='папка с level01..07.msn')
    ap.add_argument('--src', default=str(ROOT / 'viewer'))
    ap.add_argument('--tools', default=str(ROOT / 'tools'))
    ap.add_argument('--write', help='записать таблицу TSV')
    ap.add_argument('--check', help='сверить статусы с таблицей ожиданий')
    ap.add_argument('--brief', action='store_true')
    a = ap.parse_args()
    src, tools, d = Path(a.src), Path(a.tools), Path(a.msn_dir)
    cls = classify(src, tools)
    per = {}
    for n in LEVELS:
        p = d / f'level{n:02d}.msn'
        lv, c = pack_ops(p)
        if lv != n: print(f'FAIL {p}: уровень в пакете {lv}'); return 1
        per[n] = c
    unknown = sorted({op for c in per.values() for op in c if op not in cls})
    rows = []
    for op, r in cls.items():
        cnt = [per[n].get(op, 0) for n in LEVELS]
        if not any(cnt): continue
        rows.append((r, cnt))
    order = {'ignored': 0, 'runtime+ignored-engine': 1, 'offline': 2, 'runtime': 3}
    rows.sort(key=lambda x: (order.get(x[0]['status'], 4), -sum(x[1]), x[0]['name']))
    head = 'команда\tстатус\tL1\tL2\tL3\tL4\tL5\tL6\tL7\tновая против L1\tждёт\tгде\tфича'
    lines = [head] + [f"{r['name']}\t{r['status']}\t" + '\t'.join(map(str, c)) + f"\t{'да' if c[0] == 0 else ''}\t{r['needs']}\t{r['where']}\t{r['feature']}"
                      for r, c in rows]
    ign = [(r, c) for r, c in rows if r['status'] in ('ignored', 'runtime+ignored-engine')]
    tot = [sum(c[i] for _, c in ign) for i in range(7)]
    summary = (f'команд в пакетах: {len(rows)}; не исполняются игрой (ignored): {len(ign)}; вызовов ignored по уровням '
               + ' '.join(f'L{n}={tot[n - 1]}' for n in LEVELS))
    if a.write:
        Path(a.write).write_text('# сгенерировано tools/missions/coverage.py — не править руками\n# ' + summary + '\n' + '\n'.join(lines) + '\n')
    if not a.brief:
        print(head)
        for r, c in ign: print(f"{r['name']}\t{r['status']}\t" + '\t'.join(map(str, c)) + f"\t{'да' if c[0] == 0 else ''}\t{r['where']}")
    print(summary)
    if unknown: print('FAIL неизвестные опкоды в пакетах:', unknown); return 1
    if a.check:
        want = {}
        for ln in Path(a.check).read_text().splitlines():
            if not ln.strip() or ln.startswith('#'): continue
            k, v = ln.split('\t')[:2]; want[k] = v
        bad = []
        for r, c in rows:
            w = want.get(r['name'])
            if w != r['status']: bad.append(f"{r['name']}: ждали {w}, есть {r['status']}")
        for k in want:
            if not any(r['name'] == k for r, _ in rows): bad.append(f'{k}: нет в пакетах')
        if bad:
            for b in bad: print('FAIL', b)
            print('RESULT: FAIL'); return 1
        print('RESULT: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
