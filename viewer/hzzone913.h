// №913 (слово Роба 23.10: «130 + места-исключения по 150 и 250 на пристани и т. д.»): полная прорисовка города 130 м по умолчанию, лента силуэтов считается от 130 (horizon_export --near 130 --near2 150),
// а в зонах-исключениях город держится 150 или 250 м. Зоны — таблица клеток 60 м рядом с horizon.shr (файл hzzone.bin: 'HZN1', w u32, h u32, x0 f32, z0 f32, шаг f32, w·h байт: 0 — 130 м, 1 — 150, 2 — 250,
// 255 — нет данных), её строит tools/hz_zones.py по открытости вида и списку явных мест (tools/hz_zone_places.json). Переход между зонами плавный: вверх сразу, вниз после HZ913_HOLD с непрерывно более низкой зоны
// (как гистерезис №909), радиус города двигается к цели не быстрее HZ913_UP (вверх) и HZ913_DOWN (вниз) м/с — без скачков тумана и кольца. Чистая часть без PSP-заголовков: её же гоняет tests/horizon/zone913.sh
#pragma once
#include <math.h>
#ifndef HZ913_OLD
#define HZ913_OLD 0
#endif
#ifndef HZ913_HOLD
#define HZ913_HOLD 2.f
#endif
#ifndef HZ913_UP
#define HZ913_UP 40.f
#endif
#ifndef HZ913_DOWN
#define HZ913_DOWN 15.f
#endif
typedef struct { float x0, z0, step; unsigned w, h; const unsigned char *m; } HzZone;
typedef struct { float cap; int tgt; float low; int init; } Hz913;
static inline int hzZoneMode(const HzZone *z, float x, float zz, int def) {
  if (!z || !z->m) return def;
  float fx = (x - z->x0) / z->step, fz = (zz - z->z0) / z->step;   // без floorf: отрицательное — за таблицей
  if (fx < 0.f || fz < 0.f) return def;
  int gx = (int)fx, gz = (int)fz;
  if (gx >= (int)z->w || gz >= (int)z->h) return def;
  unsigned char v = z->m[(unsigned)gz * z->w + (unsigned)gx]; return v > 2 ? def : v;
}
static inline float hz913Radius(int mode, float base) { return mode >= 2 ? 250.f : mode == 1 ? (base > 150.f ? base : 150.f) : base; }
// mode — зона глаза в этом кадре; base — радиус «по умолчанию» (130); возвращает потолок радиуса города (м)
static inline float hz913Step(Hz913 *s, int mode, float base, float dt) {
  if (!s->init) { s->init = 1; s->tgt = mode; s->cap = hz913Radius(mode, base); s->low = 0.f; }
  if (mode > s->tgt) { s->tgt = mode; s->low = 0.f; }
  else if (mode < s->tgt) { s->low += dt; if (s->low >= HZ913_HOLD) { s->tgt = mode; s->low = 0.f; } }
  else s->low = 0.f;
  float want = hz913Radius(s->tgt, base), d = want - s->cap, up = HZ913_UP * dt, dn = HZ913_DOWN * dt;
  if (d > up) d = up; else if (d < -dn) d = -dn;
  s->cap += d; return s->cap;
}
