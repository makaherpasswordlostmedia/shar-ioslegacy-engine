#!/usr/bin/env python3
"""Близнецы · судья (docs/handoff/БЛИЗНЕЦЫ_2026-10-01.md §1): правила, без моделей. Сравнивает пакеты сторон одной точки.

  python3 tools/twins/judge.py build/twins/<прогон>/packets.jsonl   -> report.md, findings.json рядом (агенту — только сводка)
Правила Б1 (поза после синхронизации и N кадров без ввода; оригинал — эталон, порт — каждая его сторона отдельно):
  pose_xz   расстояние по земле > 1,0 м          pose_y  |Δy| начала модели > 0,75 м
  heading   |Δкурса| > 5°                          speed   ||v|о − |v|п| > 0,5 м/с          onfoot  пешком/в машине не совпало
Поле, которого сторона не знает (null), не сравнивается: пара уходит в «не сверено» (не молчаливое «чисто»).
TWINS_BREAK=judge_pose — отрицательный контроль гейта Б1: правило pose_xz выключено (гейт обязан покраснеть)."""
import json, math, os, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

LIMITS = {'pose_xz': 1.0, 'pose_y': 0.75, 'heading': 5.0, 'speed': 0.5}
TITLE = {'pose_xz': 'позиция по земле, м', 'pose_y': 'высота начала модели, м', 'heading': 'курс, °', 'speed': 'скорость, м/с',
         'onfoot': 'пешком / в машине'}


def _rules():
    off = set(filter(None, os.environ.get('TWINS_BREAK', '').split(',')))
    return [r for r in ('pose_xz', 'pose_y', 'heading', 'speed', 'onfoot') if not ('judge_pose' in off and r == 'pose_xz')]


def compare(o, p):
    """-> (находки, не сверено) для пары оригинал o / порт p одной точки"""
    found, unk = [], []

    def need(*keys):
        miss = [k for k in keys if o.get(k) is None or p.get(k) is None]
        return miss

    for rule in _rules():
        if rule in ('pose_xz', 'pose_y'):
            miss = need('pos')
            if miss: unk.append((rule, miss)); continue
            v = math.hypot(p['pos'][0] - o['pos'][0], p['pos'][2] - o['pos'][2]) if rule == 'pose_xz' else abs(p['pos'][1] - o['pos'][1])
        elif rule == 'heading':
            if need('heading'): unk.append((rule, need('heading'))); continue
            v = abs(math.degrees(C.wrap(p['heading'] - o['heading'])))
        elif rule == 'speed':
            if need('vel'): unk.append((rule, need('vel'))); continue
            v = abs(math.hypot(*o['vel']) - math.hypot(*p['vel']))
        else:   # onfoot
            if need('onfoot'): unk.append((rule, need('onfoot'))); continue
            if bool(o['onfoot']) != bool(p['onfoot']):
                found.append(dict(rule=rule, value=1.0, limit=0.0, ratio=99.0))
            continue
        lim = LIMITS[rule]
        if v > lim: found.append(dict(rule=rule, value=round(v, 3), limit=lim, ratio=round(v / lim, 2)))
    return found, unk


def judge(packets):
    """packets: список пакетов (схема §1). -> dict(findings, unknown, pairs, points)"""
    by = {}
    for p in packets: by.setdefault(p['point'], {})[p['side']] = C.check_packet(p)
    findings, unknown, pairs = [], [], []
    for pt, sides in by.items():
        o = sides.get('orig')
        if not o:
            unknown.append(dict(point=pt, sides='orig', rule='*', why='нет пакета оригинала')); continue
        for side in ('port_light', 'port_full'):
            p = sides.get(side)
            if not p: continue
            f, u = compare(o, p)
            for x in f:
                findings.append(dict(x, point=pt, sides=f'orig↔{side}', orig=o, port=p))
            for rule, miss in u:
                unknown.append(dict(point=pt, sides=f'orig↔{side}', rule=rule, why='не знает: ' + ', '.join(miss)))
            if o.get('shot') and p.get('shot'): pairs.append(dict(point=pt, orig=o['shot'], port=p['shot'], side=side))
    findings.sort(key=lambda x: -x['ratio'])
    return dict(findings=findings, unknown=unknown, pairs=pairs, points=sorted(by))


def _brief(p):
    f = lambda v: 'null' if v is None else ('[' + ', '.join(f'{x:.2f}' for x in v) + ']' if isinstance(v, list) else f'{v:.3f}' if isinstance(v, float) else str(v))
    return f"pos {f(p['pos'])}, курс {f(p['heading'])}, v {f(p['vel'])}, кадр {p['frame']}"


def pair_sheet(run, pairs):
    """лист пар кадров оригинал | порт (одна высота 272)"""
    from PIL import Image, ImageDraw
    rows = []
    for pr in pairs:
        a = Image.open(run / pr['orig']).convert('RGB'); b = Image.open(run / pr['port']).convert('RGB')
        a = a.resize((round(a.width * 272 / a.height), 272)); b = b.resize((round(b.width * 272 / b.height), 272))
        im = Image.new('RGB', (a.width + b.width + 8, 272 + 18), (20, 20, 20)); im.paste(a, (0, 18)); im.paste(b, (a.width + 8, 18))
        ImageDraw.Draw(im).text((4, 3), f"{pr['point']}: оригинал (PCSX2) | {pr['side']} (свой PPSSPP)", fill=(230, 230, 230))
        rows.append(im)
    if not rows: return None
    sheet = Image.new('RGB', (max(r.width for r in rows), sum(r.height for r in rows)), (20, 20, 20)); y = 0
    for r in rows: sheet.paste(r, (0, y)); y += r.height
    out = run / 'pairs.png'; sheet.save(out); return out


def report(run, res, manifest=None):
    run = Path(run); L = []
    L.append(f"# Близнецы · отчёт {run.name}\n")
    if manifest:
        L.append(f"Время (date): {manifest.get('started')} → {manifest.get('finished')} · код {manifest.get('code')} · "
                 f"точек {len(res['points'])} · стороны {', '.join(manifest.get('sides', []))}"
                 + (f" · ПОДЛОГ порта {manifest['fake_shift']} м" if manifest.get('fake_shift') else '')
                 + (f" · БЕЗ СИНХРОНИЗАЦИИ" if manifest.get('no_sync') else '') + '\n')
    n = len(res['findings'])
    L.append(f"**Расхождений: {n}** (правила: {', '.join(_rules())}; допуски {LIMITS})\n")
    if n:
        L.append('| № | точка | правило | стороны | значение | допуск | улики |\n|---|---|---|---|---|---|---|')
        for i, x in enumerate(res['findings'][:20], 1):
            L.append(f"| {i} | {x['point']} | {TITLE[x['rule']]} | {x['sides']} | {x['value']} | {x['limit']} | "
                     f"о: {_brief(x['orig'])}; п: {_brief(x['port'])} |")
        L.append('')
    if res['unknown']:
        L.append('Не сверено (сторона не знает поле — не «чисто»):\n')
        for u in res['unknown']: L.append(f"- {u['point']} · {u['sides']} · {u['rule']}: {u['why']}")
        L.append('')
    if res['pairs']:
        sheet = pair_sheet(run, res['pairs'])
        L.append(f"Пары кадров (одна точка, камеры пока свои у каждой стороны — `cam` в Б3): `{sheet.name if sheet else '-'}`\n")
        for pr in res['pairs']: L.append(f"- {pr['point']}: `{pr['orig']}` | `{pr['port']}`")
        L.append('')
    if manifest and manifest.get('notes'):
        L.append('Заметки:\n'); L += [f'- {n}' for n in manifest['notes']]; L.append('')
    (run / 'report.md').write_text('\n'.join(L) + '\n')
    slim = dict(res, findings=[{k: v for k, v in x.items() if k not in ('orig', 'port')} for x in res['findings']])
    (run / 'findings.json').write_text(json.dumps(slim, ensure_ascii=False, indent=1) + '\n')
    return run / 'report.md'


def main():
    if len(sys.argv) < 2: print(__doc__); return 2
    f = Path(sys.argv[1]); pk = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    man = json.loads((f.parent / 'manifest.json').read_text()) if (f.parent / 'manifest.json').exists() else None
    res = judge(pk); rp = report(f.parent, res, man)
    print(f"расхождений {len(res['findings'])}, не сверено {len(res['unknown'])}, пар кадров {len(res['pairs'])} → {rp.relative_to(C.DATA)}")
    for x in res['findings'][:5]: print(f"  {x['point']} {x['sides']} {x['rule']} {x['value']} > {x['limit']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
