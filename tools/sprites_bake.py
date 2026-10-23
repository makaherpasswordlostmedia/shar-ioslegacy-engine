#!/usr/bin/env python3
"""№880 (Роб 23.10: «наши спрайты — трубка над будкой, монета, гаечный ключ — чтобы тоже попадали в сборку»): спрайты из моделей диска игрока
одной командой. Сами ленты — данные игры (кадры её моделей), в git не кладутся: сборка печёт их из своего диска. Рецепты — те, что дали принятые
Робом файлы (проверено побайтно: ключ, трубка, блик; монета — до шума рендера Cycles, 0,8 из 255).

  python3 tools/sprites_bake.py wrench OUT.bin      ключ: tools/wrench/wrench_dump.py -> wrench_raster.py (32 кадра, 128 px, 4x4) -> coin_pack.py --page --soft
  python3 tools/sprites_bake.py phone MSNART OUT    трубка над будкой: msnart_sprite_dump.py phone_icon -> icon_bake.py anim:60 32 128 -> coin_pack.py (64 px)
  python3 tools/sprites_bake.py glow OUT.bin        блик под ключом: tools/wrglow_export.py
  python3 tools/sprites_bake.py coin LEVEL OUT      монета: coin_dump.py -> Blender (coin_blender.py, Cycles) -> coin_pack.py; готовые кадры build/coin_bake/frames3 —
                                                    берутся они (принятые Робом); нет ни кадров, ни Blender — пропуск (движок рисует 3D-монету)
Blender: $BLENDER, иначе /Applications/Blender.app, иначе blender из PATH."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(*a):
    r = subprocess.run([str(x) for x in a], cwd=ROOT)
    if r.returncode: sys.exit(f'ошибка: {" ".join(map(str, a))}')


def blender():
    for b in (os.environ.get('BLENDER'), '/Applications/Blender.app/Contents/MacOS/Blender', shutil.which('blender')):
        if b and Path(b).exists(): return b
    return None


def main():
    kind, args = sys.argv[1], sys.argv[2:]
    with tempfile.TemporaryDirectory(prefix='shar-spr-') as t:
        t = Path(t)
        if kind == 'wrench':
            out = args[0]
            run(PY, 'tools/wrench/wrench_dump.py', t / 'd'); run(PY, 'tools/wrench/wrench_raster.py', t / 'd', t / 'f', 32, 128, 4)
            run(PY, 'tools/coin/coin_pack.py', t / 'f', t / 'o', '--px', 128, '--page', '--soft', '--half', 1.4616, '--cy', 0, '--spin', 3.0900, '--bin', out)
        elif kind == 'phone':
            msnart, out = args
            run(PY, 'tools/wrench/msnart_sprite_dump.py', msnart, 'phone_icon', t / 'd'); run(PY, 'tools/wrench/icon_bake.py', t / 'd', t / 'f', 'anim:60', 32, 128)
            run(PY, 'tools/coin/coin_pack.py', t / 'f', t / 'o', '--half', 0.8643, '--cy', 0, '--spin', 3.1416, '--bin', out)
        elif kind == 'glow':
            run(PY, 'tools/wrglow_export.py', args[0])
        elif kind == 'coin':
            level, out = args
            frames = ROOT / 'build/coin_bake/frames3'
            if not (frames / 'f_00.png').exists():
                b = blender()
                if not b: print('НЕОБЯЗАТЕЛЬНО: пропуск — нет Blender (BLENDER=путь); без coinspr.bin монеты — 3D-моделью'); return
                run(PY, 'tools/coin/coin_dump.py', level, t / 'd')
                run(b, '-b', '--factory-startup', '-P', 'tools/coin/coin_blender.py', '--', t / 'd', t / 'f', 32, 128); frames = t / 'f'
            run(PY, 'tools/coin/coin_pack.py', frames, t / 'o', '--spin', 3.0, '--bin', out)
        else:
            sys.exit(__doc__)


if __name__ == '__main__':
    main()
