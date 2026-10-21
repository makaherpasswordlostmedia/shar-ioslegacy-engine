// №559: тест отсутствия удара колеса о скат крыши дома J10 (скат 40°, ящик COL1 17).
// Скат крыши — проходимая опора colGround, для колёс машины скат не должен быть вертикальной стеной
// (colWheelWallContacts отсекает наклонные ящики-скаты boxRoofSlope по аналогии с наклонными плитами №525).
// Зелёный (ROOF_RAMP_OLD=0): колесо на скате не получает импульс удара о ящик 17 (jn == 0).
// Красный (ROOF_RAMP_OLD=1): колесо бьётся в ящик 17 с импульсом jn > 2000 Н*с, гася ход.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "col.h"
#include "car.h"

int main(int argc, char **argv) {
  const char *lvlPath = argc > 1 ? argv[1] : "build/level.shr";
  FILE *f = fopen(lvlPath, "rb");
  if (!f) return 2;
  fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
  char *buf = malloc(sz); fread(buf, 1, sz, f); fclose(f);
  char *p = buf; char *end = buf + sz - 4;
  while (p < end && memcmp(p, "COL1", 4)) p++;
  ColWorld W;
  colInit(&W, p, sz - (p - buf));

  // Wheel 2 center on roof slope of J10
  float wp[3] = { 124.821f, 7.475f, 222.544f };
  ColSphereContact sc[16];
  colSetFoliagePass(1);
  int n = colWheelWallContacts(&W, wp, 0.35f, sc, 16);

  int hitBox17 = 0;
  for (int i = 0; i < n; i++) {
    // ref: 0x20000000 | 17 is box 17
    if ((sc[i].ref >> 29) == COL_BOX && (sc[i].ref & 0x1fffffff) == 17) {
      hitBox17 = 1;
      printf("Hit box 17: depth=%.4f normal=(%.3f, %.3f, %.3f)\n",
             sc[i].depth, sc[i].n[0], sc[i].n[1], sc[i].n[2]);
    }
  }

  printf("ROOF_RAMP_OLD=%d: contacts=%d hitBox17=%d\n", ROOF_RAMP_OLD, n, hitBox17);
  free(buf);

  if (!ROOF_RAMP_OLD) {
    if (!hitBox17) {
      printf("PASS: roof slope is not a wall for wheels\n");
      return 0;
    } else {
      printf("FAIL: wheel still hit roof slope box 17 as a wall\n");
      return 1;
    }
  } else {
    if (hitBox17) {
      printf("RED CONTROL PASS: with ROOF_RAMP_OLD=1 wheel hits roof slope as a wall\n");
      return 0;
    } else {
      printf("RED CONTROL FAIL: ROOF_RAMP_OLD=1 did not catch the wall hit\n");
      return 1;
    }
  }
}
