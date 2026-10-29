#ifndef LOAD_FUSE_IO_H
#define LOAD_FUSE_IO_H
 #ifndef LOAD_FUSE_ANIM_OLD
#define LOAD_FUSE_ANIM_OLD 0
#endif
/* The pump runs on the registering thread, under the msio lock: GPU/RAM only,
   no file I/O. The regular msio cache flush and unlock still follow each read. */
void loadFuseIoBegin(void (*pump)(void));
void loadFuseIoEnd(void);
int loadFuseIoPumping(void);
void loadFuseIoSlow(unsigned usec, unsigned chunks); /* service probe only */
int loadFuseIoProbe(void);
extern void (*loadFuseIoNote)(const char *); /* №LOADWAIT: строка в ящик */
void loadFuseIoHang(int n); /* тест: первые N чтений не завершаются */
void loadFuseIoWaitOld(int on);
void loadFuseIoLimitMs(unsigned ms);
#endif
