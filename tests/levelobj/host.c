// Гейт пакета «Объекты уровня» на Маке: настоящий level.shr + viewer/animobj.c + stateprops.c + col.c без экрана.
//   host LEVEL.shr [--plant nolive|noact|far]
// Проверки (ожидания — из данных диска, tests/levelobj/expect.py пишет их в EXPECT, см. host.sh):
//   * ANM1 есть и сходится с SPR1/COL1 (aoInit == 0); грузовик Duff (PlayAnim) найден
//   * крыша кузова Duff — опора (земля COL1 сверху на высоте верха ящика кузова из данных), по ней можно ходить
//   * △ в объёме выключателя: подъёмник Duff поднимается на величину из клипа PTRN (кадр 36 -> 72: +1.06 м), к концу клипа
//     возвращается вниз, ещё раз — снова играет; вне объёма △ не берётся
//   * ToggleOnOff (платформы АЭС): △ — едет, △ — стоит на месте; AutomaticDoor: в объёме открывается, вне — закрывается
//   * циклические (шестерня, вентиляторы) крутятся сами (spUpdate); сетка COL1 знает живой объём на каждом кадре клипа
// --plant: nolive — не вызывать aoStep (живые объёмы стоят), noact — △ не доходит, far — живой ящик уносится на 60 м
// (сетка его там не знает) — гейт обязан упасть. Итог: "CHECK имя ok|FAIL ..." и "RESULT PASS|FAIL n/m".
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "props.h"
#include "stateprops.h"
#include "animobj.h"

static int nok, nfail;
static void check(const char *name, int ok, const char *fmt, ...) __attribute__((format(printf, 3, 4)));
#include <stdarg.h>
static void check(const char *name, int ok, const char *fmt, ...) {
  char b[256]; va_list a; va_start(a, fmt); vsnprintf(b, sizeof b, fmt, a); va_end(a);
  printf("CHECK %-30s %s %s\n", name, ok ? "ok  " : "FAIL", b); if (ok) nok++; else nfail++;
}
static void *readAll(const char *p, size_t *n) {
  FILE *f = fopen(p, "rb"); if (!f) return 0;
  fseek(f, 0, SEEK_END); long s = ftell(f); rewind(f);
  unsigned char *b = aligned_alloc(16, ((size_t)s + 15) & ~(size_t)15);
  if (!b || fread(b, 1, (size_t)s, f) != (size_t)s) { fclose(f); free(b); return 0; }
  fclose(f); *n = (size_t)s; return b;
}
static ColWorld W; static Props P; static StateProps S; static AnimObjs A;
static int plantNolive, plantNoact, plantFar;

static void step(float px, float py, float pz, int foot, int act, float dt) {
  spUpdate(&S, &W, NULL, NULL, dt);
  if (!plantNolive) aoStep(&A, &S, &W, px, py, pz, foot, plantNoact ? 0 : act, dt);
}
static const float *volC(unsigned v) { const AoVol *V = &A.vol[v]; return V->kind == 0 ? W.box[V->col].c : W.cyl[V->col].c; }
static int ground(float x, float z, float top, float *y) { return colGround(&W, x, z, top, -50.f, y, 0); }
// сетка знает объём v в каждой клетке его xz-габарита
static int gridKnows(unsigned v) {
  const AoVol *V = &A.vol[v]; float lo[2], hi[2];
  if (V->kind == 0) {
    const ColBox *B = &W.box[V->col]; float ex = 0, ez = 0;
    ex = fabsf(B->ax[0]) * B->h[0] + fabsf(B->ay[0]) * B->h[1] + fabsf(B->az[0]) * B->h[2];
    ez = fabsf(B->ax[2]) * B->h[0] + fabsf(B->ay[2]) * B->h[1] + fabsf(B->az[2]) * B->h[2];
    lo[0] = B->c[0] - ex; hi[0] = B->c[0] + ex; lo[1] = B->c[2] - ez; hi[1] = B->c[2] + ez;
  } else {
    const ColCyl *C = &W.cyl[V->col]; float cx = fabsf(C->axis[0]) * C->halfLen + C->r, cz = fabsf(C->axis[2]) * C->halfLen + C->r;
    lo[0] = C->c[0] - cx; hi[0] = C->c[0] + cx; lo[1] = C->c[2] - cz; hi[1] = C->c[2] + cz;
  }
  uint32_t want = ((V->kind == 0 ? 1u : 2u) << 29) | V->col;
  int gx0 = (int)floorf((lo[0] - W.ox) * W.inv), gx1 = (int)floorf((hi[0] - W.ox) * W.inv);
  int gz0 = (int)floorf((lo[1] - W.oz) * W.inv), gz1 = (int)floorf((hi[1] - W.oz) * W.inv);
  for (int gz = gz0; gz <= gz1; gz++) for (int gx = gx0; gx <= gx1; gx++) {
    if (gx < 0 || gz < 0 || gx >= W.W || gz >= W.H) return 0;
    uint32_t c = (uint32_t)gz * (uint32_t)W.W + (uint32_t)gx; int hit = 0;
    for (uint32_t k = W.cellStart[c]; k < W.cellStart[c + 1]; k++) if (W.refs[k] == want) { hit = 1; break; }
    if (!hit) return 0;
  }
  return 1;
}

int main(int argc, char **argv) {
  if (argc < 2) { fprintf(stderr, "host LEVEL.shr [--plant nolive|noact|far]\n"); return 2; }
  for (int i = 2; i + 1 < argc; i++) if (!strcmp(argv[i], "--plant")) {
    plantNolive = !strcmp(argv[i + 1], "nolive"); plantNoact = !strcmp(argv[i + 1], "noact"); plantFar = !strcmp(argv[i + 1], "far"); }
  size_t n; unsigned char *lv = readAll(argv[1], &n);
  if (!lv || memcmp(lv, "SHR7", 4)) { printf("RESULT FAIL нет уровня %s\n", argv[1]); return 1; }
  unsigned colOff = *(unsigned *)(lv + 92), prpOff = *(unsigned *)(lv + 96);
  unsigned prpSize = *(unsigned *)(lv + prpOff + 40);
  int ec = colInit(&W, lv + colOff, prpOff - colOff), ep = propsInit(&P, lv + prpOff, prpSize), es = P.spr ? spInit(&S, P.spr, P.sprSize) : -99;
  int ea = aoInit(&A, lv + prpOff, prpSize, &S, &W);
  check("load", !ec && !ep && !es && !ea, "COL1 %d PRP2 %d SPR1 %d ANM1 %d (объектов %u, живых объёмов %u)", ec, ep, es, ea, A.nobj, A.nvol);
  if (ea) { printf("RESULT FAIL %d/%d\n", nok, nok + nfail); return 1; }

  // ---- грузовик Duff (единственный PlayAnim уровня 1, action-локатор TForml1z2_dufftruckShape01)
  int duff = -1; for (unsigned k = 0; k < A.nobj; k++) if (A.obj[k].action == AO_PLAYANIM) duff = (int)k;
  check("duff.found", duff >= 0 && A.obj[duff].nVol > 0 && A.obj[duff].nfr == 186, "объект %d, живых объёмов %d, кадров %d",
        duff, duff >= 0 ? A.obj[duff].nVol : -1, duff >= 0 ? A.obj[duff].nfr : -1);
  if (duff < 0) { printf("RESULT FAIL %d/%d\n", nok, nok + nfail); return 1; }
  const AoObj *D = &A.obj[duff]; float tc[3] = {D->c[0], D->c[1] - 0.9f, D->c[2]};
  step(tc[0], tc[1], tc[2], 1, 0, 1.f / 30);   // первый шаг: живые объёмы на месте (кадр 0)
  unsigned lift = D->firstVol;                   // платформа подъёмника: самый широкий плоский ящик среди живых
  for (unsigned v = D->firstVol; v < (unsigned)D->firstVol + D->nVol; v++)
    if (A.vol[v].kind == 0 && A.vol[v].h[1] < 0.2f && A.vol[v].h[0] * A.vol[v].h[2] > A.vol[lift].h[0] * A.vol[lift].h[2]) lift = v;
  // опора — верх платформы: земля сверху от уровня чуть выше платформы (ящики на подъёмнике выше — их верх не берём)
  float lx = volC(lift)[0], lz = volC(lift)[2], ly0 = volC(lift)[1], g0 = -99, g1 = -99, g2 = -99, gTop = -99;
  ground(lx, lz, volC(lift)[1] + 0.3f, &g0);
  // крыша кузова: статичный ящик кузова Duff (сустав duffTruck1) — земля сверху над центром грузовика выше 6.5 м
  int topOk = ground(D->c[0] + 1.4f, D->c[2] + 3.6f, 20.f, &gTop);
  check("duff.roof", topOk && gTop > 6.5f, "земля над кузовом y=%.2f (верх ящика кузова из данных ~7.8)", gTop);
  step(tc[0], tc[1], tc[2], 1, 0, 1.f / 30);
  check("duff.want", aoWantsAction(&A) == duff, "△ в объёме выключателя -> объект %d (ждали %d)", aoWantsAction(&A), duff);
  step(tc[0] + 30.f, tc[1], tc[2], 1, 0, 1.f / 30);
  check("duff.want_far", aoWantsAction(&A) == -1, "в 30 м от выключателя △ не берётся (%d)", aoWantsAction(&A));
  step(tc[0], tc[1], tc[2], 1, 0, 1.f / 30);
  step(tc[0], tc[1], tc[2], 1, 1, 1.f / 30);    // △
  for (int f = 0; f < 90; f++) step(tc[0] + 30.f, tc[1], tc[2], 0, 0, 1.f / 30);   // 3 с: подъёмник наверху (кадры 72..144)
  float ly1 = volC(lift)[1];
  ground(lx, lz, ly1 + 0.3f, &g1);
  check("duff.lift_up", g1 - g0 > 0.9f && g1 - g0 < 1.25f && ly1 - ly0 > 0.9f, "земля на подъёмнике %.2f -> %.2f (+%.2f, в клипе +1.06), платформа +%.2f",
        g0, g1, g1 - g0, ly1 - ly0);
  int gk = 1; for (unsigned v = D->firstVol; v < (unsigned)D->firstVol + D->nVol; v++) gk &= gridKnows(v);
  unsigned gbad = 0xFFFF;
  for (int f = 0; f < 120; f++) step(tc[0] + 30.f, tc[1], tc[2], 0, 0, 1.f / 30);  // ещё 4 с: клип кончился (186 кадров)
  ground(lx, lz, volC(lift)[1] + 0.3f, &g2);
  check("duff.lift_down", fabsf(g2 - g0) < 0.1f && !A.run[duff].playing, "после клипа %.2f (было %.2f), играет=%d", g2, g0, A.run[duff].playing);

  // ---- переключатели АЭС: ToggleOnOff
  int tog = -1; for (unsigned k = 0; k < A.nobj; k++) if (A.obj[k].action == AO_TOGGLE && A.obj[k].nVol) { tog = (int)k; break; }
  if (tog >= 0) {
    const AoObj *T = &A.obj[tog]; float p[3] = {T->c[0], T->c[1] - 0.9f, T->c[2]};
    step(p[0], p[1], p[2], 1, 0, 1.f / 30); float c0[3]; memcpy(c0, volC(T->firstVol), sizeof c0);
    step(p[0], p[1], p[2], 1, 1, 1.f / 30);
    for (int f = 0; f < 45; f++) step(p[0], p[1], p[2], 1, 0, 1.f / 30);
    const float *c1 = volC(T->firstVol); float d1 = sqrtf((c1[0] - c0[0]) * (c1[0] - c0[0]) + (c1[1] - c0[1]) * (c1[1] - c0[1]) + (c1[2] - c0[2]) * (c1[2] - c0[2]));
    step(p[0], p[1], p[2], 1, 1, 1.f / 30); float fr = A.run[tog].f; float c2[3]; memcpy(c2, volC(T->firstVol), sizeof c2);
    for (int f = 0; f < 45; f++) step(p[0], p[1], p[2], 1, 0, 1.f / 30);
    const float *c3 = volC(T->firstVol); float d2 = fabsf(c3[0] - c2[0]) + fabsf(c3[1] - c2[1]) + fabsf(c3[2] - c2[2]);
    check("toggle.run_stop", d1 > 0.3f && d2 < 1e-4f && A.run[tog].f == fr, "объект %d: △ — сдвиг %.2f м за 1.5 с; △ ещё раз — стоит (сдвиг %.4f)", tog, d1, d2);
    for (unsigned v = T->firstVol; v < (unsigned)T->firstVol + T->nVol; v++) gk &= gridKnows(v);
  } else check("toggle.found", 0, "нет ToggleOnOff с объёмами");
  // ---- AutomaticDoor
  int door = -1; for (unsigned k = 0; k < A.nobj; k++) if (A.obj[k].action == AO_AUTODOOR) door = (int)k;
  if (door >= 0) {
    const AoObj *O = &A.obj[door]; float p[3] = {O->c[0], O->c[1] - 0.9f, O->c[2]};
    for (int f = 0; f < 40; f++) step(p[0], p[1], p[2], 1, 0, 1.f / 30);
    float open = A.run[door].f;
    for (int f = 0; f < 40; f++) step(p[0] + 40.f, p[1], p[2], 1, 0, 1.f / 30);
    check("door.open_close", open >= O->nfr - 1.01f && A.run[door].f == 0.f, "в объёме кадр %.1f из %d, вне — %.1f", open, O->nfr - 1, A.run[door].f);
  } else check("door.found", 0, "нет AutomaticDoor");
  // ---- циклические с живыми объёмами (шестерня, вентиляторы): крутятся сами, сетка знает объём на всех кадрах
  int cyc = 0, cycMoved = 0;
  for (unsigned k = 0; k < A.nobj; k++) {   // только те, кому данные дают цикл (состояние SPR1 по кругу); клип без цикла и без
    const AoObj *O = &A.obj[k]; if (O->action || !O->nVol) continue;   // action-локатора (пружина spring3) стоит на кадре 0
    if (S.state[S.type[S.inst[O->firstInst].type].firstState].poseMode != 2) continue; cyc++;
    float p[3] = {O->c[0], O->c[1], O->c[2]}; const SpRun *r = &S.run[O->firstInst]; p[0] = r->x; p[1] = r->y; p[2] = r->z;
    step(p[0], p[1], p[2], 0, 0, 1.f / 30); float c0[12]; memcpy(c0, volC(O->firstVol), sizeof c0); float mx = 0;
    for (int f = 0; f < 60; f++) {   // центр и оси (у ящика c, ax, ay, az подряд; вентилятор крутится на месте — меняются оси)
      step(p[0], p[1], p[2], 0, 0, 1.f / 30); const float *c = volC(O->firstVol); float d = 0;
      for (int q = 0; q < (A.vol[O->firstVol].kind == 0 ? 12 : 6); q++) d += fabsf(c[q] - c0[q]);
      if (d > mx) mx = d;
      for (unsigned v = O->firstVol; v < (unsigned)O->firstVol + O->nVol; v++) if (!gridKnows(v)) { gk = 0; gbad = v; }
    }
    cycMoved += mx > 1e-3f;
    if (mx <= 1e-3f) printf("  стоит: объект %u (экз. %u, кадров %u, объёмов %u, состояние SPR1 poseMode %u)\n", k, O->firstInst, O->nfr, O->nVol,
                            S.state[S.type[S.inst[O->firstInst].type].firstState].poseMode);
  }
  check("cyclic.move", cyc > 0 && cycMoved == cyc, "%d из %d циклических с живыми объёмами двигались", cycMoved, cyc);
  if (plantFar) { ColBox *B = (ColBox *)&W.box[A.vol[lift].col]; B->c[0] += 60.f; gk &= gridKnows(lift); }
  check("grid.sweep", gk, "сетка COL1 знает каждый живой объём во всех клетках его текущего габарита%s", gk ? "" : " (нет, например объём ANM1 №...)");
  if (!gk && gbad != 0xFFFF) printf("  сетка не знает объём %u (объект %u)\n", gbad, A.vol[gbad].obj);
  printf("AO presses=%u plays=%u moved=%u\n", A.presses, A.plays, A.moved);
  printf("RESULT %s %d/%d\n", nfail ? "FAIL" : "PASS", nok, nok + nfail);
  return nfail ? 1 : 0;
}
