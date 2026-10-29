// Разбор тупика машины (правка Роба 339, L1 F4-8): геометрия вокруг точки и проба выезда тем же кодом игры (tools/bots/world.c).
// Сборка: BINS=trapwhy tools/bots/build.sh
//   trapwhy LEVEL HOMER --geo X Z R            опоры (colGround сверху вниз) сеткой 1 м и примитивы коллизии в радиусе R (T/B/C/S)
//   trapwhy LEVEL HOMER --probe X Y Z [H]      машина в точку (bwPlace), 16 курсов (или один H) × 8 заходов пробы car_trapped
//                                              (газ прямо/влево/вправо, назад ×3, назад и газ с рулём) -> строка на курс
//   trapwhy LEVEL HOMER --why X Y Z            у запертых курсов — что держит: контакты по примитивам (забор: верх, лицо/изнанка), отмены подшагов
//   trapwhy LEVEL HOMER --trace X Y Z H r|l РУЛЬ [КАДРОВ]   заезд по кадрам: положение, скорость, колёса, контакты
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "world.h"

static int layers(float x, float z, float *ys, float *ny) {
  float top = 1e4f, n3[3]; int k = 0;
  while (k < 8 && colGround(bwCol(), x, z, top, -1e4f, &ys[k], n3)) { ny[k] = n3[1]; top = ys[k] - .3f; k++; }
  return k;
}

int main(int argc, char **argv) {
  if (argc < 5 || bwData(argv[1], argv[2], 0)) { fprintf(stderr, "usage: trapwhy LEVEL HOMER --geo X Z R | --probe X Y Z [H] | --why X Y Z | --trace X Y Z H r|l РУЛЬ [КАДРОВ]\n"); return 2; }
  const ColWorld *C = bwCol();
  if (!strcmp(argv[3], "--geo") && argc >= 7) {
    float X = atof(argv[4]), Z = atof(argv[5]), R = atof(argv[6]);
    printf("# опоры сверху вниз: x z | y(ny) ...\n");
    for (float z = Z - R; z <= Z + R; z += 1.f) for (float x = X - R; x <= X + R; x += 1.f) {
      float ys[8], ny[8]; int k = layers(x, z, ys, ny);
      printf("G\t%.0f\t%.0f", x, z); for (int i = 0; i < k; i++) printf("\t%.2f(%.2f)", ys[i], ny[i]); printf("\n");
    }
    for (uint32_t i = 0; i < C->ntri; i++) { const ColTri *t = &C->tri[i];
      float cx = (t->a[0] + t->b[0] + t->c[0]) / 3, cz = (t->a[2] + t->b[2] + t->c[2]) / 3;
      float mx = fmaxf(fabsf(t->a[0] - cx), fmaxf(fabsf(t->b[0] - cx), fabsf(t->c[0] - cx))), mz = fmaxf(fabsf(t->a[2] - cz), fmaxf(fabsf(t->b[2] - cz), fabsf(t->c[2] - cz)));
      if (fabsf(cx - X) > R + mx || fabsf(cz - Z) > R + mz) continue;
      printf("T\t%u\tn %.2f %.2f %.2f\t(%.1f %.1f %.1f) (%.1f %.1f %.1f) (%.1f %.1f %.1f)\n", i, t->n[0], t->n[1], t->n[2],
             t->a[0], t->a[1], t->a[2], t->b[0], t->b[1], t->b[2], t->c[0], t->c[1], t->c[2]); }
    for (uint32_t i = 0; i < C->nbox; i++) { const ColBox *b = &C->box[i]; float e = fabsf(b->h[0]) + fabsf(b->h[1]) + fabsf(b->h[2]);
      if (fabsf(b->c[0] - X) > R + e || fabsf(b->c[2] - Z) > R + e) continue;
      printf("B\t%u\tc %.2f %.2f %.2f\th %.2f %.2f %.2f\tax %.2f %.2f %.2f ay %.2f %.2f %.2f\n", i, b->c[0], b->c[1], b->c[2], b->h[0], b->h[1], b->h[2],
             b->ax[0], b->ax[1], b->ax[2], b->ay[0], b->ay[1], b->ay[2]); }
    for (uint32_t i = 0; i < C->ncyl; i++) { const ColCyl *c = &C->cyl[i]; float e = c->r + c->halfLen;
      if (fabsf(c->c[0] - X) > R + e || fabsf(c->c[2] - Z) > R + e) continue;
      printf("C\t%u\tc %.2f %.2f %.2f\taxis %.2f %.2f %.2f r %.2f hl %.2f flat %u\n", i, c->c[0], c->c[1], c->c[2], c->axis[0], c->axis[1], c->axis[2], c->r, c->halfLen, c->flat); }
    for (uint32_t i = 0; i < C->nseg; i++) { const ColSeg *s = &C->seg[i];
      float mx = fminf(s->a[0], s->b[0]), Mx = fmaxf(s->a[0], s->b[0]), mz = fminf(s->a[1], s->b[1]), Mz = fmaxf(s->a[1], s->b[1]);
      if (Mx < X - R || mx > X + R || Mz < Z - R || mz > Z + R) continue;
      printf("S\t%u\t(%.2f %.2f)-(%.2f %.2f)\tn %.2f %.2f\ty %.2f..%.2f\n", i, s->a[0], s->a[1], s->b[0], s->b[1], s->n[0], s->n[1], s->y0, s->y1); }
    return 0;
  }
  if (!strcmp(argv[3], "--probe") && argc >= 7) {
    float X = atof(argv[4]), Y = atof(argv[5]), Z = atof(argv[6]); int one = argc >= 8; float H0 = one ? atof(argv[7]) : 0;
    static BotWorld W; static BotSnap S; bwNew(&W); bwSaveAlloc(&W, &S);
    static const float steer[8] = {0, -1, 1, 0, -1, 1, -1, 1};
    int nfree = 0, nh = one ? 1 : 16;
    for (int hi = 0; hi < nh; hi++) {
      float h = one ? H0 : hi * 6.2831853f / 16;
      bwPlace(&W, X, Y, Z, h); for (int k = 0; k < 30; k++) bwStep(&W, 0, 0, 0);
      bwSave(&W, &S); float x0 = W.car.x, z0 = W.car.z, y0 = W.car.y; int fr = 0; char res[8 * 24] = ""; float best = 0;
      for (int d = 0; d < 8; d++) {
        bwLoad(&W, &S);
        for (int f = 0; f < 150; f++) { unsigned bt = d < 3 ? GP_R : d < 6 ? GP_L : (f < 45 ? GP_L : GP_R); float ax = d >= 6 && f < 45 ? -steer[d] : steer[d];
          bwStep(&W, bt, ax, 0.f); }
        float dd = hypotf(W.car.x - x0, W.car.z - z0); if (dd > best) best = dd; if (dd > 3.f) fr = 1;
        char s[24]; snprintf(s, sizeof s, " %.1f", dd); strcat(res, s);
      }
      nfree += fr;
      printf("P\th %.2f\tстарт %.2f %.2f %.2f\t%s\tсдвиги%s\n", h, x0, y0, z0, fr ? "выезд" : "ЗАПЕРТА", res);
    }
    printf("ИТОГ\t%d из %d курсов выезжают\n", nfree, nh);
    return 0;
  }
  if (!strcmp(argv[3], "--why") && argc >= 7) {   // --why X Y Z: 16 курсов; у запертых — что держит (контакты по типам/номерам, отмены подшагов по причинам)
    float X = atof(argv[4]), Y = atof(argv[5]), Z = atof(argv[6]);
    static BotWorld W; static BotSnap S; bwNew(&W); bwSaveAlloc(&W, &S);
    static const float steer[8] = {0, -1, 1, 0, -1, 1, -1, 1};
    enum { NK = 64 }; unsigned key[NK]; int cnt[NK], nk = 0, rv[64] = {0}, ntr = 0;
    for (int hi = 0; hi < 16; hi++) {
      float h = hi * 6.2831853f / 16;
      bwPlace(&W, X, Y, Z, h); for (int k = 0; k < 30; k++) bwStep(&W, 0, 0, 0);
      bwSave(&W, &S); float x0 = W.car.x, z0 = W.car.z; int fr = 0;
      unsigned lk[NK]; int lc[NK], ln = 0, lrv[64] = {0};
      for (int d = 0; d < 8 && !fr; d++) {
        bwLoad(&W, &S); int r0 = W.car.reverts;
        for (int f = 0; f < 150; f++) { unsigned bt = d < 3 ? GP_R : d < 6 ? GP_L : (f < 45 ? GP_L : GP_R); float ax = d >= 6 && f < 45 ? -steer[d] : steer[d];
          bwStep(&W, bt, ax, 0.f);
          for (int c = 0; c < W.car.contacts && c < 4; c++) { /* тип из ctype, номер — только у сильнейшего (wallIdx) */ }
          if (W.car.wallV > 0.f || W.car.contacts) { unsigned k = (unsigned)W.car.wallType << 28 | (W.car.wallIdx & 0x0fffffff);
            if (W.car.wallV <= 0.f) k = 0xf0000000u | W.car.ctype[0];
            int j = 0; while (j < ln && lk[j] != k) j++; if (j == ln && ln < NK) { lk[ln] = k; lc[ln++] = 0; } if (j < NK) lc[j]++; }
          if (W.car.reverts != r0) { lrv[W.car.revWhy & 63]++; r0 = W.car.reverts; } }
        if (hypotf(W.car.x - x0, W.car.z - z0) > 3.f || gameOnFoot(&W.G) || W.car.destroyed) fr = 1;
      }
      if (fr) continue;
      ntr++;
      for (int j = 0; j < ln; j++) { int i = 0; while (i < nk && key[i] != lk[j]) i++; if (i == nk && nk < NK) { key[nk] = lk[j]; cnt[nk++] = 0; } if (i < NK) cnt[i] += lc[j]; }
      for (int i = 0; i < 64; i++) rv[i] += lrv[i];
    }
    printf("WHY\t%.1f %.1f %.1f\tзаперта на %d из 16 курсов\t", X, Y, Z, ntr);
    static const char *tn[4] = {"tri", "box", "cyl", "seg"};
    for (int i = 0; i < nk; i++) { unsigned t = key[i] >> 28, ix = key[i] & 0x0fffffff;
      if (t == 15) printf(" касание:%s×%d", tn[ix & 3], cnt[i]);
      else if (t == COL_SEG && ix < C->nseg) { const ColSeg *g = &C->seg[ix]; float cu = (X - g->a[0]) * g->n[0] + (Z - g->a[1]) * g->n[1];
        printf(" seg%u(%s %.1f, %s %.1f м)×%d", ix, g->y1 > 1e5f ? "беск" : "верх", g->y1 > 1e5f ? 0.f : g->y1, cu >= 0 ? "лицо" : "ИЗНАНКА", fabsf(cu), cnt[i]); }
      else printf(" %s%u×%d", tn[t & 3], ix, cnt[i]); }
    printf("\tотмены:"); for (int i = 1; i < 64; i++) if (rv[i]) printf(" %d×%d", i, rv[i]);
    printf("\n"); return 0;
  }
  if (!strcmp(argv[3], "--trace") && argc >= 10) {   // --trace X Y Z H КНОПКИ(r|l) РУЛЬ КАДРОВ: строка каждые 10 кадров
    float X = atof(argv[4]), Y = atof(argv[5]), Z = atof(argv[6]), H = atof(argv[7]); unsigned bt = argv[8][0] == 'l' ? GP_L : argv[8][0] == 'r' ? GP_R : 0;
    float ax = atof(argv[9]); int nf = argc >= 11 ? atoi(argv[10]) : 150;
    static BotWorld W; bwNew(&W); bwPlace(&W, X, Y, Z, H);
    for (int f = 0; f < 30 + nf; f++) { bwStep(&W, f < 30 ? 0 : bt, f < 30 ? 0 : ax, 0.f);
      if (f % 10 == 9) { const Car *c = &W.car; printf("F%4d\tpos %.2f %.2f %.2f h %.2f\tv %.2f vy %.2f\tpitch %.1f roll %.1f\twheels %d gr %d\tcontacts %d n0 %.2f %.2f wallV %.2f type %d idx %u\tcomp %.2f %.2f %.2f %.2f\n",
        f - 30, c->x, c->y, c->z, c->h, c->v, c->vy, c->pitch * 57.3f, c->roll * 57.3f, c->wheels, c->grounded, c->contacts, c->cnx[0], c->cnz[0], c->wallV, c->wallType, c->wallIdx,
        c->comp[0], c->comp[1], c->comp[2], c->comp[3]); } }
    return 0;
  }
  return 2;
}
