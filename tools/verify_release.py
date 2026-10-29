#!/usr/bin/env python3
"""Сверка двух наборов выпуска SHARVIEW (папки с PSP/GAME/SHARVIEW/...): каждый файл по SHA-256; EBOOT — после обнуления даты и времени сборки (__DATE__/__TIME__ вшиты в строку «EBOOT Oct 15 2026 18:54:33»).
  tools/verify_release.py SET_A SET_B     код выхода 0 — все файлы совпали (EBOOT с поправкой на время сборки)"""
import sys, re, hashlib
from pathlib import Path
a, b = Path(sys.argv[1]) / "PSP/GAME/SHARVIEW", Path(sys.argv[2]) / "PSP/GAME/SHARVIEW"
norm = lambda d: re.sub(rb"\d\d:\d\d:\d\d", b"00:00:00", re.sub(rb"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) [ 0-9]\d \d{4}", b"Xxx 00 0000", d))
sha = lambda d: hashlib.sha256(d).hexdigest()[:8]
fa = {str(p.relative_to(a)) for p in a.rglob("*") if p.is_file()}; fb = {str(p.relative_to(b)) for p in b.rglob("*") if p.is_file()}
bad = []; ok = 0
for n in sorted(fa | fb):
    if n not in fa or n not in fb: bad.append((n, "только в " + ("B" if n in fb else "A"))); continue
    da, db = (a / n).read_bytes(), (b / n).read_bytes()
    if n == "EBOOT.PBP": da, db = norm(da), norm(db)
    if da == db: ok += 1
    else: bad.append((n, f"A {sha(da)} B {sha(db)}"))
print(f"файлов A {len(fa)}, B {len(fb)}, совпало {ok}, различий {len(bad)}")
for n, why in bad: print("  РАЗНИЦА:", n, why)
sys.exit(1 if bad else 0)
