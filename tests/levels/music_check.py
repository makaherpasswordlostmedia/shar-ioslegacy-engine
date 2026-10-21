#!/usr/bin/env python3
"""Музыка уровня из композиции l<N>_music.rms (tools/sound_export.py music_table, 29.09) против эталона уровня 1.

До 29.09 таблица музыки была вписана руками только для уровня 1 (MUSIC = {1: [...]} ниже — она же, дословно из git 0a7e51b):
уровни 2–7 брали музыку уровня 1. Теперь таблица выводится по правилам из композиции уровня; на уровне 1 правила обязаны
дать ту же таблицу до строки (иначе music.sap уровня 1 изменится). Для 2–7 — печать таблицы и проверка, что файлы есть.
  music_check.py            зелёный: уровень 1 = эталон, 2–7 — роли езды и Hit & Run найдены, файлы на диске
  music_check.py --plant    красный: композиция уровня 1 с переименованным регионом Sunday_Drive_region -> провал
С 29.09 езда берётся из разобранной композиции (tools/rms.py: регион Sunday_Drive_region, вступление + повтор, выбор
logic_or — по кругу) и сверяется с ней на всех уровнях: файлы ролей езды = потоки региона по порядку.
  music_check.py --plant-strings   красный: прежнее правило «строки между Level_Intro и Sunday_Drive_region» (у уровня 5
                                   петлёй шло вступление уровня 1 sunday_drive_intro) -> провал сверки езды"""
import sys, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import sound_export as SE   # noqa: E402
import rms                  # noqa: E402

REF_L1 = [
    ('sunday_drive_intro', 'sunday_drive_intro', False, 'sunday_drive'),
    ('sunday_drive', 'sunday_drive', True, None),
    ('sunday_drive_end_sus1', 'sunday_drive_end_sus1', False, None),
    ('sunday_drive_end_sus2', 'sunday_drive_end_sus2', False, None),
    ('sunday_drive_end_sus3', 'sunday_drive_end_sus3', False, None),
    ('collection02_pickup', 'collection02_pickup', False, 'collection02_main'),
    ('collection02_main', 'collection02_main', True, None),
    ('collection02_end_pos', 'collection02_end_pos_b1_3', False, None),
    ('collection02_end_neg', 'collection02_end_neg_b4', False, None),
    ('collection02_end_sus1', 'collection02_end_sus1_b4', False, None),
    ('collection02_end_sus2', 'collection02_end_sus2_b4', False, None),
    ('kwik_e_mart_muzak', 'apu/kwik_e_mart_muzak', True, None),
    ('muzak', 'muzak', True, None),
    ('hit_run_intro', 'hit_run_intro', False, 'hit_run_main'),
    ('hit_run_main', 'hit_run_main', True, None),
    ('hit_run_end_neg', 'hit_run_end_neg', False, None),
    ('harp_music04', 'harp_music04', False, None),
    ('harp_music05', 'harp_music05', False, None),
    ('horn_triumph', 'horn_triumph', False, None),
    ('horn_blast', 'generic/horn_blast', False, None),
    ('tuba_001', 'homer/tuba_001', False, None),
    ('tuba_002', 'homer/tuba_002', False, None),
    ('tuba_003', 'homer/tuba_003', False, None),
    ('simpsons_theme', 'simpsons_theme', True, None),
    # 29.09 (правка 20): стингеры экрана загрузки и газеты — события Loading_screen / Newspaper_Spin композиции
    ('loading_screen', 'fe_trans01', False, None), ('loading_screen~1', 'fe_trans02', False, None),
    ('loading_screen~2', 'fe_trans03', False, None),
    ('newspaper_spin', 'newspaper_spin01', False, None), ('newspaper_spin~1', 'newspaper_spin02', False, None),
]
NEED = ('sunday_drive', 'hit_run_main', 'simpsons_theme')


def main():
    plant = '--plant' in sys.argv
    bad = []
    if plant:   # подменить композицию: регион езды переименован — блок езды не найден, таблица уровня 1 обязана разойтись
        orig = SE.composition
        def comp(lv):
            strs, files, decl, groups = orig(lv)
            return [s.replace('Sunday_Drive_region', 'Planted_region') for s in strs], files, decl, groups
        SE.composition = comp
        orig_name = rms.Comp.region_name
        rms.Comp.region_name = lambda self, ri: orig_name(self, ri).replace('Sunday_Drive_region', 'Planted_region')
    if '--plant-strings' in sys.argv:   # прежнее правило езды (до 29.09): строки между Level_Intro и Sunday_Drive_region
        def old_drive(lv):
            strs, files, decl, groups = SE.composition(lv)
            lo = strs.index('Level_Intro') if 'Level_Intro' in strs else -1
            hi = strs.index('Sunday_Drive_region') if 'Sunday_Drive_region' in strs else -1
            blk = [(st, k) for i, st, k in decl if lo < i < hi] if 0 <= lo < hi else []
            sus_re = re.compile(r'_end_sus\d*$', re.I)
            intro = next((k for st, k in blk if st.lower().endswith('_intro')), None)
            main = next((k for st, k in blk if not st.lower().endswith('_intro') and not sus_re.search(st)), None)
            if main is None: main, intro = intro, None
            return intro, [main] if main else []
        SE.drive_plan = old_drive
    t1 = SE.music_table(1)
    if t1 != REF_L1:
        diff = [f'{a} != {b}' for a, b in zip(t1, REF_L1) if a != b] + ([f'строк {len(t1)} != {len(REF_L1)}'] if len(t1) != len(REF_L1) else [])
        bad.append('уровень 1 не равен эталону: ' + '; '.join(diff[:4]))
    else: print('уровень 1: таблица = эталон (%d дорожек)' % len(REF_L1))
    for lv in range(2, 8):
        t = SE.music_table(lv); roles = {n: f for n, f, _, _ in t}
        miss = [r for r in NEED if r not in roles]
        nofile = [f for _, f, _, _ in t if not (SE.SND / 'music' / (f + '.rsd')).exists()]
        print(f'уровень {lv}: {len(t)} дорожек; езда {roles.get("sunday_drive_intro")} -> {roles.get("sunday_drive")}, '
              f'выход {[roles.get(f"sunday_drive_end_sus{k}") for k in (1, 2, 3) if roles.get(f"sunday_drive_end_sus{k}")]}, '
              f'миссия {roles.get("collection02_main")}, магазин {roles.get("kwik_e_mart_muzak")}')
        if miss: bad.append(f'уровень {lv}: нет ролей {miss}')
        # езда = регион Sunday_Drive_region разобранной композиции: вступление и потоки повтора по порядку
        C = rms.read(SE.SND / 'music' / f'l{lv}_music.rms'); ri = C.region_index('Sunday_Drive_region')
        if ri is None: bad.append(f'уровень {lv}: в композиции нет региона Sunday_Drive_region'); continue
        want = [C.stream_file(s)[1].replace('\\', '/').lower() for _, alts in C.region_plan(ri) for s in alts]
        got = [f for n, f, _, _ in t if n == 'sunday_drive_intro' or n == 'sunday_drive' or n.startswith('sunday_drive~')]
        if got != want: bad.append(f'уровень {lv}: езда {got} != регион композиции {want}')
        if nofile: bad.append(f'уровень {lv}: нет файлов {nofile}')
    for b in bad: print('  ПРОВАЛ:', b)
    print('PASS' if not bad else f'FAIL ({len(bad)})')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
