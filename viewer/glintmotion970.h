// №970: ход двух слоёв блика ключа — чистая математика (без PSP), тот же код считает viewer/spritelight.h (gvAdd) и гейт tests/glint970 (host.c).
// Закон движения (skill motion-kinematics-canon): задаётся СКОРОСТЬ и фаза, позиция — их интеграл; все частоты — целое число циклов за 60 с, поэтому при переходе часов
// tm = (время % 60 с) нет шва; частоты слоёв несоизмеримы (37, 21 и 11 циклов за 60 с; подобрано перебором: самое слабое повторение пульса на лагах 1…10 с — 0,73, у двух частот не лучше 0,91) — пульс «случайнее» без повторов за секунды.
#ifndef GLINTMOTION970_H
#define GLINTMOTION970_H
#include <math.h>
#define GM970_RMAX .035f    // наибольший сдвиг второй звезды от центра первой, доля размера блика (было 0,06 по x и 0,05 по y)
#define GM970_RMIN .25f     // наименьший сдвиг, доля от наибольшего: звёзды сходятся к центру, но не склеиваются
#define GM970_LAG .28f      // вторая звезда отстаёт от первой по фазе на столько секунд
__attribute__((unused)) static float gm970S(float turns) { float f = turns - floorf(turns); return sinf(6.2831853f * f); }   // sin(2π · turns); PSP: spritelight.h подменяет на таблицу (gm970Sin)
#ifndef GM970_SIN
#define GM970_SIN gm970S
#endif
// kA, kB — множители радиуса первой и второй звезды (1 ± размах); (wx, wy) — сдвиг центра второй звезды в долях размера блика по осям экрана «вправо», «вверх»
static void gm970(float tm, float *kA, float *kB, float *wx, float *wy) {
  float tb = tm - GM970_LAG;
  *kA = 1.f + .05f * (.5f * GM970_SIN(tm * (37.f / 60.f)) + .3f * GM970_SIN(tm * (21.f / 60.f) + .2f) + .2f * GM970_SIN(tm * (11.f / 60.f) + .55f));
  *kB = 1.f + .10f * (.5f * GM970_SIN(tb * (37.f / 60.f)) + .3f * GM970_SIN(tb * (21.f / 60.f) + .2f) + .2f * GM970_SIN(tb * (11.f / 60.f) + .55f));
  float th = tb * (29.f / 60.f) - .396f * GM970_SIN(tb * (7.f / 60.f) + .25f);   // угол в оборотах = интеграл скорости w0·(1 + 0,6·sin Ωt); скорость не меняет знака
  float e = .5f + .5f * GM970_SIN(tb * (13.f / 60.f)), rr = GM970_RMAX * (GM970_RMIN + (1.f - GM970_RMIN) * (e * e * (3.f - 2.f * e)));   // радиус дышит по smoothstep (ease-in-out)
  *wx = rr * GM970_SIN(th + .25f); *wy = .85f * rr * GM970_SIN(th);
}
#endif
