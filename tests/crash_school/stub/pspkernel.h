// Заглушка pspsdk для гейта tests/crash_school/ge_host.sh: файлы — stdio Мака (ge_host.c), асинхронное чтение — сразу
#ifndef STUB_PSPKERNEL_H
#define STUB_PSPKERNEL_H
#include "psptypes.h"
#define PSP_O_RDONLY 0x0001
#define PSP_O_WRONLY 0x0002
#define PSP_O_RDWR   0x0003
#define PSP_O_APPEND 0x0100
#define PSP_O_CREAT  0x0200
#define PSP_O_TRUNC  0x0400
#define PSP_SEEK_SET 0
#define PSP_SEEK_CUR 1
#define PSP_SEEK_END 2
SceUID sceIoOpen(const char *file, int flags, int mode);
int sceIoRead(SceUID fd, void *data, SceSize size);
int sceIoClose(SceUID fd);
int sceIoLseek32(SceUID fd, int offset, int whence);
int sceIoReadAsync(SceUID fd, void *data, SceSize size);
int sceIoPollAsync(SceUID fd, SceInt64 *res);
int sceIoWaitAsync(SceUID fd, SceInt64 *res);
void sceKernelDcacheWritebackRange(const void *p, unsigned int size);
unsigned int sceKernelGetSystemTimeLow(void);
#endif
