#!/usr/bin/env python3
"""Набор замены TEST17 для апки SHARTEST15 на карте: только файлы, которые отличаются от лежащих на карте (cmp; карту только читаем).
  tools/test17_set.py CARD_APP UI_BASE UI_OVERRIDE EBOOT SCENARIO OUT
CARD_APP — /Volumes/PSP/PSP/GAME/SHARTEST15; UI_BASE — ui-pkg-601 (все паки интерфейса), UI_OVERRIDE — ui-pkg-598 (ui.shr и l2..l7/ui.shr перекрывают); SCENARIO — новый scenario.txt или -"""
import sys, shutil, hashlib
from pathlib import Path
card, base, over, eboot, scn, out = map(Path, sys.argv[1:7])
files = {}
for root in (base, over):
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix == ".shr" and "logs" not in p.parts: files[str(p.relative_to(root))] = p
files["EBOOT.PBP"] = eboot
if str(scn) != "-": files["scenario.txt"] = scn
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:8]
if out.exists(): shutil.rmtree(out)
dst = out / "PSP/GAME/SHARTEST15"; dst.mkdir(parents=True)
rows = []; same = 0
for n, src in sorted(files.items()):
    c = card / n
    if c.exists() and c.stat().st_size == src.stat().st_size and c.read_bytes() == src.read_bytes(): same += 1; continue
    (dst / n).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst / n)
    rows.append((n, src.stat().st_size, sha(src), sha(c) if c.exists() else "нет на карте"))
with open(out / "ЗАМЕНА.txt", "w") as f:
    f.write(f"ЗАМЕНА TEST19 → /Volumes/PSP/PSP/GAME/SHARTEST15 · только отличающиеся от карты файлы ({len(rows)}, без изменений {same}); карта только читалась\n\nФайл | размер | sha256(8) нового | sha256(8) на карте\n")
    for r in rows: f.write(" | ".join(map(str, r)) + "\n")
print(f"к замене {len(rows)}, без изменений {same}, {sum(r[1] for r in rows)/1e6:.1f} МБ")
