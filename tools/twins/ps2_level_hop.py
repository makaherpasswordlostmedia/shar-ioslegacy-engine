#!/usr/bin/env python3
"""Клон ISO, где уровни 1..K-1 заканчиваются сами через 2 с после старта (SetLevelOver в таймере первого этапа первой миссии).
Так игра без прохождения приходит на старт уровня K (K = 2..7); оригинал game/Hit and Run.iso не трогается (cp -c, правится клон).
python3 -I tools/twins/ps2_level_hop.py K   → build/ps2stend3/iso/hop_to_L<K>.iso (путь печатается)"""
import re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ps2_car_swap as S

OUT = Path(__file__).resolve().parents[2] / 'build/ps2stend3/iso'
# первая миссия каждого уровня (по scripts/missions/levelNN/*i.mfk)
FIRST = {1: 'm0sdi', 2: 'm1sdi', 3: 'm1sdi', 4: 'm1sdi', 5: 'm1sdi', 6: 'm1sdi', 7: 'm1sdi'}
import os
HOP = 'AddObjective("timer");\n\tSetDurationTime(' + os.environ.get('HOP_DUR', '2') + ');\n\tSetLevelOver();\n\tCloseObjective();\n'

def hop_text(src):
    m = re.search(r'^[ \t]*AddStage\([^)]*\);[^\n]*\n(.*?)^[ \t]*CloseStage\(\);', src, re.S | re.M)
    assert m, 'нет первого этапа'
    return src[:m.start(1)] + '\t' + HOP + src[m.end(1):]

def hop_keep(src):
    """первый этап остаётся как есть (облёт камеры и туториал живут от его цели), рядом добавлен таймер; всё после этапа отрезано"""
    m = re.search(r'^[ \t]*AddStage\([^)]*\);[^\n]*\n(.*?)^([ \t]*)CloseStage\(\);', src, re.S | re.M)
    assert m, 'нет первого этапа'
    return src[:m.start(2)] + '\t' + HOP + src[m.start(2):m.end()] + '\n'

KEEP = set(int(x) for x in (__import__('os').environ.get('HOP_KEEP', '').split(',') if __import__('os').environ.get('HOP_KEEP') else []))

NOCAM = set(int(x) for x in os.environ.get('HOP_NOCAM', '').split(',') if x)

def nocam(src):
    """убрать строки облёта камеры старта миссии (SetMissionStartCamera*/SetAnimated*Camera*/Multicont)"""
    return '\n'.join(('//' + l if re.match(r'\s*Set(MissionStart|Animated|AnimCam)\w*\(', l) else l) for l in src.split('\n'))

M8 = set(int(x) for x in os.environ.get('HOP_M8', '').split(',') if x)   # уровень: финальная миссия ставится первой в level.mfk (её родной SetLevelOver)

def swap_last_first(src, last):
    a, b = 'AddMission("m1");', f'AddMission("{last}");'
    assert a in src and b in src
    return src.replace(a, '@@A@@').replace(b, a).replace('@@A@@', b)

FMV = set(int(x) for x in os.environ.get('HOP_FMV', '').split(',') if x)   # уровни, где подмена повторяет родной конец уровня: ролик, затем таймер

MOVIE = {2: 'fmv3.rmv', 3: 'fmv4.rmv', 4: 'fmv3.rmv', 5: 'fmv3.rmv', 6: 'fmv3.rmv'}
HIDE = {2: 'bart', 3: 'lisa', 4: 'marge', 5: 'apu', 6: 'bart'}

def hop_fmv(src, movie, hide):
    """этап 0 заменяется двумя этапами как в m8l.mfk: ролик конца уровня и таймер с SetLevelOver"""
    m = re.search(r'^[ \t]*AddStage\([^)]*\);[^\n]*\n(.*?)^[ \t]*CloseStage\(\);', src, re.S | re.M)
    assert m
    body = ('\tSetCharacterToHide("%s");\n\tAddObjective("fmv");\n\t\tSetFMVInfo("%s");\n\tCloseObjective();\nCloseStage();\n\n'
            'AddStage(2);\n\tAddObjective("timer");\n\t\tSetDurationTime(2);\n\t\tSetLevelOver();\n\tCloseObjective();\n' % (hide, movie))
    return src[:m.start(1)] + body + src[m.end(1):]

def main(k):
    assert 2 <= k <= 7
    OUT.mkdir(parents=True, exist_ok=True); dst = OUT / f'hop_to_L{k}.iso'
    if dst.exists(): dst.unlink()
    subprocess.run(['cp', '-c', str(S.SRC), str(dst)], check=True)
    f = open(dst, 'r+b')
    for n in range(1, k):
        if n in M8:
            rel = f'scripts/missions/level0{n}/level.mfk'; d = (S.GAME / rel).read_bytes().decode('latin-1')
            S.patch(f, rel, swap_last_first(d, os.environ.get('HOP_LAST', 'm8')).encode('latin-1')); continue
        rel = f'scripts/missions/level0{n}/{FIRST[n]}.mfk'
        d = (S.GAME / rel).read_bytes().decode('latin-1')
        new = (hop_fmv(d, MOVIE[n], HIDE[n]) if n in FMV else hop_keep(d) if n in KEEP else hop_text(nocam(d) if n in NOCAM else d)).encode('latin-1'); old = d.encode('latin-1')
        S.patch(f, rel, new + b' ' * (len(old) - len(new)))   # размер файла не меняется: снимки совместимы с любым клоном
    f.close(); print(dst)

if __name__ == '__main__': main(int(sys.argv[1]))
