#!/usr/bin/env python3
"""Стенд: прогон рецепта orig2 на клоне ISO с другой машиной. python3 -I tools/twins/ps2s_run.py МАШИНА РЕЦЕПТ.json
Клон делает ps2_car_swap.py (build/ps2stend/iso/МАШИНА.iso). Результат: build/twins/o4/<id рецепта>/."""
import sys, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orig2
car, recipe = sys.argv[1], sys.argv[2]
iso = Path(__file__).resolve().parents[2] / f'build/ps2stend/iso/{car}.iso'
assert iso.exists(), iso
orig2.ISO = iso
orig2.run(recipe)
