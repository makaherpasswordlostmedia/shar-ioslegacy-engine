// Разбор SMV1 на Маке тем же кодом, что на PSP (viewer/movie.c: mvHeader/mvIndex/mvChunk — movieOpen и поток чтения).
//   host FILE.smv...   1) каждый файл целый: все куски проходят, звук ровно кадры*1764, кадры = заголовку
//                      2) порча каждого байта заголовка, байта индекса, поля размера JPEG, SOI/EOI кадров, длины файла
//                         обязана быть отвергнута (иначе PSP разожмёт мусор или прочтёт мимо куска)
// Красное: подать испорченный файл как целый (tests/movie/host.sh BAD.smv) -> FAIL.
#define MOVIE_HOST
#include "../../viewer/movie.c"
#include <stdio.h>

static int walk(const unsigned char *d, unsigned n, unsigned *frames) {   // кадров или -1
  MvHdr h; unsigned pcm = 0;
  if (n < 64 || mvHeader(d, n, &h) || mvIndex(&h, d + h.idxOff)) return -1;
  for (unsigned i = 0; i < h.frames; i++) {
    unsigned a = rd32(d + h.idxOff + 4 * i), b = rd32(d + h.idxOff + 4 * i + 4), jl, pl;
    if (mvChunk(&h, d + a, b - a, &jl, &pl)) return -1;
    pcm += pl;
  }
  if (pcm != h.total) return -1;
  *frames = h.frames; return 0;
}
int main(int argc, char **argv) {
  int fail = 0;
  for (int k = 1; k < argc; k++) {
    FILE *f = fopen(argv[k], "rb"); if (!f) { printf("  FAIL %s: нет файла\n", argv[k]); fail = 1; continue; }
    fseek(f, 0, SEEK_END); unsigned n = ftell(f); fseek(f, 0, SEEK_SET);
    unsigned char *d = malloc(n + 1); if (fread(d, 1, n, f) != n) n = 0; fclose(f);
    unsigned fr = 0; int ok = walk(d, n, &fr) == 0, tried = 0, caught = 0;
    if (!ok) { printf("  FAIL %s: целый файл отвергнут\n", argv[k]); fail = 1; free(d); continue; }
    MvHdr h; mvHeader(d, n, &h);
    unsigned pos[256]; int np = 0;
    for (unsigned i = 0; i < 64; i++) pos[np++] = i;                                   // заголовок
    for (unsigned i = 0; i < 4 * (h.frames + 1) && np < 160; i += 1 + i / 7) pos[np++] = h.idxOff + i;   // индекс
    for (unsigned c = 0; c < h.frames && np < 250; c += 1 + h.frames / 20) {         // куски: размер JPEG, SOI, EOI
      unsigned a = rd32(d + h.idxOff + 4 * c), jl = rd32(d + a);
      pos[np++] = a; pos[np++] = a + 8; pos[np++] = a + 8 + jl - 1;
    }
    for (int i = 0; i < np; i++) {
      unsigned char o = d[pos[i]]; d[pos[i]] ^= 0x55; tried++;
      unsigned x; if (walk(d, n, &x)) caught++; else printf("  FAIL %s: порча байта %u не замечена\n", argv[k], pos[i]);
      d[pos[i]] = o;
    }
    unsigned x; tried += 2; caught += walk(d, n - 1, &x) != 0; d[n] = 0; caught += walk(d, n + 1, &x) != 0;   // длина файла
    printf("  %s %s: кадров %u, порча отвергнута %d/%d\n", caught == tried ? "ok  " : "FAIL", argv[k], fr, caught, tried);
    if (caught != tried) fail = 1;
    free(d);
  }
  printf("movie host: %s\n", fail ? "FAIL" : "PASS");
  return fail;
}
