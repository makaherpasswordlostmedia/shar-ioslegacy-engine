#!/usr/bin/env python3
"""Набор выпуска SHARVIEW: игровой EBOOT + данные v4 интерфейса поверх пакета 1721; таблица «файл · размер · SHA · ЗАМЕНИТЬ/совпадает».
  tools/release_set.py PKG1721 UI601 UI598 EBOOT OUT   (карту PSP не трогает; пакет 1721 побайтно = карта)"""
import sys, os, shutil, hashlib, subprocess
from pathlib import Path
pkg, u601, u598, eboot, out = map(Path, sys.argv[1:6]); lv = Path(sys.argv[6]) if len(sys.argv) > 6 else None   # lv — папка с перевыпущенными level.shr (lN/level.shr, l1 → level.shr)
names = [l.split("|")[0] for l in subprocess.run(["bash", "tools/ship_files.sh", "--pairs"], capture_output=True, text=True, env=dict(os.environ, SHIP_LEVELS="2 3 4 5 6 7")).stdout.split("\n") if "|" in l]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()[:8]
dst = out / "PSP/GAME/SHARVIEW"
for p in dst.rglob("*") if dst.exists() else []: pass
tmp = out / "PSP/GAME/SHARVIEW"; rows = []; repl = 0; same = 0; missing = []
for n in ["EBOOT.PBP"] + names:
    b = pkg / n
    if n == "EBOOT.PBP": new = eboot
    else:
        new = None
        if lv is not None and n.endswith("level.shr"):
            k = "1" if n == "level.shr" else n.split("/")[0][1:]
            if (lv / f"l{k}/level.shr").exists(): new = lv / f"l{k}/level.shr"
        for u in ((u598, u601) if new is None else ()):
            if (u / n).exists() and n.endswith(".shr") and Path(n).name in ("ui.shr", "fsave.shr", "load.shr", "menu.shr", "pextra.shr", "phone.shr", "pmenu.shr", "psave.shr", "shop.shr", "boot.shr"): new = u / n; break
        if new is None: new = b
    if not b.exists() or not Path(new).exists(): missing.append(n); continue
    same_ = Path(new).read_bytes() == b.read_bytes()
    if same_: same += 1; rows.append((n, Path(new).stat().st_size, sha(new), "совпадает с 1721/картой"))
    else:
        repl += 1; (tmp / n).parent.mkdir(parents=True, exist_ok=True); shutil.copy2(new, tmp / n)
        rows.append((n, Path(new).stat().st_size, sha(new), f"ЗАМЕНИТЬ (на карте {sha(b)})"))
with open(out / "ЗАМЕНА.txt", "w") as f:
    f.write(f"НАБОР ВЫПУСКА SHARVIEW · игровой EBOOT (без оверлея, подпись и значок как у 1721) + интерфейс v4 · против пакета 1721 (= карта)\nЗАМЕНИТЬ: {repl} файлов, совпадает: {same}, не найдено: {len(missing)}\n\nФайл | размер | sha256(8) нового | статус\n")
    for r in sorted(rows, key=lambda r: (not r[3].startswith("ЗАМЕНИТЬ"), r[0])): f.write(" | ".join(map(str, r)) + "\n")
    if missing: f.write("\nНе найдено: " + ", ".join(missing) + "\n")
print(f"ЗАМЕНИТЬ {repl}, совпадает {same}, не найдено {len(missing)}, {sum(r[1] for r in rows if r[3].startswith('ЗАМЕНИТЬ'))/1e6:.1f} МБ")
