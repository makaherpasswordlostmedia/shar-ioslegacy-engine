#!/usr/bin/env python3
"""№788 (Роб 18.10 после TEST34: «в мультике не накладывать цветокоррекцию на билборды (Красти), разбиваемые стёкла, стоп-знаки — пусть остаются светлыми,
звонкими»): списки текстур уровня без шагов мультика — notoon.txt (номера записей текстур level.shr через пробел) для L1 рядом с EBOOT, для L2–L7 в l<N>/.

Номер записи -> url ('textures/<sha256 сырых точек [:20]>.png') — из <level.shr>.texsrc.json того же экспорта (tools/psp_export.py пишет его рядом); url -> имя
текстуры — из чанков 0x19000 файлов .p3d диска (как hit-and-run-web/tools/convert.py: имя чанка, sha256 данных 0x19002[4:]). Отбор по имени — правило NAME_RE.
Первая строка файла — «ntex N sig X» по level.shr рядом с texsrc.json (число текстур и FNV-1a по номерам текстур всех кусков, Rec.tex @24): движок
(main_levels.h, №788) применяет список только к тому же экспорту.
  python3 tools/notoon_list.py --texsrc DIR_C_l1..l7 --out DIR [--list]   (--list — напечатать отобранные имена по уровням)"""
import argparse, hashlib, json, os, re, struct, sys
from pathlib import Path
R = Path(__file__).resolve().parents[1]
HRW = Path(os.environ.get('HRW', R / 'hit-and-run-web'))
sys.path.insert(0, str(HRW / 'tools'))
from p3d import read, walk, string   # noqa: E402
# вывески, щиты, знаки, логотипы, реклама, витринное стекло; не стены, не окна домов (их тон — как у мира)
NAME_RE = re.compile(r'(billboard|bboard|board_|_board|sign|stop|poster|banner|logo|advert|marquee|menu|neon|letters|lard_lad|lard_donut|duff_blimp|^duff\.bmp|kwiki_sign|'
                     r'krusty_glass|krusty_ humancola|krusty_globe|krusty_friends|krusty_fence|^glass\.bmp|glass_day|glass_sunset|glass_decal)', re.I)   # здания Красти и Duff (стены, крыши) — нет
EXCLUDE_RE = re.compile(r'(famil_v|_wall|vent|duct)', re.I)
# №825: листва (деревья, кусты, живые изгороди) — раздел foliage: мультик красит её сочнее и радостнее травы (viewer/tone.c foliage825); «street» — не дерево
FOLIAGE_RE = re.compile(r'((?<!s)tree|leaf|leaves|foliage|bush|hedge|shrub|palm|pine|ivy|oak|(?<!power)plant)', re.I)   # oakl/oaks — кроны дубов у дома Симпсонов
FOLIAGE_EX = re.compile(r'(shad|trunk|grate|bare|dead)', re.I)   # тени под деревьями, стволы, решётки, голые ветки — не листва   # стены и трубы фабрики Lard Lad, наклейка на машине семьи — тон как у мира

def names_by_digest(cache_path):
    if cache_path and Path(cache_path).exists(): return json.loads(Path(cache_path).read_text())
    m = {}
    for p in sorted((HRW / 'source' / 'game').rglob('*.p3d')):
        try: root = read(p)
        except Exception: continue
        for c in walk(root):
            if c.id != 0x19000: continue
            try:
                name = string(c.data)[0].lower()
                img = next(v for v in c.children if v.id == 0x19001)
                raw = next(v for v in img.children if v.id == 0x19002).data[4:]
            except (StopIteration, ValueError): continue
            d = hashlib.sha256(raw).hexdigest()[:20]
            m.setdefault(d, [])
            if name not in m[d]: m[d].append(name)
    if cache_path: Path(cache_path).write_text(json.dumps(m))
    return m

def shr_sig(shr):
    h = open(shr, 'rb').read(104); ntex, npc = struct.unpack_from('<II', h, 4); toff = struct.unpack_from('<I', h, 76)[0]
    f = open(shr, 'rb'); f.seek(toff); tab = f.read(80 * npc); x = 2166136261
    for i in range(npc): x = ((x ^ struct.unpack_from('<I', tab, 80 * i + 24)[0]) * 16777619) & 0xffffffff
    return ntex, x

def main():
    a = argparse.ArgumentParser(); a.add_argument('--texsrc', required=True, help='папка с l1..l7/level.shr.texsrc.json (экспорт текущих level.shr)')
    a.add_argument('--out', required=True); a.add_argument('--cache', default=''); a.add_argument('--list', action='store_true'); o = a.parse_args()
    m = names_by_digest(o.cache)
    for L in range(1, 8):
        ts = Path(o.texsrc) / ('l%d' % L) / 'level.shr.texsrc.json'
        if not ts.exists(): print('L%d: нет %s' % (L, ts)); continue
        tex = json.loads(ts.read_text())['tex']; pick = []; fol = []
        ntex, sig = shr_sig(ts.parent / ts.name[:-len('.texsrc.json')])
        if ntex != len(tex): print('L%d: в level.shr %d текстур, в texsrc.json %d — пропуск' % (L, ntex, len(tex))); continue
        for i, t in enumerate(tex):
            if not t: continue
            d = t['url'].split('/')[-1].split('.')[0]
            nm = m.get(d, [])
            if any(NAME_RE.search(n) and not EXCLUDE_RE.search(n) for n in nm): pick.append((i, nm))
            elif any(FOLIAGE_RE.search(n) and not FOLIAGE_EX.search(n) for n in nm): fol.append((i, nm))
        dst = Path(o.out) / ('notoon.txt' if L == 1 else 'l%d/notoon.txt' % L); dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text('ntex %d sig %08x\n' % (ntex, sig) + ' '.join(str(i) for i, _ in pick) + '\nfoliage\n' + ' '.join(str(i) for i, _ in fol) + '\n')
        print('L%d: %d текстур без мультика, %d листвы из %d, подпись %08x -> %s' % (L, len(pick), len(fol), len(tex), sig, dst))
        if o.list:
            for i, nm in pick: print('   %4d %s' % (i, ', '.join(nm[:3])))
            for i, nm in fol: print('   лист %4d %s' % (i, ', '.join(nm[:3])))

if __name__ == '__main__': main()
