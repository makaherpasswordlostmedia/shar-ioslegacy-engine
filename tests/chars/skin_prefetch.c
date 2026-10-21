// Хост-проверка предзагрузки модели персонажа (viewer/skin.c skinPreStart/Ready/Finish, разбор тура 12): тот же результат, что у skinLoad, на всех
// .chr папки; повреждённый и пустой файл — отказ без падения; отмена освобождает. Красный: STAGE_PREFETCH_OLD к skin.c не относится — контроль
// сравнением (если Finish вернёт модель с другим числом суставов/клипов/батчей — FAIL).
//   cc -std=c11 -O2 -DSKIN_HOST -I viewer tests/chars/skin_prefetch.c viewer/skin.c viewer/levlight.c -lm -o build/tmp/skin_prefetch && build/tmp/skin_prefetch build/chars
#include <stdio.h>
#include <string.h>
#include <dirent.h>
#include "skin.h"
int main(int argc, char **argv) {
  const char *dir = argc > 1 ? argv[1] : "build/chars"; DIR *d = opendir(dir); if (!d) { printf("FAIL нет папки %s\n", dir); return 1; }
  struct dirent *e; int n = 0, bad = 0;
  while ((e = readdir(d))) {
    size_t l = strlen(e->d_name); if (l < 5 || strcmp(e->d_name + l - 4, ".chr")) continue;
    char fn[512]; snprintf(fn, sizeof fn, "%s/%s", dir, e->d_name);
    SkinModel *a = skinLoad(fn); SkinPre *p = skinPreStart(fn); int rdy = p ? skinPreReady(p) : -1; SkinModel *b = skinPreFinish(p);
    int ok = a && b && a->h->size == b->h->size && a->h->nJoints == b->h->nJoints && a->h->nBatches == b->h->nBatches && a->h->nClips == b->h->nClips && a->h->nTex == b->h->nTex &&
             !memcmp(a->base, b->base, a->h->size) && rdy == 1;
    if (!ok) { bad++; printf("FAIL %s\n", e->d_name); }
    skinFree(a); skinFree(b); n++;
  }
  closedir(d);
  { FILE *f = fopen("build/tmp/_bad.chr", "wb"); if (f) { fwrite("CHR1xxxx", 1, 8, f); fclose(f); }
    SkinPre *p = skinPreStart("build/tmp/_bad.chr"); SkinModel *m = skinPreFinish(p); int ok = !m; printf("%s повреждённый файл — отказ без падения\n", ok ? "PASS" : "FAIL"); bad += !ok;
    SkinPre *q = skinPreStart("build/tmp/_нет_файла.chr"); ok = !q; printf("%s нет файла — NULL\n", ok ? "PASS" : "FAIL"); bad += !ok;
    SkinPre *r = skinPreStart("build/tmp/_bad.chr"); skinPreCancel(r); printf("PASS отмена\n"); }
  printf("%s предзагрузка = skinLoad на %d файлах .chr\n", bad ? "FAIL" : "PASS", n);
  return bad ? 1 : 0;
}
