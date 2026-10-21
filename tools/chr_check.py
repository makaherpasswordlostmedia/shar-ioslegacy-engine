#!/usr/bin/env python3
"""Гейт правки 143(а): пакеты персонажей миссий (viewer/msn_view.c npcFiles) после char_export.py --npc.

Для КАЖДОГО файла из npcFiles:
  (1) каждый клип, который может запросить движок, находится так же, как его ищет skinFindClip (viewer/skin.c: точное имя
      или '<префикс>_' + имя): loco_idle_rest / loco_walk — строки skinFindClip из msn_view.c, жесты — AddAmbientNpcAnimation
      скриптов диска всех уровней (список выводит char_export.npc_clip_names, руками не вписан);
  (2) размер пакета <= 200 КБ (до правки bart/lisa/marge/apu весили 392–429 КБ).
Печатает размеры и итог; код выхода 1 при любом FAIL.

  python3 tools/chr_check.py                 # build/chars
  python3 tools/chr_check.py --root DIR      # DIR/chars (красный контроль tests/chr/run.sh)
"""
import argparse, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import char_export as ce   # noqa: E402

LIMIT = 200 * 1024


def npc_files():
    return re.findall(r'"(chars/[a-z0-9_]+\.chr)"', (ROOT / 'viewer/msn_view.c').read_text(encoding='utf-8'))


def disc_clips(pack):
    """Правка 240: клипы файла анимаций, из которого собран пакет (tools/ship_rules.txt: --anims, иначе <имя>_a.p3d, как
    char_export.py). Свои риги marge/lisa/apu/bart: flail и get_up есть, fall_land нет (art/chars/*.cho) — его отсутствие в пакете
    не ошибка экспорта; потерянный при экспорте клип, который на диске есть, — по-прежнему FAIL"""
    anims = f'art/chars/{Path(pack).stem}_a.p3d'
    for line in (ROOT / 'tools/ship_rules.txt').read_text(encoding='utf-8').splitlines():
        if line.split('|')[0].strip() == pack and '--anims' in line: anims = line.split('--anims')[1].split()[0]
    p = ce.GAME / anims
    if not p.exists(): return []
    return [ce.string(c.data, 4)[0] for c in ce.read(p).children if c.id == 0x121000]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default=str(ROOT / 'build')); a = ap.parse_args()
    want = ce.npc_clip_names()
    if not {'loco_idle_rest', 'loco_walk'} <= set(want) or not any(w.startswith('dialogue_') for w in want):
        print(f'FAIL список клипов не выведен: {want}'); return 1
    files = npc_files(); bad = 0; total = 0
    print(f'клипов нужно: {len(want)} {want}; файлов npcFiles: {len(files)}')
    for f in files:
        p = Path(a.root) / f
        if not p.exists(): print(f'FAIL {f}: нет файла'); bad += 1; continue
        size = p.stat().st_size; total += size
        names = [c['name'] for c in ce.read_chr(p)['clips']]
        miss = [w for w in want if not any(ce.clip_matches(n, w) for n in names)]
        absent = [w for w in miss if not any(ce.clip_matches(n, w) for n in disc_clips(f))]   # правка 240: нет и в риге на диске
        miss = [w for w in miss if w not in absent]
        if absent: print(f'  нет на диске (файл анимаций рига) {absent} для {f} — не потеря экспорта (движок обходится)')
        if miss: print(f'FAIL {f}: нет клипов {miss}'); bad += 1
        if size > LIMIT: print(f'FAIL {f}: {size} Б > {LIMIT}'); bad += 1
        print(f'  {f:22s} {size:8d} Б  клипов {len(names)}')
    print(f'RESULT {"PASS" if not bad else "FAIL"} файлов {len(files)}, всего {total} Б, ошибок {bad}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
