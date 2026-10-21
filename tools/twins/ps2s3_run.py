#!/usr/bin/env python3
"""Стенд 3: рецепт orig2 на любом клоне ISO, со своим близнецом pcsx2_s3 и своей папкой o4_s3.
python3 -I tools/twins/ps2s3_run.py ПУТЬ_К_ISO РЕЦЕПТ.json → build/twins/o4_s3/<id>/"""
import sys, os
from pathlib import Path
os.environ.setdefault('PCSX2_DIR', 'build/twins/pcsx2_s3'); os.environ.setdefault('O4_DIR', 'o4_s3')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orig2
iso = Path(sys.argv[1]).resolve(); assert iso.exists(), iso
orig2.ISO = iso
orig2.run(sys.argv[2])
