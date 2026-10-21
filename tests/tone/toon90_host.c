// №754: пресет «Мультик 90-х» (viewer/tone.c toon90) против пробы на Python (preset90.py, по ней оценивался вид): сетка 16³ цветов -> stdout,
// сверка tests/tone/toon90_check.py. cc -O1 -I viewer tests/tone/toon90_host.c -lm -o build/toon90-host
#include "../../viewer/tone.c"
#include <stdio.h>
#include <string.h>
int main(void) {
  for (int r = 0; r < 16; r++) for (int g = 0; g < 16; g++) for (int b = 0; b < 16; b++) {
    unsigned char c[4] = {(unsigned char)(r * 17), (unsigned char)(g * 17), (unsigned char)(b * 17), 255}, e[4]; memcpy(e, c, 4); toon90(c); toon90lut(e);
    printf("%d %d %d %d %d %d %d %d %d\n", r * 17, g * 17, b * 17, c[0], c[1], c[2], e[0], e[1], e[2]);
  }
  return 0;
}
