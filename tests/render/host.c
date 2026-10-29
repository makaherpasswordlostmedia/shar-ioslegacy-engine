// Гейт ускорения отрисовки (05.10, облако; viewer/render_fast.h, docs/ОПТИМИЗАЦИИ_ОТОБРАЖЕНИЯ_2026-10-05.md О2/О4/О11). Без level.shr:
// синтетические миры с фиксированным seed, настоящий код viewer/render_fast.h, viewer/ge_guard.h и viewer/stateprops.c.
//   О2 (стейтпропы вне кадра): случайные типы (цепочки суставов, ключи клипа, масштабы, не нормированные повороты), любая поза
//      (spPose + spPieceMatrix — настоящие) — все 8 углов куба вершин каждого куска внутри сферы rfSpTypeRadius; экземпляр, который
//      rfSphereOut отсёк, не имеет ни одного угла внутри пирамиды кадра (картинка та же). Красный (-DRF_TEST_BROKEN): радиус по
//      коробке кадра 0 (spBounds, как у карточек collDraw) — анимация выходит за сферу, проба обязана упасть.
//   О11 (листы у камеры): клетки из кусков-треугольников у камеры с ближней 0,25–1,5 м; если ни один кусок не под риском по своему
//      боксу (ggBoxRiskAx), лист рисует то же, что drawGeoG: ни один треугольник не прошёл бы срез (ggRisk). Красный: «клетка в
//      риске — всегда листом» (без проверки кусков) — пропускает треугольники под риском, обязан упасть.
//   О4 (повтор клетки в dlCity): модель цикла dlCity по отсортированному списку — новый путь (клетка рядом с ключом) делает те же
//      действия в том же порядке, что прежний. Красный: метка без признака полупрозрачности — теряет стекло, обязан упасть.
// Выход 0 — всё зелёное; печать — сводка (сколько экземпляров/клеток отсечено/спасено — ориентир выигрыша на синтетике).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "render_fast.h"
#include "ge_guard.h"

static unsigned rng = 12345u;
static float fr(void) { rng = rng * 1664525u + 1013904223u; return (rng >> 8) * (1.f / 16777216.f); }
static float fu(float a, float b) { return a + (b - a) * fr(); }
static void randQ(float q[4], float m) { float l = 0; for (int k = 0; k < 4; k++) { q[k] = fu(-1, 1); l += q[k] * q[k]; } l = m / sqrtf(l); for (int k = 0; k < 4; k++) q[k] *= l; }
static void quatRc(const float q[4], float R[9]) {   // как stateprops.c quatR (R по столбцам)
  float w = q[0], x = q[1], y = q[2], z = q[3];
  R[0] = 1.f - 2.f * (y * y + z * z); R[1] = 2.f * (x * y + w * z); R[2] = 2.f * (x * z - w * y);
  R[3] = 2.f * (x * y - w * z); R[4] = 1.f - 2.f * (x * x + z * z); R[5] = 2.f * (y * z + w * x);
  R[6] = 2.f * (x * z + w * y); R[7] = 2.f * (y * z - w * x); R[8] = 1.f - 2.f * (x * x + y * y);
}
// пирамида кадра — копия main.c setupPlanes (внутренние нормали 4 боковых плоскостей)
static void planes(float fx, float fy, float fz, float fovy, float pl[4][3]) {
  float rx = -fz, rz = fx, rl = sqrtf(rx * rx + rz * rz); if (rl < 1e-4f) { rx = 1; rz = 0; rl = 1; }
  rx /= rl; rz /= rl;
  float ux = -rz * fy, uy = rz * fx - rx * fz, uz = rx * fy;
  float tv = tanf(fovy * .5f * 3.14159265f / 180.f) * 1.03f, th = tv * (480.f / 272.f);
  float n[4][3] = {{fx * th - rx, fy * th, fz * th - rz}, {fx * th + rx, fy * th, fz * th + rz},
                   {fx * tv - ux, fy * tv - uy, fz * tv - uz}, {fx * tv + ux, fy * tv + uy, fz * tv + uz}};
  memcpy(pl, n, sizeof n);
}

// ---------------------------------------------------------------- О2
#define NT 300
#define MAXJ 12
#define MAXP 8
#define MAXF 24
static int testSp(void) {
  static SpType ty[NT]; static SpJoint jt[NT * MAXJ]; static SpPiece pcs[NT * MAXP]; static float key[NT * MAXF * MAXJ * 7];
  static SpInst inst[NT]; static SpRun run[NT]; static float jm[NT * MAXJ * 12];
  StateProps sp; memset(&sp, 0, sizeof sp);
  unsigned nj = 0, np = 0, nk = 0;
  for (unsigned t = 0; t < NT; t++) {
    SpType *T = &ty[t]; memset(T, 0, sizeof *T);
    unsigned nJ = 1 + (unsigned)(fr() * MAXJ) % MAXJ, nP = 1 + (unsigned)(fr() * MAXP) % MAXP, nfr = (t % 3) ? 1 + (unsigned)(fr() * MAXF) % MAXF : 0;
    unsigned ntr = 0;
    T->firstJoint = (uint16_t)nj; T->nJoint = (uint16_t)nJ; T->firstPiece = (uint16_t)np; T->nPiece = (uint16_t)nP; T->keyOff = nk / 7;
    for (unsigned j = 0; j < nJ; j++) {
      SpJoint *J = &jt[nj + j]; memset(J, 0, sizeof *J);
      J->parent = (int16_t)(j ? (int)(fr() * j) - (fr() < .2f) : -1); if (J->parent >= (int)j) J->parent = (int16_t)(j - 1);
      J->track = (int16_t)(nfr && fr() < .7f ? (int)ntr++ : -1);
      randQ(J->q, fu(.85f, 1.15f)); for (int k = 0; k < 3; k++) { J->t[k] = fu(-1.5f, 1.5f); J->s[k] = fu(.6f, 1.6f); }
    }
    T->frames = nfr | (ntr << 16);
    for (unsigned f = 0; f < nfr; f++) for (unsigned r = 0; r < ntr; r++) {
      float *a = key + nk + ((size_t)f * ntr + r) * 7; for (int k = 0; k < 3; k++) a[k] = fu(-2.f, 2.f); randQ(a + 3, 1.f); }
    nk += nfr * ntr * 7;
    // коробка кадра 0 (как экспорт: c, h в осях объекта) — для красного контроля: углы кусков в позе кадра 0
    float lo[3] = {1e9f, 1e9f, 1e9f}, hi[3] = {-1e9f, -1e9f, -1e9f};
    for (unsigned k = 0; k < nP; k++) {
      SpPiece *P = &pcs[np + k]; memset(P, 0, sizeof *P);
      P->ox = fu(-1, 1); P->oy = fu(-1, 1); P->oz = fu(-1, 1); P->sc = fu(.1f, 2.f); P->flags = (int32_t)(((unsigned)(fr() * nJ) % nJ) << 8); P->ni = 3;
    }
    nj += nJ; np += nP;
    inst[t].type = (uint16_t)t; randQ(inst[t].q, 1.f);
    SpRun *r = &run[t]; memset(r, 0, sizeof *r); r->alive = 1; r->x = fu(-50, 50); r->y = fu(-5, 5); r->z = fu(-50, 50);
    quatRc(inst[t].q, r->R); r->jm = jm + t * MAXJ * 12;
    (void)lo; (void)hi;
  }
  sp.type = ty; sp.joint = jt; sp.piece = pcs; sp.key = key; sp.inst = inst; sp.run = run; sp.ntype = NT; sp.ninst = NT;
  // коробка кадра 0 для красного: поза кадра 0, углы кусков в осях объекта
  for (unsigned t = 0; t < NT; t++) {
    SpRun *r = &run[t]; r->poseF = 0; r->poseValid = 0; spPose(&sp, t);
    float lo[3] = {1e9f, 1e9f, 1e9f}, hi[3] = {-1e9f, -1e9f, -1e9f}, Rs[9]; memcpy(Rs, r->R, sizeof Rs);
    static const float I[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1}; memcpy(r->R, I, sizeof I); float x0 = r->x, y0 = r->y, z0 = r->z; r->x = r->y = r->z = 0;
    for (unsigned k = 0; k < ty[t].nPiece; k++) { float m[16]; spPieceMatrix(&sp, t, k, m);
      for (int c = 0; c < 8; c++) { float v[3] = {c & 1 ? 1.f : -1.f, c & 2 ? 1.f : -1.f, c & 4 ? 1.f : -1.f};
        for (int a = 0; a < 3; a++) { float w = m[a] * v[0] + m[4 + a] * v[1] + m[8 + a] * v[2] + m[12 + a]; if (w < lo[a]) lo[a] = w; if (w > hi[a]) hi[a] = w; } } }
    for (int a = 0; a < 3; a++) { ty[t].c[a] = (lo[a] + hi[a]) * .5f; ty[t].h[a] = (hi[a] - lo[a]) * .5f; }
    memcpy(r->R, Rs, sizeof Rs); r->x = x0; r->y = y0; r->z = z0;
  }
  float rad[NT];
  for (unsigned t = 0; t < NT; t++) {
#ifdef RF_TEST_BROKEN
    float c[3], rr; spBounds(&sp, t, c, &rr); rad[t] = rr + sqrtf(ty[t].c[0] * ty[t].c[0] + ty[t].c[1] * ty[t].c[1] + ty[t].c[2] * ty[t].c[2]);   // сфера кадра 0 вокруг экземпляра
#else
    rad[t] = rfSpTypeRadius(&sp, t);
#endif
    if (rad[t] < 0.f) { printf("О2 FAIL: тип %u — радиус не посчитан\n", t); return 1; }
  }
  unsigned bad = 0, checked = 0, cut = 0, cutBad = 0, poses = 0; float worst = 0.f, sumR = 0.f;
  for (unsigned t = 0; t < NT; t++) sumR += rad[t];
  for (int it = 0; it < 40; it++) {
    float pl[4][3], e[3] = {fu(-60, 60), fu(0, 8), fu(-60, 60)}, f[3] = {fu(-1, 1), fu(-.3f, .3f), fu(-1, 1)};
    float fl = sqrtf(f[0] * f[0] + f[1] * f[1] + f[2] * f[2]); for (int a = 0; a < 3; a++) f[a] /= fl;
    planes(f[0], f[1], f[2], 52.f, pl);
    for (unsigned t = 0; t < NT; t++) {
      SpRun *r = &run[t]; unsigned nfr = ty[t].frames & 0xFFFF;
      r->poseF = nfr ? fu(-1.f, (float)nfr + 1.f) : 0.f; r->poseValid = 0; spPose(&sp, t); poses++;
      float c[3] = {r->x, r->y, r->z}; int out = rfSphereOut((const float (*)[3])pl, e, c, rad[t]); cut += out;
      for (unsigned k = 0; k < ty[t].nPiece; k++) { float m[16]; spPieceMatrix(&sp, t, k, m);
        for (int q = 0; q < 8; q++) { float v[3] = {q & 1 ? 1.f : -1.f, q & 2 ? 1.f : -1.f, q & 4 ? 1.f : -1.f}, w[3];
          for (int a = 0; a < 3; a++) w[a] = m[a] * v[0] + m[4 + a] * v[1] + m[8 + a] * v[2] + m[12 + a];
          float d = sqrtf((w[0] - c[0]) * (w[0] - c[0]) + (w[1] - c[1]) * (w[1] - c[1]) + (w[2] - c[2]) * (w[2] - c[2]));
          checked++; if (d > rad[t]) { bad++; if (d - rad[t] > worst) worst = d - rad[t]; }
          if (out) { int inside = 1; for (int i = 0; i < 4; i++) if ((w[0] - e[0]) * pl[i][0] + (w[1] - e[1]) * pl[i][1] + (w[2] - e[2]) * pl[i][2] < 0) inside = 0;
            cutBad += inside; } } }
    }
  }
  printf("О2: типов %d, поз %u, углов %u; вне сферы %u (худший выход %.3f м); отсечено экземпляров %u из %u (%.0f %%), из них с углом в кадре %u; средний радиус %.2f м\n",
         NT, poses, checked, bad, worst, cut, poses, 100.f * cut / poses, cutBad, sumR / NT);
  return bad || cutBad;
}

// ---------------------------------------------------------------- О11
static void camAxes(const float f[3], float R[3], float U[3]) {   // как main.c: R = f × up, U = R × f
  const float up[3] = {0, 1, 0};
  R[0] = f[1] * up[2] - f[2] * up[1]; R[1] = f[2] * up[0] - f[0] * up[2]; R[2] = f[0] * up[1] - f[1] * up[0];
  float l = sqrtf(R[0] * R[0] + R[1] * R[1] + R[2] * R[2]); for (int a = 0; a < 3; a++) R[a] /= l;
  U[0] = R[1] * f[2] - R[2] * f[1]; U[1] = R[2] * f[0] - R[0] * f[2]; U[2] = R[0] * f[1] - R[1] * f[0];
}
static int testGg(void) {
  unsigned cellsRisk = 0, cellsList = 0, trisMiss = 0, trisAll = 0;
  for (int it = 0; it < 4000; it++) {
    float E[3] = {0, fu(.8f, 2.f), 0}, F[3] = {fu(-1, 1), fu(-.5f, .2f), fu(-1, 1)}, R[3], U[3];
    float fl = sqrtf(F[0] * F[0] + F[1] * F[1] + F[2] * F[2]); for (int a = 0; a < 3; a++) F[a] /= fl;
    camAxes(F, R, U);
    GgCam k; k.tvy = tanf(52.f * 3.14159265f / 360.f); k.tvx = k.tvy * (480.f / 272.f); k.zn = fu(.25f, 1.5f);
    // клетка 20×20 м рядом с камерой; куски — 1..6 полос треугольников (земля, стена, тень), рёбра до 7 м
    float cx = fu(-15, 15), cz = fu(-15, 15); float cell[6] = {cx - 10, -1, cz - 10, cx + 10, 6, cz + 10};
    int np = 1 + it % 6; float tri[6][12][3][3]; int nt[6]; float bb[6][6];
    for (int p = 0; p < np; p++) {
      float px = fu(cell[0], cell[3] - 7), pz = fu(cell[2], cell[5] - 7), py = fu(-.5f, 4.f), sz = fu(.5f, 7.f); nt[p] = 1 + (int)(fr() * 12) % 12;
      for (int a = 0; a < 3; a++) { bb[p][a] = 1e9f; bb[p][3 + a] = -1e9f; }
      for (int t = 0; t < nt[p]; t++) for (int v = 0; v < 3; v++) {
        float w[3] = {px + fu(0, sz), py + fu(0, sz * (p & 1 ? 1.f : .05f)), pz + fu(0, sz)};
        for (int a = 0; a < 3; a++) { tri[p][t][v][a] = w[a]; if (w[a] < bb[p][a]) bb[p][a] = w[a]; if (w[a] > bb[p][3 + a]) bb[p][3 + a] = w[a]; }
      }
    }
    if (!ggBoxRiskAx(cell, E, R, U, F, &k)) continue;   // клетка не в риске — листом и раньше
    cellsRisk++;
    int anyRisk = 0;
#ifndef RF_TEST_BROKEN
    for (int p = 0; p < np; p++) anyRisk |= ggBoxRiskAx(bb[p], E, R, U, F, &k);   // main.c ggCellCut
#endif
    if (anyRisk) continue;   // по кускам, как раньше
    cellsList++;
    for (int p = 0; p < np; p++) for (int t = 0; t < nt[p]; t++) {   // лист: drawGeoG не резал бы ни одного треугольника?
      GgV g[3]; memset(g, 0, sizeof g);
      for (int v = 0; v < 3; v++) { float w[3] = {tri[p][t][v][0] - E[0], tri[p][t][v][1] - E[1], tri[p][t][v][2] - E[2]};
        g[v].c[0] = w[0] * R[0] + w[1] * R[1] + w[2] * R[2]; g[v].c[1] = w[0] * U[0] + w[1] * U[1] + w[2] * U[2]; g[v].c[2] = w[0] * F[0] + w[1] * F[1] + w[2] * F[2]; }
      trisAll++; if (ggRisk(&g[0], &g[1], &g[2], &k)) trisMiss++;
    }
  }
  printf("О11: клеток в риске %u, из них листом %u (%.0f %%); треугольников в них %u, под риском (лист их бы не срезал) %u\n",
         cellsRisk, cellsList, cellsRisk ? 100.f * cellsList / cellsRisk : 0.f, trisAll, trisMiss);
  return trisMiss != 0 || cellsList == 0;
}

// ---------------------------------------------------------------- О4
// модель dlCity: на отсортированный кусок — действие: 'T' стекло в очередь tq, 'L' лист клетки, 'F' прежний путь, '-' пропуск
#define ND 600
#define NC 80
static int testDl(void) {
  unsigned diff = 0, skipped = 0, total = 0;
  for (int it = 0; it < 300; it++) {
    int nd = 50 + (int)(fr() * (ND - 50)); unsigned cellOf[ND]; int transp[ND], farv[ND]; unsigned short scl[ND];
    unsigned ok[NC]; for (int c = 0; c < NC; c++) ok[c] = fr() < .9f;   // 10 % клеток без листа (прежний путь)
    for (int i = 0; i < nd; i++) { cellOf[i] = (unsigned)(fr() * (NC + 2)); transp[i] = fr() < .15f; farv[i] = fr() < .3f;
#ifdef RF_TEST_BROKEN
      scl[i] = cellOf[i] >= 0xFFFFu ? 0xFFFFu : (unsigned short)cellOf[i];   // без признака полупрозрачности
#else
      scl[i] = transp[i] || cellOf[i] >= 0xFFFFu ? 0xFFFFu : (unsigned short)cellOf[i];   // main.c cullPiece tcl
#endif
    }
    char a0[ND], a1[ND];
    for (int pass = 0; pass < 2; pass++) {
      unsigned mark[NC]; memset(mark, 0, sizeof mark); unsigned ep = 7; char *a = pass ? a1 : a0;
      for (int i = 0; i < nd; i++) {
        a[i] = '-';
        if (farv[i] && (i % 17) == 3) continue;   // geOver(GE_SOFT) у дальних (детерминированно)
        if (pass && scl[i] < NC && mark[scl[i]] == ep) { skipped++; continue; }   // О4
        unsigned ci = cellOf[i];
        if (transp[i]) { a[i] = 'T'; continue; }
        if (ci >= NC) continue;
        if (mark[ci] == ep) continue;
        if (mark[ci] == (ep | 0x80000000u) || !ok[ci]) { mark[ci] = ep | 0x80000000u; a[i] = 'F'; continue; }
        mark[ci] = ep; a[i] = 'L';
      }
    }
    total += (unsigned)nd; diff += memcmp(a0, a1, (size_t)nd) != 0;
  }
  printf("О4: прогонов 300, кусков %u, без чтения Piece %u (%.0f %%), прогонов с другим порядком действий %u\n", total, skipped, 100.f * skipped / total, diff);
  return diff != 0;
}

int main(void) {
  int e2 = testSp(), e11 = testGg(), e4 = testDl();
  printf("%s О2 %s, О11 %s, О4 %s\n", e2 || e11 || e4 ? "ИТОГ: FAIL —" : "ИТОГ: PASS —", e2 ? "FAIL" : "ok", e11 ? "FAIL" : "ok", e4 ? "FAIL" : "ok");
  return e2 || e11 || e4;
}
