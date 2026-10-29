// Заглушка <malloc.h> (newlib PSP) для гейта tests/crash_school/ge_host.sh: memalign — в ge_host.c (posix_memalign Мака)
#ifndef STUB_MALLOC_H
#define STUB_MALLOC_H
#include <stdlib.h>
void *memalign(size_t align, size_t size);
#endif
