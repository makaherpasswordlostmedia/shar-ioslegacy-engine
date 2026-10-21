#!/usr/bin/env python3
"""Живая страница ботов (просьба Роба 30.09: «вывести отображение локальных тестов, чтобы смотреть, как гоняются»).
Каждые 5 с: build/bots/live/index.html из последнего прогона build/bots/nights/*/night.json + процессы Мака (ps).
Карта — лист уровня 1 с сеткой кодов мест (tools/place.py --sheet 1, 1 px = 1 м): точки — где застряли миссии, вечные углы
догонялок. Боты считают без картинки (тысячи раундов пачками), поэтому страница показывает ход счёта, а не кадры.
  python3 tools/bots/live.py           # пишет страницу и держит сервер http://127.0.0.1:8777 (закрыть окно — стоп)"""
import html, json, math, os, re, subprocess, sys, threading, time, http.server, socketserver
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; OUT = ROOT / 'build/bots/live'; OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / 'tools'))
import place as PL

def sheet_origin():   # тот же расчёт, что place.sheet: левый верх листа в метрах движка
    import ui_export as U
    m = U.bake_radar_map(1); lo, hi = m['lo'], m['hi']; M_ = 60.0
    xa = max(0, math.floor((lo[0] - M_ - PL.X0) / PL.CELL)); za = max(0, math.floor((-hi[1] - M_ - PL.Z0) / PL.CELL))
    return PL.X0 + xa * PL.CELL - 40, PL.Z0 + za * PL.CELL - 40   # PAD 40 px = 40 м
OX, OZ = sheet_origin()
MAP = ROOT / 'build/maps/l1_codes.png'
if MAP.exists():
    import shutil; shutil.copy(MAP, OUT / 'map.png')
from PIL import Image
MW, MH = Image.open(OUT / 'map.png').size if (OUT / 'map.png').exists() else (1, 1)

def latest():
    runs = sorted((ROOT / 'build/bots/nights').glob('*/night.json'), key=lambda p: p.stat().st_mtime)
    return runs[-1] if runs else None

def procs():
    try: out = subprocess.run(['ps', '-axo', 'pcpu,etime,command'], capture_output=True, text=True).stdout
    except Exception: return []
    rows = []
    for l in out.splitlines():
        if 'build/bots/nights/' in l and '/bin/' in l:
            cpu, et, cmd = l.split(None, 2); name = cmd.split('/bin/')[1].split()[0]; rows.append((name, cpu, et))
    return rows

def page():
    p = latest(); d = json.loads(p.read_text()) if p else {}
    dots = []
    for k, m in (d.get('missions') or {}).items():
        pl = m.get('place') or [0, 0]
        if m.get('result') != 'пройдена' and (pl[0] or pl[1]): dots.append((pl[0], pl[1], '#d33', f"{k}: {m.get('result','')}"))
    for key in ((d.get('chase') or {}).get('corners') or {}):
        nums = re.findall(r'-?\d+', key.split('eternal_corner')[-1])
        if len(nums) >= 2: dots.append((float(nums[-2]), float(nums[-1]), '#36c', 'вечный угол ' + ':'.join(nums[-2:])))
    svg = ''.join(f'<circle cx="{(x-OX):.0f}" cy="{(z-OZ):.0f}" r="9" fill="{c}" stroke="#fff" stroke-width="3"><title>{html.escape(t)}</title></circle>'
                  f'<text x="{(x-OX)+12:.0f}" y="{(z-OZ)+5:.0f}" font-size="18" fill="{c}" stroke="#fff" stroke-width="4" paint-order="stroke">{html.escape(t.split(":")[0])}</text>' for x, z, c, t in dots)
    gm = d.get('gameMinutes') or {}; runs = d.get('runs') or {}
    ch = d.get('chase') or {}; f0, fl = ch.get('first') or {}, ch.get('last') or {}
    nav = d.get('nav') or {}
    mrows = ''.join(f"<tr class='{'ok' if m.get('result')=='пройдена' else 'bad'}'><td>{html.escape(k)}</td><td>{html.escape(m.get('title',''))}</td><td>{html.escape(m.get('result',''))}</td><td>{m.get('time','')}</td><td>{html.escape(m.get('cls',''))}</td></tr>"
                    for k, m in (d.get('missions') or {}).items())
    prow = ''.join(f'<tr><td>{n}</td><td>{c}%</td><td>{e}</td></tr>' for n, c, e in procs()) or '<tr><td colspan=3>боты не идут</td></tr>'
    state = 'идёт' if not d.get('finished') and not d.get('stopped') else ('остановлен' if d.get('stopped') else 'закончен')
    return f"""<!doctype html><html lang=ru><head><meta charset=utf-8><meta http-equiv=refresh content=5><title>Боты SHAR</title>
<style>body{{margin:0;font:14px -apple-system,Helvetica,sans-serif;background:#111;color:#ddd;display:flex;gap:16px;padding:16px}}
.map{{flex:1;min-width:0}} .map svg{{width:100%;height:auto;background:#eee;border-radius:6px}} .side{{width:420px}}
h1{{font-size:18px;margin:0 0 8px}} h2{{font-size:14px;margin:16px 0 6px;color:#aaa}} table{{border-collapse:collapse;width:100%}}
td{{padding:3px 6px;border-bottom:1px solid #222}} tr.ok td:nth-child(3){{color:#6c6}} tr.bad td:nth-child(3){{color:#e66}} .big{{font-size:22px;color:#fff}}</style></head><body>
<div class=map><svg viewBox="0 0 {MW} {MH}"><image href="map.png" width="{MW}" height="{MH}"/>{svg}</svg>
<div style="color:#888;margin-top:6px">Красные — где застряла миссия, синие — вечные углы догонялок. Наведи на точку — подпись. Обновление каждые 5 с · {time.strftime('%H:%M:%S')}</div></div>
<div class=side><h1>Боты SHAR · прогон {html.escape(str(d.get('stamp','—')))} · {state}</h1>
<div>с {d.get('started','—')} до {d.get('until','—')}</div>
<h2>Сейчас на процессоре Мака</h2><table>{prow}</table>
<h2>Сыграно</h2><div class=big>{sum(gm.values())/60:.0f} ч игры</div>
<div>догонялки {gm.get('chase',0)/60:.0f} ч ({runs.get('chase',0)} прогонов) · миссии {gm.get('missions',0)/60:.0f} ч ({runs.get('missions',0)}) · навигатор {gm.get('nav',0)/60:.0f} ч ({runs.get('nav',0)}) · каскадёр {gm.get('explore',0)/60:.0f} ч</div>
<h2>Догонялки</h2><div>поймали за {f0.get('meanCatch','—')} с → {fl.get('meanCatch','—')} с; доля поимок {f0.get('catchRate','—')} → {fl.get('catchRate','—')} (поколение {fl.get('gen','—')}); вечных углов {len(ch.get('corners') or {})}</div>
<h2>Навигатор</h2><div>маршрутов {nav.get('routes','—')}, доехал {nav.get('reached','—')}, повтор совпал {nav.get('replayOk','—')}</div>
<h2>Миссии уровня 1</h2><table>{mrows}</table>
<h2>Остановить</h2><div>«SHAR боты СТОП» на рабочем столе</div></div></body></html>"""

def loop():
    while True:
        try: (OUT / 'index.html').write_text(page())
        except Exception as e: (OUT / 'index.html').write_text(f'<meta http-equiv=refresh content=5>ошибка страницы: {html.escape(str(e))}')
        time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=loop, daemon=True).start(); time.sleep(1)
    os.chdir(OUT)
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('127.0.0.1', 8777), Q) as srv:
        print('Боты SHAR: http://127.0.0.1:8777 (закрыть окно — стоп)'); srv.serve_forever()
