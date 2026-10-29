/* iOS has no <malloc.h>/memalign/malloc_usable_size */
#ifndef SHIM_MALLOC_H
#define SHIM_MALLOC_H
#include <stdlib.h>
#ifdef __APPLE__
#include <malloc/malloc.h>
#define malloc_usable_size(p) malloc_size(p)
#endif
static inline void *memalign(size_t a, size_t n) { void *p = 0; if (a < sizeof(void *)) a = sizeof(void *); return posix_memalign(&p, a, n) ? 0 : p; }
#endif
