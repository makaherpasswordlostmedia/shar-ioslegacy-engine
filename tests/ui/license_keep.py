"""Правка Роба 271 (04.10): на экране BootupLoad (LOADING после заставки прав Fox) текст лицензии остаётся, «чтобы почитать».
Макет экспортёра build/ui/load_bootload_0.png: в полосе текста лицензии (y 85..205) должны быть голубые буквы.
КРАСНЫЙ: UI_LIC_COVER=1 (прежнее — закрышка LicenseTextCover) обязан упасть. python3 tests/ui/license_keep.py -> 0 = PASS"""
import os, subprocess, sys
from pathlib import Path
from PIL import Image
ROOT = Path(__file__).resolve().parents[2]; PY = str(ROOT / '.venv/bin/python')

def cyan(env_extra):
    env = dict(os.environ, **env_extra)
    subprocess.run([PY, 'tools/load_export.py', 'mock'], cwd=ROOT, env=env, check=True, capture_output=True)
    im = Image.open(ROOT / 'build/ui/load_bootload_0.png').convert('RGB')
    return sum(1 for y in range(85, 205) for x in range(60, 420) if (lambda p: p[2] > 150 and p[1] > 150 and p[0] < 120)(im.getpixel((x, y))))

red = cyan({'UI_LIC_COVER': '1'}); green = cyan({})
print(f'красный UI_LIC_COVER=1: голубых {red}; зелёный: голубых {green}')
ok = red < 50 and green > 1500
print('PASS: текст лицензии остаётся под LOADING, красный пойман' if ok else 'FAIL'); sys.exit(0 if ok else 1)
