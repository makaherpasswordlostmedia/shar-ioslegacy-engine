#!/usr/bin/env python3
"""Разбор прогона tests/levelmech/emu.sh (smoke.txt движка).

  emu_check.py SMOKE.txt --level N --mode barriers|ufo --shr level.shr --collect collect-lN.shr   -> PASS / FAIL (код 0 / 1)
Проверки: загружен уровень N (строка LEVEL n=N); данные прогона несут механику — barriers: в SPR1 level.shr есть огни
барьеров (билборды с флагом SP_BILL_PVIS 1<<16), ufo: в SPR1 пакета collect есть экземпляры без записей CLT1 (летающие
актёры) и строка COLL показала столько же экземпляров; свободная куча на старте уровня ≥ 20 МБ (heapMB сцены spawn);
сцена механики — ровные 30 FPS (медиана без «settling» ≥ 29.4, минимум ≥ 28); прогон дошёл до END."""
import argparse, re, statistics, struct, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import spr1




def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('smoke'); ap.add_argument('--level', type=int, required=True); ap.add_argument('--mode', required=True)
    ap.add_argument('--shr'); ap.add_argument('--collect')
    a = ap.parse_args()
    p = Path(a.smoke)
    if not p.exists(): print(f'FAIL: нет {p}'); return 1
    lines = p.read_text(errors='replace').splitlines(); bad = []
    lv = next((l for l in lines if l.startswith('LEVEL ') and 'ev=load' in l), None)
    m = re.search(r' n=(\d+)', lv or '')
    print('LEVEL:', (lv or '-')[:160])
    if not m or int(m.group(1)) != a.level: bad.append(f'уровень {a.level} не загружен')
    scene_name = {'barriers': 'barrier', 'ufo': 'ufo', 'shield': 'shield'}[a.mode]
    if a.mode == 'barriers':
        n = 0
        b = Path(a.shr).read_bytes()
        for S in spr1.find(a.shr):
            bp, cnt = S['parts']['bill']
            n += sum(1 for k in range(cnt // 40) if struct.unpack_from('<I', b, bp + 40 * k + 36)[0] & (1 << 16))
        print(f'огней барьеров в SPR1 уровня: {n}')
        if n == 0: bad.append('в level.shr прогона нет барьеров 0x3F0000F')
    elif a.mode == 'shield':
        b = Path(a.collect).read_bytes(); u = struct.unpack_from('<15I', b, 4)
        sh = sum(1 for i in range(u[8]) if struct.unpack_from('<H', b, u[9] + 80 * i + 66)[0] & 2)
        print(f'ос со щитом в пакете прогона: {sh} из {u[8]}')
        if not sh: bad.append('в пакете collect прогона нет ос со щитом')
    else:
        b = Path(a.collect).read_bytes()
        u = struct.unpack_from('<15I', b, 4)
        S = spr1.parse(b, u[4])
        used = {struct.unpack_from('<H', b, u[7] + 32 * i + 20)[0] for i in range(u[6])}
        used |= {v for i in range(u[8]) for v, fl, sh in [struct.unpack_from('<HHH', b, u[9] + 80 * i + 64)] for v in ([v, sh] if fl & 2 else [v])}
        used |= {struct.unpack_from('<h', b, u[11] + 128 * i + 48)[0] for i in range(u[10])}
        extra = [i for i in range(S['head']['ninst']) if i not in used]
        cl = next((l for l in lines if l.startswith('COLL ok')), '')
        ci = re.search(r'inst=(\d+)', cl)
        print(f'летающих актёров в пакете: {len(extra)}; {cl[:100]}')
        if not extra: bad.append('в пакете collect прогона нет летающих актёров')
        if not ci or int(ci.group(1)) != S['head']['ninst']: bad.append('движок прочитал другой пакет collect')
    scene, fps, heap = None, {}, {}
    for l in lines:
        if l.startswith('SCENE '): scene = l.split()[1]
        f = l.split()
        if len(f) >= 15 and re.match(r'^[\d.]+$', f[0]):
            sc = f[1]
            fps.setdefault(sc, []).append((float(f[2]), 'settling' in l))
            heap.setdefault(sc, float(f[14]))
    h = heap.get('spawn')
    print(f'куча на старте: {h} МБ')
    if h is None or h < 20.0: bad.append(f'свободная куча на старте {h} МБ < 20')
    df = [v for v, st in fps.get(scene_name, []) if not st]
    med = statistics.median(df) if df else 0.0
    print(f'FPS сцены {scene_name}: {[round(v, 1) for v in df]} (медиана {med:.1f})')
    if med < 29.4 or (df and min(df) < 28.0): bad.append(f'FPS сцены {scene_name}: медиана {med:.1f}, минимум {min(df) if df else 0:.1f} (нужно ровно 30)')
    if not any(l.startswith('END') for l in lines): bad.append('прогон не дошёл до END')
    for x in bad: print('  ПРОВАЛ:', x)
    print(f'уровень {a.level} {a.mode}: ' + ('PASS' if not bad else f'FAIL ({len(bad)})'))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
