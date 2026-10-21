#!/usr/bin/env python3
"""Compatibility entry: only retained same-frame logs can establish image equivalence.
Time-separated legacy RFAST screenshots fail this check instead of claiming PASS.
"""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name('frozen.py')), run_name='__main__')
