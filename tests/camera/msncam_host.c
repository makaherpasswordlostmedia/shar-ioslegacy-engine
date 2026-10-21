// Камеры старта этапов миссий на Маке (правка Роба 40, tests/camera/msncam.sh): пакет msncam.shr через viewer/msncam.c (тот же
// код, что в EBOOT). Строки: CAM имя миссия кадров fps фаза; POSE фаза t eye(3) look(3) fovY идёт; FIND фаза камера|-;
// ошибка разбора — «BAD».
//   cc -std=c99 -O2 -I viewer tests/camera/msncam_host.c viewer/msncam.c -lm -o build/msncam_host && build/msncam_host build/msncam.shr
#include <stdio.h>
#include <stdlib.h>
#include "msncam.h"

int main(int argc, char **argv) {
  FILE *f = fopen(argc > 1 ? argv[1] : "build/msncam.shr", "rb"); if (!f) { puts("BAD нет пакета"); return 2; }
  fseek(f, 0, SEEK_END); long n = ftell(f); rewind(f); unsigned char *b = malloc(n); if (fread(b, 1, n, f) != (size_t)n) return 2; fclose(f);
  static MsnCam c[24]; int k = msncamParse(c, 24, b, (unsigned)n);
  if (k <= 0) { printf("BAD разбор %d\n", k); return 1; }
  for (int i = 0; i < k; i++) {
    printf("CAM %s %d %u %.1f %s\n", c[i].name, c[i].mission, c[i].nfr, c[i].fps, c[i].phase);
    const MsnCam *fc = msncamFind(c, k, c[i].phase, c[i].name), *wrong = msncamFind(c, k, c[i].phase, "noSuchCamShape");
    printf("FIND %s %s %s\n", c[i].phase, fc ? fc->name : "-", wrong ? "wrong-name-accepted" : "wrong-name-refused");
    float dur = (c[i].nfr - 1) / c[i].fps;
    for (float t = 0.f; t <= dur + .2f; t += 1.f / 30.f) {
      float e[3], l[3], u[3], fy; int go = msncamPose(&c[i], t, e, l, u, &fy);
      printf("POSE %s %.4f %.3f %.3f %.3f %.3f %.3f %.3f %.2f %d\n", c[i].phase, t, e[0], e[1], e[2], l[0], l[1], l[2], fy, go);
    }
  }
  return 0;
}
