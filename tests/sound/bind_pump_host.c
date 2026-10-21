/* №517: sndBindObjects — кадр экрана загрузки изнутри привязки (sndBindPump) и тот же результат, что у полного перебора.
   Использование: bind_pump_host каталог_audio/ [N] (компилируется с -I viewer, без sound.c в списке); печатает "calls K sum S". Результат S (сумма id) обязан совпасть у -DSNDBIND_PUMP_OLD=1 и без; K у OLD = 0. */
#include <stdio.h>
#include <stdlib.h>
#include "sound.c"   /* целиком: нужны objs/nobj, чтобы поставить точки ровно на объекты звукового пакета */
static int calls; static void pump(void) { calls++; }
typedef struct { float x, y, z; } P3;
int main(int argc, char **argv) {
  if (argc < 2 || sndInit(argv[1]) < 0) return 2;
  unsigned n = argc > 2 ? (unsigned)atoi(argv[2]) : 600; P3 *p = malloc(n * sizeof *p); srand(5);
  for (unsigned i = 0; i < n; i++) { const XObj *o = &objs[(unsigned)rand() % nobj]; p[i].x = o->x + (i % 5 ? 0.f : 0.3f); p[i].y = o->y; p[i].z = o->z; }   // 4 из 5 точно на объекте, каждая пятая рядом
  sndBindPump = pump; sndBindObjects(SND_SET_PROPS, n, p, sizeof *p); sndBindObjects(SND_SET_SPROPS, n, p, sizeof *p);
  long sum = 0; for (unsigned i = 0; i < n; i++) sum += sndObjectSound(SND_SET_PROPS, i) * 3 + sndObjectSound(SND_SET_SPROPS, i);
  printf("calls %d sum %ld\n", calls, sum); sndShutdown(); return 0;
}
