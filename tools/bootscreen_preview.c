// Превью загрузочного экрана на Маке (пункт Л): тот же ход viewer/bootseq.h (+ bootui.h, bootanim.h), что на PSP, кадры
// 480×272 сырыми RGB в stdout (по кадру на 16 мс); tools/bootscreen_preview.py собирает GIF 1:1 и ×2 и последний кадр PNG.
//   cc -std=c99 -I viewer tools/bootscreen_preview.c -o build/bootscreen_preview && build/bootscreen_preview > frames.rgb
// Значения железа — как в PPSSPP (333 МГц, 24576K, батарея 100%, MS0:); на PSP — настоящие.
#include <stdio.h>
#include <string.h>
#include "bootseq.h"
#ifndef BOOT_MARKS
#define BOOT_MARKS 1   // = viewer/bootscreen.h (правка Роба 148)
#endif
#include "bootbeep.h"
static unsigned fb[BUI_H][BUI_W];
static void put(void *u, int x, int y, unsigned c) { (void)u; if (x >= 0 && x < BUI_W && y >= 0 && y < BUI_H) fb[y][x] = c; }
static void frame(int n) {   // n кадров по 16 мс
  static unsigned char row[BUI_W * 3];
  for (; n > 0; n--) for (int y = 0; y < BUI_H; y++) {
    for (int x = 0; x < BUI_W; x++) { unsigned c = fb[y][x]; row[3 * x] = c & 255; row[3 * x + 1] = (c >> 8) & 255; row[3 * x + 2] = (c >> 16) & 255; }
    fwrite(row, 1, sizeof row, stdout);
  }
}
// правка 203: настоящие числа строк данных — те же заголовки файлов, что на PSP, но из build/ (argv[2], по умолчанию build/)
#include <dirent.h>
#include <strings.h>
#include <sys/stat.h>
static const char *pvDir = "build/";
static int pvRd(void *u, const char *name, unsigned off, void *buf, int n) {
  (void)u; char fn[512]; snprintf(fn, sizeof fn, "%s%s", pvDir, name); FILE *f = fopen(fn, "rb"); if (!f) return -1;
  int r = fseek(f, (long)off, SEEK_SET) ? -1 : (int)fread(buf, 1, (size_t)n, f); fclose(f); return r;
}
static void pvScan(const char *dir, const char *ext, int depth, int *count, unsigned long long *bytes) {
  DIR *d = opendir(dir); if (!d) return; struct dirent *e; size_t el = strlen(ext);
  while ((e = readdir(d))) {
    if (e->d_name[0] == '.') continue;
    char fn[1024]; snprintf(fn, sizeof fn, "%s%s", dir, e->d_name); struct stat st; if (stat(fn, &st)) continue;
    if (S_ISDIR(st.st_mode)) { if (depth > 0 && strcmp(e->d_name, "_archive")) { strncat(fn, "/", sizeof fn - strlen(fn) - 1); pvScan(fn, ext, depth - 1, count, bytes); } continue; }
    size_t nl = strlen(e->d_name); if (el && (nl < el || strcasecmp(e->d_name + nl - el, ext))) continue;
    if (strstr(e->d_name, "_ok.")) continue;   // запасные копии build/ на карту не идут
    (*count)++; *bytes += (unsigned long long)st.st_size;
  }
  closedir(d);
}
static void pvDirFn(void *u, const char *dir, const char *ext, int *count, unsigned *mb) {
  (void)u; char fn[512]; unsigned long long by = 0; *count = 0;
  snprintf(fn, sizeof fn, "%s%s%s", pvDir, dir, dir[0] ? "/" : ""); pvScan(fn, ext, dir[0] ? 0 : 1, count, &by); *mb = (unsigned)((by + (1u << 19)) >> 20);
}
int main(int argc, char **argv) {   // argv[1] — build/bootmarks.bin (правка 127; нет файла — без знаков)
  static unsigned char mk[65536]; static BootMarks marks;
  FILE *f = argc > 1 ? fopen(argv[1], "rb") : 0;
  if (f) { int n = (int)fread(mk, 1, sizeof mk, f); fclose(f); if (BOOT_MARKS && bootMarksParse(mk, n, &marks) > 0) bootSeqMarks = &marks; }   // правка 148: знаки выключены, как на PSP
  for (int y = 0; y < BUI_H; y++) for (int x = 0; x < BUI_W; x++) fb[y][x] = BUI_BG;
  BootSys s = {333, 166, 24576, -2, BOOT_BEEP_HZ, 100, "MS0:"}; s.vramK = 2048;
  if (argc > 2) pvDir = argv[2];
  bootDataScan(&s, pvRd, pvDirFn, 0);
  int len = bootSeqLen();
  for (int n = 0; n < len; n++) { if (n == 2) s.audioCh = 0; bootSeqDraw(n, &s, put, 0); frame(1); }
  bootSeqDraw(len, &s, put, 0); frame(30);
  return 0;
}
