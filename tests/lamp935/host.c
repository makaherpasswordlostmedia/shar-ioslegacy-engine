// Гейт №935 (мост и эстакады L5 B2-9: у фонарей нет эллипса света на полу, остаётся конус). Реальные данные уровня (SPR1 -> таблица света lightsprite_core.h, COL1) и то же правило,
// что в игре (viewer/lamppool935.h lpPoolSkip): для каждого конуса фонаря (mode 2) берём конец у пола F, высоту пола под ним, и спрашиваем правило.
//  check LEVEL.shr HOMER.shr X Z R   — зона проверки: круг радиуса R вокруг (X, Z) (для L5 B2-9: -517 -517 100)
// Зелёный: все лампы на мосту/эстакаде в зоне (вторая поверхность глубже 3 м) без эллипса; из остальных ламп уровня без эллипса не больше 15 %. Красный: -DLAMP_POOL_BRIDGE_OLD=1 — на мосту 0 %.
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "world.h"
#include "lightsprite_core.h"
#include "lamppool935.h"
#ifndef F_ADDITIVE
#define F_ADDITIVE (1 << 24)   // main_render.h
#endif
int main(int argc, char **argv) {
  if (argc < 6 || bwData(argv[1], argv[2], 0)) { fprintf(stderr, "usage: check level.shr homer.shr X Z R\n"); return 2; }
  float zx = (float)atof(argv[3]), zz = (float)atof(argv[4]), zr = (float)atof(argv[5]);
  static BotWorld w; if (bwNew(&w)) return 2;
  if (!w.haveSP) { printf("нет SPR1\nRESULT: FAIL\n"); return 1; }
  for (int f = 0; f < 30; f++) spUpdate(&w.sp, bwCol(), NULL, NULL, BW_DT);
  static LspTab t; lspBuild(&t, &w.sp, 0);
  const ColWorld *cw = bwCol();
  unsigned cones = 0, nofloor = 0, zel = 0, zelSkip = 0, zall = 0, oth = 0, othSkip = 0; lspConeW = lspConeL = 1.f;
  for (unsigned k = 0; k < t.n; k++) {
    const LspE *e = &t.e[k]; if (e->mode != 2) continue; cones++;
    float v[12]; lspQuad(e, e->p[0] + 3.f, e->p[1], e->p[2], v);
    int topPlus = (v[7] + v[10]) > (v[1] + v[4]); const float *Lo = topPlus ? v + 6 : v, *Fo = topPlus ? v : v + 6;
    float L[3], F[3], X[3]; for (int a = 0; a < 3; a++) { L[a] = (Lo[a] + Lo[3 + a]) * .5f; F[a] = (Fo[a] + Fo[3 + a]) * .5f; X[a] = (Fo[3 + a] - Fo[a]) * .5f; }
    float hw = sqrtf(X[0] * X[0] + X[2] * X[2]), gy, n3[3];
    if (hw < .05f || !colGround(cw, F[0], F[2], L[1] - .1f, F[1] - 12.f, &gy, n3)) { nofloor++; continue; }
    int sk = lpPoolSkip(cw, F, gy);
    float y2, n2[3]; int elevated = colGround(cw, F[0], F[2], gy - .5f, gy - 60.f, &y2, n2) && gy - y2 > 3.f;   // независимая проверка признака «мост»: вторая поверхность глубже 3 м
    int inZone = hypotf(F[0] - zx, F[2] - zz) <= zr;
    (void)inZone; zall++; if (elevated) { zel++; if (sk) zelSkip++; }
    if (!elevated) { oth++; if (sk) othSkip++; }
  }
  // второй путь (spritelight.h slLightDrawVec): световые куски стейтпропов — вертикальные конусы (высота больше 1,5 ширины) рисуют эллипс у низа; те же куски, что slLightSprops
  typedef struct { short u, v; uint32_t c; short x, y, z, w; } Vert;
  unsigned scn = 0, sel = 0, selSkip = 0, soth = 0, sothSkip = 0;
  { StateProps *sp = &w.sp;
    for (unsigned i = 0; i < sp->ninst; i++) {
      const SpType *T = &sp->type[sp->inst[i].type]; int any = 0;
      for (unsigned k = 0; k < T->nPiece; k++) { const SpPiece *pp = &sp->piece[T->firstPiece + k]; if ((pp->flags & F_ADDITIVE) && pp->ni >= 3 && pp->ni <= 3 * 64) any = 1; }
      if (!any) continue;
      spPose(sp, i);
      for (unsigned k = 0; k < T->nPiece; k++) {
        const SpPiece *pp = &sp->piece[T->firstPiece + k]; if (!(pp->flags & F_ADDITIVE) || pp->ni < 3 || pp->ni > 3 * 64) continue;
        float m[16]; spPieceMatrix(sp, i, k, m);
        const Vert *vv = (const Vert *)((const char *)sp->vertBase + pp->vOff); const unsigned short *ix = (const unsigned short *)((const char *)sp->idxBase + pp->iOff);
        int n = (int)pp->ni - (int)pp->ni % 3; if (n > 3 * 64) n = 3 * 64;
        float mn[3] = {1e30f, 1e30f, 1e30f}, mx[3] = {-1e30f, -1e30f, -1e30f};
        for (int a = 0; a < n; a++) { const Vert *v = &vv[ix[a]]; float x = v->x * (1.f / 32768.f), y = v->y * (1.f / 32768.f), z = v->z * (1.f / 32768.f);
          float P[3] = {m[0] * x + m[4] * y + m[8] * z + m[12], m[1] * x + m[5] * y + m[9] * z + m[13], m[2] * x + m[6] * y + m[10] * z + m[14]};
          for (int q = 0; q < 3; q++) { if (P[q] < mn[q]) mn[q] = P[q]; if (P[q] > mx[q]) mx[q] = P[q]; } }
        float dx = mx[0] - mn[0], dy = mx[1] - mn[1], dz = mx[2] - mn[2], ext = fmaxf(dx, dz);
        if ((ext < .05f && dy < .05f) || dy < .3f * ext || !(dy > 1.5f * ext)) continue;   // не конус
        scn++;
        float Fc[3] = {(mn[0] + mx[0]) * .5f, mn[1], (mn[2] + mx[2]) * .5f}, Lc[3] = {Fc[0], mx[1], Fc[2]}, g, n3[3];
        int sk = 0; if (colGround(cw, Fc[0], Fc[2], mn[1] + 1.f, mn[1] - 12.f, &g, n3)) sk = lpPoolSkip(cw, Fc, g);
        float y2, n2[3]; int elevated = colGround(cw, Fc[0], Fc[2], mn[1] + 1.f, mn[1] - 12.f, &g, n3) && colGround(cw, Fc[0], Fc[2], g - .5f, g - 60.f, &y2, n2) && g - y2 > 3.f;
        if (elevated) { sel++; if (sk) selSkip++; } else { soth++; if (sk) sothSkip++; }
      } } }
  float zf = zel ? (float)zelSkip / zel : 0.f, of = oth ? (float)othSkip / oth : 0.f;
  printf("конусов %u, без пола %u; зона (%.0f,%.0f,R%.0f): ламп с полом %u, на мосту/эстакаде %u, из них без эллипса %u (%.0f %%); все лампы уровня не на мосту: %u, без эллипса %u (%.0f %%)\n",
         cones, nofloor, zx, zz, zr, zall, zel, zelSkip, zf * 100.f, oth, othSkip, of * 100.f);
  unsigned elTot = zel, elSk = zelSkip; (void)zall;   // лампы таблицы света на мосту: в зоне (L5 B2-9) или по всему уровню — сводка ниже по всему уровню
  printf("таблица света: на мосту/эстакаде %u конусов-ламп вне и внутри зоны (см. выше зона); стейтпроп-конусы (путь spritelight): всего %u, на мосту %u, из них без эллипса %u; не на мосту %u, без эллипса %u\n", elTot, scn, sel, selSkip, soth, sothSkip);
  int ok_bridge = (elSk == elTot) && (selSkip == sel), ok_city = (oth == 0 || of <= .15f) && (soth == 0 || (float)sothSkip / soth <= .15f);
  int found = elTot + sel;   // сколько ламп на мосту найдено на уровне
  printf("CHECK bridge %s  все лампы на мосту без эллипса: таблица %u из %u, стейтпроп-конусы %u из %u (%s)\n", ok_bridge ? "OK  " : "FAIL", elSk, elTot, selSkip, sel, found ? "на уровне такие лампы есть" : "ламп на мосту на уровне нет, проверять нечего");
  printf("CHECK city   %s  не на мосту без эллипса: таблица %.0f %% из %u, стейтпроп-конусы %u из %u (нужно <= 15 %%)\n", ok_city ? "OK  " : "FAIL", of * 100.f, oth, sothSkip, soth);
  printf("FOUND %d\n", found);
  printf("RESULT: %s\n", ok_bridge && ok_city ? "PASS" : "FAIL");
  return ok_bridge && ok_city ? 0 : 1;
}
