#!/usr/bin/env python3
"""
Проверка серий снимков тура: в каждой серии из 12 снимков должно быть движение.
Никаких двух одинаковых кадров по MD5 в серии быть не должно.
"""
import sys
import os
import glob
import hashlib
from pathlib import Path

SERIES = [
    ("b538_b0", "b538_b0_*.bmp"),
    ("b538_b3fff", "b538_b3fff_*.bmp"),
    ("b538_b1000", "b538_b1000_*.bmp"),
    ("b538_b2000", "b538_b2000_*.bmp"),
    ("b538_aes_b0", "b538_aes_b0_*.bmp"),
    ("b538_aes_b3fff", "b538_aes_b3fff_*.bmp"),
    ("b538_aes_b1000", "b538_aes_b1000_*.bmp"),
    ("b538_aes_b2000", "b538_aes_b2000_*.bmp"),
    ("gb1_10", "gb1_10_[0-9][0-9].*"),
    ("gb1_15", "gb1_15_[0-9][0-9].*"),
    ("gb1_20", "gb1_20_[0-9][0-9].*"),
    ("l1_aes_light", "l1_aes_light_*.bmp"),
    ("l1_street_light", "l1_street_light_*.bmp"),
    ("l7_lamp_light", "l7_lamp_light_*.bmp"),
]

def check_dir(shots_dir, require_all=False):
    d = Path(shots_dir)
    if not d.is_dir():
        print(f"FAIL: директория не найдена: {shots_dir}")
        return False

    fails = 0
    checked = 0

    for name, pattern in SERIES:
        # Check both .bmp and .png
        files = sorted(d.glob(pattern))
        if not files and pattern.endswith(".bmp"):
            files = sorted(d.glob(pattern.replace(".bmp", ".png")))

        if not files:
            if require_all:
                print(f"FAIL: серия {name} отсутствует")
                fails += 1
            continue

        checked += 1
        hashes = [hashlib.md5(f.read_bytes()).hexdigest() for f in files]
        unique_hashes = set(hashes)

        # Проверяем, есть ли дубликаты
        if len(unique_hashes) < len(hashes):
            dups = len(hashes) - len(unique_hashes)
            print(f"FAIL: серия {name} ({len(files)} кадров) замёрзла: {len(unique_hashes)} уникальных хешей ({dups} дублей)")
            fails += 1
        else:
            print(f"OK: серия {name} ({len(files)} кадров) — все {len(unique_hashes)} кадров уникальны")

    if checked == 0:
        print("FAIL: ни одной серии снимков не найдено")
        return False

    print(f"\nИтог: проверено {checked} серий, ошибок: {fails}")
    return fails == 0

def check_scenario_syntax(scn_file):
    txt = Path(scn_file).read_text(encoding="utf-8")
    required_scenes = [
        "B538_b0", "B538_b3fff", "B538_b1000", "B538_b2000",
        "B538_aes_b0", "B538_aes_b3fff", "B538_aes_b1000", "B538_aes_b2000",
        "L1_light_aes", "L1_light_street", "L1_gb", "L7_light_lamps"
    ]
    missing = [s for s in required_scenes if f"scene {s}" not in txt]
    if missing:
        print(f"FAIL: в сценарии отсутствуют сцены: {missing}")
        return False

    # Проверяем наличие команд движения перед сериями
    for s in ["B538_b0", "B538_aes_b0", "L1_light_aes", "L1_light_street", "L1_gb", "L7_light_lamps"]:
        idx = txt.find(f"scene {s}")
        chunk = txt[idx:idx+400]
        if "autostraight" not in chunk and "wpgo" not in chunk:
            print(f"FAIL: в сцене {s} нет команды движения (autostraight / wpgo)")
            return False

    print("OK: сценарий содержит все требуемые сцены света и движения")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: check_shots.py <каталог_снимков | файл_сценария> [--require-all]")
        sys.exit(1)

    target = sys.argv[1]
    req_all = "--require-all" in sys.argv

    if os.path.isfile(target):
        ok = check_scenario_syntax(target)
    else:
        ok = check_dir(target, require_all=req_all)

    sys.exit(0 if ok else 1)
