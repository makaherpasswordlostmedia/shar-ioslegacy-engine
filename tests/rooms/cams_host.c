// Камеры комнат на Маке (пункт 11.2, tests/rooms/cams.sh): пакет рисования SHG1 -> камеры через viewer/roomcam.c (тот же
// код, что в EBOOT). Для каждой камеры и каждого её триггера — точка в центре триггера (ноги Гомера): какую камеру выбирает
// движок и её поза без запаздывания. Строки: CAM комната номер имя вид триггер x y z выбрана fovY eye(3) look(3)
//   cc -std=c99 -O2 -I viewer tests/rooms/cams_host.c viewer/roomcam.c -lm -o build/cams_host && build/cams_host build/interiors-l1-gfx.bin
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "roomcam.h"

int main(int argc, char **argv) {
  FILE *f = fopen(argc > 1 ? argv[1] : "build/interiors-l1-gfx.bin", "rb"); if (!f) { puts("нет пакета"); return 2; }
  fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f); unsigned char *b = malloc(n); if (fread(b, 1, n, f) != (size_t)n) return 2; fclose(f);
  if (n < 16 || memcmp(b, "SHG1", 4)) { puts("не SHG1"); return 2; }
  unsigned nr; memcpy(&nr, b + 4, 4);
  static RoomCam c[ROOM_CAMS];
  for (unsigned r = 0; r < nr; r++) {
    char name[33] = {0}; unsigned off, size; memcpy(name, b + 16 + 48 * r, 32); memcpy(&off, b + 16 + 48 * r + 32, 4); memcpy(&size, b + 16 + 48 * r + 36, 4);
    if ((long)off + size > n) { printf("ROOM %s битая запись\n", name); return 1; }
    int k = roomCamsParse(c, ROOM_CAMS, b + off, size);
    printf("ROOM %s cams %d\n", name, k);
    if (k < 0) return 1;
    for (int i = 0; i < k; i++) if (c[i].type == 1)   // рельс: сколько точек и длина ломаной — как их видит движок (с 29.09 точек сколько в данных)
      printf("RAIL %s %d %s %d %.4f %.4f %.4f %.4f\n", name, i, c[i].name, c[i].npts, roomRailLen(&c[i]),
             c[i].pts[c[i].npts - 1][0], c[i].pts[c[i].npts - 1][1], c[i].pts[c[i].npts - 1][2]);
    for (int i = 0; i < k; i++)
      for (int t = 0; t < c[i].ntrig; t++) {
        float p[3] = {c[i].trig[t].c[0], c[i].trig[t].c[1], c[i].trig[t].c[2]}, e[3], l[3];
        int pick = roomCamPick(c, k, -1, p);
        roomCamIdeal(&c[pick >= 0 ? pick : i], p, e, l);
        printf("CAM %s %d %s %d %d %.4f %.4f %.4f %d %.4f %.4f %.4f %.4f %.4f %.4f %.4f\n", name, i, c[i].name, c[i].type, t, p[0], p[1], p[2],
               pick, roomCamFovY(&c[pick >= 0 ? pick : i]), e[0], e[1], e[2], l[0], l[1], l[2]);
      }
  }
  return 0;
}
