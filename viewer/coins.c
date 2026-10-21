// Монеты: реализация (см. coins.h).
#include "coins.h"
#include <stdlib.h>
#include <string.h>
#include <math.h>

#define C_REACH 2.25f
#define C_CARSCALE 2.25f
#define C_DIAMOND 3.f
#define C_COLLECT 0.4f
#define C_G 21.f
#define C_BOUNCE 0.6f
#define C_LAUNCH 9.5f
#define C_FADE 11.f
#define C_LIFE 16.f
#define C_SPIN 3.f

// генератор — в состоянии монет (Б0: мир целиком в структурах, save/load ботов); старт 12345, как прежний static
static float frand(Coins *cs) { cs->rng = cs->rng * 1664525u + 1013904223u; return (cs->rng >> 8) * (1.f / 16777216.f); }

int coinsInit(Coins *cs, const float *pos, unsigned nworld) {
  memset(cs, 0, sizeof *cs); cs->rng = 12345u;
  cs->c = calloc(nworld + COIN_POOL, sizeof(Coin));
  if (!cs->c) return -1;
  cs->n = nworld + COIN_POOL; cs->nworld = nworld; cs->total = (int)nworld;
  for (unsigned i = 0; i < nworld; i++) {
    Coin *c = &cs->c[i];
    c->x = c->ox = pos[i * 3]; c->y = c->oy = pos[i * 3 + 1]; c->z = c->oz = pos[i * 3 + 2];
    c->floor = c->y; c->active = 1; c->spin = frand(cs) * 3.14159f;
  }
  return 0;
}

void coinsFree(Coins *cs) { free(cs->c); memset(cs, 0, sizeof *cs); }

// Направление вылета: к случайному единичному вектору добавляем +1.1 вверх и нормируем ЕЩЁ раз, потом ×9.5 м/с.
// Раньше нормировка была до добавки: вертикаль доходила до 20 м/с, монеты висели ~2 с и улетали на 10–30 м
// (пешком собиралось 1–2 из 30). Порядок операций в оригинале не подтверждён — сверить по видео.
static void launchDir(Coin *c, float x, float y, float z) {
  y += 1.1f;
  float l = sqrtf(x * x + y * y + z * z); if (l < 1e-3f) { x = 0.f; y = 1.f; z = 0.f; l = 1.f; }
  c->vx = x / l * C_LAUNCH; c->vy = y / l * C_LAUNCH; c->vz = z / l * C_LAUNCH;
}

void coinsDropDir(Coins *cs, int n, float x, float y, float z, float floor, float dx, float dz, float cone) {
  float l = sqrtf(dx * dx + dz * dz);
  if (l < 1e-4f) { coinsDrop(cs, n, x, y, z, floor); return; }
  dx /= l; dz /= l;
  float half = acosf(fmaxf(-1.f, fminf(1.f, cone)));
  for (unsigned i = cs->nworld; i < cs->n && n > 0; i++) {
    Coin *c = &cs->c[i];
    if (c->active) continue;
    memset(c, 0, sizeof *c);
    c->active = c->airborne = c->loose = 1; c->autoCollect = (unsigned char)cs->dropAuto;
    c->x = x; c->y = fmaxf(y, floor + 0.5f); c->z = z; c->floor = floor;
    float a = (frand(cs) * 2.f - 1.f) * half, ca = cosf(a), sa = sinf(a);
    float hx = dx * ca - dz * sa, hz = dx * sa + dz * ca, hs = 0.4f + 0.6f * frand(cs), vy = frand(cs);
    float vl = sqrtf(hs * hs + vy * vy);   // та же скорость вылета, что у coinsDrop, но вперёд из пропа
    launchDir(c, hx * hs / vl, vy / vl, hz * hs / vl);
    c->spin = frand(cs) * 3.14159f;
    n--;
  }
  cs->collected += n;
}

void coinsDrop(Coins *cs, int n, float x, float y, float z, float floor) {
  for (unsigned i = cs->nworld; i < cs->n && n > 0; i++) {
    Coin *c = &cs->c[i];
    if (c->active) continue;
    memset(c, 0, sizeof *c);
    c->active = c->airborne = c->loose = 1; c->autoCollect = (unsigned char)cs->dropAuto;
    c->x = x; c->y = fmaxf(y, floor + 0.5f); c->z = z; c->floor = floor;
    float vx = frand(cs) * 2.f - 1.f, vy = frand(cs), vz = frand(cs) * 2.f - 1.f, l = sqrtf(vx * vx + vy * vy + vz * vz);
    if (l < 1e-3f) { vy = 1.f; l = 1.f; }
    launchDir(c, vx / l, vy / l, vz / l);
    c->spin = frand(cs) * 3.14159f;
    n--;
  }
  cs->collected += n;   // пул полон — сразу в кошелёк
}

float coinAlpha(const Coin *c) {
  if (!c->loose || c->age <= C_FADE) return 1.f;
  return fmaxf(0.f, 1.f - (c->age - C_FADE) / (C_LIFE - C_FADE));
}

static int inReach(const Coin *c, float px, float py, float pz, int inCar) {
  float x = fabsf(c->x - px), z = fabsf(c->z - pz), s = inCar ? C_CARSCALE : 1.f;
  return x < C_REACH * s && z < C_REACH * s && fabsf(c->y - py) < C_REACH && x + z < C_DIAMOND * s;
}

int coinsUpdate(Coins *cs, float px, float py, float pz, int inCar, float dt) {
  const float h = 1.f / 60.f;
  int earned = 0;
  cs->acc += fminf(dt, 0.1f);
  while (cs->acc >= h) {
    cs->acc -= h;
    for (unsigned i = 0; i < cs->n; i++) {
      Coin *c = &cs->c[i];
      if (!c->active) continue;
      c->age += h; c->spin += C_SPIN * h;
      if (c->collecting) {   // притягивается к игроку и исчезает в кошельке
        c->magnet += h;
        if (c->magnet > C_COLLECT) { c->active = 0; earned++; continue; }
        c->x += (px - c->x) * c->magnet; c->y += (py - c->y) * c->magnet; c->z += (pz - c->z) * c->magnet;
        c->y += (1.f - c->magnet) * 0.4f;
        continue;
      }
      if (!c->airborne && inReach(c, px, py, pz, inCar)) { c->collecting = 1; c->magnet = 0; continue; }
      if (c->loose) {
        if (c->age > C_LIFE) { c->active = 0; continue; }
        if (c->vx != 0.f || c->vy != 0.f || c->vz != 0.f) {
          c->x += c->vx * h; c->y += c->vy * h; c->z += c->vz * h;
          { float g; if (cs->ground && cs->ground(cs->groundU, c->x, c->z, c->y + 1.f, &g)) c->floor = g; }   // правка 81: пол по месту
          float d = expf(-0.2f * h); c->vx *= d; c->vy *= d; c->vz *= d;
          c->vy -= C_G * h;
          if (c->y < c->floor) {
            c->y = c->floor; c->vy = fabsf(c->vy) * C_BOUNCE; c->airborne = 0;
            c->vx *= 0.5f; c->vz *= 0.5f;   // трение о землю при отскоке (подобрано, в данных нет)
            if (c->autoCollect) { c->collecting = 1; c->magnet = 0; continue; }
            if (c->vy < 0.1f) c->vx = c->vy = c->vz = 0.f;
          }
        }
      }
    }
  }
  cs->collected += earned;
  return earned;
}
