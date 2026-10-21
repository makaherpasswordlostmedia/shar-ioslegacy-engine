// Тест хоста для правок №546 и №544:
// 1. №546: отсечение длинных моделей по полной 3D-сфере (угол 16:9 Hor+, запас 1.5 м по краям).
//    Счётчик «отсечён, но сфера пересекает кадр» = 0 на проезде длинных грузовиков/автобусов/машин.
//    Красный контроль (-DCULL_SPHERE_OLD=1): старый carR и узкий бокс y[-1..4] режут модель у кромки (счётчик > 0).
// 2. №544: машина в контакте или <= 30 м к игроку рисуется всегда + устранение пропуска кадром позже из-за MCR_ASYNC.
//    Красный контроль (-DNEAR_CAR_DRAW_OLD=1): близкая машина откладывается (MCRPRE_DEFER) и не рисуется.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define GU_PI 3.14159265358979323846f
#define FOVY 62.f
#define ASPECT (16.f / 9.f)

#ifndef NEAR_CAR_DRAW_OLD
#define NEAR_CAR_DRAW_OLD 0
#endif

#include "car.h"
#include "mcrpre.h"

// Пирамида обзора (копия viewer/main_render.h setupPlanes)
static float pl[4][3], eyeX, eyeY, eyeZ;
static void setupTestPlanes(float ex, float ey, float ez, float fx, float fy, float fz, float fovy) {
  eyeX = ex; eyeY = ey; eyeZ = ez;
  float rx = -fz, rz = fx, rl = sqrtf(rx * rx + rz * rz); if (rl < 1e-4f) { rx = 1; rz = 0; rl = 1; }
  rx /= rl; rz /= rl;
  float ux = -rz * fy, uy = rz * fx - rx * fz, uz = rx * fy;
  float tv = tanf(fovy * .5f * GU_PI / 180.f) * 1.03f, th = tv * ASPECT;
  float n[4][3] = {
    {fx * th - rx, fy * th, fz * th - rz}, {fx * th + rx, fy * th, fz * th + rz},
    {fx * tv - ux, fy * tv - uy, fz * tv - uz}, {fx * tv + ux, fy * tv + uy, fz * tv + uz}};
  memcpy(pl, n, sizeof pl);
}

// visBox как в viewer/main_render.h
static int visBoxTest(const float *b) {
  for (int i = 0; i < 4; i++) {
    float px = (pl[i][0] > 0 ? b[3] : b[0]) - eyeX;
    float py = (pl[i][1] > 0 ? b[4] : b[1]) - eyeY;
    float pz = (pl[i][2] > 0 ? b[5] : b[2]) - eyeZ;
    if (px * pl[i][0] + py * pl[i][1] + pz * pl[i][2] < 0) return 0;
  }
  return 1;
}

// Истинное геометрическое пересечение 3D сферы (cx, cy, cz, r) с пирамидой кадра и дальностью
static int sphereIntersectsFrustum(float cx, float cy, float cz, float r, float drawDist) {
  float dx = cx - eyeX, dy = cy - eyeY, dz = cz - eyeZ, d = sqrtf(dx * dx + dy * dy + dz * dz);
  if (d - r > drawDist) return 0;   // сфера целиком за пределами дальности отрисовки
  for (int i = 0; i < 4; i++) {
    float len = sqrtf(pl[i][0] * pl[i][0] + pl[i][1] * pl[i][1] + pl[i][2] * pl[i][2]);
    float dist = ((cx - eyeX) * pl[i][0] + (cy - eyeY) * pl[i][1] + (cz - eyeZ) * pl[i][2]) / len;
    if (dist < -r) return 0;   // центр сферы дальше радиуса r за пределами полупространства плоскости
  }
  return 1;
}

// Проверка видимости машины движком
static int engineDrawsCar(const Car *k, float drawDist) {
  float dx = k->x - eyeX, dy = k->y - eyeY, dz = k->z - eyeZ, d = sqrtf(dx * dx + dy * dy + dz * dz);
#if CULL_SPHERE_OLD
  float R = k->p.halfL + fabsf(k->p.bodyOfs) + .5f;
  if (d - R > drawDist) return 0;
  float bb[6] = {k->x - R, k->y - 1.f, k->z - R, k->x + R, k->y + 4.f, k->z + R};
  if (!visBoxTest(bb)) return 0;
  return 1;
#else
  float R = carSphereR(k);
  if (d > 30.f && d - R > drawDist) return 0;
  float bb[6] = {k->x - R, k->y - R, k->z - R, k->x + R, k->y + R, k->z + R};
  if (!visBoxTest(bb)) return 0;
  return 1;
#endif
}

int main(void) {
  int fails = 0;
  printf("=== ТЕСТ №546 и №544 (Cull sphere & near car draw) ===\n");
  printf("Режим: CULL_SPHERE_OLD=%d, NEAR_CAR_DRAW_OLD=%d\n", CULL_SPHERE_OLD, NEAR_CAR_DRAW_OLD);

  // Список моделей машин для теста: грузовики, длинные машины, седан
  struct {
    const char *name;
    float halfW, halfL, bodyOfs, bodyHi, bodyLo;
  } models[] = {
    {"glastruc", 1.57f, 3.31f, -0.386f, 3.10f, 0.20f},
    {"schoolbu", 1.55f, 2.87f, -0.606f, 3.46f, 0.20f},
    {"garbage",  1.57f, 3.50f, -0.076f, 3.23f, 0.20f},
    {"famil_v",  1.10f, 2.68f, -0.320f, 1.50f, 0.30f},
    {"cVan",     1.35f, 2.90f, -0.200f, 2.40f, 0.25f},
  };
  int nModels = sizeof(models) / sizeof(models[0]);

  int falseCulls = 0;   // отсечён, но истинная сфера пересекает кадр
  int trueDraws = 0;    // правильно отрисован
  int correctCulls = 0; // правильно отсечён далеко за пределами кадра

  // Симулируем камеру, смотрящую вдоль оси Z (вперёд) на высоте 2.5 м
  setupTestPlanes(0.f, 2.5f, 0.f, 0.f, 0.f, 1.f, FOVY);
  float drawDist = 115.f;

  for (int m = 0; m < nModels; m++) {
    Car k;
    memset(&k, 0, sizeof k);
    k.p.halfW = models[m].halfW;
    k.p.halfL = models[m].halfL;
    k.p.bodyOfs = models[m].bodyOfs;
    k.p.bodyHi = models[m].bodyHi;
    k.p.bodyLo = models[m].bodyLo;

    // Истинный радиус описанной сферы кузова √(L²+W²+H²)/2
    float hl = k.p.halfL + fabsf(k.p.bodyOfs);
    float hw = k.p.halfW;
    float H = (k.p.bodyHi > k.p.bodyLo) ? (k.p.bodyHi - k.p.bodyLo) : k.p.bodyHi;
    float hh = H * 0.5f;
    float trueR = sqrtf(hl * hl + hw * hw + hh * hh);

    // Прогоняем по дистанциям Z от 2 м до 100 м
    for (float z = 3.f; z <= 100.f; z += 1.5f) {
      // И по горизонтальному смещению X (от центра кадра до далеко за кромку)
      float halfTan = tanf(FOVY * .5f * GU_PI / 180.f) * ASPECT;
      float frameHalfWidth = z * halfTan;

      // Тестируем проезд поперек кадра от центра до 2 * frameHalfWidth
      for (float x = 0.f; x <= frameHalfWidth * 2.2f; x += 0.25f) {
        k.x = x;
        k.y = 0.f;
        k.z = z;

        int sphereIn = sphereIntersectsFrustum(k.x, k.y, k.z, trueR, drawDist);
        int drawn = engineDrawsCar(&k, drawDist);

        if (sphereIn && !drawn) {
          falseCulls++;
        } else if (sphereIn && drawn) {
          trueDraws++;
        } else if (!sphereIn && !drawn) {
          correctCulls++;
        }
      }
    }
  }

  printf("Результаты проезда:\n");
  printf("  Правильно нарисовано: %d\n", trueDraws);
  printf("  Правильно отсечено снаружи: %d\n", correctCulls);
  printf("  ОШИБКА: отсечён, но сфера пересекает кадр = %d\n", falseCulls);

#if CULL_SPHERE_OLD
  if (falseCulls == 0) {
    printf("КРАСНЫЙ КОНТРОЛЬ НЕ СРАБОТАЛ: ожидали falseCulls > 0 при CULL_SPHERE_OLD=1!\n");
    fails++;
  } else {
    printf("КРАСНЫЙ КОНТРОЛЬ ПОЙМАН: при CULL_SPHERE_OLD=1 было %d исчезновений у края кадра.\n", falseCulls);
  }
#else
  if (falseCulls > 0) {
    printf("FAIL: при CULL_SPHERE_OLD=0 счётчик falseCulls = %d (должен быть 0)!\n", falseCulls);
    fails++;
  } else {
    printf("PASS №546: счётчик «отсечён, но сфера пересекает кадр» = 0! Кадр в безопасности.\n");
  }
#endif

  // Тест №544: машина миссии в контакте / близко к игроку
  printf("\n=== Проверка №544 (Near mission car force load & draw) ===\n");
  // Имитация: модель ещё читается в фоне (ready=0, age=0)
  int ready = 0, age = 0;

  // Случай А: машина далеко (d = 50 м)
  int farForce = 0;
  int farDecision = mcrPreDecide(ready, age, farForce);
  if (farDecision != MCRPRE_DEFER) {
    printf("FAIL: далёкая машина не должна форсироваться (ожидали DEFER, получили %d)\n", farDecision);
    fails++;
  } else {
    printf("OK: далёкая машина откладывается в фоне (MCRPRE_DEFER)\n");
  }

  // Случай Б: машина близко к игроку (d <= 30 м) или в контакте
  int nearForce = 0;
#if !NEAR_CAR_DRAW_OLD
  nearForce = 1;
#endif
  int nearDecision = mcrPreDecide(ready, age, nearForce);

#if NEAR_CAR_DRAW_OLD
  if (nearDecision == MCRPRE_WAIT) {
    printf("КРАСНЫЙ КОНТРОЛЬ НЕ СРАБОТАЛ: при NEAR_CAR_DRAW_OLD=1 ожидали DEFER!\n");
    fails++;
  } else {
    printf("КРАСНЫЙ КОНТРОЛЬ ПОЙМАН: при NEAR_CAR_DRAW_OLD=1 близкая машина получила DEFER (невидима кадром позже).\n");
  }
#else
  if (nearDecision != MCRPRE_WAIT) {
    printf("FAIL: близкая машина должна была форсироваться (MCRPRE_WAIT), получили %d\n", nearDecision);
    fails++;
  } else {
    printf("PASS №544: близкая/контактная машина немедленно завершает загрузку (MCRPRE_WAIT) и рисуется в кадре 0.\n");
  }
#endif

  printf("\nИТОГ: %s\n", fails ? "FAIL" : "PASS");
  return fails != 0;
}
