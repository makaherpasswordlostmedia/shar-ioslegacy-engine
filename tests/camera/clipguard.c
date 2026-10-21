// CLIP_GUARD (слово Роба 15.10, TEST20b): объект ближе 0,3 м к глазу не рисуется, как бы мала ни была ближняя плоскость. Хост-проверка viewer/clipguard.h.
// Красный: -DCAM_CLIP_GUARD_OLD=1 (прежнее: только camnear.h) обязан дать «нарисовано ближе 0,3 м» > 0.
#include <stdio.h>
#include <string.h>
#include "clipguard.h"
float camNearNow; int camNearOld; unsigned clipSeen, clipDrawnClose, clipHid; float camFwdN[3] = {0, 0, 1};
static int fails;
static void chk(const char *n, int got, int want) { printf("%s %-58s получено %d нужно %d\n", got == want ? "ok  " : "FAIL", n, got, want); if (got != want) fails++; }
int main(void) {
  float box[6] = {-1, 0, -2, 1, 1.5f, 2};   // кузов 2 x 1,5 x 4 м
  for (int nearK = 0; nearK < 2; nearK++) {
    camNearNow = nearK ? 0.08f : 0.f;   // ближняя плоскость после camsafe / не задана (разговор, ролик)
    char t[96];
    snprintf(t, sizeof t, "машина: глаз 0,2 м от бока (near %.2f) скрыта", camNearNow); chk(t, clipGuardBox(1.2f, 1.f, 0.f, box), 1);
    snprintf(t, sizeof t, "машина: глаз внутри кузова скрыта (near %.2f)", camNearNow); chk(t, clipGuardBox(0.f, 1.f, 0.f, box), 1);
    snprintf(t, sizeof t, "машина: глаз 0,5 м от бока виден (near %.2f)", camNearNow); chk(t, clipGuardBox(1.5f, 1.f, 0.f, box), 0);
    snprintf(t, sizeof t, "машина: глаз 0,25 м над крышей скрыта (near %.2f)", camNearNow); chk(t, clipGuardBox(0.f, 1.75f, 0.f, box), 1);
    snprintf(t, sizeof t, "персонаж: глаз 0,5 м от оси (бок на 0,15 м) скрыт (near %.2f)", camNearNow); chk(t, clipGuardBody(0.5f, 1.f, 0.f, 0.f, 0.f, 1.9f, 0.f, .35f, CAM_HIDE_NPC), 1);
    snprintf(t, sizeof t, "персонаж: глаз 1,0 м от оси виден (near %.2f)", camNearNow); chk(t, clipGuardBody(1.0f, 1.f, 0.f, 0.f, 0.f, 1.9f, 0.f, .35f, CAM_HIDE_NPC), nearK ? 0 : 0);
    snprintf(t, sizeof t, "проп (столб r 0,3, h 3): глаз 0,2 м от бока скрыт (near %.2f)", camNearNow); chk(t, clipGuardProp(0.5f, 1.f, 0.f, 0.f, 0.f, 0.f, .3f, 1.5f, 0), 1);
    snprintf(t, sizeof t, "проп (столб): глаз 0,8 м от бока виден (near %.2f)", camNearNow); chk(t, clipGuardProp(1.1f, 1.f, 0.f, 0.f, 0.f, 0.f, .3f, 1.5f, 0), 0);
  }
  camNearNow = .35f;   // следящая камера после camsafe: борт автобуса в 1,2 м по взгляду заполняет кадр, хотя плоскость его не режет
  { float bus[6] = {-1.3f, 0, 1.2f, 1.3f, 3.4f, 7.f}, side[6] = {3.f, 0, 1.2f, 5.f, 3.4f, 7.f}, far_[6] = {-1.3f, 0, 2.5f, 1.3f, 3.4f, 7.f}, behind[6] = {-1.3f, 0, -7.f, 1.3f, 3.4f, -1.2f};
    chk("по взгляду: борт в 1,2 м скрыт", clipGuardBox(0, 1.5f, 0, bus), 1);
    chk("по взгляду: объект сбоку (3 м влево) виден", clipGuardBox(0, 1.5f, 0, side), 0);
    chk("по взгляду: борт в 2,5 м виден", clipGuardBox(0, 1.5f, 0, far_), 0);
    chk("по взгляду: за спиной виден", clipGuardBox(0, 1.5f, 0, behind), 0);
    camNearNow = 0.f; chk("разговорная камера (near 0): борт по взгляду в 1,2 м не скрываем (кинокамера)", clipGuardBox(0, 1.5f, 0, bus), 0); camNearNow = .35f; }
  { // машина по настоящему кузову, а не по сфере R 2,8 (TR_CARBOX_OLD): кузов 1,9 x 4,4 м у начала координат, курс +z
    Car k; memset(&k, 0, sizeof k); k.q[3] = 1.f; k.p.halfW = .95f; k.p.halfL = 2.2f; k.p.bodyLo = .3f; k.p.bodyHi = 1.5f; k.p.bandLo = .35f; k.p.bandHi = 1.2f;
    float R = 2.8f, sph[6] = {-R, -1.f, -R, R, 4.f, R};   // ящик списка отрисовки: сфера R 2,8, по высоте −1…+4 м
    camNearNow = .35f; camFwdN[0] = 1.f; camFwdN[1] = 0.f; camFwdN[2] = 0.f;   // смотрим вдоль +x, на борт
    chk("машина: глаз 2,5 м сбоку от кузова (зазор 1,55 м): грубый ящик прячет (pop)", clipGuardBox(2.5f, 1.f, 0.f, sph), 1);
    chk("машина: тот же глаз, по кузову: виден", clipGuardCar(2.5f, 1.f, 0.f, &k, sph), 0);
    chk("машина: глаз 0,2 м от борта: по кузову скрыта", clipGuardCar(1.15f, 1.f, 0.f, &k, sph), 1);
    chk("машина: глаз внутри кузова: скрыта", clipGuardCar(0.f, 1.f, 0.f, &k, sph), 1);
    chk("машина: борт 1,2 м по взгляду (глаз −2,15): скрыта", clipGuardCar(-2.15f, 1.f, 0.f, &k, sph), 1);
    chk("машина: борт 3,05 м по взгляду (глаз −4): по кузову виден", clipGuardCar(-4.f, 1.f, 0.f, &k, sph), 0);
    chk("машина: борт 3,05 м по взгляду (глаз −4): грубый ящик прячет (pop)", clipGuardBox(-4.f, 1.f, 0.f, sph), 1);
    camFwdN[0] = 0.f; camFwdN[2] = 1.f;
  }
  chk("счётчики: близкий объект замечен (скрыт правилом либо нарисован в прежнем)", clipHid + clipDrawnClose > 0, 1);
  printf("RESULT %s (скрыто правилом %u, нарисовано ближе 0,3 м в прежнем %u)\n", fails ? "FAIL" : "PASS", clipHid, clipDrawnClose); return fails ? 1 : 0;
}
