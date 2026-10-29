#!/usr/bin/env python3
"""318: eight requested roles, exported from disc into real UIP1 files.
TYPO_318_OLD=1 preserves the old shop label font and must fail role 2.
The generated reference is consumed by typo_318.mjs to verify panel/game parity.
All fixture values are isolated from Rob's build/ui_typo.json.
"""
import copy, json, os, sys, pickle
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import ui_export as U
import ui_typo as UT
import typo_panel as P

OUT = ROOT / 'build/typo318'
CFG = {'version': 1, 'groups': {
    'phone_stats': {'dx': 7, 'dy': 3},
    'st_shop_stars': {'k': 1.4},
    'save_slots': {'dy': 5, 'pitch': 25},
    'pause_coins': {'dx': 12, 'dy': -3},
    'brief_btn': {'font': 'pix8', 'trk': 1},
    'tut_text': {'trk': 2}, 'tut_board': {'gw': 3, 'gh': 2},
    'hud_nums': {'place_dx': -8},
    'hud_small': {'face': 'swz721mi_12*1.8667', 'ord_dx': 3},
    'hud_busted': {'face': 'boulder_24*2'}, 'st_ticket': {'k': 1.6},
}}


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = OUT / 'fixture.json'; cfg.write_text(json.dumps(CFG))
    U.project('frontend.p3d')
    data = []
    for label, config in [('base', '0'), ('new', str(cfg))]:
        os.environ['UI_TYPO'] = config
        tmp = OUT / label; tmp.mkdir(exist_ok=True)
        print('export', label, flush=True)
        cache = tmp / 'export.pkl'
        if '--reuse' in sys.argv and cache.exists():
            data.append(pickle.loads(cache.read_bytes()))
            if '--refresh-ui' in sys.argv:
                data[-1]['ui'] = P.ui_pack(tmp)
                cache.write_bytes(pickle.dumps(data[-1]))
        else:
            data.append(P.packs(tmp))
            cache.write_bytes(pickle.dumps(data[-1]))
    a, b = data
    if '--old-shop' in sys.argv:
        import shop_export as SH
        os.environ['TYPO_318_OLD'] = '1'
        b['shop'] = SH.ui_pack(SH.forsale(U.LEVEL), OUT / 'old-shop.shr')
        os.environ['UI_TYPO'] = '0'
        old = OUT / 'old-default'; old.mkdir(exist_ok=True)
        a['ui'] = P.ui_pack(old)
    def items(pack, screen, gid):
        pairs = []
        for t in a[pack]['screens'][screen]:
            if UT.matches(UT.GROUP[gid], screen, t):
                n = next(q for q in b[pack]['screens'][screen] if q['page'] == t['page'] and q['name'] == t['name'] and q['type'] == t['type'])
                pairs.append((t, n))
        assert pairs, (pack, screen, gid)
        return pairs
    results = []
    def check(role, ok, detail):
        results.append((role, bool(ok), detail)); print(('PASS ' if ok else 'FAIL ') + role + ': ' + detail, flush=True)
    ph = items('phone', 'phone', 'phone_stats')
    check('1 booth edge controls', all(n['dst'][:2] == [t['dst'][0]+7,t['dst'][1]+3] for t,n in ph), f'{len(ph)} labels/stars move together')
    sh = items('shop', 'purchase', 'shop_stats'); stars = items('shop', 'purchase', 'st_shop_stars')
    scaled = all(b['shop']['fonts'].get(n['font'])['lh'] > a['shop']['fonts'].get(t['font'])['lh'] for t,n in sh)
    check('2 proportional shop labels', scaled and all(n['dst'][2:] == [round(t['dst'][2]*1.4),round(t['dst'][3]*1.4)] for t,n in sh+stars), f'{len(sh)} fonts and {len(stars)} stars scale 1.4')
    sv = items('psave', 'pslots', 'save_slots'); ys = sorted({n['dst'][1] for _,n in sv})
    check('3 save rows', len(ys)==4 and all(y-x==25 for x,y in zip(ys,ys[1:])), str(ys))
    pa = items('ui', 'pause', 'pause_coins')
    check('4 pause coins corner', all(n['dst'][:2] == [t['dst'][0]+12,t['dst'][1]-3] for t,n in pa), f'{len(pa)} icon/number elements')
    br = items('ui', 'missionload', 'brief_btn')
    default = [t for t in a['ui']['screens']['missionload'] if t['type']==U.T_TEXT and t['name']=='Continue']
    check('5 briefing pixel font', bool(default) and all(t.get('pix8') for t in default) and all(n.get('pix8') for _,n in br), f'Continue defaults pix8; {len(br)} configurable labels')
    tu = items('ui', 'tutorial', 'tut_text'); board = items('ui', 'tutorial', 'tut_board')
    check('6 Bart tracking/frame', all(all(n['glyphs'][c][4]==gl[4]+2 for c,gl in t['glyphs'].items()) for t,n in tu) and all(t['dst']!=n['dst'] for t,n in board), f'{len(tu)} text and {len(board)} frame parts')
    race = items('ui', 'hud', 'hud_nums'); pos = [(t,n) for t,n in race if t['name']=='Position']
    ords = [(t,n) for t,n in items('ui','hud','hud_small') if t['name']=='PositionOrdinal']
    check('7 3rd independent/italic', bool(pos and ords) and all(n['dst'][0]==t['dst'][0]-8 for t,n in pos) and all(n['dst'][0]==t['dst'][0]+3 and n['font'].startswith('swz721mi_12') for t,n in ords), '3 dx=-8; rd dx=3, disc italic retained')
    bu = items('ui','hud','hud_busted'); tk = items('ui','hud','st_ticket')
    check('8 fine enlargement', all(n['font']=='boulder_24*2' for _,n in bu) and all(n['dst'][2]==round(t['dst'][2]*1.6) for t,n in tk), 'BUSTED font and receipt dimensions')
    ref = {}
    for pack, res in b.items():
        for screen, dl in res['screens'].items():
            ref[pack+':'+screen] = [{k:t[k] for k in ('page','name','type','dst','font','pix8','typo_res') if k in t} for t in dl]
    robpath = ROOT/'build/ui_typo.json'
    if robpath.exists() and '--old-shop' not in sys.argv:
        rob = json.loads(robpath.read_text())
        dl = UT.apply('missionload', copy.deepcopy(a['ui']['screens']['missionload']), None, a['ui']['fonts'], cfg=rob, U=U)
        t = next(t for t in dl if t['type']==U.T_TEXT and t['name']=='Continue')
        if rob.get('groups',{}).get('brief_btn',{}).get('face'):
            assert t.get('nopix8') and t['font']==rob['groups']['brief_btn']['face'], 'explicit Rob face must override default'
        ref['_robContinue'] = {k:t.get(k) for k in ('font','pix8','dst')}
        print('PASS explicit Rob Continue override:', t['font'], bool(t.get('pix8')))
    (OUT/'reference.json').write_text(json.dumps(ref, default=lambda v: v.item()))
    (OUT/'roles.json').write_text(json.dumps(results,indent=2))
    print(f'{sum(ok for _,ok,_ in results)}/8 roles PASS')
    return 0 if all(ok for _,ok,_ in results) else 1

if __name__=='__main__': sys.exit(run())
