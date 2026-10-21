"""Опора под точками миссий уровня (правка Роба 108, пункт 11.3; часть floor, 30.09). Только чтение.
  python tools/msn_ground_check.py --json build/tmp_conv/floor/level01.json --shr build/level.shr [--rooms build/interiors-l1.bin]
  --json  — дамп tools/missions/compile.py (--scratch), --shr — уровень (COL1), --rooms — комнаты SHI1 (tools/interior_export.py)
  --rule old|new — правило разговора без SetDialoguePositions (viewer/game_msn.c talkBegin): old — как до b522fab (игрок всегда на
               линии к собеседнику в 2.45 м), new — точка на линии только с опорой (-2..+1 м от пола игрока), иначе стоит, где стоял
Что печатает:
  1) все точки-локаторы из команд миссий (цели, NPC, места разговоров, сброс игрока/машины, персонажи этапа…), под которыми нет
     опоры COL1 в пределах [y - BELOW, y + ABOVE] (земля n.y > 0.5, верх ящиков, торцы вертикальных цилиндров — как colGround);
     точка ниже -10 м ищется и в комнатах (у каждой свой COL1)
  2) разговоры без мест в данных: где правило --rule ставит игрока и есть ли там опора. Выход 1 — если игрок встаёт без опоры
     (гейт: --rule old обязан упасть на m4 «Blind Big Brother», --rule new — пройти)
Правило разговора здесь — модель на данных (без луча colRayFrac движка); настоящую проверку делает миссионер (tools/bots/missioner.c)"""
import sys, json, struct, argparse, math
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import col_check as cc

TALK_DIST, TALK_UP, TALK_DOWN = 2.45, 1.0, 2.0   # viewer/game_msn.h GAME_TALK_DIST / GAME_TALK_UP / GAME_TALK_DOWN
TALK_NEAR = 30.0   # игрок у цели прошлого этапа — только если она ближе к собеседнику (триггер у пульта, двери); иначе не моделируем


class World:
    def __init__(self, name, C):
        self.name, self.C = name, C
        T = C['tri']; n = T[:, 3]
        self.walk = n[:, 1] > 0.5                               # как colGround: проходимые треугольники

    def covers(self, x, z):
        C = self.C
        return C['ox'] <= x < C['ox'] + C['W'] * C['cell'] and C['oz'] <= z < C['oz'] + C['H'] * C['cell']

    def ground(self, x, z):
        """высоты всех опор в точке (x, z): треугольники земли, верх ящиков, торцы вертикальных цилиндров"""
        C = self.C
        gx = int(math.floor((x - C['ox']) / C['cell'])); gz = int(math.floor((z - C['oz']) / C['cell']))
        if gx < 0 or gz < 0 or gx >= C['W'] or gz >= C['H']: return []
        k = gz * C['W'] + gx; refs = C['refs'][C['start'][k]:C['start'][k + 1]]
        out = []
        for r in refs:
            typ, i = int(r >> 29), int(r & ((1 << 29) - 1))
            if typ == 0 and self.walk[i]:
                a, b, c = C['tri'][i, 0], C['tri'][i, 1], C['tri'][i, 2]
                v0, v1 = b - a, c - a; det = v0[0] * v1[2] - v1[0] * v0[2]
                if abs(det) < 1e-12: continue
                dx, dz = x - a[0], z - a[2]
                u = (dx * v1[2] - v1[0] * dz) / det; v = (v0[0] * dz - dx * v0[2]) / det
                if u >= -1e-6 and v >= -1e-6 and u + v <= 1 + 1e-6: out.append(float(a[1] + u * v0[1] + v * v1[1]))
            elif typ == 1:                                      # ящик: вертикальный луч, выход сверху (слэбы)
                B = C['box'][i]; c0 = B[0:3]; A = B[3:12].reshape(3, 3); h = B[12:15]
                o = np.array([x, 0.0, z]) - c0; lo, hi = -1e9, 1e9; ok = True
                for j in range(3):
                    dy, p = A[j, 1], o @ A[j]
                    if abs(dy) < 1e-9:
                        if abs(p) > h[j]: ok = False; break
                    else:
                        t0, t1 = (-h[j] - p) / dy, (h[j] - p) / dy
                        lo, hi = max(lo, min(t0, t1)), min(hi, max(t0, t1))
                if ok and lo <= hi:
                    top = hi                                    # y выхода луча сверху
                    # верхняя грань проходима, если ось ящика у неё почти вертикальна
                    if np.abs(A[:, 1]).max() > 0.5: out.append(float(top))
            elif typ == 2:
                Y = C['cyl'][i]; ax = Y[3:6]
                if abs(ax[1]) > 0.9 and math.hypot(x - Y[0], z - Y[2]) <= Y[6]:
                    out.append(float(Y[1] + Y[7] + (0 if C['cyl_flat'][i] == 1 else Y[6])))
        return sorted(out)

    def support(self, x, y, z, below, above):
        g = [v for v in self.ground(x, z) if y - below <= v <= y + above]
        return max(g) if g else None


def load_worlds(shr, rooms):
    b, L = cc.load(shr); W = [World('город', cc.parse_col(b, L['col']))]
    if rooms and Path(rooms).exists():
        r = Path(rooms).read_bytes(); assert r[:4] == b'SHI1', f'{rooms}: не SHI1'
        n, = struct.unpack_from('<I', r, 4)
        for k in range(n):
            o = 16 + 128 * k; name = r[o:o + 32].split(b'\0')[0].decode(); off, = struct.unpack_from('<I', r, o + 60)
            if off and r[off:off + 4] == b'COL1': W.append(World(name, cc.parse_col(r, off)))
    return W


def support_any(worlds, x, y, z, below, above):
    """-> (мир, высота опоры) или (ближайшие опоры в столбе, None)"""
    for w in worlds:
        if w.name != 'город' and y > -10: continue              # комнаты — глубоко под городом (y -20..-100)
        if not w.covers(x, z): continue
        s = w.support(x, y, z, below, above)
        if s is not None: return w.name, s
    near = []
    for w in worlds:
        if w.covers(x, z): near += [(w.name, round(v, 2)) for v in w.ground(x, z)]
    return near, None


def points(M):
    """-> [(миссия, фаза, этап, команда, аргумент-локатор)] по всем командам уровня"""
    out = []
    for m in M['missions']:
        for ph in m['phases']:
            for si, st in enumerate([dict(cmds=ph.get('setup', []))] + ph.get('stages', [])):
                for c in st['cmds']:
                    for a in c['args']:
                        if isinstance(a, dict) and 'pos' in a: out.append((m['id'], ph['name'], si - 1, c['op'], a))
    return out


def talks(M):
    """разговоры без SetDialoguePositions: (миссия, фаза, этап, собеседник, место NPC, где стоит игрок — цель прошлого этапа)"""
    out = []
    for m in M['missions']:
        for ph in m['phases']:
            npc, dest = {}, None
            for si, st in enumerate(ph.get('stages', [])):
                ops = {c['op']: c for c in st['cmds']}
                for c in st['cmds']:
                    if c['op'] == 'AddNPC' and len(c['args']) > 1 and isinstance(c['args'][1], dict): npc[c['args'][0].lower()] = c['args'][1]
                di = ops.get('SetDialogueInfo')
                if di and 'SetDialoguePositions' not in ops and dest is not None:
                    a, b = str(di['args'][0]).lower(), str(di['args'][1]).lower()
                    who = b if b in npc else a if a in npc else None
                    if who: out.append((m['id'], ph['name'], si, who, npc[who], dest))
                for c in st['cmds']:
                    if c['op'] == 'SetDestination' and isinstance(c['args'][0], dict): dest = c['args'][0]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--json', required=True); ap.add_argument('--shr', required=True); ap.add_argument('--rooms', default='')
    ap.add_argument('--below', type=float, default=2.0); ap.add_argument('--above', type=float, default=0.5)
    ap.add_argument('--rule', choices=('old', 'new'), default='new')
    a = ap.parse_args()
    M = json.loads(Path(a.json).read_text()); worlds = load_worlds(a.shr, a.rooms)
    print(f'миров коллизии: {len(worlds)} (город + комнат {len(worlds) - 1}); опора: [y - {a.below}, y + {a.above}] м')
    seen, bad, total = {}, [], 0
    for mid, ph, si, op, loc in points(M):
        key = (loc['loc'], op)
        if key in seen: seen[key].append(f'{mid}/{ph}'); continue
        seen[key] = [f'{mid}/{ph}']; total += 1
        x, y, z = loc['pos']
        w, s = support_any(worlds, x, y, z, a.below, a.above)
        if s is None: bad.append((op, loc['loc'], (x, y, z), w, seen[key]))
    print(f'\n1) точки команд миссий: {total} (локатор + команда), без опоры: {len(bad)}')
    for op, name, (x, y, z), near, where in sorted(bad, key=lambda r: (r[0], r[1])):
        print(f'  {op:28s} {name:28s} ({x:8.2f} {y:7.2f} {z:8.2f})  {",".join(sorted(set(where)))[:60]}  опоры в столбе: {near[:4] if near else "нет"}')
    print(f'\n2) разговоры без мест в данных (правило {a.rule}):')
    fails = 0
    for mid, ph, si, who, N, P in talks(M):
        nx, ny, nz = N['pos']; px, py, pz = P['pos']
        dx, dz = px - nx, pz - nz; d = math.hypot(dx, dz) or 1.0
        if d > TALK_NEAR:   # цель прошлого этапа далеко (вход в комнату и т.п.): где стоит игрок, по данным не знаем
            print(f'  ?   {mid}/{ph} этап {si}: {who} у {N["loc"]}, цель прошлого этапа {P["loc"]} за {d:.0f} м — не моделируем'); continue
        qx, qz = nx + dx / d * TALK_DIST, nz + dz / d * TALK_DIST
        wq, sq = support_any(worlds, qx, py, qz, TALK_DOWN, TALK_UP)
        if a.rule == 'old' or sq is not None: fx, fz, fy, how = qx, qz, sq, 'на линии в 2.45 м'
        else: fx, fz, fy, how = px, pz, support_any(worlds, px, py, pz, TALK_DOWN, TALK_UP)[1], 'стоит у цели (на линии опоры нет)'
        ok = fy is not None; fails += not ok
        print(f'  {"ok " if ok else "НЕТ"} {mid}/{ph} этап {si}: {who} у {N["loc"]} ({nx:.1f} {nz:.1f}), игрок у {P["loc"]} ({px:.1f} {pz:.1f}), '
              f'd {d:.1f} м -> {how} ({fx:.1f} {fz:.1f}), опора {"%.2f" % fy if ok else "нет"}')
    print(f'\nитог: без опоры точек {len(bad)}; разговоров, где игрок встаёт без опоры: {fails}')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
