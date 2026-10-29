#!/usr/bin/env python3
"""Откуда числа камер разговора (viewer/convcam.c, правка Роба 40): подбор по кадрам записи PS2.

Геометрии планов npc_far / pc_near / ... в данных диска нет (она в коде оригинала), поэтому — ПРАВИЛО ПОРТА по эталону PS2
(tools/ps2ref, ролик bziOipI4gDI, build/ps2ref/external/yt-bziOipI4gDI.mp4; кадр 4:3 = 960 x 720 после обрезки полей).
Пиксели сняты глазом по сетке 96 x 72 (ffmpeg crop=960:720:160:0,drawgrid) — макушка и ноги героев:
  90.0 с  m0sd реплика 0 (Мардж), npc_far: Мардж 310/178 (макушка причёски) 315/495 (ноги); Гомер 672/245, 680/590
  97.5 с  m0sd реплика 1 (Гомер), pc_near: Гомер 565/155, 590/575; ожерелье Мардж (шея 1.30 м) 345/515
  650  с  m2 reward реплика 1 (Нед), npc_near: Нед 370/112, 335/575; макушка Гомера 490/180
  273  с  m1sd реплика 0, npc_far (другая лучшая сторона — зеркально): Гомер 275/240, 285/590; Мардж 650/178, 650/495 — проверка
Места — SetDialoguePositions (level1_homer_walkto, m1_marge_sd; m2_homer_ned, m2_ned_sd), лучшая сторона — SetCamBestSide,
рост — модели (Гомер 1.80, Мардж 2.11 с причёской, Нед 1.87). Неизвестные: глаз (назад, вбок, высота), взгляд (доля оси,
высота), вертикальный FOV кадра 4:3 (общий план сходится при 38–40°, взят 40° для обоих планов).

    python tools/convcam_fit.py        -> числа FAR_* / NEAR_* и невязки в пикселях"""
import math
import numpy as np

UP = np.array([0., 1., 0.]); W, H = 960., 720.
P = np.array([221.8, 3.4, 177.0]); N = np.array([219.3, 3.4, 177.1])     # m0sd / m1sd: Гомер, Мардж
B0 = np.array([221.5, 3.4, 179.5]); B1 = np.array([221.5, 3.4, 174.1])   # bestside_m0, bestside_m1
P2 = np.array([264.0, 3.7, 176.5]); N2 = np.array([265.4, 3.6, 178.5]); B2 = np.array([268.1, 4.5, 168.1])   # m2: Гомер, Нед, bestside_m2
FOVY = 40.0


def frame(F, S, B):
    a = S - F; a[1] = 0; d = np.linalg.norm(a); a /= d
    left = np.array([a[2], 0., -a[0]])
    return a, (left if np.dot(B - F, left) > 0 else -left), d


def project(E, T, X, fovy=FOVY):
    f = T - E; f /= np.linalg.norm(f); r = np.cross(f, UP); r /= np.linalg.norm(r); u = np.cross(r, f)
    q = X - E; z = q @ f; fl = (H / 2) / math.tan(math.radians(fovy / 2))
    return np.array([W / 2 + fl * (q @ r) / z, H / 2 - fl * (q @ u) / z])


def cam(p, F, S, B):
    back, side, h, k, ht = p; a, v, d = frame(F, S, B)
    return F - a * back + v * side + UP * h, F + a * (k * d) + UP * ht


def resid(p, sets):
    r = []
    for F, S, B, obs in sets:
        E, T = cam(p, F, S, B)
        for X, px in obs: r.extend(project(E, T, X) - np.array(px))
    return np.array(r)


def solve(p0, sets):
    p = np.array(p0, float)
    for _ in range(300):
        r = resid(p, sets); J = np.zeros((len(r), 5))
        for i in range(5):
            dp = np.zeros(5); dp[i] = 1e-4; J[:, i] = (resid(p + dp, sets) - r) / 1e-4
        st = np.linalg.solve(J.T @ J + 1e-3 * np.eye(5), -J.T @ r); p = p + st
        if np.linalg.norm(st) < 1e-7: break
    return p, float(np.sqrt(np.mean(resid(p, sets) ** 2)))


def main():
    far = [(P, N, B0, [(N + UP * 2.11, (310, 178)), (N, (315, 495)), (P + UP * 1.80, (672, 245)), (P, (680, 590))])]
    pf, ef = solve([2.0, 1.5, 1.2, 0.5, 1.0], far)
    print('FAR  back=%.2f side=%.2f h=%.2f k=%.2f ht=%.2f  невязка %.1f px из 720' % (*pf, ef))
    chk = [(P, N, B1, [(N + UP * 2.11, (650, 178)), (N, (650, 495)), (P + UP * 1.80, (275, 240)), (P, (285, 590))])]
    print('     проверка на m1sd (зеркальная сторона, в подбор не входила): %.1f px' % np.sqrt(np.mean(resid(pf, chk) ** 2)))
    near = [(N, P, B0, [(P + UP * 1.80, (565, 155)), (P, (590, 575)), (N + UP * 1.30, (345, 515))]),
            (P2, N2, B2, [(N2 + UP * 1.87, (370, 112)), (N2, (335, 575)), (P2 + UP * 1.80, (490, 180))])]
    pn, en = solve([1.3, 0.4, 1.95, 0.2, 1.4], near)
    print('NEAR back=%.2f side=%.2f h=%.2f k=%.2f ht=%.2f  невязка %.1f px из 720 (два плана разом)' % (*pn, en))


if __name__ == '__main__':
    main()
