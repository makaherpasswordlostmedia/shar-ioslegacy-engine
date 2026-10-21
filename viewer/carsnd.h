// SHAR PSP: звук удара машины игрока за кадр (правка Роба 135). Один раз за кадр после физики и контактов машин
// (main.c; тот же вызов в гейте tests/sfx135). Поля Car — viewer/car.h (hardV, foliV, wallType/wallIdx/wallP, carHitV).
//  - твёрдое / листва -> sndCarHitWorld: crash только от твёрдого (135.4: днище о землю сюда не идёт, посадка — sndCarLand;
//    135.5: листва без металлического crash); звук объекта — только если сильнейший контакт был его цилиндром/коробкой (135.2)
//  - машина о машину -> sndCarHitCar (135.3): crash + реплика CarWay, без звуков соседних объектов
#ifndef SHAR_CARSND_H
#define SHAR_CARSND_H
#include "car.h"
#include "sound.h"

static inline void carSndFrame(const Car *c, const ColWorld *w) {
  if (c->hardV > 0.f || c->foliV > 0.f) {
    int prim = 0; float o[3] = {0, 0, 0};
    if (w && c->wallV > 0.f && c->wallType == COL_CYL && c->wallIdx < w->ncyl) { const float *q = w->cyl[c->wallIdx].c; o[0] = q[0]; o[1] = q[1]; o[2] = q[2]; prim = 1; }
    else if (w && c->wallV > 0.f && c->wallType == COL_BOX && c->wallIdx < w->nbox) { const float *q = w->box[c->wallIdx].c; o[0] = q[0]; o[1] = q[1]; o[2] = q[2]; prim = 1; }
    sndCarHitWorld(c->hardV, c->foliV, c->wallP[0], c->wallP[1], c->wallP[2], prim, o[0], o[1], o[2]);
  }
  if (c->carHitV > 0.f) sndCarHitCar(c->carHitV, c->carHitP[0], c->carHitP[1], c->carHitP[2]);
}
#endif
