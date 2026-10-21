#!/usr/bin/env python3
"""L7 CreditsPostFMV.scr -> ending.shr; disc pages/text/art, no invented motion.
ENDING_ASSETS_OLD=1 keeps the placeholder dot (red data control).
"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ui_export as U
import menu_export as M

SCREEN = 'ending'
PAGES = U.project('ingame.p3d').screens['CreditsPostFMV.scr']
assert PAGES == ['CreditsBgd.pag', 'ViewCredits.pag', 'CreditsKK.pag'], PAGES


def build(sc, assets, fonts):
    U.SCREEN_PAGES[sc] = [('ingame.p3d', p) for p in PAGES]
    its = U.build_items(sc)[0]
    provenance = []
    prj = U.project('ingame.p3d')
    for it in its:
        if it['page'] != 'CreditsKK.pag': continue
        it['tag'] = 'STREETRACE'  # existing credits foreground pass: figures and black bars
    figures = []
    for path, e in U.iter_leaves(prj.pages['CreditsKK.pag']):
        if e['kind'] != 'sprite': continue  # ui_export intentionally drops placeholder ['dot'] sprites
        name = e['name'].lower()
        src = U.ROOT / 'hit-and-run-web/source/game/art/frontend/dynaload/images' / (name + '.p3d')
        chunk = next(c for c in U.read(src).children if c.id == U.C_IMAGE)
        key, image = U.decode_sprite_image(chunk)
        # Scrooby figures use centre anchors; fit actual texture uniformly in its authored box
        k = min(e['w'] / image.width, e['h'] / image.height)
        w, h = image.width * k, image.height * k
        it = dict(name=e['name'], page='CreditsKK.pag', path='/'.join(path), type=U.T_IMG, tag='STREETRACE',
                  unit=('CreditsKK.pag', e['name']), forced=None, field='NONE', fmt='none', menu=-1,
                  rect=[e['x'] - w / 2, U.SRC_H - e['y'] - h / 2, w, h], color=e['color'],
                  frames=['dot.png'], jx=e['jx'], jy=e['jy'])
        if os.environ.get('ENDING_ASSETS_OLD') != '1':
            assets.images[key] = image
            it['frames'] = [key]
        figures.append(it)
        provenance.append(dict(name=it['name'], source=str(src.relative_to(U.ROOT)), texture=key,
                               texture_size=list(image.size), source_centre=[e['x'], e['y']],
                               source_box=[e['w'], e['h']], fitted_rect=it['rect']))
    at = next(i for i,t in enumerate(its) if t['page']=='CreditsKK.pag')
    its[at:at] = figures  # authored Foreground precedes BlackBars
    dl, _ = U.adapt(M.credits(its), {}, 'psp', assets, fonts)
    for q in provenance:
        t = next(t for t in dl if t['name'] == q['name']); q['dst'] = [int(v) for v in t['dst']]; q['frames'] = t['frames']
    target = U.ROOT/'build/content/ending'; target.mkdir(parents=True, exist_ok=True)
    (target/('assets-old.json' if os.environ.get('ENDING_ASSETS_OLD') == '1' else 'assets.json')).write_text(json.dumps(provenance,indent=2))
    return dl


def export(out):
    spec = dict(screens=[SCREEN], build=build, tags={SCREEN:{'ALWAYS','SKIP','STREETRACE'}}, radar=False,
                layout='layout_ending.json')
    return U.pack(out, spec)


if __name__=='__main__':
    out = Path(sys.argv[sys.argv.index('--out')+1]) if '--out' in sys.argv else U.ROOT/'build/ending.shr'
    out.parent.mkdir(parents=True,exist_ok=True)
    r=export(out); print('ending',out,r['size'],'bytes')
