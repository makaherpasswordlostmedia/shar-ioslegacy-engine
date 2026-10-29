#!/usr/bin/env python3
"""Правка Роба 312: гейт моста твик-панели типографики (build/ui_typo.json -> tools/ui_typo.py -> пакеты UIP1).
  1) нулевой контроль: без файла, с UI_TYPO=0 и с пустыми группами ui.shr побайтно один и тот же (прежний пакет);
  2) с проверочным json в пакете ровно то, что просили: BUSTED! — грань boulder_24*1.3 (строка 21 px), квитанция x1,25, у текста
     пузыря задания в записи элемента res[2] = межбуквенное 1, межстрочное 1, поле от аватарки 6, res[1] = поле без значка 6;
     шаг пунктов паузы 30 px; подписи кнопок в углу — правый край на месте.
  КРАСНЫЙ: --red (мост выключен UI_TYPO=0 при том же ожидании) — гейт обязан упасть.
python3 tests/ui/typo_bridge.py [--red] -> 0 = PASS"""
import hashlib, json, os, struct, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / '.venv/bin/python') if (ROOT / '.venv/bin/python').exists() else '/Users/USER/Downloads/shar-psp/.venv/bin/python'
TEST = {'version': 1, 'groups': {'hud_busted': {'face': 'boulder_24*1.3'}, 'st_ticket': {'k': 1.25},
                                 'hud_bubble': {'trk': 1, 'lead': 1, 'padL': 6, 'padN': 6},
                                 'pause_items': {'pitch': 30}, 'hints': {'face': 'swz721n_10*1.8'}}}


def export(tmp, name, typo):
    out = tmp / name; env = dict(os.environ, UI_SCRATCH=str(tmp / 'scratch'))
    env.pop('UI_TYPO', None)
    if typo is not None: env['UI_TYPO'] = str(typo)
    r = subprocess.run([PY, 'tools/ui_export.py', '--out', str(out)], cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode: print(r.stdout[-800:], r.stderr[-1500:]); raise SystemExit('экспорт упал')
    return out


def parse(path):
    b = path.read_bytes()
    h = struct.unpack_from('<4s19Ii3f', b, 0)
    ntex, off_tex, nitem, off_item, nscr, off_scr, nfont, off_font, nstr, off_str = h[2:12]
    strs = [b[o:b.index(b'\0', o)].decode('latin-1') for o in struct.unpack_from('<%dI' % nstr, b, off_str)]
    fonts = []
    for i in range(nfont):
        tex, lh, base, pad, name, _ = struct.unpack_from('<4H2I', b, off_font + i * (16 + 8 * 256))
        fonts.append(dict(name=strs[name], lh=lh, gh=pad))
    items = [struct.unpack_from('<8B4h2I4B2H3fIf3I', b, off_item + 64 * i) for i in range(nitem)]
    scr = [struct.unpack_from('<4I', b, off_scr + 16 * i) for i in range(nscr)]
    return dict(strs=strs, fonts=fonts, items=items, scr=scr)


def screen_items(P, si):
    f, n = P['scr'][si][:2]
    return P['items'][f:f + n]


def find_text(P, si, s):
    """текстовые элементы экрана si, у которых первая строка s (запись: 16 грань, 18 первая строка, 19 строк, 26–27 res[1–2])"""
    return [it for it in screen_items(P, si) if it[0] == 3 and P['strs'][it[18]] == s]


def main(red):
    tmp = Path(tempfile.mkdtemp(prefix='typo_bridge_'))
    (tmp / 'empty.json').write_text(json.dumps({'version': 1, 'groups': {}}))
    (tmp / 'test.json').write_text(json.dumps(TEST))
    md = lambda p: hashlib.md5(p.read_bytes()).hexdigest()
    a = export(tmp, 'nofile.shr', tmp / 'нет_такого.json'); b = export(tmp, 'off.shr', '0'); c = export(tmp, 'empty.shr', tmp / 'empty.json')
    null_ok = md(a) == md(b) == md(c)
    print(f'нулевой контроль: без файла {md(a)[:12]}, UI_TYPO=0 {md(b)[:12]}, пустой json {md(c)[:12]} -> {"один пакет" if null_ok else "РАЗНЫЕ"}')
    t = export(tmp, 'test.shr', '0' if red else tmp / 'test.json')
    P0, P1 = parse(a), parse(t)
    bad = []
    # BUSTED!
    bu = find_text(P1, 0, 'BUSTED!') or [it for it in screen_items(P1, 0) if it[0] == 3 and 'BUSTED!' in P1['strs'][it[18]:it[18] + it[19]]]
    bu0 = [it for it in screen_items(P0, 0) if it[0] == 3 and 'BUSTED!' in P0['strs'][it[18]:it[18] + it[19]]]
    if not bu or P1['fonts'][bu[0][16]]['name'] != 'boulder_24*1.3': bad.append('BUSTED! не гранью boulder_24*1.3: %s' % (P1['fonts'][bu[0][16]]['name'] if bu else '-'))
    else: print(f'BUSTED!: грань {P0["fonts"][bu0[0][16]]["name"]} -> {P1["fonts"][bu[0][16]]["name"]}, строка {P0["fonts"][bu0[0][16]]["lh"]} -> {P1["fonts"][bu[0][16]]["lh"]} px, y {bu0[0][9]} -> {bu[0][9]}')
    # пузырь задания: res[1], res[2]
    msg = [it for it in screen_items(P1, 0) if it[0] == 3 and it[3] == 13]   # FIELDS.index('OBJECTIVE') = 13
    if not msg: bad.append('нет текста задания')
    else:
        r1, r2 = msg[0][26], msg[0][27]
        trk, lead, padT, padL, padR = (r2 & 15 ^ 8) - 8, (r2 >> 4 & 15 ^ 8) - 8, r2 >> 8 & 255, r2 >> 16 & 255, r2 >> 24 & 255
        print(f'пузырь задания: res[2]={r2:#010x} (межбукв {trk}, межстроч {lead}, сверху {padT}, от аватарки {padL}, справа {padR}), res[1]={r1} (без значка)')
        if (trk, lead, padL, r1) != (1, 1, 6, 6): bad.append('пузырь: ждали межбукв 1, межстроч 1, от аватарки 6, без значка 6')
    # квитанция: ширина x1,25
    tk0 = [it for it in screen_items(P0, 0) if it[0] == 2 and it[2] == 12 and it[3] == 18]   # тег HNR_TICKET, поле HNR_TEXT
    tk1 = [it for it in screen_items(P1, 0) if it[0] == 2 and it[2] == 12 and it[3] == 18]
    if tk0 and tk1:
        print(f'квитанция: {tk0[0][10]}x{tk0[0][11]} -> {tk1[0][10]}x{tk1[0][11]} px')
        if (tk1[0][10], tk1[0][11]) != (round(tk0[0][10] * 1.25), round(tk0[0][11] * 1.25)): bad.append('квитанция не x1,25')
    else: bad.append('нет квитанции')
    # пункты паузы: шаг
    def rows(P):
        return sorted({it[9] for it in screen_items(P, 1) if it[0] == 3 and it[7] & 8})
    r0, r1_ = rows(P0), rows(P1)
    st = sorted({r1_[i + 1] - r1_[i] for i in range(len(r1_) - 1)})
    print(f'пункты паузы: y {r0} -> {r1_} (шаг {st})')
    if st != [30]: bad.append('шаг пунктов паузы не 30')
    if abs((r1_[0] + r1_[-1]) / 2 - (r0[0] + r0[-1]) / 2) > 1: bad.append('центр списка паузы сдвинулся')
    # подписи кнопок паузы: правый край строки на месте
    acc0 = find_text(P0, 1, 'Accept'); acc1 = find_text(P1, 1, 'Accept')
    if acc0 and acc1:
        e0, e1 = acc0[0][8] + acc0[0][10], acc1[0][8] + acc1[0][10]
        print(f'Accept паузы: грань {P1["fonts"][acc1[0][16]]["name"]}, x {acc0[0][8]}..{e0} -> {acc1[0][8]}..{e1}')
        if e0 != e1 or acc1[0][10] <= acc0[0][10]: bad.append('подпись кнопки: правый край не на месте или не шире')
    print(f'с проверочным json пакет {md(t)[:12]} ({"тот же" if md(t) == md(a) else "другой"})')
    ok = null_ok and not bad
    for x in bad: print('  -', x)
    print(('PASS' if ok else 'FAIL') + (' (красный контроль: мост выключен — обязан упасть)' if red else ''))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main('--red' in sys.argv))
