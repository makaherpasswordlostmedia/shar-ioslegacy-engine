// Камеры комнат на Маке для проверки «камера в стене» (правка Роба 27, tests/rooms/walls.py): тот же viewer/roomcam.c,
// что в EBOOT. stdin: строки «КОМНАТА x y z» (ноги Гомера); stdout: «VIEW КОМНАТА x y z камера имя fovY eye(3) look(3)»
// (поза без запаздывания; камеры нет — «VIEW ... -1»).
//   cc -std=c99 -O2 -I viewer tests/rooms/view_host.c viewer/roomcam.c -lm -o build/rooms_cams/view_host
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "roomcam.h"

int main(int argc, char **argv) {
  FILE *f = fopen(argc > 1 ? argv[1] : "build/interiors-l1-gfx.bin", "rb"); if (!f) { puts("нет пакета"); return 2; }
  fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f); unsigned char *b = malloc(n); if (fread(b, 1, n, f) != (size_t)n) return 2; fclose(f);
  if (n < 16 || memcmp(b, "SHG1", 4)) { puts("не SHG1"); return 2; }
  unsigned nr; memcpy(&nr, b + 4, 4);
  static RoomCam cam[8][ROOM_CAMS]; int ncam[8] = {0}; char names[8][33];
  for (unsigned r = 0; r < nr && r < 8; r++) {
    unsigned off, size; memset(names[r], 0, 33); memcpy(names[r], b + 16 + 48 * r, 32); memcpy(&off, b + 16 + 48 * r + 32, 4); memcpy(&size, b + 16 + 48 * r + 36, 4);
    ncam[r] = roomCamsParse(cam[r], ROOM_CAMS, b + off, size); if (ncam[r] < 0) { printf("ROOM %s битые камеры\n", names[r]); return 1; }
  }
  char room[64]; float p[3];
  while (scanf("%63s %f %f %f", room, &p[0], &p[1], &p[2]) == 4) {
    int r = -1; for (unsigned k = 0; k < nr && k < 8; k++) if (!strcmp(names[k], room)) r = (int)k;
    int i = r >= 0 ? roomCamPick(cam[r], ncam[r], -1, p) : -1;
    if (i < 0) { printf("VIEW %s %.4f %.4f %.4f -1\n", room, p[0], p[1], p[2]); continue; }
    float e[3], l[3]; roomCamIdeal(&cam[r][i], p, e, l);
    printf("VIEW %s %.4f %.4f %.4f %d %s %.4f %.4f %.4f %.4f %.4f %.4f %.4f\n", room, p[0], p[1], p[2], i, cam[r][i].name,
           roomCamFovY(&cam[r][i]), e[0], e[1], e[2], l[0], l[1], l[2]);
  }
  return 0;
}
