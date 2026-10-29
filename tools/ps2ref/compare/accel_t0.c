// Клип t0 (разгон с места, газ после 30 кадров покоя) в порте — для сверки с трассой PCSX2 build/ps2ref/clips/t0/run1.tsv.
// Старт там же, где машина в build/ps2ref/state_l1_incar.p2s (z отзеркален). ВАЖНО: PAL идёт 50 кадров/с, порт 60 — сравнивать
// по времени газа, не по номеру кадра. Эталон 28.09 (исправлено аудитом): газ 0.6/1.0/1.4 с — PS2 1.33/3.72/7.63 м,
// порт 1.27/3.72/7.51 м: разгон совпадает в пределах 2%. Прежний вывод «оригинал резче в 1.5 раза» — ошибка счёта по кадрам.
// Сборка — как tools/cartest/roadblock.c.
#include <stdio.h>
#include <math.h>
#include "world.h"
// тот же клип t0 в порте: старт там же (z отзеркален), 30 кадров покоя, газ (R) 240 кадров; путь и скорость по кадрам
int main(void) { static BotWorld w; bwData("build/level.shr", "build/homer.shr", 0); bwNew(&w);
  float fx = -0.295f, fz = -0.955f; bwPlace(&w, 215.03f, 4.05f, 170.21f, atan2f(fx, fz));
  float x0 = w.car.x, z0 = w.car.z, px = x0, pz = z0;
  printf("кадр  путь_м  скорость_м/с\n");
  for (int f = 1; f <= 200; f++) { bwStep(&w, f > 30 ? GP_R : 0, 0, 0);
    if (f % 20 == 0) { printf("%4d  %6.2f  %6.2f\n", f, hypotf(w.car.x - x0, w.car.z - z0), hypotf(w.car.x - px, w.car.z - pz) * 3.f); }
    if (f % 20 == 0) { px = w.car.x; pz = w.car.z; } }
}
