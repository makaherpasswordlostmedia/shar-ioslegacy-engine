#!/usr/bin/env python3
"""Аудит картинок брифинга миссий (экран MissionLoad, SetPresentationBitmap): миссия -> картинка есть/нет -> почему.
Правило движка (viewer/mission/msn_game.c, viewer/msn_view.c): картинка из скрипта (SetPresentationBitmap в mXsdi/mXi) главнее; иначе у бонусных
миссий с NPC-заказчиком (leveli.mfk AddNPCCharacterBonusMission) — таблица исполняемого файла b_<NPC> -> misXX (viewer/mission/briefcards_data.h);
иначе картинки нет (ни у оригинала в скриптах, ни в таблице).
  python3 tools/mload_audit.py [--scratch DIR с level0N.json от tools/missions/compile.py --all --scratch DIR] [--pack DIR с l<N>/msnart.shr]"""
import argparse, json, os, re, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / 'hit-and-run-web/source/game'
sys.path.insert(0, str(ROOT / 'tools'))


def builtin():
    import briefcards_source as B
    return B.builtin_mappings()


def msnart_rows(pack, lv):
    for p in (Path(pack) / f'l{lv}' / 'msnart.shr', Path(pack) / 'msnart.shr'):
        if p.exists():
            d = p.read_bytes(); n, off = struct.unpack_from('<II', d, 4)
            return {d[off + i * 96:off + i * 96 + 80].split(b'\0')[0].decode().lower() for i in range(n)}
    return None


def scripted(m):
    out = []
    def walk(x):
        if isinstance(x, dict):
            if x.get('op') == 'SetPresentationBitmap': out.append(os.path.basename(str(x['args'][0]).replace('\\', '/')).lower())
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    walk(m); return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--scratch', required=True); ap.add_argument('--pack'); a = ap.parse_args()
    bi = builtin(); disc = {p.name.lower() for p in (GAME / 'art/frontend/dynaload/images').glob('*.p3d')}
    rows_out = []
    for lv in range(1, 8):
        d = json.load(open(Path(a.scratch) / f'level0{lv}.json'))
        li = (GAME / f'scripts/missions/level0{lv}/leveli.mfk').read_text(errors='replace')
        giver = {}
        for mt in re.finditer(r'AddNPCCharacterBonusMission\s*\(\s*"([^"]*)"\s*,[^;]*?"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"', li):
            giver[mt.group(4).lower()] = mt.group(1).lower()
        rows = msnart_rows(a.pack, lv) if a.pack else None
        for m in d['missions']:
            code = m['id'].lower(); sc = scripted(m); npc = giver.get(code)
            bi_path = bi.get(npc) if npc else None
            kind = 'гонка' if m['flags'] & 2 else 'ставка' if m['flags'] & 4 else 'бонус' if m['flags'] & 8 else 'сюжет'
            if m['flags'] & 256: kind = 'переход'
            if sc: img, why = sc[0], 'скрипт SetPresentationBitmap'
            elif bi_path: img, why = os.path.basename(bi_path), f'таблица exe b_{npc}'
            else: img, why = None, ('нет в скрипте и нет NPC-заказчика в таблице exe' + (f' (NPC {npc})' if npc else ''))
            ondisc = img in disc if img else None
            inpack = None if (rows is None or not img) else any(r.endswith('/' + img) for r in rows)
            rows_out.append((lv, code, kind, m['title'][:28], img, why, ondisc, inpack))
    print('L  миссия  вид     название                      картинка       откуда                          диск  пакет')
    for lv, code, kind, title, img, why, od, ip in rows_out:
        print(f'{lv}  {code:6} {kind:7} {title:29} {str(img or "-"):14} {why[:44]:44} {"да" if od else "-" if od is None else "НЕТ":4} {"да" if ip else "-" if ip is None else "НЕТ"}')
    miss = [r for r in rows_out if r[4] is None]; bad = [r for r in rows_out if r[4] and (r[6] is False or r[7] is False)]
    print(f'\nвсего {len(rows_out)}; без картинки {len(miss)}; картинка названа, но нет на диске/в пакете {len(bad)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
