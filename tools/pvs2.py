#!/usr/bin/env python3
"""PVS по курсу в горячих клетках (секция PV2S в конце level.shr, после PVS1; engine: viewer/pvs2.h, PVS_SECTOR_OLD=1 — выкл.).
Горячая клетка PVS1 (20 м) — где модель кадра PSP (tools/autoexplore/tracks/frame_model.py, гибрид) выше порога. Для каждой: 8 секторов курса по 45°, список
кусков сектора = всё, что хоть одним пикселем видно из выборки поз клетки (глаз: углы и центр, высоты над слоями карты высот, курсы сектора ±42°, наклон взгляда),
затем доводка: свежие контрольные позы (курс в пределах ±30° от центра сектора — гистерезис движка), любой недостающий кусок добавляется, пока контроль не даст 0.
Видимость — настоящая растеризация города хост-рендером (rast.c render_ids): непрозрачные куски закрывают, альфа/смешанные не закрывают и считаются видимыми, если прошли глубину.
Формат PV2S (заголовок 32 Б): 'PV2S', u32 nhot, u32 nsec (8), u32 npool, u32 sig (FNV-1a по nv, ni всех кусков: другой экспорт уровня — секция игнорируется), 12 Б нулей; u32 cell[nhot] (gz*W+gx PVS1, по возрастанию); {u32 start, u32 n}[nhot*nsec]; u16 pool[npool] (номера кусков).
  python3 tools/pvs2.py LEVEL.shr OUT.shr [--level N] [--max-hot 120] [--threshold 29] [--check 80]   (OUT = копия LEVEL + секция; без OUT — только отчёт)"""
import argparse, ctypes, math, random, struct, sys, time
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; TR = ROOT / 'tools/autoexplore/tracks'; sys.path.insert(0, str(TR))
import hostshot as H, frame_model as FM
P = ctypes.POINTER
H.LIB.render_ids.argtypes = [ctypes.c_int, P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_int), P(ctypes.c_float), ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float,
                             P(ctypes.c_float), P(ctypes.c_float), P(ctypes.c_float), P(ctypes.c_float), P(ctypes.c_int), P(ctypes.c_float), P(ctypes.c_uint8)]
H.LIB.render_ids.restype = ctypes.c_int
def ptr(a, t): return a.ctypes.data_as(P(t))
NSEC = 8; SEC_STEP = 2 * math.pi / NSEC; SEC_SAMPLE = math.radians(48); SEC_TEST = math.radians(30)
class World:
    def __init__(s, path, size=(480, 272), fovy=60.0):
        s.S = H.Shooter(path, size, fovy); S = s.S; s.W, s.Hh = size; s.fy = S.fy; s.fx = S.fx; r = S.rec; s.npc = len(r)
        city = S.city; tris = []; s.pstart = np.zeros(s.npc, np.int32); s.pcount = np.zeros(s.npc, np.int32); n = 0
        for pi in city:
            T, _ = S.piece_tris(int(pi))
            if T is None: continue
            s.pstart[pi] = n; s.pcount[pi] = len(T); n += len(T); tris.append(T.reshape(-1, 9))
        s.tri = np.ascontiguousarray(np.concatenate(tris), np.float32); s.pflags = np.ascontiguousarray((r['flags'] & 3).astype(np.int32)); s.cen = S.cen; s.rad = S.rad
    def visible(s, eye, yaw, pitch, cand):
        """Номера кусков, видимых из позы (eye, курс yaw, наклон pitch): среди cand."""
        fw = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)]); up = np.array([0, 1.0, 0]); sv = np.cross(fw, up); sv /= np.linalg.norm(sv); uv = np.cross(sv, fw)
        dv = s.cen[cand] - eye; dist = np.linalg.norm(dv, axis=1); fwd = dv @ fw; side = np.sqrt(np.maximum(0, dist ** 2 - fwd ** 2)); rad = s.rad[cand]
        sel = cand[(dist - rad <= 250.0) & ~(side * .60 - fwd * .80 > rad)].astype(np.int32)
        idb = np.full((s.Hh, s.W), -1, np.int32); zb = np.zeros((s.Hh, s.W), np.float32); mark = np.zeros(s.npc, np.uint8)
        e = eye.astype(np.float32); a = sv.astype(np.float32); b = uv.astype(np.float32); c = fw.astype(np.float32)
        H.LIB.render_ids(len(sel), ptr(sel, ctypes.c_int), ptr(s.pstart, ctypes.c_int), ptr(s.pcount, ctypes.c_int), ptr(s.pflags, ctypes.c_int), ptr(s.tri, ctypes.c_float), s.W, s.Hh, s.fx, s.fy, 0.3,
                         ptr(e, ctypes.c_float), ptr(a, ctypes.c_float), ptr(b, ctypes.c_float), ptr(c, ctypes.c_float), ptr(idb, ctypes.c_int), ptr(zb, ctypes.c_float), ptr(mark, ctypes.c_uint8))
        v = set(np.unique(idb[idb >= 0]).tolist()); v.update(np.nonzero(mark)[0].tolist()); return v
    def layers(s, x, z):
        S = s.S; gx, gz = int((x - S.hox) // S.hcell), int((z - S.hoz) // S.hcell)
        if not (0 <= gx < S.hW and 0 <= gz < S.hH): return []
        h = S.hm[gz, gx]; return [float(v) * .01 for v in h if v != -32768]
def piece_sig(S):
    h = 2166136261
    for v in np.concatenate([S.rec['nv'].astype(np.uint32), S.rec['ni'].astype(np.uint32)]).tolist(): h = ((h ^ (v & 0xffffffff)) * 16777619) & 0xffffffff
    return h
def hot_cells(S, lv, pkg_cache, threshold, max_hot):
    X, Z, KM, KW = FM.city_table(S.path, pkg_cache); ox, oz, cell, W, Hh, ent, pl = S.pvs; out = []
    for x, z, km, kw in zip(X, Z, KM, KW):
        gx, gz = int((x - ox) // cell), int((z - oz) // cell)
        if not (0 <= gx < W and 0 <= gz < Hh) or ent[gz * W + gx][1] == 0xFFFFFFFF: continue
        est = FM.BASE[lv] + 6.0 + FM.K_KT * km * FM.CORR.get(lv, 1.0) * 0.725   # +6 мс: типичные ИИ-машины и трафик в миссии
        if est > threshold: out.append((est, gz * W + gx, gx, gz))
    out.sort(reverse=True); return out[:max_hot]
def poses_for(Wd, ox, oz, cell, gx, gz, rng, n, jitter=True):
    out = []
    while len(out) < n:
        x = ox + (gx + rng.random()) * cell; z = oz + (gz + rng.random()) * cell; ly = Wd.layers(x, z)
        if not ly: continue
        out.append((x, rng.choice(ly) + rng.uniform(1.5, 5.8), z))
    return out
def build_cell(Wd, S, gx, gz, rng, check_n, log):
    ox, oz, cell, W, Hh, ent, pl = S.pvs; cand = np.array(sorted(set(S.pvs_list(ox + (gx + .5) * cell, oz + (gz + .5) * cell).astype(np.int64).tolist())), np.int64)
    lists = [set() for _ in range(NSEC)]; t0 = time.time()
    grid = [(ox + (gx + fx) * cell, oz + (gz + fz) * cell) for fx in (.15, .5, .85) for fz in (.15, .5, .85)]
    for (x, z) in grid:
        for ly in Wd.layers(x, z):
            for h in (2.2, 4.2):
                eye = np.array([x, ly + h, z])
                for s_ in range(NSEC):
                    for k in (-1.0, -.5, 0, .5, 1.0): lists[s_] |= Wd.visible(eye, s_ * SEC_STEP + k * SEC_SAMPLE, -0.2, cand)
    added = 0; miss_last = 0
    for rnd in range(8):   # доводка: контрольные позы, курс ±30° от центра сектора
        miss = 0
        for (x, y, z) in poses_for(Wd, ox, oz, cell, gx, gz, rng, check_n):
            s_ = rng.randrange(NSEC); yaw = s_ * SEC_STEP + rng.uniform(-SEC_TEST, SEC_TEST); pitch = rng.uniform(-0.35, 0.05); eye = np.array([x, y, z])
            full = Wd.visible(eye, yaw, pitch, cand); lack = full - lists[s_]
            if lack: miss += len(lack); added += len(lack); lists[s_] |= lack
        miss_last = miss
        if miss == 0 and rnd > 0: break
    return lists, cand, dict(added=added, last_missing=miss_last, sec=time.time() - t0)
def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0]); ap.add_argument('level'); ap.add_argument('out', nargs='?'); ap.add_argument('--section', help='записать только секцию PV2S в отдельный файл (pv2s.shr рядом с level.shr; движок читает его при подписи уровня)'); ap.add_argument('--level-no', type=int, default=1); ap.add_argument('--max-hot', type=int, default=100)
    ap.add_argument('--threshold', type=float, default=29.0); ap.add_argument('--check', type=int, default=80); ap.add_argument('--seed', type=int, default=1); ap.add_argument('--cache', default='/tmp/ae_city'); ap.add_argument('--only', type=int, default=0)
    a = ap.parse_args(); t0 = time.time(); Wd = World(a.level); S = Wd.S; rng = random.Random(a.seed)
    hot = hot_cells(S, a.level_no, a.cache, a.threshold, a.max_hot)
    if a.only: hot = hot[:a.only]
    print(f'L{a.level_no}: горячих клеток {len(hot)} (порог {a.threshold} мс, оценка гибрида); мир загружен за {time.time()-t0:.0f} с', flush=True)
    ox, oz, cell, W, Hh, ent, pl = S.pvs; res = []
    for i, (est, ci, gx, gz) in enumerate(hot):
        lists, cand, info = build_cell(Wd, S, gx, gz, rng, a.check, print); full = len(S.pvs_list(ox + (gx + .5) * cell, oz + (gz + .5) * cell))
        res.append((ci, [np.array(sorted(l), np.uint16) for l in lists])); mean = np.mean([len(l) for l in lists])
        print(f'  {i+1}/{len(hot)} клетка ({gx},{gz}) оценка {est:.1f} мс: PVS {full} кусков, секторы в среднем {mean:.0f} ({100*(1-mean/full):.0f} % меньше), доведено {info["added"]}, контроль последнего круга {info["last_missing"]}, {info["sec"]:.0f} с', flush=True)
    res.sort(key=lambda r: r[0]); nhot = len(res); pool = []; sec = []
    for ci, ls in res:
        for l in ls: sec.append((len(pool), len(l))); pool.extend(l.tolist())
    blob = b'PV2S' + struct.pack('<4I', nhot, NSEC, len(pool), piece_sig(S)) + b'\0' * 12 + struct.pack('<%dI' % nhot, *[r[0] for r in res]) + b''.join(struct.pack('<II', s_, n_) for s_, n_ in sec) + struct.pack('<%dH' % len(pool), *pool)
    blob += b'\0' * (-len(blob) % 16)
    print(f'PV2S: {nhot} клеток, пул {len(pool)} записей, блок {len(blob)/1024:.0f} КБ')
    if a.section: Path(a.section).write_bytes(blob); print('секция записана', a.section)
    if a.out:
        data = bytearray(S.b); 
        if len(data) % 16: data += b'\0' * (-len(data) % 16)
        Path(a.out).write_bytes(bytes(data) + blob); print('записано', a.out)
if __name__ == '__main__': main()
