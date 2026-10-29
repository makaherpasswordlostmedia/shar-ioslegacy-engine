#ifndef FXHOST_PSPKERNEL_H
#define FXHOST_PSPKERNEL_H
typedef int SceUID;
static inline void sceKernelDcacheWritebackRange(const void *p, unsigned n) { (void)p; (void)n; }
static inline void sceKernelDcacheWritebackInvalidateRange(const void *p, unsigned n) { (void)p; (void)n; }
static inline void sceKernelDcacheInvalidateRange(const void *p, unsigned n) { (void)p; (void)n; }
#endif
