// Сверка кодов мест (правка Роба 58): тот же viewer/placecode.h, что в EBOOT, на Маке. stdin: «x z» по строке -> stdout: код
#include <stdio.h>
#include "../../viewer/placecode.h"
int main(void) {
  float x, z; char c[16];
  while (scanf("%f %f", &x, &z) == 2) { placeCode(x, z, c, sizeof c); puts(c); }
  return 0;
}
