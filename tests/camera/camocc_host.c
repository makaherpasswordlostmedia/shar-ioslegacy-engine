// №602: камера не входит в чужие кузова и людей между опорой и глазом. Движковый код viewer/camsafe.c (csRayFrac, csProbe) на Маке.
// Красный контроль: прежняя маска луча (только мир, bodies=1) не видит высокий кузов между опорой и глазом; новая (5) видит;
// своя машина за рулём (own) не загораживает.  cc -std=c11 -I viewer tests/camera/camocc_host.c viewer/camsafe.c viewer/col.c -lm
#include <stdio.h>
#include <string.h>
#include "camsafe.h"
int main(void) {
  static CsScene s; memset(&s, 0, sizeof s);
  float P[3] = {0, 3.f, 0}, E[3] = {0, 2.6f, -7.f};              // опора над крышей, глаз сзади
  CsBox *b = &s.box[s.nbox++]; b->x = 0; b->z = -5.f; b->fx = 0; b->fz = 1; b->hw = 1.3f; b->hl = 1.5f; b->y = 0; b->lo = 0; b->hi = 3.4f;   // автобус 3,4 м
  int bad = 0;
  float oldF = csRayFrac(&s, P, E, 1), newF = csRayFrac(&s, P, E, 5);
  printf("автобус между опорой и глазом: старая маска %.2f (1 = не видит), новая %.2f\n", oldF, newF);
  if (!(oldF > .999f && newF < .9f)) bad++;
  b->own = 1; float ownF = csRayFrac(&s, P, E, 5);
  printf("своя машина за рулём: новая маска %.2f (1 = не мешает)\n", ownF); if (ownF < .999f) bad++;
  b->own = 0; int fl = csProbe(&s, E, (float[3]){0, 0, 1}, .6f, 1.07f, .5f, P); printf("замер csProbe: occ=%d\n", !!(fl & CS_OCC_BODY)); if (!(fl & CS_OCC_BODY)) bad++;
  b->hi = 1.4f; float lowF = csRayFrac(&s, P, E, 5); printf("низкая легковая (1,4 м), камера над крышей: %.2f (1 = проходит над)\n", lowF); if (lowF < .999f) bad++;
  // №620: видимая геометрия без коллизии (карниз/крыша/вывеска — один треугольник) между опорой и глазом
  { static CsScene g; memset(&g, 0, sizeof g);
    float T[9] = {-2, 0, -4, 2, 0, -4, 0, 4, -4}; memcpy(g.tri[g.ntri++], T, sizeof T);
    g.useTri = 0; float oldG = csRayFrac(&g, P, E, 9); g.useTri = 1; float newG = csRayFrac(&g, P, E, 9);
    printf("треугольник на пути: прежнее %.2f (1 = не видит), новое %.2f\n", oldG, newG); if (!(oldG > .999f && newG < .7f)) bad++;
    float P2[3] = {5, 3, 0}, E2[3] = {5, 2.6f, -7}; float miss = csRayFrac(&g, P2, E2, 9); printf("мимо треугольника: %.2f\n", miss); if (miss < .999f) bad++;
    int fl = csProbe(&g, E, (float[3]){0, 0, 1}, .6f, 1.07f, .5f, P); printf("замер: geom=%d\n", !!(fl & CS_IN_GEOM)); if (!(fl & CS_IN_GEOM)) bad++; }
  puts(bad ? "FAIL" : "PASS"); return bad;
}
