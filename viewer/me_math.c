// Same errno-free overflow helpers as sharme.c. ME may never call libc __errno
static float __attribute__((noinline)) meXflowf(unsigned sign,float y){volatile float t=sign?-y:y;return t*y;}
float __math_oflowf(unsigned sign){return meXflowf(sign,0x1p97f);}
float __math_uflowf(unsigned sign){return meXflowf(sign,0x1p-95f);}
