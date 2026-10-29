#pragma once
#include "psp_compat.h"
/* shim for PSP kubridge (ARK-4): signatures match definitions in ios/src/psp_sys.c */
#ifdef __cplusplus
extern "C" {
#endif
SceUID kuKernelLoadModule(const char *path, int flags, void *option);
int kuKernelCall(void *func, void *args);
#ifdef __cplusplus
}
#endif
