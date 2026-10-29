#!/usr/bin/env python3
"""Близнецы · утренний отчёт (ТЗ БЛИЗНЕЦЫ §5, слово Роба 01.10: «каждое утро — топ-20 расхождений с уликами и что уже исправлено»).
Без AI: собирает из файлов, ничего не придумывает.

  python3 tools/twins/morning.py [--out build/twins/<дата>/morning.md]
Источники: docs/handoff/ПРАВКИ_РОБА.md (строки, где упомянут близнец / Б2 / oracle), knowledge/questions.tsv (статусы),
knowledge/facts/ps2-*.yaml (улики). Порядок: открытые расхождения сверху, исправленные («в main», «на PSP») — отдельным списком."""
import argparse, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def rows_pravki():
    out = []
    for l in (C.WT / 'docs/handoff/ПРАВКИ_РОБА.md').read_text().splitlines():
        m = re.match(r'^\| (\d+[а-я]?) \| (.*?) \| (.*?) \| (.*) \|$', l)
        if not m: continue
        num, text, when, status = m.groups()
        if not re.search(r'близн|Б2|oracle|оракул|ps2-', text + status, re.I): continue
        fixed = bool(re.search(r'в main|на PSP|сделано|исправлен', status, re.I)) and not re.search(r'не сделано', status, re.I)
        ev = re.findall(r'(knowledge/facts/[\w./-]+\.yaml|build/twins/[\w./-]+)', text + ' ' + status)
        out.append(dict(num=num, text=text, when=when, status=status, fixed=fixed, evidence=ev))
    return out


def questions():
    q = C.WT / 'knowledge/questions.tsv'
    rows = [l.split('\t') for l in q.read_text().splitlines()[1:] if l.strip()]
    return [dict(id=r[0], q=r[1], status=r[4] if len(r) > 4 else '', card=r[5] if len(r) > 5 else '') for r in rows]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter); ap.add_argument('--out')
    a = ap.parse_args()
    out = Path(a.out) if a.out else C.OUT / C.stamp()[:8] / 'morning.md'
    pr = rows_pravki(); qs = questions()
    open_ = [r for r in pr if not r['fixed']]; fixed = [r for r in pr if r['fixed']]
    ans = [x for x in qs if x['status'].startswith('отвечен')]; cant = [x for x in qs if x['status'].startswith('не может')]
    opn = [x for x in qs if not x['status'].startswith(('отвечен', 'не может'))]
    L = [f'# Близнецы · утро {C.clock()}', '',
         f'Вопросов к оригиналу: отвечено {len(ans)}, «не может» {len(cant)}, открыто {len(opn)}. Расхождений в списке правок: открыто {len(open_)}, исправлено {len(fixed)}.', '',
         '## Топ расхождений (открытые, с уликами)', '']
    for r in open_[:20]:
        L.append(f"- **{r['num']}** {r['text'][:220]}" + (f"  \n  улики: {', '.join(sorted(set(r['evidence'])))}" if r['evidence'] else ''))
    L += ['', '## Уже исправлено', '']
    L += [f"- {r['num']}: {r['status'][:160]}" for r in fixed[:20]] or ['- пока нет']
    L += ['', '## Ждут оригинала (открытые вопросы)', ''] + [f"- {x['id']}: {x['q'][:140]}" for x in opn[:20]]
    L += ['', '## Оригинал не может ответить — чего не хватает', ''] + [f"- {x['id']}: {x['status'][:200]}" for x in cant]
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text('\n'.join(L) + '\n')
    print('\n'.join(L[:4])); print(f'→ {out.relative_to(C.DATA)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
