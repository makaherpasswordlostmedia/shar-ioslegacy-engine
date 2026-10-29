// №522: тень под машиной не уходит под землю. Настоящий уровень (COL1 + рисуемая геометрия), настоящий carVisDrawShadow с захватом сетки; машина ставится в тысячи
// мест (склоны, бордюры, стыки клеток, под подложкой №509) в случайных курсах. Для каждой видимой клетки тени считаем, насколько её высота НИЖЕ нарисованной земли
// (сигнал «ушла под текстуру»: зрительная земля выше тени). Проверка: доля образцов, ушедших под землю глубже 2 см, и худшая глубина — у новой тени кратно меньше, чем
// у плоскости №433 (SHADOW_OLD=1), и худшая глубина не больше порога. Узел без опоры не провален: альфа 0.
//   tests/shadow522/run.sh [level.shr]   -> код 0 = PASS
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <pspgu.h>
unsigned homerSolidFrame;
#include "scene.h"
#include "carvis.h"
#include "carparams.h"
static int draws, nidx; static unsigned char meshBuf[4096]; static const unsigned short *meshIx; static int nvtx;
int sceGuGetStatus(int s) { (void)s; return 1; }
void sceGuDepthOffset(int v) { (void)v; }
void sceGuDisable(int s) { (void)s; }
void sceGuEnable(int s) { (void)s; }
void sceGuDrawArray(int a, int b, int count, const void *ix, const void *vtx) { (void)a; (void)b; nidx = count; meshIx = ix; memcpy(meshBuf, vtx, sizeof meshBuf); draws++; }
typedef struct { unsigned c; float x, y, z; } SV;
static unsigned long long rs = 88172645463325252ull; static float rnd(void) { rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17; return (rs >> 11) * (1.0 / 9007199254740992.0); }
int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "build/level.shr";
  if (sceneLoad(path)) { printf("FAIL нет уровня %s\n", path); return 2; }
  loadRender(); loadProps();
  CarParams p; if (!carParamsFor("famil_v", &p)) carDefaults(&p);
  int ndump = 0; int poses = 0, samples = 0, sunk2 = 0, sunk10 = 0, sunkCol = 0; float worst = 0; int bad = 0;
  for (int tries = 0; poses < 3000 && tries < 400000; tries++) {
    float x = W.ox + rnd() * W.W * W.cell, z = W.oz + rnd() * W.H * W.cell, y;
    float n[3]; if (!colGround(&W, x, z, 300.f, -300.f, &y, n)) continue;
    if (n[1] < .75f) continue;   // стоять машине можно только на ходовой опоре
    Car car; carInit(&car, &p, &W, 0, .5f, 0, 0); car.x = x; car.y = y; car.z = z; car.h = rnd() * 6.2831853f; car.grounded = 1; car.wheels = 4;
    car.q[0] = cosf(car.h * .5f); car.q[1] = 0; car.q[2] = sinf(car.h * .5f); car.q[3] = 0; car.vel[0] = 1;
    CarVis v; memset(&v, 0, sizeof v); v.ok = 1; v.wheelRad = p.wheelRad; carVisReset(&v);
    draws = 0; carVisDrawShadow(&v, &car, &W); if (!draws) continue;
    poses++;
    const SV *vb = (const SV *)meshBuf;
    for (int t = 0; t + 2 < nidx; t += 3) {
      const SV *a = &vb[meshIx[t]], *b = &vb[meshIx[t + 1]], *c = &vb[meshIx[t + 2]];
      if (!((a->c | b->c | c->c) >> 24)) continue;   // невидимый треугольник
      for (int i = 0; i < 3; i++) for (int j = 0; i + j < 3; j++) {
        float u = (i + .33f) / 3.f, w = (j + .33f) / 3.f, k = 1.f - u - w; if (k < 0) continue;
        float px = a->x * k + b->x * u + c->x * w, py = a->y * k + b->y * u + c->y * w, pz = a->z * k + b->z * u + c->z * w;
        float alphaHere = ((a->c >> 24) * k + (b->c >> 24) * u + (c->c >> 24) * w); if (alphaHere < 40.f) continue;   // заметная часть тени
        float rg = renderGround(px, pz, py + .6f, 3.f); if (rg < -1e8f) continue;   // нарисованное выше тени больше чем на 0,6 м — это настил над ней, не земля
        float cy_, cn_[3]; int hasC = colGround(&W, px, pz, py + .6f, py - 3.f, &cy_, cn_);
        samples++; float d = rg - py; if (d > .25f && ndump < 14 && getenv("SH_DUMP")) { ndump++; float cy2, cn2[3]; int h2 = colGround(&W, px, pz, py + 3.f, py - 3.f, &cy2, cn2); printf("  пример: (%.1f,%.1f,%.1f) тень %.2f нарисованная земля %.2f (выше на %.2f), коллизия под ±3 м: %s%.2f нормаль %.2f\n", px, py, pz, py, rg, d, h2 ? "есть " : "нет ", h2 ? cy2 : 0.f, h2 ? cn2[1] : 0.f); } if (d > .02f) { sunk2++; if (hasC && cy_ - py > .02f) sunkCol++; } if (d > .10f) sunk10++; if (d > worst) worst = d;
      }
    }
  }
  printf("поз %d, образцов тени %d: ниже нарисованной земли > 2 см %d (%.2f %%), > 10 см %d (%.2f %%), худшая глубина %.3f м; из «ушедших» опора коллизии тоже выше тени у %d\n", poses, samples, sunk2, 100.0 * sunk2 / (samples ? samples : 1), sunk10, 100.0 * sunk10 / (samples ? samples : 1), worst, sunkCol);
  FILE *o = fopen("build/tmp/shadow522.txt", "w"); if (o) { fprintf(o, "%d %d %d %.5f %d\n", samples, sunk2, sunk10, worst, sunkCol); fclose(o); }
  (void)bad; return 0;
}
