#ifndef COLL_STREAM_H
#define COLL_STREAM_H
#include "gag_skin.h"
#ifndef GAG_SKIN_STREAM_OLD
#define GAG_SKIN_STREAM_OLD 0
#endif
extern int gagSkinStreamOld;
extern unsigned collStreamResidentBytes,collStreamTrackBytes;
void *collStreamLoad(Collect *c,CollectRead read,void *user,unsigned size);
int collStreamPrepare(Collect *c,int room,float ex,float ez,float distance,int snap);
void collStreamFree(void);
#endif
