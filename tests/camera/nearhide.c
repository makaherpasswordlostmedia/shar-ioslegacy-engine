// №502: правило «объект у самого глаза не рисуется» (viewer/camnear.h). Обычный вид не меняется: всё, что дальше порога, рисуется.
//   cc -std=c99 -Iviewer tests/camera/nearhide.c -lm -o /tmp/nh && /tmp/nh [-DCAM_NEARHIDE_OLD=1 — красный контроль: всё рисуется]
#include <stdio.h>
#include "camnear.h"
float camNearNow; int camNearOld = 1;   // №502: гейт прежних порогов
static int bad;
static void ck(const char *w, int got, int want) { printf("%s %s\n", got == want ? "ok  " : "FAIL", w); bad += got != want; }
int main(void) {
  int h = !CAM_NEARHIDE_OLD;   // ждём «скрыть» только в новой сборке
  camNearNow = 1.5f;   // следящая камера, ничего рядом: ближняя плоскость NEAR_Z
  ck("персонаж в 1,0 м от глаза скрыт", camNearBody(0, 2, 0, 1.0f, 0, 1.9f, 0, 0.8f), h);
  ck("персонаж в 1,7 м (плоскость 1,5 + тело .35 = 1,85) скрыт", camNearBody(0, 1, 0, 1.7f, 0, 1.9f, 0, 0.8f), h);
  ck("персонаж в 3 м виден", camNearBody(0, 2, 0, 3.f, 0, 1.9f, 0, 0.8f), 0);
  ck("персонаж в 6,45 м (обычный вид за спиной) виден", camNearBody(0, 2.4f, 0, 6.45f, 0, 1.9f, 0, 0.8f), 0);
  ck("знак миссии в 1,5 м скрыт", camNearPoint(0, 2, 0, 1.5f, 2.4f, 0, 1.0f), h);
  ck("знак миссии в 4 м виден", camNearPoint(0, 2, 0, 4.f, 2.4f, 0, 1.0f), 0);
  float car[6] = {-1, 0, 0.8f, 1, 1.5f, 4.5f};
  ck("коробка машины в 0,8 м спереди скрыта", camNearBox(0, 1, 0, car, 0.5f), h);
  float car2[6] = {-1, 0, 3.5f, 1, 1.5f, 8.f};
  ck("коробка машины в 3,5 м видна", camNearBox(0, 1, 0, car2, 0.5f), 0);
  ck("проп r .4 в 1,2 м скрыт", camNearSphere(0, 1, 0, 1.2f, 1, 0, .4f), h);
  ck("проп r .4 в 5 м виден", camNearSphere(0, 1, 0, 5.f, 1, 0, .4f), 0);
  camNearNow = 0.3f;   // камера у стены, плоскость прижата: порог — постоянный минимум
  ck("при плоскости .3 персонаж в 1,0 м виден", camNearBody(0, 2, 0, 1.0f, 0, 1.9f, 0, 0.8f), 0);
  ck("при плоскости .3 персонаж в 0,6 м скрыт", camNearBody(0, 1, 0, 0.6f, 0, 1.9f, 0, 0.8f), h);
  camNearNow = 0.f;   // кинокамера разговора: порог только постоянный; слушающий в 1,3 м виден
  ck("разговор: слушающий в 1,3 м виден", camNearBody(0, 1.7f, 0, 1.3f, 0, 1.9f, 0, 0.8f), 0);
  printf("%s\n", bad ? "FAIL" : "PASS"); return bad;
}
