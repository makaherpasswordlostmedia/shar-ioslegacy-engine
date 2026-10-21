// Камеры старта этапов миссий — «наезды» (правка Роба 40): анимация камеры с диска (tools/msncam_export.py, пакет msncam.shr).
// Камера фазы (SetMissionStartCameraName в mNsdi.mfk, SetAnimatedCameraName в srNi/grNi.mfk) прилетает к месту, куда
// сценарий ставит игрока на старте этой фазы; у m0 — облёт улицы к дому Симпсонов на старте уровня (по записи PS2,
// tools/ps2ref/CATALOG_L1.md 0:58–1:03). Когда играть — крючок миссий (viewer/game_msn.c gameMsnStartCam).
// Чистый C99 (проверка на Маке: tests/camera/msncam.sh).
#ifndef MSNCAM_H
#define MSNCAM_H
typedef struct { char name[32]; int mission; unsigned nfr; float fps; const float *fr; char phase[16]; } MsnCam;   // кадр: pos3 look3 up3 fov
typedef struct { const MsnCam *cam; float t; } MsnCamPlay;
// разбор пакета в памяти (данные живут, пока жив буфер): число камер, <0 — битый пакет. Версия 1 (без фазы) читается:
// фаза тогда "m<N>sd" по номеру миссии
int msncamParse(MsnCam *out, int max, const unsigned char *b, unsigned size);
// камера фазы по имени SelectMission ("m1sd", "sr1"; регистр не важен), NULL — нет. cam (может быть NULL) — имя камеры
// из данных фазы: должно совпасть, иначе NULL (пакет не от этих скриптов)
const MsnCam *msncamFind(const MsnCam *c, int n, const char *phase, const char *cam);
// поза в момент t (с): глаз, точка взгляда (глаз + взгляд), верх, вертикальный FOV в градусах для кадра 16:9 (Hor+:
// FOV данных — по горизонтали кадра 4:3). 1 — идёт, 0 — анимация кончилась (поза последнего кадра)
int msncamPose(const MsnCam *c, float t, float eye[3], float look[3], float up[3], float *fovY);
#endif
