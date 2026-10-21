// Камеры зон города на Маке (правка Роба 40, tests/camera/zonecam.sh): пакет zonecam-l1.shr через viewer/roomcam.c (тот же код,
// что в EBOOT). На каждую камеру пакета: ноги Гомера в центре её первого триггера -> какая камера выбрана, её глаз и взгляд.
// Строки: CAM имя вид триггеров; PICK имя_ожидаемой выбранная|- eye(3) look(3) fovY; ошибка разбора — «BAD».
//   cc -std=c99 -O2 -I viewer tests/camera/zonecam_host.c viewer/roomcam.c -lm -o build/zonecam_host
#include <stdio.h>
#include <stdlib.h>
#include "roomcam.h"

int main(int argc, char **argv) {
  FILE *f = fopen(argc > 1 ? argv[1] : "build/zonecam-l1.shr", "rb"); if (!f) { puts("BAD нет пакета"); return 2; }
  fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f); unsigned char *b = malloc(n); if (fread(b, 1, n, f) != (size_t)n) return 2; fclose(f);
  static RoomCam c[64]; int k = roomCamsParse(c, 64, b, (unsigned)n);
  if (k <= 0) { printf("BAD разбор %d\n", k); return 1; }
  for (int i = 0; i < k; i++) {
    printf("CAM %s %d %d\n", c[i].name, c[i].type, c[i].ntrig);
    if (c[i].ntrig < 1) continue;
    float p[3] = {c[i].trig[0].c[0], c[i].trig[0].c[1], c[i].trig[0].c[2]};
    RoomCamState st = {-1}; float e[3] = {0}, l[3] = {0}, fy = 0.f;
    int j = -1; for (int s = 0; s < 3; s++) j = roomCamStep(c, k, &st, p, 1.f / 30.f, e, l, &fy);   // три кадра: рельс встаёт на место
    printf("PICK %s %s %.3f %.3f %.3f %.3f %.3f %.3f %.2f %.3f %.3f %.3f\n", c[i].name, j >= 0 ? c[j].name : "-", e[0], e[1], e[2], l[0], l[1], l[2], fy, p[0], p[1], p[2]);
  }
  return 0;
}
