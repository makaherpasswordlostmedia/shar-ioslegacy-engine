#ifndef GAG_SKIN_H
#define GAG_SKIN_H
#include "collect.h"
typedef int (*CollectRead)(void *user,unsigned off,void *data,unsigned size);
int gagSkinInit(const Collect *c);
int gagSkinInitSource(const Collect *c,CollectRead read,void *user,unsigned fileSize);
int gagSkinPrepare(const Collect *c,const unsigned char *wanted);
extern unsigned gagSkinResidentBytes;
void gagSkinFree(void);
unsigned gagSkinDraw(const Collect *c, int room, float ex, float ez, float distance);
#endif
