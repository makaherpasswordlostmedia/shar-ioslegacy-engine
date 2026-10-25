#!/usr/bin/env python3
"""Ориентир дали виден (№928, L6, пирс C7-6): пикселей, отличающихся между «flag hzlm 1» и «flag hzlm 0» (кадры lm_on / lm_off). lmpx.py КАТАЛОГ_прогона  -> число"""
import sys, numpy as np
from PIL import Image
d = sys.argv[1]; a = np.array(Image.open(f'{d}/lm_on.png').convert('RGB')).astype(int); b = np.array(Image.open(f'{d}/lm_off.png').convert('RGB')).astype(int)
print(int((np.abs(a - b)[60:215].sum(-1) > 40).sum()))
