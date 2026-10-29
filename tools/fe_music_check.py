#!/usr/bin/env python3
"""Правка Роба 134: музыка входа в игру (меню -> газета) по данным композиции l1_music.rms (tools/rms.py).

  python3 tools/fe_music_check.py SMOKE.txt [--rms путь] [--main viewer/main.c]

Данные: событие FE -> регион FE_region (Simpsons_Theme), Loading_screen -> FE_trans01, Newspaper_Spin -> FE_trans02;
переходы fade_transitions — только FE_region -> FE_trans01/02 (затухание source_time мс, доли beat_set). Значит, за темой
меню идёт ровно ОДИН стингер. Проверки по журналу смоука (строки FEMUS, FESTING, FESTCUT, LOADSHOW):
  · каждый переход музыки от FEMUS (тема меню) до LOADSHOW — пара (регион -> регион) из fade_transitions;
  · не больше одного стингера на вход в игру, хотя бы один Newspaper_Spin (если режим не «тема под газетой»);
  · нет FESTCUT (стингер, оборванный другим раньше конца);
  · fade= в строке FESTING равен source_time перехода; wait_ms= не длиннее одной доли темы;
  · константы FE_THEME_BPM / FE_THEME_FADE_S в viewer/main.c совпадают с tempo_track Simpsons_Theme и source_time.
Код выхода 0 — зелёный, 1 — красный (причины построчно)."""
from pathlib import Path as _MainPath
import sys as _MainSys
_MainSys.path.insert(0, str(_MainPath(__file__).resolve().parents[1]/"tools"))
from main_source import read_main
import argparse, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import rms

ROOT = pathlib.Path(__file__).resolve().parent.parent
RMS = ROOT / 'hit-and-run-web/source/game/sound/music/l1_music.rms'


def kv(line):
    return dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)


def data(path):
    C = rms.read(str(path))
    P = C.pools
    def reg_of(addr):
        o = C.owner(addr); return C.region_name(o[1]) if o and o[0] == 'regions' else None
    trans = {}
    for t in P['fade_transitions']['els']:
        trans[(reg_of(t[0]), reg_of(t[1]))] = t[2] / 1000.0
    ev2reg = {}
    for name, acts in C.events():
        for kind, ri in acts:
            if kind == 'play_region' and ri is not None: ev2reg[name.lower()] = C.region_name(ri)
    st2reg = {}
    for ri in range(len(P['regions']['els'])):
        for alt in C.region_streams(ri):
            for si in alt: st2reg[C.stream_file(si)[0].lower()] = C.region_name(ri)
    bpm = {C.store[s[0]].lower(): s[4] for s in P['streams']['els']}
    return trans, ev2reg, st2reg, bpm


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('log'); ap.add_argument('--rms', default=str(RMS))
    ap.add_argument('--main', default=str(ROOT / 'viewer/main.c')); a = ap.parse_args()
    trans, ev2reg, st2reg, bpm = data(a.rms)
    errs = []
    src = read_main(pathlib.Path(a.main), errors='replace')
    m_bpm = re.search(r'#define FE_THEME_BPM ([\d.]+)f', src); m_fd = re.search(r'#define FE_THEME_FADE_S ([\d.]+)f', src)
    theme_bpm = bpm.get('simpsons_theme')
    if not m_bpm or abs(float(m_bpm.group(1)) - theme_bpm) > 0.01: errs.append(f'FE_THEME_BPM в коде {m_bpm and m_bpm.group(1)} != tempo_track Simpsons_Theme {theme_bpm}')
    fe_fade = trans.get(('FE_region', ev2reg.get('newspaper_spin')))
    if not m_fd or fe_fade is None or abs(float(m_fd.group(1)) - fe_fade) > 0.01: errs.append(f'FE_THEME_FADE_S в коде {m_fd and m_fd.group(1)} != source_time {fe_fade}')
    beat_ms = 60000.0 / theme_bpm
    lines = pathlib.Path(a.log).read_text(errors='replace').splitlines()
    runs, cur = [], None
    for l in lines:
        tag = l.split(' ', 1)[0]
        if tag == 'FEMUS': cur = dict(music=kv(l).get('music', '-'), st=[], cut=[])
        elif cur is not None and tag == 'FESTING': cur['st'].append(kv(l))
        elif cur is not None and tag == 'FESTCUT': cur['cut'].append(kv(l))
        elif cur is not None and tag == 'LOADSHOW': runs.append(cur); cur = None
    if not runs: errs.append('нет входа в игру из меню (FEMUS … LOADSHOW)')
    for i, r in enumerate(runs, 1):
        reg = st2reg.get(r['music'].lower()); path = [reg or r['music']]
        stings = [d for d in r['st'] if d.get('ev', '-') != '-']
        theme_kept = any(d.get('mode') == '1' for d in r['st'])
        for d in stings:
            dst = ev2reg.get(d['ev'].lower())
            if (reg, dst) not in trans: errs.append(f'вход {i}: переход {reg} -> {dst} ({d["ev"]}, {d.get("track")}) не из fade_transitions')
            elif 'fade' in d and abs(float(d['fade']) - trans[(reg, dst)]) > 0.01:
                errs.append(f'вход {i}: затухание {d["fade"]} с != source_time {trans[(reg, dst)]:.2f} с ({reg} -> {dst})')
            if 'wait_ms' in d and float(d['wait_ms']) > beat_ms + 40: errs.append(f'вход {i}: ожидание доли {d["wait_ms"]} мс > доли {beat_ms:.0f} мс')
            reg = dst; path.append(dst)
        if len(stings) > 1: errs.append(f'вход {i}: {len(stings)} стингера подряд (' + ', '.join(d['ev'] for d in stings) + ') — в данных за темой один')
        if not theme_kept and not any(d['ev'].lower() == 'newspaper_spin' for d in stings): errs.append(f'вход {i}: нет Newspaper_Spin при влёте газеты')
        for c in r['cut']: errs.append(f'вход {i}: FESTCUT — {c.get("cut")} оборван на {c.get("at")} из {c.get("len")} с ({c.get("by")})')
        print(f'вход {i}: ' + ' -> '.join(str(p) for p in path) + ('  [тема под газетой]' if theme_kept else ''))
    if errs:
        print('КРАСНЫЙ: ' + '; '.join(errs)); return 1
    print(f'ЗЕЛЁНЫЙ: {len(runs)} входов, переходы из fade_transitions, один стингер, доля {beat_ms:.0f} мс, без обрывов'); return 0


if __name__ == '__main__':
    sys.exit(main())
