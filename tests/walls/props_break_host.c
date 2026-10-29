// Тест хоста для гейта #588 (сбиваемое) и #589 (исчезновение пнутых пропов)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "props.h"
#include "stateprops.h"
#include "car.h"

// Стаб для Гомера
unsigned homerSolidFrame = 0;

static Props props;
static StateProps sp;
static ColWorld world;
static Car car;

// Настоящая логика gamePropKick из viewer/game.c
static int testPropKick(void *u, unsigned i, float dx, float dz) {
  (void)u; (void)dx; (void)dz;
  float pos[3] = {props.def[i].x, props.def[i].y, props.def[i].z};
  int b = spBreakOf(&sp, props.def[i].type);
  if (b < 0) return 0;
  int r = spBreak(&sp, (unsigned)b, pos, props.def[i].q);
#ifndef BREAK_FX_OLD
  if (!r) {
    unsigned bi = sp.type[b].bindex;
#ifndef HYDRANT_SMASH_OLD
    // №588 (#10, №434): гидрант (bi == 3, вода гидранта) при ударе заменяется эффектом воды и прячется
    if (bi == 3) r = 1;
#endif
    if (bi == 18 || bi == 30 || bi == 31 || bi == 32) r = 1;
  }
#endif
  return r;
}

static int step_seen_all(void *u, float x, float y, float z, float r) { (void)u; (void)x; (void)y; (void)z; (void)r; return 1; }
static int step_seen_none(void *u, float x, float y, float z, float r) { (void)u; (void)x; (void)y; (void)z; (void)r; return 0; }

int main(int argc, char **argv) {
  int red_mode = (argc > 1 && !strcmp(argv[1], "red"));
  const char *l1_path = (argc > 2) ? argv[2] : "build/level.shr";
  const char *l2_path = (argc > 3) ? argv[3] : "build/levels/l2/level.shr";

  printf("=== Тест #588 и #589 (%s) ===\n", red_mode ? "КРАСНЫЙ КОНТРОЛЬ" : "ЗЕЛЁНЫЙ ПРОГОН");

  int fails = 0;

  // -------------------------------------------------------------
  // 1. Проверка #588 (гидрант L1: inst 258)
  // -------------------------------------------------------------
  {
    FILE *f = fopen(l1_path, "rb");
    if (!f) { printf("Не найден %s\n", l1_path); return 2; }
    fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
    unsigned char *data = malloc((size + 15) & ~15);
    fread(data, 1, size, f); fclose(f);
    unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
    if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
    colInit(&world, data + co, ce - co);
    propsInit(&props, data + po, *(unsigned *)(data + po + 40));
    if (props.spr) spInit(&sp, props.spr, props.sprSize);
    props.onKick = testPropKick;

    // Гидрант inst 258 в L1: удар машиной
    unsigned hi = 258;
    PropState *hst = &props.st[hi];
    carInit(&car, 0, &world, props.def[hi].x, 3.5f, props.def[hi].z - 6.0f, 0.0f);
    carSetSpeed(&car, 15.0f);
    CarInput in = {1.0f, 0, 0, 0};

    int kicked = 0;
    for (int step = 0; step < 20; step++) {
      carUpdate(&car, &world, &in, 1.0f / 30.0f);
      propsUpdate(&props, &world, &car, 1.0f / 30.0f);
      if (hst->hidden) { kicked = 1; break; }
    }

    if (kicked && hst->hidden) {
      printf("  [#588 HYDRANT] hidden=%d, kicked=1, car v=%.2f -> PASS\n", hst->hidden, car.v);
    } else {
      printf("  [#588 HYDRANT] hidden=%d, kicked=%d, car v=%.2f -> FAIL\n", hst->hidden, kicked, car.v);
      fails++;
    }

    free(data);
  }

  // -------------------------------------------------------------
  // 2. Проверка #588 (заборчик L2 C3-5: inst 6, щепки SPFX_WOOD)
  // -------------------------------------------------------------
  {
    FILE *f = fopen(l2_path, "rb");
    if (!f) { printf("Не найден %s\n", l2_path); return 2; }
    fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
    unsigned char *data = malloc((size + 15) & ~15);
    fread(data, 1, size, f); fclose(f);
    unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
    if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
    colInit(&world, data + co, ce - co);
    propsInit(&props, data + po, *(unsigned *)(data + po + 40));
    if (props.spr) spInit(&sp, props.spr, props.sprSize);
    props.onKick = testPropKick;

    // Заборчик inst 6 в L2
    unsigned fi = 6;
    SpRun *frun = &sp.run[fi];
    carInit(&car, 0, &world, sp.inst[fi].x, sp.inst[fi].y + 0.5f, sp.inst[fi].z - 6.0f, 0.0f);
    carSetSpeed(&car, 15.0f);

    int wood_fx = 0;
    for (int step = 0; step < 20; step++) {
      carUpdate(&car, &world, &(CarInput){1.0f, 0, 0, 0}, 1.0f / 30.0f);
      spUpdate(&sp, &world, &car, NULL, 1.0f / 30.0f);
      SpFxOut o;
      while (spFxPop(&sp, &o)) {
        if (o.preset == SPFX_WOOD) wood_fx++;
      }
      if (!frun->colOn) break;
    }

    if (wood_fx >= 3) {
      printf("  [#588 FENCE] wood debris particles count=%d -> PASS\n", wood_fx);
    } else {
      printf("  [#588 FENCE] wood debris particles count=%d (need >=3) -> FAIL\n", wood_fx);
      fails++;
    }

    // -------------------------------------------------------------
    // 3. Проверка #588 (стоящие пропы L2 не пролетаются как призрак: inst 381)
    // -------------------------------------------------------------
    {
      unsigned pi = 381;
      PropState *pst = &props.st[pi];

      CarBox cb;
      carInit(&car, 0, &world, pst->x, 28.75f + 0.5f, pst->z - 6.0f, 0.0f);
      carBox(&car, &cb);
      float ext = pst->hy;
      car.y = (pst->y + ext - cb.lo) + 0.20f;
      car.vel[1] = -2.0f;
      car.vel[2] = 15.0f;
      car.v = 15.0f;

      for (int step = 0; step < 20; step++) {
        car.z += car.vel[2] * (1.0f / 30.0f);
        propsHitCar(&props, &world, &car, NULL);
        if (!pst->asleep) break;
      }

      if (!pst->asleep) {
        printf("  [#588 GHOST PROP] prop 381 hit registered: asleep=%d vel=(%.2f, %.2f) -> PASS\n", pst->asleep, pst->vel[0], pst->vel[2]);
      } else {
        printf("  [#588 GHOST PROP] prop 381 passed through as ghost: asleep=%d -> FAIL\n", pst->asleep);
        fails++;
      }
    }

    // -------------------------------------------------------------
    // 4. Проверка #589 (трубы L2 inst 429: через 30 с (PROP_FADE_S, решение 15.10; до — 12 с) сбитый предмет уходит, только когда камера его не видит; видимый и миссионный остаются)
    // -------------------------------------------------------------
    {
      unsigned pi = 429;
      PropState *pst = &props.st[pi];
      int hid[3], at25 = -1;
      for (int var = 0; var < 3; var++) {   // 0 — вне вида, 1 — в виде, 2 — вне вида, но предмет миссии (noRespawn)
        pst->asleep = 0; pst->fresh = 0; pst->vel[0] = 0.f; pst->fadeT = 0.0f; pst->hidden = 0; pst->noRespawn = var == 2; pst->away = 0.f;
        for (int step = 0; step < 31 * 30; step++) {
          if (var == 0 && step == 25 * 30) at25 = pst->hidden;   // к 25 с ещё лежит: 12 с прежнего правила уже не уходят
          propsAdvance(&props, &world, 1.0f / 30.0f);
          propsRespawnStep(&props, pst->x + 10.f, pst->z, 1.0f / 30.0f, var == 1 ? step_seen_all : step_seen_none, NULL);
        }
        hid[var] = pst->hidden;
      }
      pst->noRespawn = 0;
      if (hid[0] == 1 && hid[1] == 0 && hid[2] == 0 && at25 == 0) {
        printf("  [#589 PROP FADE] 25 с лежит (%d), 31 с: вне вида — убран, в виде — лежит, предмет миссии — лежит (%d %d %d) -> PASS\n", at25, hid[0], hid[1], hid[2]);
      } else {
        printf("  [#589 PROP FADE] через 25 с убран %d (нужно 0), через 31 с: вне вида %d (нужно 1), в виде %d (0), миссионный %d (0) -> FAIL\n", at25, hid[0], hid[1], hid[2]);
        fails++;
      }
    }

    free(data);
  }

  // -------------------------------------------------------------
  // 5. Проверка #588 (ларёк L2 J7-7, проп 434, тип 18, x 120.8 z -33.3): удар машиной 5/10/20 м/с с 4 сторон — проп обязан сдвинуться
  //    (проснуться или спрятаться), машина не проходит сквозь него «призраком»
  // -------------------------------------------------------------
  {
    FILE *f = fopen(l2_path, "rb");
    if (!f) { printf("Не найден %s\n", l2_path); return 2; }
    fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
    unsigned char *data = malloc((size + 15) & ~15);
    fread(data, 1, size, f); fclose(f);
    unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
    if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
    static const float spd[3] = {5.f, 10.f, 20.f}; static const float dirs[4][2] = {{0, 1}, {0, -1}, {1, 0}, {-1, 0}};
    int bad = 0, total = 0;
    for (int d = 0; d < 4; d++) for (int si = 0; si < 3; si++) {
      memset(&props, 0, sizeof props); memset(&sp, 0, sizeof sp); memset(&world, 0, sizeof world);
      colInit(&world, data + co, ce - co);
      propsInit(&props, data + po, *(unsigned *)(data + po + 40));
      if (props.spr) spInit(&sp, props.spr, props.sprSize);
      props.onKick = testPropKick;
      PropState *s = &props.st[434];
      float cx = s->x, cz = s->z, ux = dirs[d][0], uz = dirs[d][1], sx = cx - ux * 9.f, sz = cz - uz * 9.f, g = 0.f;
      colGround(&world, sx, sz, s->y + 3.f, s->y - 5.f, &g, 0);
      carInit(&car, 0, &world, sx, g + 0.6f, sz, atan2f(ux, uz));
      carSetSpeed(&car, spd[si]);
      int kicked = 0;
      for (int st = 0; st < 30 * 4; st++) {
        carUpdate(&car, &world, &(CarInput){1.0f, 0, 0, 0}, 1.0f / 30.0f);
        propsUpdate(&props, &world, &car, 1.0f / 30.0f);
        if (!s->asleep || s->hidden) kicked = 1;
        if ((car.x - cx) * ux + (car.z - cz) * uz > 0.5f) break;
      }
      total++;
      if (!kicked) { bad++; printf("  [#588 STALL 434] сторона %d, %.0f м/с: ларёк не тронут, машина прошла насквозь -> FAIL\n", d, spd[si]); }
    }
    free(data);
    if (!bad) printf("  [#588 STALL 434] 4 стороны x 5/10/20 м/с: ларёк сбит во всех %d заездах -> PASS\n", total);
    else fails++;
  }

  printf("\nИТОГ: %s (%d сбоев)\n", fails ? "FAIL" : "PASS", fails);
  return fails ? 1 : 0;
}
