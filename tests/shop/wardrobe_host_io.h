#ifndef WARDROBE_HOST_IO_H
#define WARDROBE_HOST_IO_H
#include <fcntl.h>
#include <unistd.h>
typedef int SceUID;
#define PSP_O_RDONLY O_RDONLY
#define PSP_CTRL_LEFT 0x0080
#define PSP_CTRL_RIGHT 0x0020
#define PSP_CTRL_TRIANGLE 0x1000
#define PSP_CTRL_CIRCLE 0x2000
#define PSP_CTRL_CROSS 0x4000
static inline int sceIoOpen(const char *p, int f, int m) { return open(p, f, m); }
static inline int sceIoRead(int f, void *p, int n) { return (int)read(f, p, n); }
static inline int sceIoClose(int f) { return close(f); }
#endif
