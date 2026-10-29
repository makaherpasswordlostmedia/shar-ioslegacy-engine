#!/usr/bin/env python3
"""Опись бонус-игры (мини-игра «Super Sprint», правка Роба 420) по диску PS2 — только чтение.
  python tools/bonus/inventory.py [--json build/bonus/inventory.json]
Что собирается (каждая строка — с диска, без догадок; выводы помечены «вывод»):
  * трассы art/b00..b07.p3d + b0Ndata.p3d: размер, локаторы по видам (старты, финиш/чекпойнты с номерами, точки пути ИИ WPR/WPL,
    камеры spycam, прыжки, ловушки, DEATH, огонь, прочие), камера sprint_camShape (угол кадра, положение, взгляд);
    b02l/b02m/b02s/b02st — те же камеры другого масштаба (вывод: заготовки); minigamecam (missions/generic и art/) — облёт;
  * машины соперников scripts/cars/bonus/bgT_K.con: TopSpeedKmh, GasScale, Mass;
  * экраны art/frontend/scrooby/minigame.p3d: страницы и строки (MiniMenu, MiniHud, MiniPause, MiniSummary);
  * звук: sound/scripts/minigame.spt (ресурсы), sound/music/minigame/*, sound/soundfx/minigame/*;
  * сценарии scripts/ss.mfk / ssi.mfk (что грузит мини-игра);
  * строки исполняемого файла SLES_518.97 в окне таблицы мини-игры (имена классов, пути, форматы)."""
import argparse, json, re, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/bonus')); sys.path.insert(0, str(ROOT / 'tools'))
import track as T   # noqa: E402

EV = {1: 'камера spycam', 2: 'чекпойнт/точка пути', 4: 'DEATH', 48: 'прыжок', 63: 'B04G (Event 63)', 65: 'огонь', 66: 'ловушка'}


def con_vals(p):
    t = p.read_text(errors='replace'); g = lambda k: float(re.search(rf'{k}\(\s*([-\d.]+)', t).group(1))
    return dict(top_kmh=g('SetTopSpeedKmh'), gas=g('SetGasScale'), mass=g('SetMass'))


def track_info(n):
    L = T.locators(n); cps = T.checkpoints(L); st = T.starts(L); cam = T.camera(n)
    kinds = {}
    for l in L:
        if l['type'] == 3: k = 'старт CarStart'
        elif l['type'] == 0 and l['data']: k = EV.get(l['data'][0], f"Event {l['data'][0]}")
        else: k = f"тип {l['type']}"
        if k == 'чекпойнт/точка пути': k = 'точка пути ИИ' if l['name'][:3] in ('WPR', 'WPL') else 'финиш/чекпойнт' if l['data'][1:2] and l['data'][1] > 0 else 'прочее Event 2'
        kinds.setdefault(k, []).append(l['name'])
    return dict(file=f'b0{n}.p3d', bytes=(T.ART / f'b0{n}.p3d').stat().st_size, data_bytes=(T.ART / f'b0{n}data.p3d').stat().st_size,
                locators={k: sorted(v) for k, v in kinds.items()},
                checkpoints=[dict(name=c['name'], order=c['data'][1], box=[round(x, 2) for x in c['trig'][0]['h']]) for c in cps],
                starts=[dict(name=s['name'], pos=[round(x, 2) for x in s['pos']], heading=round(s['heading'], 4)) for s in st],
                wpr=[w['name'] for w in T.waypoints(L, 'WPR')], wpl=[w['name'] for w in T.waypoints(L, 'WPL')],
                camera=dict(name=cam['name'], fov_rad=round(cam['fov'], 4), near=cam['near'], far=cam['far'],
                            pos=[round(x, 1) for x in cam['pos']], look=[round(x, 3) for x in cam['look']]) if cam else None,
                ai=[dict(con=f'bonus/bg{n}_{k}.con', **con_vals(T.ai_con(n, k))) for k in (1, 2, 3) if n >= 1 and T.ai_con(n, k).exists()])


def scrooby():
    import ui_export as U
    P = U.project('minigame.p3d'); out = {}
    def walk(nodes, acc):
        for x in nodes if isinstance(nodes, list) else [nodes]:
            if x['kind'] in ('layer', 'group'): walk(x['children'], acc)
            elif x['kind'] == 'text': acc.extend(s['text'] for s in x['strings'] if s['text'])
    for pg in ('MiniMenu.pag', 'MiniHud.pag', 'MiniPause.pag', 'MiniSummary.pag'):
        acc = []; walk(P.pages.get(pg, []), acc); out[pg] = sorted(set(acc))
    out['screens'] = P.screens
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json', default=str(ROOT / 'build/bonus/inventory.json'))
    a = ap.parse_args()
    G = T.GAME
    inv = dict(tracks={f'b0{n}': track_info(n) for n in range(8)},
               extra_tracks={f: (T.ART / f).stat().st_size for f in ('b02l.p3d', 'b02m.p3d', 'b02s.p3d', 'b02st.p3d')},
               menu_track_files={f'Track{i}': f'b0{n}' for i, n in enumerate(T.TRACKS)},
               scripts={f: (G / 'scripts' / f).read_text(errors='replace').splitlines() for f in ('ss.mfk', 'ssi.mfk')},
               sound=dict(spt=re.findall(r'create daSoundResourceData named (\w+)', (G / 'sound/scripts/minigame.spt').read_text(errors='replace')),
                          music=sorted(p.name for p in (G / 'sound/music/minigame').iterdir()),
                          sfx=sorted(p.name for p in (G / 'sound/soundfx/minigame').iterdir())),
               exe=[s for _, s in T.exe_strings()], exe_classes=[s for _, s in T.exe_strings(0x37dfe0, 0x37e060)])
    try: inv['scrooby'] = scrooby()
    except Exception as e: inv['scrooby'] = dict(error=str(e))
    Path(a.json).parent.mkdir(parents=True, exist_ok=True); Path(a.json).write_text(json.dumps(inv, ensure_ascii=False, indent=1))
    for k, t in inv['tracks'].items():
        cam = t['camera']
        print(f"{k}: {t['bytes'] // 1024} КБ + data {t['data_bytes']} Б | чекпойнтов {len(t['checkpoints'])} | WPR {len(t['wpr'])} WPL {len(t['wpl'])} | "
              + ', '.join(f'{kk} {len(v)}' for kk, v in t['locators'].items() if kk not in ('финиш/чекпойнт', 'точка пути ИИ'))
              + (f" | камера {cam['name']} fov {cam['fov_rad']} рад" if cam else '')
              + (' | ИИ ' + ', '.join(f"{x['con'].split('/')[-1]} {x['top_kmh']:.0f} км/ч" for x in t['ai']) if t['ai'] else ''))
    print('звук:', inv['sound']['spt'], '| музыка:', inv['sound']['music'])
    if 'MiniMenu.pag' in inv['scrooby']: print('MiniMenu:', inv['scrooby']['MiniMenu.pag'][:12])
    print(f'опись: {a.json}')


if __name__ == '__main__':
    main()
