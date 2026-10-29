#ifndef FXHOST_MALLOC_H
#define FXHOST_MALLOC_H
#include <stdlib.h>
static inline void *memalign(size_t a, size_t n) { void *p = 0; return posix_memalign(&p, a < sizeof(void *) ? sizeof(void *) : a, n) ? 0 : p; }
#endif
