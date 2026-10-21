#ifndef FXHOST_PSPIO_H
#define FXHOST_PSPIO_H
#include <stdio.h>
#define PSP_O_RDONLY 1
#define PSP_SEEK_SET 0
#define PSP_SEEK_END 2
SceUID sceIoOpen(const char *p, int f, int m); int sceIoLseek32(SceUID fd, int off, int wh); int sceIoRead(SceUID fd, void *d, unsigned n); int sceIoClose(SceUID fd);
#endif
