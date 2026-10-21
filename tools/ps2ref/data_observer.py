#!/usr/bin/env python3
"""N2.3: owner's extracted data -> bounded animation/sound observations, no game code.
Resources/previews stay in ignored build/ps2ref; facts contain measurements, not assets.
MIT parser/texture decoder: hit-and-run-web/tools (retains its original license).
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
GAME = ROOT / 'hit-and-run-web/source/game'
SCROOBY = GAME / 'art/frontend/scrooby'
sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import decompress


def chunks(b, start=0, end=None):
    end = len(b) if end is None else end
    while start < end:
        if start + 12 > end: raise ValueError('truncated chunk header')
        kind, head, size = struct.unpack_from('<III', b, start)
        if head < 12 or size < head or start + size > end: raise ValueError('bad chunk bounds')
        yield dict(id=kind, offset=start, data=b[start+12:start+head], children=list(chunks(b, start+head, start+size)))
        start += size


def walk(nodes):
    for n in nodes:
        yield n
        yield from walk(n['children'])


def string(b, pos):
    if pos >= len(b): raise ValueError('missing string')
    end = pos + 1 + b[pos]
    if end > len(b): raise ValueError('truncated string')
    return b[pos+1:end].rstrip(b'\0').decode('latin1'), end


def animation(node):
    b = node['data']; name, p = string(b, 4)
    if p + 16 != len(b): raise ValueError('unexpected animation header length')
    tag = b[p:p+4].rstrip(b'\0').decode('ascii'); frames, fps, loop = struct.unpack_from('<ffI', b, p+4)
    if not (0 < frames <= 1e6 and 0 < fps <= 1000): raise ValueError('invalid animation clock')
    out = dict(name=name, type=tag, frames=frames, fps=fps, loop=loop,
               nominal_seconds=frames/fps, decompressed_offset=node['offset'], channels=[])
    for c in walk(node['children']):
        if c['id'] not in (0x121100, 0x121104, 0x121107): continue
        b = c['data']
        if len(b) < 12: raise ValueError('short channel')
        param = b[4:8].rstrip(b'\0').decode('ascii'); n = struct.unpack_from('<I', b, 8)[0]
        if not 0 < n <= 100000 or 12 + 2*n > len(b): raise ValueError('invalid channel count')
        keys = list(struct.unpack_from('<' + 'H'*n, b, 12)); p = 12 + 2*n
        if keys != sorted(set(keys)) or keys[-1] > frames: raise ValueError('invalid keyframe order/range')
        if c['id'] == 0x121107:
            vals = []
            for _ in keys:
                v, p = string(b, p); vals.append(v)
        else:
            dim = 1 if c['id'] == 0x121100 else 3
            if p + 4*n*dim != len(b): raise ValueError('channel size mismatch')
            raw = struct.unpack_from('<' + 'f'*(n*dim), b, p); p += 4*n*dim
            vals = list(raw) if dim == 1 else [list(raw[i:i+3]) for i in range(0,len(raw),3)]
        if p != len(b): raise ValueError('unparsed channel bytes')
        modes = [struct.unpack('<II', x['data'])[1] for x in c['children'] if x['id']==0x121110]
        out['channels'].append(dict(id=hex(c['id']), parameter=param, keys=keys, values=vals,
                                    interpolation_modes=modes, decompressed_offset=c['offset']))
    return out


def sounds(path):
    text = path.read_text(); rows = []
    for m in re.finditer(r'create\s+daSoundResourceData\s+named\s+(\w+)\s*\{([^}]+)\}', text):
        body = m[2]; files = re.findall(r'AddFilename\s*\(\s*"([^"]+)"\s+([\d.]+)', body)
        trim = re.search(r'SetTrim\s*\(\s*([\d.]+)', body)
        if not files: raise ValueError('sound resource without filename')
        rows.append(dict(name=m[1], line=text[:m.start()].count('\n')+1,
                         files=[dict(path=f, weight=float(w), exists=(GAME/f).is_file()) for f,w in files],
                         trim=float(trim[1]) if trim else None,
                         trigger_timing='not established by resource declaration'))
    if not rows: raise ValueError('no sound declarations')
    return rows


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def extract(out):
    out.mkdir(parents=True, exist_ok=True); report = dict(files=[], animations=[], sounds=[], sprites=[])
    for p in sorted(SCROOBY.rglob('*.p3d')):
        nodes = list(chunks(decompress(p.read_bytes())))
        animations = [animation(n) for n in walk(nodes) if n['id']==0x121000]
        if p.name in ('ingame.p3d', 'backend.p3d') and p.parent==SCROOBY:
            for n in walk(nodes):
                if n['id']!=0x18006: continue
                name,q=string(n['data'],0)
                if name not in ('ActionButton','Fire','Loading'): continue
                count=struct.unpack_from('<I',n['data'],q+40)[0];q+=44;images=[]
                for _ in range(count):
                    value,q=string(n['data'],q);images.append(value)
                report['sprites'].append(dict(source=str(p.relative_to(ROOT)),sha256=sha(p),name=name,
                    decompressed_offset=n['offset'],images=images,timing='not present in this sprite record'))
        report['files'].append(dict(path=str(p.relative_to(ROOT)), sha256=sha(p), animation_count=len(animations)))
        for a in animations: report['animations'].append(dict(source=str(p.relative_to(ROOT)), sha256=sha(p), **a))
    p = GAME/'sound/scripts/frontend.spt'
    report['sounds'] = sounds(p); report['sound_source'] = dict(path=str(p.relative_to(ROOT)), sha256=sha(p))
    (out/'data.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    p = SCROOBY/'resource/pure3d/loading.p3d'
    from textures import decode_image
    textures = {}
    for n in walk(list(chunks(decompress(p.read_bytes())))):
        if n['id'] != 0x19000: continue
        name, _ = string(n['data'],0)
        images = [x for x in walk(n['children']) if x['id']==0x19002]
        if images: textures[name]=images[0]['data'][4:]
    loading = next(a for a in report['animations'] if a['name']=='TEX_loading_screen_m')
    ch = next(c for c in loading['channels'] if c['id']=='0x121107')
    for i,name in enumerate(ch['values']):
        if name not in textures: raise ValueError('missing loading texture '+name)
        decode_image(textures[name]).save(out/f'loading-{i}.png')
    rows=['animation\tkey_frame\tnominal_seconds\ttexture']
    for key,name in zip(ch['keys'],ch['values']): rows.append(f"{loading['name']}\t{key}\t{key/loading['fps']:.9f}\t{name}")
    (out/'loading.tsv').write_text('\n'.join(rows)+'\n')
    facts = ROOT/'knowledge/facts'; facts.mkdir(parents=True,exist_ok=True)
    cards = [
      dict(id='ps2-loading-data', question='Как устроена текстурная анимация Щекотки и Царапки в loading.p3d?',
           answer=f"{len(ch['keys'])} текстурных ключей, {loading['frames']:g} единиц длительности, {loading['fps']:g} кадров/с, loop={loading['loop']}; номинальный цикл {loading['nominal_seconds']:g} с",
           ladder_stage=1, status='data_observed_runtime_unconfirmed', evidence=dict(source=loading['source'],sha256=loading['sha256'],decompressed_offset=loading['decompressed_offset']),
           test='python3 tools/ps2ref/data_observer.py --gate', limitation='Скорость контроллера во время игры и соответствие кадрам PCSX2 ещё не измерены'),
      dict(id='ps2-frontend-sounds-data',question='Какие звуковые ресурсы объявлены для интерфейса?',
           answer={r['name']:dict(files=[f['path'] for f in r['files']],trim=r['trim']) for r in report['sounds']},
           ladder_stage=1,status='resource_mapping_only',evidence=report['sound_source'],
           test='python3 tools/ps2ref/data_observer.py --gate', limitation='Объявление звука не доказывает момент его запуска или синхронизацию с анимацией'),
      dict(id='ps2-scrooby-animation-scope',question='Есть ли ключевые кривые во всех основных проектах Scrooby?',
           answer={Path(f['path']).name:f['animation_count'] for f in report['files'] if Path(f['path']).parent.name=='scrooby'},
           ladder_stage=1,status='bounded_scan',evidence=dict(report='build/ps2ref/data/data.json',files_scanned=len(report['files'])),
           test='python3 tools/ps2ref/data_observer.py --gate',limitation='Отсутствие чанка 0x121000 не исключает программную анимацию, sprite sequences и другие форматы; пульс △ из этих данных пока не восстановлен')]
    cards.append(dict(id='ps2-action-fire-sprite-data',question='Где пульс △ и скорость огня фитиля?',
        answer='ActionButton содержит одно изображение; Fire в backend содержит два. Записи спрайтов не задают скорость переключения и кривую пульса',
        ladder_stage=1,status='runtime_timing_unknown',evidence=report['sprites'],
        test='python3 tools/ps2ref/data_observer.py --gate',limitation='Нужна запись оригинала; нельзя переносить 30fps из другого ресурса loading.p3d на эти спрайты'))
    for card in cards: (facts/(card['id']+'.yaml')).write_text(json.dumps(card,ensure_ascii=False,indent=2)+'\n')
    page='''<!doctype html><meta charset="utf-8"><title>Наблюдатель PS2 — данные</title>
<style>body{font:16px system-ui;background:#f6f5f2;color:#1a1a1a;margin:32px;max-width:1000px}img{max-width:90vw;image-rendering:pixelated}small{display:block}td,th{padding:8px;text-align:left}</style>
<h1>Анимация загрузки: Щекотка и Царапка из loading.p3d</h1><p>Ступень 1 · темп задан в ресурсе · совпадение с записью PCSX2 ещё не проверено</p><p>Здесь исходные квадратные текстуры; проекция на экран игры не воспроизведена</p>
<img id="frame"><small id="time"></small><p><button id="toggle">Пауза</button></p>
<p><a href="loading.tsv">Ключевые кадры TSV</a> · <a href="data.json">Извлечённые данные</a></p>'''
    page += '<script>const a='+json.dumps(loading)+''';const c=a.channels.find(c=>c.id==='0x121107'); let playing=true,t=0,last=performance.now();
document.querySelector('#toggle').onclick=()=>playing=!playing;
function tick(now){if(playing)t+=(now-last)/1000;last=now;const f=(t*a.fps)%a.frames;let i=0;for(let k=0;k<c.keys.length;k++)if(c.keys[k]<=f)i=k;
document.querySelector('#frame').src=`loading-${i}.png`;document.querySelector('#time').textContent=`Ключ ${c.keys[i]} / ${a.frames}; ${a.fps} кадров/с в данных`;requestAnimationFrame(tick)}requestAnimationFrame(tick)</script>'''
    (out/'index.html').write_text(page)
    return report


def gate(out):
    out.mkdir(parents=True,exist_ok=True)
    checks={}
    # Corrupt the original length field in memory. Never modifies the disc/extracted files.
    raw=bytearray(decompress((SCROOBY/'resource/pure3d/loading.p3d').read_bytes()))
    struct.pack_into('<I',raw,8,len(raw)+100)
    try: list(chunks(raw))
    except ValueError: checks['bad_bounds_rejected']=True; print('RED: corrupt chunk rejected')
    else: checks['bad_bounds_rejected']=False
    r=extract(out)
    a=next(x for x in r['animations'] if x['name']=='TEX_loading_screen_m')
    c=next(x for x in a['channels'] if x['id']=='0x121107')
    checks['loading_contract']=a['frames']==18 and a['fps']==30 and c['keys']==list(range(0,18,2))
    checks['sound_references']=len(r['sounds'])==10 and all(f['exists'] for s in r['sounds'] for f in s['files'])
    result=dict(ok=all(checks.values()),checks=checks,runtime_frame_match='pending_capture',full_N23_gate=False)
    (out/'gate.json').write_text(json.dumps(result,indent=2)+'\n')
    print('DATA',result,'files',len(r['files']),'animations',len(r['animations']))
    return result['ok']


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gate',action='store_true')
    p.add_argument('--out',type=Path,default=ROOT/'build/ps2ref/data');a=p.parse_args()
    if a.gate: sys.exit(0 if gate(a.out) else 1)
    extract(a.out)
