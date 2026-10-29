#ifndef OPTBENCH_FRAME_IO_H
#define OPTBENCH_FRAME_IO_H
#include <stdint.h>
#include <stddef.h>

/* CPU word reads from uncached VRAM into ordinary RAM. Never give VRAM to
 * libc/file drivers, including their fast paths for large fwrite requests. */
static void snapshot_words(uint32_t *ram, const volatile uint32_t *vram, size_t bytes) {
    for(size_t i=0;i<bytes/sizeof(uint32_t);i++) ram[i]=vram[i];
}

/* A short write is an error, not permission to claim that a frame was saved.
 * The caller always closes the file, including on failure. */
typedef int (*FrameWriter)(void *, const void *, unsigned);
static int write_frame_chunks(const void *ram, unsigned bytes, FrameWriter write, void *ctx) {
    const unsigned char *p=ram;
    for(unsigned off=0;off<bytes;) {
        unsigned n=bytes-off;if(n>16384)n=16384;
        if(write(ctx,p+off,n)!=(int)n)return -1;
        off+=n;
    }
    return 0;
}
#endif
