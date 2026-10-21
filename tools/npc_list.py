#!/usr/bin/env python3
"""Персонажи миссий уровня из его скриптов -> строки правил tools/ship_rules.txt (chars/<имя>.chr) и проверка файлов диска.

Кто: AddNPC / AddAmbientCharacter / AddNPCCharacterBonusMission / AddBonusMissionNPCWaypoint / AddPurchaseCarReward
в scripts/missions/levelNN/*.mfk (только то, что грузит уровень: level.mfk, leveli.mfk, mX*.mfk, бонусы). Модель —
art/chars/<имя[:6]>_m.p3d (имена файлов персонажей на диске — первые 6 букв, как у пешеходов tools/traffic_export.py),
клипы — свои art/chars/<имя[:6]>_a.p3d, если есть (Гомер, Мардж, Апу, Лиза, Барт), иначе риг из аргумента скрипта
(AddNPCCharacterBonusMission / AddPurchaseCarReward: у всех персонажей уровня 1 — "npd"); у AddNPC/AddAmbientCharacter
рига в аргументах нет — берём тот же, что у персонажей уровня в данных (npd; правило порта — сверить с эталоном PS2).
Скелеты всех персонажей уровня 1 и риги npd/ndr/nps совпадают по именам суставов (33/36 из 33/36).

  python3 tools/npc_list.py [--level 1]            -> таблица: имя, модель, клипы, откуда
  python3 tools/npc_list.py --rules                -> строки для tools/ship_rules.txt
  python3 tools/npc_list.py --c                    -> список путей для viewer/msn_view.c npcFiles
"""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/missions'))
import mfk   # noqa: E402
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read, walk   # noqa: E402  (MIT)


def native_skin(path):
    """модель читается tools/char_export.py: есть кожа 0x10001 и у каждой её группы — родные PS2-полосы 0x10012
    или обычные списки Pure3D 0x10005… (louie_m.p3d, правка 180); у npd_m.p3d кожи нет — не рисуется, в отчёте)"""
    skins = [c for c in walk(read(path)) if c.id == 0x10001]
    pgs = [pg for s in skins for pg in s.children if pg.id == 0x10002]
    return bool(pgs) and all(any(k.id in (0x10012, 0x10005) for k in pg.children) for pg in pgs)   # правка 180: и обычные списки Pure3D (louie_m)

GAME = (ROOT / 'hit-and-run-web/source/game').resolve()
OPS = {'AddNPC': None, 'AddAmbientCharacter': None, 'AddNPCCharacterBonusMission': 1, 'AddBonusMissionNPCWaypoint': None,
       'AddPurchaseCarReward': 2}   # номер аргумента с ригом (None — нет)
OWN = ('homer', 'marge', 'apu', 'bart', 'lisa')


def npcs(level):
    out = {}
    for f in sorted((GAME / f'scripts/missions/level{level:02d}').glob('*.mfk')):
        n = f.name.lower()
        if n.startswith(('demo', 'e3', 'd1', 'leveli-d', 'level-d', 'ss')): continue   # не грузятся уровнем
        calls, _ = mfk.parse_file(f)
        for c in calls:
            if c.op not in OPS or not c.args: continue
            name = str(c.args[1] if c.op == 'AddPurchaseCarReward' else c.args[0]).lower()
            rig = str(c.args[OPS[c.op]]).lower() if OPS[c.op] is not None and len(c.args) > OPS[c.op] else None
            d = out.setdefault(name, dict(rigs=set(), ops=set()))
            if rig: d['rigs'].add(rig)
            d['ops'].add(c.op)
    rigs = {r for d in out.values() for r in d['rigs']}
    level_rig = rigs.pop() if len(rigs) == 1 else 'npd'
    rows = []
    for name, d in sorted(out.items()):
        stem = name[:6]
        model = f'art/chars/{stem}_m.p3d'
        own = f'art/chars/{stem}_a.p3d'
        anims = own if (GAME / own).exists() else f'art/chars/{(sorted(d["rigs"])[0] if d["rigs"] else level_rig)}_a.p3d'
        ok = (GAME / model).exists() and native_skin(GAME / model)
        rows.append(dict(name=name, model=model, anims=anims, ok=ok, ops=sorted(d['ops']),
                         rig_from='свои клипы' if anims == own else ('скрипт' if d['rigs'] else f'риг уровня ({level_rig}), правило порта')))
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--level', type=int, default=1)
    ap.add_argument('--rules', action='store_true'); ap.add_argument('--c', action='store_true')
    a = ap.parse_args()
    rows = [r for r in npcs(a.level) if r['name'] != 'homer']
    if a.rules:
        for r in rows:
            if not r['ok']: continue
            out = f'chars/{r["name"]}.chr'
            print(f'{out:22s}| build/{out:22s}| tools/char_export.py | python tools/char_export.py --name {r["name"]} --model {r["model"]} --anims {r["anims"]} --npc --out {{out}}')
    elif a.c:
        print(', '.join(f'"chars/{r["name"]}.chr"' for r in rows if r['ok']))
    else:
        for r in rows:
            print(f'{r["name"]:10s} {"ok " if r["ok"] else "НЕТ"} {r["model"]:28s} {r["anims"]:26s} {r["rig_from"]:28s} {",".join(r["ops"])}')
