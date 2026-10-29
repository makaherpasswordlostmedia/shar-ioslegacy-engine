#!/usr/bin/env python3
"""Близнецы · Б2: «оригинал читает — порт нет». Список файлов диска, которые оригинал прочитал на маршруте (b2_reads.py → files.tsv),
против того, что есть в данных порта (build/ основной папки):
  звук (.rsd)              — build/audio/pack_report.json: поле file у sfx и music (какой файл диска лёг в пакет);
  персонажи art/chars/*_m  — build/chars/<имя>.chr по правилам выпуска (tools/ship_rules.txt: --model) и homer.shr;
  гэги art/nis/gags/*      — имена гэгов в build/collect-l1.shr;
  мир уровня art/l1*.p3d   — зоны и дороги уровня берёт tools/psp_export.py (level.shr), интерьеры — tools/interior_export.py;
  остальное                — «не проверено» (честно, не «есть»).

  python3 tools/twins/b2_compare.py ANSWER_ID [--drop ПУТЬ_ДИСКА]    --drop: гейт — этот файл считать убранным из экспорта
Выход build/twins/b2/<id>/missing.tsv и строки в summary.md. Гейт: tools/twins/b2_compare.py ID --gate; TWINS_BREAK=b2_nodrop (убирание не действует) — гейт обязан быть FAIL"""
import argparse, json, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def port_sets(drop=None):
    B = C.DATA / 'build'
    rep = json.loads((B / 'audio/pack_report.json').read_text())
    audio = {e['file'].lower() for k in ('sfx', 'music') for e in rep.get(k, []) if e.get('file')}
    chars = set()
    for l in (C.DATA / 'tools/ship_rules.txt').read_text().splitlines():
        m = re.match(r'^chars/(\w+)\.chr\s*\|\s*(\S+)', l)
        if not m or not (C.DATA / m.group(2)).exists(): continue
        mm = re.search(r'--model (\S+)', l)
        chars.add((mm.group(1) if mm else f'art/chars/{m.group(1)}_m.p3d').lower())
    if (B / 'homer.shr').exists(): chars.add('art/chars/homer_m.p3d')
    gags = set()
    if (B / 'collect-l1.shr').exists():
        gags = {f'art/nis/gags/{g.decode()}.p3d' for g in set(re.findall(rb'gag_[a-z0-9_]{2,20}', (B / 'collect-l1.shr').read_bytes()))}
    peds = set()   # пешеходы уровня: tools/traffic_export.py level_script — группы CreatePedGroup/AddPed, модель art/chars/<имя[:6]>_m.p3d
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('traffic_export', C.DATA / 'tools/traffic_export.py'); te = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(C.DATA / 'tools')); spec.loader.exec_module(te)
        for g in te.level_script(1)[1].values(): peds |= {f'art/chars/{n[:6]}_m.p3d' for n, _ in g}
    except Exception as e: print(f'пешеходы порта не прочитаны: {e}')
    chars |= peds
    have = dict(audio=audio, chars=chars, gags=gags)
    if drop and 'b2_nodrop' not in os.environ.get('TWINS_BREAK', ''):   # TWINS_BREAK=b2_nodrop — отрицательный контроль гейта
        for s in have.values(): s.discard(drop.lower())
    return have


def judge(path, have):
    """путь диска (АРХИВ:путь) → (категория, есть ли у порта: True/False/None — не проверено, улика)"""
    inner = path.split(':', 1)[1] if ':' in path else path
    if inner.endswith('.rsd'): return 'звук', inner in have['audio'], 'build/audio/pack_report.json'
    if inner.startswith('art/chars/') and inner.endswith('_m.p3d'):
        return 'персонаж', inner in have['chars'], 'tools/ship_rules.txt chars/*.chr, homer.shr, пешеходы tools/traffic_export.py'
    if inner.startswith('art/nis/gags/'): return 'гэг', inner in have['gags'], 'build/collect-l1.shr'
    # мир и интерьеры порт берёт глобом всех файлов уровня: tools/psp_export.py:1428 (l1r*, l1z*), tools/interior_export.py:273 (l1i*)
    if re.match(r'art/l1[zr]\w*\.p3d$', inner): return 'мир уровня', True, 'tools/psp_export.py:1428 glob l1r*/l1z* → level.shr'
    if re.match(r'art/l1i\d+\.p3d$', inner): return 'интерьер', True, 'tools/interior_export.py:273 glob l1i* → interiors-l1.bin'
    return 'прочее', None, '—'


def compare(aid, drop=None):
    out = C.OUT / 'b2' / aid
    rows = [l.split('\t') for l in (out / 'files.tsv').read_text().splitlines()[1:] if l.strip()]
    have = port_sets(drop)
    res = []
    for r in rows:
        cat, ok, ev = judge(r[0], have)
        res.append(dict(path=r[0], read=int(r[1]), frame=r[4], where=r[5], cat=cat, port=ok, evidence=ev))
    return res, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('id'); ap.add_argument('--drop'); ap.add_argument('--gate', action='store_true')
    a = ap.parse_args()
    if a.gate:   # красный: убранный из экспорта файл обязан найтись; зелёный: без убирания его в списке нет
        res, _ = compare(a.id)
        present = [x for x in res if x['port'] is True]
        if not present: print('FAIL гейт Б2: нет ни одного файла, который у порта есть, — нечего убирать'); return 1
        probe = present[0]['path'].split(':', 1)[1]
        miss_clean = {x['path'].split(':', 1)[1] for x in res if x['port'] is False}
        res2, _ = compare(a.id, drop=probe)
        miss_drop = {x['path'].split(':', 1)[1] for x in res2 if x['port'] is False}
        ok = probe not in miss_clean and probe in miss_drop and miss_drop - {probe} == miss_clean
        print(('PASS' if ok else 'FAIL'), f'гейт Б2: убран из экспорта {probe} → найден: {probe in miss_drop}; без убирания в списке: {probe in miss_clean}; '
              f'прочие находки не изменились: {miss_drop - {probe} == miss_clean}')
        return 0 if ok else 1
    res, out = compare(a.id, a.drop)
    with (out / 'missing.tsv').open('w') as fo:
        fo.write('файл диска\tчто\tу порта\tпрочитано байт\tпервый кадр\tточка маршрута\tгде смотрели\n')
        for x in sorted(res, key=lambda x: (x['port'] is not False, x['cat'], x['path'])):
            st = {True: 'есть', False: 'НЕТ', None: 'не сверено'}[x['port']]
            fo.write(f"{x['path']}\t{x['cat']}\t{st}\t{x['read']}\t{x['frame']}\t{x['where']}\t{x['evidence']}\n")
    miss = [x for x in res if x['port'] is False]
    print(f"файлов прочитано {len(res)}: у порта нет {len(miss)}, есть {sum(1 for x in res if x['port'])}, не сверено {sum(1 for x in res if x['port'] is None)}")
    for x in miss: print(f"  НЕТ {x['cat']}: {x['path']} (точка «{x['where']}»)")
    print(f'→ {(out / "missing.tsv").relative_to(C.DATA)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
