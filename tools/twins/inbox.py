#!/usr/bin/env python3
"""Близнецы · вопросы к оригиналу: одна очередь на всех — knowledge/questions.tsv (ОРАКУЛ_PS2 §4), второй копии нет.

Кто кладёт: любая сессия или бот, когда ответа нет в данных диска и в коде (слово Роба 01.10: «что непонятно — близнецу»).
Кто отвечает: поток П7 (близнецы). Ответ — карточка knowledge/facts/ps2-<тема>.yaml (ОРАКУЛ §5) и статус в строке вопроса.

  python3 tools/twins/inbox.py list [--open]           открытые — статус не начинается с «отвечен» / «не может»
  python3 tools/twins/inbox.py ask --who main --need "правка 171, viewer/x.c" --how "живьём: …" "вопрос одной строкой"
  python3 tools/twins/inbox.py answer В11 --stage 3 --card ps2-kwik-camera "ответ коротко"
  python3 tools/twins/inbox.py answer В11 --cannot "чего не хватает (ввод О4, адрес, камера)"

Читает и пишет файл рабочей копии, из которой запущен (в worktree П7 — после слияния свежего main). Столбцы файла не меняются:
id · вопрос оригиналу · кому нужно · способ · статус · карточка. Ступень правды (ОРАКУЛ §2): 1 диск · 3 своё наблюдение в PCSX2 ·
4 свой опыт в PCSX2 (хирургия, ввод) · 5 правило порта. Ответ без ступени и без карточки не принимается."""
import argparse, os, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

Q = C.WT / 'knowledge/questions.tsv'
HEAD = ['id', 'вопрос оригиналу', 'кому нужно', 'способ', 'статус', 'карточка']
STAGE = {'1': 'диск', '3': 'PS2 наблюдение', '4': 'PS2 опыт', '5': 'правило порта'}


def _clean(s):
    return ' '.join(str(s).replace('\t', ' ').split())


def read():
    lines = Q.read_text().splitlines()
    if lines[0].split('\t') != HEAD: raise SystemExit(f'{Q}: шапка не та — {lines[0]!r}')
    rows = []
    for l in lines[1:]:
        if not l.strip(): continue
        f = l.split('\t'); rows.append(dict(zip(HEAD, f + [''] * (len(HEAD) - len(f)))))
    return rows


def write(rows):
    tmp = Q.with_suffix('.tmp')
    tmp.write_text('\t'.join(HEAD) + '\n' + ''.join('\t'.join(_clean(r[c]) for c in HEAD) + '\n' for r in rows))
    os.replace(tmp, Q)


def is_open(r):
    return not r['статус'].startswith(('отвечен', 'не может'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    l = sub.add_parser('list'); l.add_argument('--open', action='store_true')
    a = sub.add_parser('ask'); a.add_argument('text'); a.add_argument('--who', required=True)
    a.add_argument('--need', default=''); a.add_argument('--how', default='')
    w = sub.add_parser('answer'); w.add_argument('id'); w.add_argument('text', nargs='?', default='')
    w.add_argument('--stage', choices=sorted(STAGE)); w.add_argument('--card', default=''); w.add_argument('--cannot', default='')
    x = ap.parse_args()
    rows = read()
    if x.cmd == 'ask':
        n = max([int(r['id'][1:]) for r in rows if r['id'][1:].isdigit()], default=0) + 1
        rows.append(dict(zip(HEAD, [f'В{n}', x.text, f'{x.who}: {x.need}'.strip(': '), x.how, f'новый {C.clock()[:10]}', ''])))
        write(rows); print(f'В{n}: принят → {Q.relative_to(C.WT)}'); return 0
    if x.cmd == 'answer':
        r = next((r for r in rows if r['id'] == x.id), None)
        if not r: raise SystemExit(f'нет вопроса {x.id}')
        if x.cannot:
            r['статус'] = f'не может {C.clock()[:16]}: {x.cannot}'
        else:
            if not x.stage or not x.card or not x.text: raise SystemExit('ответ без ступени (--stage), карточки (--card) и текста не принимается')
            if not (C.WT / 'knowledge/facts' / f'{x.card}.yaml').exists(): raise SystemExit(f'нет карточки knowledge/facts/{x.card}.yaml')
            r['статус'] = f'отвечен {C.clock()[:16]} (ступень {x.stage}, {STAGE[x.stage]}): {x.text}'; r['карточка'] = x.card
        write(rows); print(f"{x.id}: {r['статус'][:120]}"); return 0
    shown = [r for r in rows if not x.open or is_open(r)]
    for r in shown: print(f"{r['id']:>4} · {r['статус'][:24]:<24} · {r['вопрос оригиналу'][:96]}")
    print(f'всего {len(rows)}, показано {len(shown)} · {Q.relative_to(C.WT)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
