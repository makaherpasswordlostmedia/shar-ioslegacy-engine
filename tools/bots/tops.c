// Куда goto смоука поставит машину (анатомия уровня, Роб 04.10): для каждой точки «x z» со входа — верхняя опора коллизии ниже
// 200 м (как viewer/main.c: ground() по карте высот — верхний слой, потом carPlace — опора от него вниз). tools/bots/anatomy.py
// строит по ней маску клетки 6 м (9 точек через 2 м): goto в эту часть клетки кладёт машину на поверхность, где ездят боты,
// а не на крышу или навес над ней.
//   tops LEVEL HOMER < точки > "x z верх_y" (nan — опоры нет)
#include <stdio.h>
#include <math.h>
#include "world.h"
int main(int argc, char **argv) {
  if (argc < 3) { fprintf(stderr, "usage: tops LEVEL HOMER < \"x z\" строки\n"); return 2; }
  if (bwData(argv[1], argv[2], 0)) { fprintf(stderr, "tops: нет данных\n"); return 2; }
  const ColWorld *cw = bwCol(); float x, z;
  while (scanf("%f %f", &x, &z) == 2) { float g; printf("%.2f %.2f %.2f\n", x, z, colGround(cw, x, z, 202.f, -1e6f, &g, 0) ? g : NAN); }
  return 0;
}
