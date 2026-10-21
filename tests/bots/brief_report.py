#!/usr/bin/env python3
"""One-screen report contract, real TSV/parser/writer, including OLD negative."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('allrisk', ROOT / 'tools/bots/allrisk.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
OUT = Path(tempfile.mkdtemp(prefix='bot-brief-', dir=ROOT / 'build'))


def row(fam, verdict, place, idx='one', lv='L5'):
    return '\t'.join([fam, verdict, idx, lv, place, '10', '0', '20', '-1:-', '40', 'test=1', 'bin --only one', 'fixture'])


def folder(name, lines, digest='same'):
    d = OUT / name; d.mkdir()
    (d / 'cases.tsv').write_text('\n'.join(lines) + '\n')
    (d / 'result.json').write_text(json.dumps({'meta': {'git': 'fixture', 'files': {'run/bin/allrisk': 'bot', 'l5/level.shr': digest}}}))
    return d


def render(d, base):
    p, _ = A.report(d, base)
    text = p.read_text()
    head = text.split('## Полный отчёт', 1)[0]
    assert len(head.splitlines()) <= 18, head
    assert '| Риск |' in text and 'повтор:' in text, 'full evidence table lost'
    return head


base = folder('previous-night', [row('rollover', 'risk', 'H8-4'), row('rollover', 'ok', 'K8-2'), row('police', 'ok', 'F11-5')])
now = folder('current-night', [row('rollover', 'risk', 'H8-4'), row('rollover', 'risk', 'K8-2'), row('rollover', 'risk', 'K9-2'), row('police', 'fail', 'F11-5')])
head = render(now, base)
assert 'Новый риск в проверенном месте: переворот; L5 K8-2' in head, head
assert 'Впервые проверенное место с риском: переворот; L5 K9-2' in head, head
assert 'Не удалось проверить: 1' in head and 'H8-4' not in head, head
assert 'Сравнение условное' not in head, head
no_base = render(now, None)
assert 'Сравнения с прошлой ночью нет' in no_base and 'Новый риск' not in no_base
same = folder('unchanged', A.load_cases(base) and (base / 'cases.tsv').read_text().splitlines())
head = render(same, base)
assert 'Новых мест риска не обнаружено' in head and 'Новый риск' not in head, head
changed = folder('changed-data', (now / 'cases.tsv').read_text().splitlines(), 'different')
assert 'Сравнение условное' in render(changed, base)
missing = folder('missing-coverage', [row('rollover', 'risk', 'H8-4')])
assert 'Нет прежнего покрытия: 1' in render(missing, base)
print('PASS: known regression location, new coverage, failed check, absent/equal baseline, changed data, missing coverage, full table, <=18 lines')
os.environ['BOT_BRIEF_OLD'] = '1'
try:
    assert 'Новый риск в проверенном месте: переворот; L5 K8-2' in render(now, base)
except AssertionError:
    print('PASS negative: OLD report hides the new location in its first screen')
else:
    raise AssertionError('OLD escaped')
