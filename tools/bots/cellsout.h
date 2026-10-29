// Анатомия уровня (Роб 04.10: «у тебя есть боты, которые несколько дней играли — посмотри их пути: где заезжали, где нет»):
// запись всех мест, где побывал бот, в файлы — ключ --cells-out DIR у ботов (explorer). Без ключа ничего не пишется и не
// меняется. Подключается как исходник (#include) в одну единицу трансляции с миром (tools/bots/world.c).
//   DIR/cells.tsv  — ячейка = x, z по 6 м; y по 2 м; режим (car/foot); опора (ground/air): посещений (выборка раз в 4 кадра),
//                    первое время (секунды эпохи, для насыщения роя), средняя точка, верхняя поверхность коллизии над ней (куда
//                    поставит машину goto смоука: верхняя опора ниже 200 м), курс движения машины: ось (по модулю π) и её сила
//                    0..1, средний курс со знаком, средняя скорость. Пишется целиком раз в 30 с и в конце (tmp + rename)
//   DIR/edges.tsv  — переходы «машина на земле -> машина на земле» между соседними выборками (≤ 24 кадров, перепад < 1.5 м):
//                    связность дорог и срезок без прыжков (крыша, куда попадают только прыжком, — отдельный остров)
//   DIR/events.tsv — каждое событие застревания и провала с координатами (не только первое в кластере)
#ifndef CELLSOUT_H
#define CELLSOUT_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <sys/time.h>
#include <sys/stat.h>
#include "world.h"

#define CO_XZ 6.f
#define CO_Y 2.f
typedef struct { uint32_t key; unsigned hits; double first; double sx, sy, sz; float c2, s2, cv, sv, vs; unsigned nv; } CoCell;
typedef struct { uint64_t key; unsigned n; } CoEdge;
static CoCell *coC; static unsigned coCap, coN;
static CoEdge *coE; static unsigned coECap, coEN;
static char coDir[400]; static FILE *coEv; static int coOn; static double coLastDump;
static uint32_t coLastKey; static long coLastFrame = -1000000; static float coLastY;

static double coNow(void) { struct timeval tv; gettimeofday(&tv, 0); return tv.tv_sec + tv.tv_usec * 1e-6; }
// ключ: x/6 + 512 (10 бит), z/6 + 512 (10 бит), y/2 + 256 (9 бит), пешком (1 бит), на опоре (1 бит), бит занятости
static uint32_t coKey(float x, float y, float z, int foot, int ground) {
  int ix = (int)floorf(x / CO_XZ) + 512, iz = (int)floorf(z / CO_XZ) + 512, iy = (int)floorf(y / CO_Y) + 256;
  if (ix < 0) ix = 0; if (ix > 1023) ix = 1023; if (iz < 0) iz = 0; if (iz > 1023) iz = 1023; if (iy < 0) iy = 0; if (iy > 511) iy = 511;
  return (uint32_t)ix | (uint32_t)iz << 10 | (uint32_t)iy << 20 | (uint32_t)(foot != 0) << 29 | (uint32_t)(ground != 0) << 30 | 1u << 31;
}
static CoCell *coCell(uint32_t k) {
  if ((coN + 1) * 2 > coCap) {   // рост таблицы: заполнение до половины
    unsigned nc = coCap ? coCap * 2 : 1u << 16; CoCell *t = calloc(nc, sizeof(CoCell));
    for (unsigned i = 0; i < coCap; i++) if (coC[i].key) { unsigned h = (coC[i].key * 2654435761u) & (nc - 1); while (t[h].key) h = (h + 1) & (nc - 1); t[h] = coC[i]; }
    free(coC); coC = t; coCap = nc;
  }
  unsigned h = (k * 2654435761u) & (coCap - 1);
  while (coC[h].key && coC[h].key != k) h = (h + 1) & (coCap - 1);
  if (!coC[h].key) { memset(&coC[h], 0, sizeof(CoCell)); coC[h].key = k; coC[h].first = coNow(); coN++; }
  return &coC[h];
}
static void coEdge(uint32_t a, uint32_t b) {
  uint64_t k = (uint64_t)(a & 0x1fffffff) | (uint64_t)(b & 0x1fffffff) << 29 | 1ull << 63;
  if ((coEN + 1) * 2 > coECap) {
    unsigned nc = coECap ? coECap * 2 : 1u << 16; CoEdge *t = calloc(nc, sizeof(CoEdge));
    for (unsigned i = 0; i < coECap; i++) if (coE[i].key) { unsigned h = (unsigned)((coE[i].key * 0x9E3779B97F4A7C15ull) >> 40) & (nc - 1); while (t[h].key) h = (h + 1) & (nc - 1); t[h] = coE[i]; }
    free(coE); coE = t; coECap = nc;
  }
  unsigned h = (unsigned)((k * 0x9E3779B97F4A7C15ull) >> 40) & (coECap - 1);
  while (coE[h].key && coE[h].key != k) h = (h + 1) & (coECap - 1);
  if (!coE[h].key) { coE[h].key = k; coEN++; }
  coE[h].n++;
}
static void coInit(const char *dir) {
  if (!dir) return;
  snprintf(coDir, sizeof coDir, "%s", dir); mkdir(dir, 0755);   // родительская папка — у вызывающего
  char p[460]; snprintf(p, sizeof p, "%s/events.tsv", dir); coEv = fopen(p, "w");
  if (!coEv) { fprintf(stderr, "cellsout: не пишется %s\n", p); exit(2); }
  fprintf(coEv, "# событие\tx\ty\tz\tвремя_эпохи\tслой\tобъект\tпешком\n");
  coOn = 1; coLastDump = coNow();
}
static void coBreak(void) { coLastFrame = -1000000; }   // мир перенесён (снимок, старт): переход не засчитывать
// выборка: игрок в (x, y, z); пешком; на опоре; курс машины (вперёд = (sin h, cos h)) и скорость со знаком; кадр (сквозной счётчик)
static void coSample(float x, float y, float z, int foot, int ground, float h, float v, long frame) {
  if (!coOn || !(x == x) || !(y == y) || !(z == z)) return;
  uint32_t k = coKey(x, y, z, foot, ground); CoCell *c = coCell(k);
  c->hits++; c->sx += x; c->sy += y; c->sz += z;
  if (!foot && fabsf(v) > 3.f) { float a = v < 0 ? h + 3.14159265f : h; c->c2 += cosf(2.f * a); c->s2 += sinf(2.f * a); c->cv += cosf(a); c->sv += sinf(a); c->vs += fabsf(v); c->nv++; }
  if (!foot && ground) {
    if (frame - coLastFrame <= 24 && fabsf(y - coLastY) < 1.5f && coLastKey != k) coEdge(coLastKey, k);
    coLastKey = k; coLastFrame = frame; coLastY = y;
  }
}
static void coSampleWorld(const BotWorld *w, long frame) {
  int foot = gameOnFoot(&w->G);
  if (foot) coSample(w->homer.x, w->homer.y, w->homer.z, 1, w->homer.grounded, 0.f, w->homer.speed, frame);
  else coSample(w->car.x, w->car.y, w->car.z, 0, w->car.grounded, w->car.h, w->car.v, frame);
}
static void coEvent(const char *kind, float x, float y, float z, int layer, const char *obj, int foot) {
  if (!coOn) return;
  fprintf(coEv, "%s\t%.2f\t%.2f\t%.2f\t%.1f\t%d\t%s\t%d\n", kind, x, y, z, coNow(), layer, obj ? obj : "-", foot);
}
static void coDump(void) {
  if (!coOn) return;
  char p[460], q[470]; snprintf(p, sizeof p, "%s/cells.tsv", coDir); snprintf(q, sizeof q, "%s.tmp", p);
  FILE *f = fopen(q, "w"); if (!f) return;
  fprintf(f, "# x\tz\ty\tрежим\tопора\tпосещений\tпервое_время\tср_x\tср_y\tср_z\tверх_y\tкурс_ось\tсила_оси\tкурс\tскорость\n");
  const ColWorld *cw = bwCol();
  for (unsigned i = 0; i < coCap; i++) { const CoCell *c = &coC[i]; if (!c->key) continue;
    int ix = (int)(c->key & 1023) - 512, iz = (int)(c->key >> 10 & 1023) - 512, iy = (int)(c->key >> 20 & 511) - 256, foot = c->key >> 29 & 1, gr = c->key >> 30 & 1;
    float mx = (float)(c->sx / c->hits), my = (float)(c->sy / c->hits), mz = (float)(c->sz / c->hits), top = NAN, g;
    if (colGround(cw, mx, mz, 202.f, -1e6f, &g, 0)) top = g;   // как goto смоука: верхняя опора ниже 200 м (viewer/main.c ground + carPlace)
    float ax = NAN, as = 0, cr = NAN, sp = 0;
    if (c->nv) { ax = .5f * atan2f(c->s2, c->c2); as = hypotf(c->s2, c->c2) / c->nv; cr = atan2f(c->sv, c->cv); sp = c->vs / c->nv; }
    fprintf(f, "%d\t%d\t%d\t%s\t%s\t%u\t%.1f\t%.2f\t%.2f\t%.2f\t%.2f\t%.4f\t%.3f\t%.4f\t%.1f\n", ix * 6, iz * 6, iy * 2, foot ? "foot" : "car", gr ? "ground" : "air",
            c->hits, c->first, mx, my, mz, top, ax, as, cr, sp);
  }
  fclose(f); rename(q, p);
  snprintf(p, sizeof p, "%s/edges.tsv", coDir); snprintf(q, sizeof q, "%s.tmp", p); f = fopen(q, "w"); if (!f) return;
  fprintf(f, "# x_a\tz_a\ty_a\tx_b\tz_b\ty_b\tраз (машина на земле -> машина на земле)\n");
  for (unsigned i = 0; i < coECap; i++) { const CoEdge *e = &coE[i]; if (!e->key) continue;
    uint32_t a = (uint32_t)(e->key & 0x1fffffff), b = (uint32_t)(e->key >> 29 & 0x1fffffff);
    fprintf(f, "%d\t%d\t%d\t%d\t%d\t%d\t%u\n", ((int)(a & 1023) - 512) * 6, ((int)(a >> 10 & 1023) - 512) * 6, ((int)(a >> 20 & 511) - 256) * 2,
            ((int)(b & 1023) - 512) * 6, ((int)(b >> 10 & 1023) - 512) * 6, ((int)(b >> 20 & 511) - 256) * 2, e->n); }
  fclose(f); rename(q, p); fflush(coEv); coLastDump = coNow();
}
static void coTick(void) { if (coOn && coNow() - coLastDump > 30.) coDump(); }   // раз в 30 с стены — для замера насыщения роя
#endif
