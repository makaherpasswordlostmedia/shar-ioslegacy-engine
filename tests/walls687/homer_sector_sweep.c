// №339 (остаток): Гомер пешком в секторе: старт (x z) в 16 направлений шагом и бегом 6 с; падение = y ниже -10 (за мир). cc -std=c11 -O2 -DSKIN_HOST -Iviewer tests/walls687/homer_sector_sweep.c viewer/homer.c viewer/skin.c viewer/col.c viewer/car.c -lm; ./a.out level.shr homer.shr x z; старт на линии забора даёт ложное падение
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "homer.h"
static ColWorld world; static Homer h;
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb"); fseek(f, 0, SEEK_END); long size = ftell(f); rewind(f); unsigned char *data = aligned_alloc(16, (size + 15) & ~15); if (fread(data, 1, size, f) != (size_t)size) return 2; fclose(f);
  unsigned co = *(unsigned *)(data + 92), po = *(unsigned *)(data + 96), pv = *(unsigned *)(data + 88), ce = (unsigned)size; if (po > co && po < ce) ce = po; if (pv > co && pv < ce) ce = pv;
  if (colInit(&world, data + co, ce - co)) return 2; SkinModel *model = skinLoad(argv[2]); if (!model || homerInit(&h, model)) return 2;
  float sx = atof(argv[3]), sz = atof(argv[4]); int bad = 0, runs = 0;
  for (int dir = 0; dir < 16; dir++) for (int dash = 0; dash < 2; dash++) {
    float g; if (!colGround(&world, sx, sz, 12, -20, &g, 0)) { printf("нет земли\n"); return 2; }
    homerPlace(&h, &world, sx, g, sz, 0); for (int n = 0; n < 20; n++) { HomerInput in = {0}; homerUpdate(&h, &world, NULL, &in, 1/60.f); }
    float yaw = dir * 6.2832f / 16, ymin = h.y, y0 = h.y; runs++;
    for (int n = 0; n < 60 * 6; n++) { HomerInput in = {0}; in.my = 1.f; in.camYaw = yaw; in.dash = dash; homerUpdate(&h, &world, NULL, &in, 1/60.f); HomerEvent e; while (homerPopEvent(&h, &e)) {} if (h.y < ymin) ymin = h.y; }
    int fall = ymin < -10.f;
    if (fall) { bad++; printf("ПАДЕНИЕ курс %3.0f° %s: y %.2f → мин %.2f, конец (%.1f %.1f %.1f)\n", yaw * 57.3f, dash ? "бег" : "шаг", y0, ymin, h.x, h.y, h.z); } }
  printf("RESULT падений %d из %d (старт %.1f %.1f)\n", bad, runs, sx, sz); return bad ? 1 : 0; }
