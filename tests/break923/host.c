// №923 (Роб 24.10: «бью вперёд, а разбивается влево»): настоящие props.c / stateprops.c на данных уровня, без эмулятора. Каждый тип обломка, у которого есть куски
// (BreakableObject 0x3001000), проигрывается в точке своего предмета при скорости машины по 12 направлениям; смещение кусков за весь клип (последний кадр минус
// покой) — среднее по горизонтали; угол между ним и скоростью машины. Печать: тип, чисел заездов, из них угол > 20°, наибольший угол. Типы, у которых куски не уходят
// вбок (падают на месте), помечены «на месте». Ключ old: spBreak (как было); без ключа: spBreakDir (с поворотом по ходу машины)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "props.h"
#include "stateprops.h"
unsigned homerSolidFrame = 0;
static Props props; static StateProps sp; static ColWorld world;
static int pieceAt(unsigned i, float *out, int n) {   // положения кусков (начало в мире) -> out[3n]
  const SpType *T = &sp.type[sp.inst[i].type]; int c = 0;
  for (unsigned k = 0; k < T->nPiece && c < n; k++) { float m[16]; spPieceMatrix(&sp, i, k, m); out[3 * c] = m[12]; out[3 * c + 1] = m[13]; out[3 * c + 2] = m[14]; c++; }
  return c;
}
int main(int argc, char **argv) {
  if (argc < 2) return 2; int old = argc > 2 && !strcmp(argv[2], "old");
  FILE *f = fopen(argv[1], "rb"); if (!f) return 2;
  fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f);
  unsigned char *data = aligned_alloc(16, (size + 15) & ~15); if (!data || fread(data, 1, size, f) != (size_t)size) return 2; fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size;
  if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&world, data + co, ce - co) || propsInit(&props, data + po, *(unsigned *)(data + po + 40)) || !props.spr || spInit(&sp, props.spr, props.sprSize)) { printf("нет стейтпропов\n"); return 0; }
  int bad = 0, tested = 0, place = 0; unsigned seen[64]; int ns = 0;
  for (unsigned pi = 0; pi < props.ninst; pi++) {
    int b = spBreakOf(&sp, props.def[pi].type); if (b < 0 || sp.type[b].nPiece == 0) continue;
    int dup = 0; for (int k = 0; k < ns; k++) dup |= seen[k] == (unsigned)b; if (dup || ns >= 64) continue; seen[ns++] = (unsigned)b;
    float pos[3] = {props.def[pi].x, props.def[pi].y, props.def[pi].z}; const float *q = props.def[pi].q;
    int n = 0, over = 0; float worst = 0.f; int flat = 0;
    for (int a = 0; a < 12; a++) {
      float ang = a * 0.5235988f, v[2] = {12.f * sinf(ang), 12.f * cosf(ang)};
      spFree(&sp); if (spInit(&sp, props.spr, props.sprSize)) return 3;
      if (old) spBreak(&sp, (unsigned)b, pos, q); else spBreakDir(&sp, (unsigned)b, pos, q, v);
      unsigned inst = 0; int found = 0; for (unsigned i = 0; i < sp.ninst; i++) if (sp.inst[i].type == (unsigned)b && sp.run[i].state != 0) { inst = i; found = 1; break; }
      if (!found) continue;
      const SpType *T = &sp.type[b]; unsigned nfr = T->frames & 0xFFFF; if (nfr < 2) continue;
      float p0[96], p1[96]; SpRun *r = &sp.run[inst];
      r->poseF = 0.f; r->poseValid = 0; spPose(&sp, inst); int c0 = pieceAt(inst, p0, 32);
      r->poseF = (float)(nfr - 1); r->poseValid = 0; spPose(&sp, inst); int c1 = pieceAt(inst, p1, 32);
      float dx = 0, dz = 0; for (int k = 0; k < c0 && k < c1; k++) { dx += p1[3 * k] - p0[3 * k]; dz += p1[3 * k + 2] - p0[3 * k + 2]; }
      float dl = hypotf(dx, dz) / (c0 ? c0 : 1); if (dl < .3f) { flat = 1; continue; }
      float cs = (dx * v[0] + dz * v[1]) / (hypotf(dx, dz) * hypotf(v[0], v[1])); if (cs > 1.f) cs = 1.f; if (cs < -1.f) cs = -1.f;
      float deg = acosf(cs) * 57.29578f; n++; if (deg > 20.f) over++; if (deg > worst) worst = deg;
    }
    if (n) { tested++; bad += over > 0; printf("обломок %2d (пропов типа %u): заездов %d, угол > 20°: %d, наибольший %.0f°\n", b, props.def[pi].type, n, over, worst); }
    else if (flat) { place++; printf("обломок %2d: на месте (куски не уходят вбок)\n", b); }
  }
  printf("ИТОГ: типов проверено %d, с углом > 20°: %d, на месте %d\n", tested, bad, place);
  return bad ? 1 : 0;
}
