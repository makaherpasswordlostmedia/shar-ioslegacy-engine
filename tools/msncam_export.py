#!/usr/bin/env python3
"""Камеры старта этапов миссий — «наезды» (правка Роба 40, 28.09: «не хватает этих всех камер наездов»).

Данные диска: скрипт фазы миссии (mNsdi.mfk — вступление сюжетной миссии, srNi.mfk / grNi.mfk — уличные гонки и гонка
на ставку) задаёт SetMissionStartCameraName("missionKcamShape") (+ SetMissionStartMulticontName) или
SetAnimatedCameraName("raceKcamShape") (+ SetAnimCamMulticontName); файл камеры — LoadP3DFile(".../missionKcam.p3d") в
скрипте загрузки той же фазы (mNsdl.mfk, srNl.mfk); в p3d — камера 0x2200 и анимация CAM_<камера> (каналы TRAN, LOOK,
UP, FOV, NCLP, FCLP; 30 кадров/с, 2–4 с). Конец каждой камеры — в 3–10 м от места, куда сценарий ставит игрока на старте
этой фазы (SetMissionResetPlayer*, у гонок — PlacePlayerCar): камера прилетает к игроку (сверка — tests/camera/msncam_check.py).
Имена камер повторяются (mission6camShape есть и в level04/mission6cam.p3d для m1sd, и в level01 для m6sd), поэтому
ключ камеры — имя фазы (SelectMission: "m1sd", "sr1").

    python tools/msncam_export.py [--level 1] [--out build/msncam.shr]

Формат MCM1 (little endian): 'MCM1', u32 камер, u32 версия (2), u32 0; камера 64 Б: имя камеры[32], i32 миссия (N из mN,
-1 — не сюжетная), u32 кадров, f32 кадров/с, u32 смещение кадров от начала файла, фаза[16] (имя SelectMission, версия 2;
у версии 1 — нули); кадр 40 Б: позиция xyz, взгляд xyz (единичный), верх xyz, FOV (радианы, по горизонтали кадра 4:3, как
FE_Camera меню — Hor+ в движке). Координаты движка (z отзеркален). Движок: viewer/msncam.c."""
import argparse, re, struct, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools')); sys.path.insert(0, str(ROOT / 'hit-and-run-web/tools'))
from p3d import read   # noqa: E402
import frontend3d_export as F   # noqa: E402  разбор анимации камеры (anims, sample) — тот же, что у камеры меню

GAME = (ROOT / 'hit-and-run-web/source/game').resolve()
VERSION = 2


def _clean(text):
    return '\n'.join(l.split('//')[0] for l in text.splitlines())   # закомментированные строки не в счёт


def cameras(level):
    """[(миссия N или -1, файл скрипта, камера, p3d, фаза)] — все фазы уровня с камерой старта в данных"""
    sd = GAME / 'scripts/missions' / f'level0{level}'
    out = []
    # Перепись миссий 04.10: скрипт фазы ищется по SelectMission, как в компиляторе (tools/missions/compile.py script_for): на диске
    # часть файлов переставлена — сценарий L6 sr1 лежит в m8sdl.mfk, L7 gr1 в e3m1sdl.mfk; по маске *i.mfk их камеры старта
    # не попадали в пакет. Свой файл (<фаза>i.mfk) — первым, чужой — только если своего нет; список загрузки — <фаза>l.mfk
    cand = {}
    for f in sorted(sd.glob('*.mfk')):
        s = _clean(f.read_text(errors='replace'))
        sel = re.search(r'SelectMission\s*\(\s*"([^"]+)"', s)
        if sel: cand.setdefault(sel.group(1).lower(), []).append((f, s, sel))
    picks = []
    for ph, lst in cand.items():
        own = [x for x in lst if x[0].name.lower() == ph + 'i.mfk']
        picks.append((own or lst)[0] + (ph,))
    for f, s, sel, ph in sorted(picks, key=lambda x: x[0].name):
        cam = re.search(r'SetMissionStartCameraName\s*\(\s*"([^"]+)"', s) or re.search(r'SetAnimatedCameraName\s*\(\s*"([^"]+)"', s)
        if not cam: continue
        load = sd / (ph + 'l.mfk')   # mNsd -> mNsdl.mfk, sr1 -> sr1l.mfk (у переставленных — свой список загрузки фазы)
        p3d = None
        if load.exists():
            for mm in re.finditer(r'LoadP3DFile\s*\(\s*"([^"]+)"', _clean(load.read_text(errors='replace'))):
                if 'cam' in mm.group(1).lower(): p3d = GAME / mm.group(1).replace('\\', '/')
        m = re.fullmatch(r'm(\d+)(sd)?', sel.group(1).lower())
        out.append((int(m.group(1)) if m else -1, f.name, cam.group(1), p3d, sel.group(1)))
    # Правка Роба 166 (01.10: «после того как появляется машина, камера-мув: сначала на тебя, потом на машину и обратно на
    # тебя»): level.mfk всех уровней грузит LoadP3DFile("art\phonecamera.p3d") — камера phonecameraShape, анимация
    # CAM_phonecameraShape 70 кадров @30 (2.3 с): глаз почти стоит (−5.1, −0.5, −4.1), взгляд от будки уходит на 57° к месту
    # машины (кадры 29–34), держит и возвращается. Координаты — НЕ мира, а будки: фаза "phone", движок ставит кадры осями
    # локатора будки (viewer/main.c phoneCamFrame). Хранятся, как все, с отзеркаленным z (оси кадра движок берёт под это)
    lv = sd / 'level.mfk'
    if lv.exists():
        for mm in re.finditer(r'LoadP3DFile\s*\(\s*"([^"]*phonecamera\.p3d)"', _clean(lv.read_text(errors='replace')), re.I):
            out.append((-1, lv.name, 'phonecameraShape', GAME / mm.group(1).replace('\\', '/'), 'phone')); break
    return out


def frames(p3d, cam):
    A = F.anims(read(p3d)); key = 'CAM_' + cam
    if key not in A: key = next((k for k in A if k.lower() == key.lower()), None)
    if not key: return None
    typ, nfr, fps, groups = A[key]; ch = groups[key] if key in groups else next(iter(groups.values()))
    rows = []
    for f in range(nfr):
        pos = F.sample(*ch['TRAN'], f); look = F.sample(*ch['LOOK'], f); up = F.sample(*ch['UP'], f)
        look = look / np.linalg.norm(look); up = up / np.linalg.norm(up); fov = float(F.sample(*ch['FOV'], f)[0])
        rows.append(np.r_[pos * [1, 1, -1], look * [1, 1, -1], up * [1, 1, -1], fov])
    return nfr, fps, np.array(rows, np.float32)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--level', type=int, default=1); ap.add_argument('--out', default=str(ROOT / 'build/msncam.shr'))
    a = ap.parse_args()
    cams, seen = [], set()
    for mission, script, cam, p3d, phase in cameras(a.level):
        if phase.lower() in seen or not p3d or not p3d.exists(): continue
        fr = frames(p3d, cam)
        if not fr: print(f'{phase}: в {p3d.name} нет анимации CAM_{cam}'); continue
        seen.add(phase.lower()); cams.append((mission, cam, *fr, phase))
        nfr, fps, R = fr
        print(f'{phase} ({script}): {cam} из {p3d.parent.name}/{p3d.name}: {nfr} кадров, {fps:g}/с, от {np.round(R[0, :3], 1)} к {np.round(R[-1, :3], 1)}')
    head = b'MCM1' + struct.pack('<3I', len(cams), VERSION, 0)
    off = len(head) + 64 * len(cams); recs, body = b'', b''
    for mission, cam, nfr, fps, R, phase in cams:
        recs += struct.pack('<32siIfI16s', cam.encode()[:31], mission, nfr, fps, off + len(body), phase.encode()[:15]); body += R.tobytes()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_bytes(head + recs + body)
    print('->', a.out, len(head + recs + body), 'Б')


if __name__ == '__main__':
    main()
