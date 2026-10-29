#!/usr/bin/env python3
"""Камеры разговора (правки Роба 40 и 38): проверка в экранных координатах кадра 16:9, независимо от движка.

Сцены — из данных диска уровня 1: каждый разговор с местами в данных (SetDialoguePositions этапа, у бонус-миссий
SetBonusMissionDialoguePos из leveli.mfk), план на реплику (SetConversationCam), лучшая сторона (SetCamBestSide), кто
говорит реплику (имя файла голоса conversations/c_<разговор>_<N>_..._<кто>_l1[миссия].rsd), лицо — сустав Head модели
+ 0.08 м (build/chars/*.chr, у Гомера 1.5 м), рост — габарит модели.

На каждую реплику: ОЖИДАЕМЫЙ герой плана считается здесь, не берётся у движка — из данных (npc_* — собеседник, pc_* —
игрок) или по правилу порта (реплика 0 — собеседник общим планом, дальше — говорящий). Проверки кадра:
  лицо героя в кадре и вне полос «кино» (x 0.08–0.92, y 0.16–0.84), перед камерой;
  герой лицом к камере (он смотрит на собеседника: угол до камеры по горизонтали меньше 76°);
  лицо героя не закрыто собеседником (отрезок глаз -> лицо дальше 0.22 м от оси его тела: радиус головы моделей 0.17–0.20 м) — «Мардж за Гомером не видно»;
  общий план (*_far): оба целиком в кадре (ноги и макушки);
  все планы разговора по одну сторону оси, и по лучшей стороне, если она в данных (правило 180°, как у записи PS2);
  ближняя плоскость кадра не режет ни одного из двоих (голова и грудь дальше неё на 0.3 м): иначе на крупном плане затылок
  слушающего срезан и его лицо видно «сквозь» голову (так было с ближней плоскостью города 1.5 м — эмулятор 29.09).

    python tests/camera/convcam_check.py scenes > IN.txt                 вход для tests/camera/convcam_host.c
    python tests/camera/convcam_check.py host OUT.txt [--expect-red]     проверка выхода хоста
    python tests/camera/convcam_check.py emu smoke.txt [--expect-red]    проверка строк TALKCAM эмулятора (камера, как нарисована)"""
import math, re, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools')); sys.path.insert(0, str(ROOT / 'tools/missions'))
GAME = (ROOT / 'hit-and-run-web/source/game').resolve()
LV = GAME / 'scripts/missions/level01'
PC_CODES = {'hom'}          # голос игрока уровня 1 (Гомер)
HOMER_FACE, HOMER_H = 1.5, 1.8
FRAME_X, FRAME_Y = (0.08, 0.92), (0.16, 0.84)
FACE_ANGLE = 76.0
CAPSULE_R = 0.22   # радиус головы моделей (0.17–0.20 м) + 2 см; у крупного плана PS2 голова слушающего вплотную к лицу говорящего


def clean(t): return '\n'.join(l.split('//')[0] for l in t.splitlines())


def models():
    import char_export as CE
    out = {}
    for p in sorted((ROOT / 'build/chars').glob('*.chr')):
        m = CE.read_chr(p); pal, world = CE.palette(m, [(j['q'], j['t']) for j in m['joints']])
        head = next((float(world[i][1, 3]) for i, j in enumerate(m['joints']) if j['name'] == 'Head'), 0.72 * m['bbox'][4])
        out[p.stem] = (head + 0.08, float(m['bbox'][4]))
    return out


def speakers(conv, code):
    files = [f.name for f in (GAME / 'conversations').glob(f'c_{conv}_*_l1*.rsd')]
    for suffix in (f'_l1{code}.rsd', '_l1.rsd'):
        got = {}
        for f in files:
            m = re.match(rf'c_{re.escape(conv)}_(\d+)_[a-z]+_([a-z]+)_l1', f)
            if m and f.endswith(suffix): got[int(m.group(1))] = m.group(2)
        if got: return [got[k] for k in sorted(got)]
    return []


def scenes():
    import compile as C
    locs = {}
    for d in C.Compiler(1).p3d_locs.values():
        for k, L in d.items(): locs.setdefault(k, np.array(L.pos))
    L = lambda n: locs.get(str(n).lower())
    heads = models(); out = []
    def add(name, a, b, pa, pb, conv, code, cams, best):
        pcFirst = a.lower() == 'homer'; npc = b if pcFirst else a
        P, N = (L(pa), L(pb)) if pcFirst else (L(pb), L(pa))
        if P is None or N is None: return
        sp = speakers(conv, code)
        if not sp: return
        fh, h = heads.get(npc.lower(), (HOMER_FACE, 1.8))
        B = L(best) if best else None
        out.append(dict(name=name, npc=npc, conv=conv, pc=P, npcpos=N, pchead=HOMER_FACE, npchead=fh, pch=HOMER_H, npch=h,
                        best=B, cams=cams, pcs=[1 if s in PC_CODES else 0 for s in sp], room=P[1] < -10 or N[1] < -10))
    for f in sorted(LV.glob('*i.mfk')):
        cm = re.match(r'([a-z]+\d)', f.name)
        if not cm: continue   # leveli (бонус — ниже), demoi (демо)
        code = cm.group(1)
        for k, st in enumerate(re.split(r'AddStage', clean(f.read_text(errors='replace')))):
            di = re.search(r'SetDialogueInfo\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"', st)
            dp = re.search(r'SetDialoguePositions\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"', st)
            if not di or not dp: continue
            cams = {}
            for i, n in re.findall(r'SetConversationCam\s*\(\s*(\d+)\s*,\s*"([^"]+)"', st): cams[int(i)] = n
            bs = re.search(r'SetCamBestSide\s*\(\s*"([^"]+)"', st)
            add(f'{f.stem}.{k}', di.group(1), di.group(2), dp.group(1), dp.group(2), di.group(3), code, cams, bs.group(1) if bs else None)
    li = clean((LV / 'leveli.mfk').read_text(errors='replace'))
    for m in re.finditer(r'AddNPCCharacterBonusMission\s*\(\s*"([^"]+)"\s*,\s*"[^"]*"\s*,\s*"[^"]*"\s*,\s*"([^"]+)"\s*,\s*"[^"]*"\s*,\s*"([^"]+)"', li):
        npc, code, conv = m.groups()
        pos = re.search(rf'SetBonusMissionDialoguePos\s*\(\s*"{code}"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"', li)
        if not pos: continue
        cams = {int(i): n for i, n in re.findall(rf'SetConversationCam\s*\(\s*(\d+)\s*,\s*"([^"]+)"\s*,\s*"{code}"', li)}
        bs = re.search(rf'SetCamBestSide\s*\(\s*"([^"]+)"\s*,\s*"{code}"', li)
        add(f'leveli.{code}', 'homer', npc, pos.group(1), pos.group(2), conv, code, cams, bs.group(1) if bs else None)
    return out


def expected_on_pc(sc, line, pc):
    shot = None
    for i in range(line + 1):
        if i in sc['cams']: shot = sc['cams'][i]
    if shot: return shot.startswith('pc_'), shot.endswith('_far')
    if line == 0: return False, True
    return bool(pc), False


def project(eye, look, fovy, p):
    f = look - eye; f = f / np.linalg.norm(f); r = np.cross(f, [0, 1, 0]); r /= np.linalg.norm(r); u = np.cross(r, f)
    q = p - eye; z = q @ f
    if z <= 1e-3: return None
    t = math.tan(math.radians(fovy) / 2)
    return 0.5 + 0.5 * (q @ r) / z / (t * 16 / 9), 0.5 - 0.5 * (q @ u) / z / t


def seg_dist(p0, p1, q0, q1):
    """наименьшее расстояние между отрезками p0p1 и q0q1 (выборкой, 200 x 200 — для гейта достаточно)"""
    s = np.linspace(0, 1, 60)[:, None]; A = p0 + (p1 - p0) * s; B = q0 + (q1 - q0) * s
    return float(np.min(np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2)))


def check_pose(eye, look, fovy, P, N, ph, nh, pH, nH, on_pc, far, near=None):
    """ошибки кадра одной реплики (пусто — ок)"""
    X, Y, xh, yh, xH, yH = (P, N, ph, nh, pH, nH) if on_pc else (N, P, nh, ph, nH, pH)
    errs = []; face = X + [0, xh, 0]
    pr = project(eye, look, fovy, face)
    if pr is None: return ['лицо героя за камерой']
    if not (FRAME_X[0] <= pr[0] <= FRAME_X[1] and FRAME_Y[0] <= pr[1] <= FRAME_Y[1]): errs.append(f'лицо героя вне кадра ({pr[0]:.2f}, {pr[1]:.2f})')
    fwd = (Y - X)[[0, 2]]; to = (eye - face)[[0, 2]]
    ang = math.degrees(math.acos(np.clip(fwd @ to / (np.linalg.norm(fwd) * np.linalg.norm(to) + 1e-9), -1, 1)))
    if ang > FACE_ANGLE: errs.append(f'герой к камере спиной/боком ({ang:.0f}°)')
    d = seg_dist(eye, face, Y + [0, 0.3, 0], Y + [0, yH, 0])
    if d < CAPSULE_R: errs.append(f'лицо героя закрыто собеседником (просвет {d:.2f} м)')
    if near is not None:
        f = look - eye; f = f / np.linalg.norm(f)
        for Z, fh, H, who in ((P, ph, pH, 'игрока'), (N, nh, nH, 'собеседника')):
            for q in (Z + [0, fh, 0], Z + [0, 0.55 * H, 0]):
                if (q - eye) @ f - 0.3 < near: errs.append(f'ближняя плоскость {near:.2f} м режет {who}'); break
            else: continue
            break
    if far:
        for Z, H in ((P, pH), (N, nH)):
            for q in (Z, Z + [0, H, 0]):
                p = project(eye, look, fovy, q)
                if p is None or not (0.02 <= p[0] <= 0.98 and 0.10 <= p[1] <= 0.92): errs.append('общий план: не оба целиком в кадре'); break
            else: continue
            break
    return errs


def side_of(P, N, eye):
    a = (N - P)[[0, 2]]; w = (eye - (P + N) / 2)[[0, 2]]
    return 1 if (a[1] * w[0] - a[0] * w[1]) >= 0 else -1   # слева от оси P->N (up x a) = +1


def main():
    mode = sys.argv[1]
    if mode == 'scenes':
        for sc in scenes():
            B = sc['best']; cams = [sc['cams'].get(i, '-') for i in range(max(sc['cams'], default=-1) + 1)]
            print('S', sc['name'], *[f'{v:.4f}' for v in sc['pc']], *[f'{v:.4f}' for v in sc['npcpos']], f"{sc['pchead']:.3f}", f"{sc['npchead']:.3f}",
                  1 if B is not None else 0, *([f'{v:.4f}' for v in B] if B is not None else ['0', '0', '0']), len(cams), *cams, len(sc['pcs']), *sc['pcs'])
        return 0
    red = '--expect-red' in sys.argv
    fails, notes, n = [], [], 0
    if mode == 'host':
        S = {sc['name']: sc for sc in scenes()}; sides = {}
        for r in open(sys.argv[2]).read().splitlines():
            if r.startswith('BAD'): fails.append(r); continue
            if not r.startswith('P '): continue
            p = r.split(); sc = S[p[1]]; line = int(p[2]); eye = np.array(list(map(float, p[6:9]))); look = np.array(list(map(float, p[9:12])))
            on_pc, far = expected_on_pc(sc, line, sc['pcs'][line])
            e = check_pose(eye, look, float(p[12]), sc['pc'], sc['npcpos'], sc['pchead'], sc['npchead'], sc['pch'], sc['npch'], on_pc, far, float(p[13]))
            sd = side_of(sc['pc'], sc['npcpos'], eye); sides.setdefault(p[1], set()).add(sd)
            if sc['best'] is not None and sd != side_of(sc['pc'], sc['npcpos'], sc['best']): e.append('камера не на лучшей стороне (SetCamBestSide)')
            n += 1
            tag = f"{p[1]} ({sc['npc']}) реплика {line} {p[3]}{' [комната: в игре камера комнаты]' if sc['room'] else ''}"
            if e: fails.append(f'{tag}: ' + '; '.join(e))
            else: notes.append(tag)
        for k, v in sides.items():
            if len(v) > 1: fails.append(f'{k}: планы по разные стороны оси (правило 180°)')
    else:
        rows = [r for r in open(sys.argv[2]).read().splitlines() if r.startswith('TALKCAM ')]
        sides = {}; S = scenes(); seen = set()
        for r in rows:
            kv = dict(x.split('=', 1) for x in r.split()[1:])
            v3 = lambda k: np.array(list(map(float, kv[k].split(','))))
            shot = kv['shot']; line, pc = int(kv['line']), int(kv['pc']); conv = kv.get('conv', '')
            sc = next((c for c in S if c['conv'].lower() == conv.lower() and c['npc'].lower() == kv['npc'].lower()), None)   # разговор из данных
            if sc is not None: exp_pc, far = expected_on_pc(sc, line, pc)
            else: exp_pc, far = (bool(pc) if line > 0 else False), line == 0   # мест в данных нет — правило порта
            if (shot.startswith('pc_'), shot.endswith('_far')) != (bool(exp_pc), far) and (conv, line) not in seen:
                fails.append(f"{conv} реплика {line}: план {shot}, по данным {'pc' if exp_pc else 'npc'}_{'far' if far else 'near'}")
            seen.add((conv, line))
            e = check_pose(v3('eye'), v3('look'), float(kv['fovy']), v3('pcpos'), v3('npcpos'), float(kv['pchead']), float(kv['npchead']),
                           float(kv['pch']), float(kv['npch']), exp_pc, far, float(kv['near']))
            sd = side_of(v3('pcpos'), v3('npcpos'), v3('eye')); sides.setdefault(conv, set()).add(sd)
            if sc is not None and sc['best'] is not None and sd != side_of(sc['pc'], sc['npcpos'], sc['best']):
                e.append('камера не на лучшей стороне (SetCamBestSide)')
            n += 1
            tag = f"{conv} ({kv['npc']}) t={kv['t']} реплика {line} {shot}{'' if sc is not None else ' [мест в данных нет]'}"
            if e: fails.append(f'{tag}: ' + '; '.join(e))
            else: notes.append(tag)
        for k, v in sides.items():
            if len(v) > 1: fails.append(f'{k}: планы по разные стороны оси (правило 180°)')
        if not rows: fails.append('нет строк TALKCAM: разговор не снимала камера разговора')
        allrows = open(sys.argv[2], errors='replace').read().splitlines()
        lb = [r for r in allrows if r.startswith('LETTERBOX ')]
        if not any('on=1 prompt=2' in r for r in lb): fails.append('экран разговора перед миссией без подписей «✕ Start Mission / △ Cancel» (LETTERBOX prompt=2)')
        # правка Роба 55: на разговор — шины «Letterbox» тюнера диска (музыка 0.29, SND_MODE_LETTERBOX = 3), музыка места играет
        # дальше (не «-»), после разговора режим под полосами возвращается
        for r in lb:
            m = re.search(r' on=(\d) .*snd=(\d+) music=(\S+)', r)
            if not m: fails.append(f'LETTERBOX без snd/music ({r.strip()}) — правка 55 не проверена'); break
            on, snd, mus = int(m.group(1)), int(m.group(2)), m.group(3)
            if on and snd != 3: fails.append(f'разговор без приглушения: режим звука {snd}, не Letterbox ({r.strip()}) — правка 55')
            if not on and snd == 3: fails.append(f'после разговора режим Letterbox не снят ({r.strip()}) — правка 55')
            if mus == '-': fails.append(f'музыка остановилась ({r.strip()}) — должна играть дальше, правка 55')
        if lb: notes.append('звук разговора: ' + '; '.join(re.sub(r'^LETTERBOX ', '', r.strip()) for r in lb[:4]))
        tm = lambda r: float(re.search(r'(?<![A-Za-z_])t=([0-9.]+)', r).group(1))   # «start=1» — не время
        for i, r in enumerate(allrows):   # X в разговоре перед миссией: разговор кончается, сразу брифинг (LetterBoxButtons.pag)
            if r.startswith('TALKSKIP '):
                nxt = next((x for x in allrows[i + 1:] if x.startswith('MSN briefing ')), None)
                if not nxt or tm(nxt) - tm(r) > 1.0: fails.append(f'X в разговоре ({r.strip()}): брифинг не пришёл сразу')
                else: notes.append(f'пропуск X: {r.strip()} -> {nxt.strip()[:40]}')
    if red:
        ok = bool(fails) and n > 0
        print(('PASS (красный пойман): ' if ok else 'FAIL (красный не пойман): ') + (fails[0] if fails else f'{n} кадров без ошибок'))
        return 0 if ok else 1
    print(('FAIL: ' + fails[0]) if fails else f'PASS: {n} кадров разговоров — лицо говорящего в кадре, к камере, не закрыто собеседником')
    for f in fails[1:12]: print('  ещё: ' + f)
    if len(fails) > 12: print(f'  … ещё {len(fails) - 12}')
    for t in notes[:40]: print('  ок: ' + t)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
