#!/usr/bin/env python3
"""Catalog every command of every .mfk on the disc and (re)generate the tables in docs/missions.md.

  python tools/missions/catalog.py [--json out.json] [--doc docs/missions.md]

Counts per level, argument counts seen, where the command appears (level / init / load / setup /
stage / objective / condition / gag / rewards / other), our meaning, engine feature, plan stage and
PSP difficulty (from commands.py). Generated blocks in the doc live between
<!-- GEN:name --> and <!-- /GEN:name --> markers; the rest of the doc is hand-written.
"""
import argparse, json, re, sys
from pathlib import Path
from collections import Counter, defaultdict

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GAME = ROOT / 'hit-and-run-web/source/game'
sys.path.insert(0, str(HERE))
import mfk
import commands as CMD

CTX_ORDER = ['level', 'init', 'load', 'setup', 'stage', 'objective', 'condition', 'gag', 'rewards', 'other']
CTX_RU = {'level': 'ур', 'init': 'иниц', 'load': 'загр', 'setup': 'миссия', 'stage': 'этап', 'objective': 'цель',
          'condition': 'усл', 'gag': 'гэг', 'rewards': 'награды', 'other': 'прочее'}

def kind_of(path):
    n = path.name.lower()
    if path.parent.name.startswith('level'):
        lv = int(path.parent.name[5:])
        if n in ('level.mfk',): return lv, 'level'
        if n in ('leveli.mfk',): return lv, 'init'
        if n.endswith('l.mfk'): return lv, 'load'
        if n.endswith('i.mfk'): return lv, 'mission'
        return lv, 'other'
    if n in ('rewards.mfk',): return 0, 'rewards'
    return 0, 'other'

def scan():
    base = GAME / 'scripts'
    cmds = defaultdict(lambda: dict(levels=Counter(), argc=Counter(), ctx=Counter(), example=None))
    objs = defaultdict(Counter); conds = defaultdict(Counter); files = Counter(); total = 0
    scheduled = {}
    for lv in range(1, 8):
        sched = mfk.parse_file(base / f'missions/level{lv:02d}/level.mfk')[0]
        scheduled[lv] = {str(c.args[0]).lower() for c in sched if c.op in ('AddMission', 'AddBonusMission')}
    for p in sorted(base.rglob('*.mfk')):
        rel = str(p.relative_to(base))
        calls, _ = mfk.parse_file(p, rel)
        lv, kind = kind_of(p)
        if kind in ('load', 'other') and any(c.op == 'SelectMission' for c in calls):
            kind = 'mission'    # content under a swapped name (see docs/missions.md, section 7)
        files[kind] += 1
        in_stage = in_obj = in_cond = in_gag = False
        for c in calls:
            total += 1
            d = cmds[c.op]
            d['levels'][f'L{lv}' if lv else 'other'] += 1
            d['argc'][len(c.args)] += 1
            if d['example'] is None:
                d['example'] = f'{rel}:{c.line}: {c.op}({", ".join(repr(a) if isinstance(a, str) else str(a) for a in c.args)})'
            if c.op == 'GagBegin': in_gag = True
            if kind == 'mission':
                if c.op == 'AddStage': in_stage = True
                if c.op == 'AddObjective':
                    in_obj = True; objs[str(c.args[0]).lower()][f'L{lv}'] += 1
                if c.op == 'AddCondition':
                    in_cond = True; conds[str(c.args[0]).lower()][f'L{lv}'] += 1
                ctx = 'condition' if in_cond else 'objective' if in_obj else 'stage' if in_stage else 'setup'
                if c.op == 'CloseCondition': in_cond = False
                if c.op == 'CloseObjective': in_obj = False; in_cond = False
                if c.op == 'CloseStage': in_stage = in_obj = in_cond = False
            elif in_gag:
                ctx = 'gag'
            else:
                ctx = kind
            d['ctx'][ctx] += 1
            if c.op == 'GagEnd': in_gag = False
    return dict(cmds=cmds, objs=objs, conds=conds, files=files, total=total)

def md_commands(data):
    cmds = data['cmds']
    rows = ['| Команда | L1 | L2 | L3 | L4 | L5 | L6 | L7 | др. | арг. | где | смысл | фича движка | этап плана | PSP |',
            '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    def key(name):
        s = CMD.BY_NAME[name.lower()]
        return (list(CMD.FEATURES).index(s.feature), name.lower())
    for name in sorted(cmds, key=key):
        d = cmds[name]; s = CMD.BY_NAME[name.lower()]
        feat = CMD.FEATURES[s.feature]
        lv = [str(d['levels'].get(f'L{i}', '')) for i in range(1, 8)]
        argc = '/'.join(str(k) for k in sorted(d['argc']))
        ctx = ', '.join(CTX_RU[c] for c in CTX_ORDER if d['ctx'].get(c))
        rows.append(f'| `{name}` | ' + ' | '.join(lv) + f" | {d['levels'].get('other', '')} | {argc} | {ctx} | {s.ru} | {s.feature} | {feat[1]} | {feat[2]} |")
    return '\n'.join(rows)

def md_features():
    rows = ['| Ключ | Что это | Этап плана | Сложность на PSP | Заметка |', '|---|---|---|---|---|']
    for k, (name, stage, diff, note) in CMD.FEATURES.items():
        rows.append(f'| `{k}` | {name} | {stage} | {diff} | {note} |')
    return '\n'.join(rows)

def md_types(data):
    out = ['| Цель (AddObjective) | L1 | L2 | L3 | L4 | L5 | L6 | L7 | всего | что делает игрок |', '|---|---|---|---|---|---|---|---|---|---|']
    for t in CMD.OBJECTIVES:
        c = data['objs'].get(t, Counter())
        out.append(f'| `{t}` | ' + ' | '.join(str(c.get(f"L{i}", '')) for i in range(1, 8)) + f' | {sum(c.values())} | {CMD.OBJ_RU[t]} |')
    out += ['', '| Условие провала (AddCondition) | L1 | L2 | L3 | L4 | L5 | L6 | L7 | всего | провал, если |', '|---|---|---|---|---|---|---|---|---|---|']
    for t in CMD.CONDITIONS:
        c = data['conds'].get(t, Counter())
        out.append(f'| `{t}` | ' + ' | '.join(str(c.get(f"L{i}", '')) for i in range(1, 8)) + f' | {sum(c.values())} | {CMD.COND_RU[t]} |')
    return '\n'.join(out)

def md_unused(data):
    unused = [s for s in CMD.SPECS if s.name not in data['cmds']]
    by = defaultdict(list)
    for s in unused:
        by[s.feature].append(s.name)
    return '\n'.join(f'- **{k}**: ' + ', '.join(f'`{n}`' for n in v) for k, v in by.items())

def replace_block(doc, name, body):
    a, b = f'<!-- GEN:{name} -->', f'<!-- /GEN:{name} -->'
    if a not in doc:
        return doc + f'\n{a}\n{body}\n{b}\n'
    pre, rest = doc.split(a, 1)
    _, post = rest.split(b, 1)
    return pre + a + '\n' + body + '\n' + b + post

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json'); ap.add_argument('--doc', default=str(ROOT / 'docs/missions.md'))
    a = ap.parse_args()
    data = scan()
    used = len(data['cmds'])
    print(f"{sum(data['files'].values())} .mfk files ({dict(data['files'])}), {data['total']} calls, {used} distinct commands "
          f"(of {len(CMD.SPECS)} registered), unknown: {[n for n in data['cmds'] if n.lower() not in CMD.BY_NAME]}")
    if a.json:
        Path(a.json).write_text(json.dumps({k: {'levels': dict(v['levels']), 'argc': dict(v['argc']), 'ctx': dict(v['ctx']), 'example': v['example']}
                                            for k, v in data['cmds'].items()}, indent=1, ensure_ascii=False))
    doc_path = Path(a.doc)
    if doc_path.exists():
        doc = doc_path.read_text()
        doc = replace_block(doc, 'summary', f"Всего на диске: **{sum(data['files'].values())} файлов .mfk**, **{data['total']} вызовов**, "
                                            f"**{used} разных команд** (из {len(CMD.SPECS)} зарегистрированных в игре по donut); неизвестных: **0**.")
        doc = replace_block(doc, 'features', md_features())
        doc = replace_block(doc, 'types', md_types(data))
        doc = replace_block(doc, 'commands', md_commands(data))
        doc = replace_block(doc, 'unused', md_unused(data))
        doc_path.write_text(doc)
        print('updated', doc_path)

if __name__ == '__main__':
    main()
