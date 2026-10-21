// Заглушка pspsdk для гейта tests/crash_school/ge_host.sh (сборка skin.c и msnart.c на Маке): только типы
#ifndef STUB_PSPTYPES_H
#define STUB_PSPTYPES_H
typedef struct { float x, y, z; } ScePspFVector3;
typedef struct { float x, y, z, w; } ScePspFVector4;
typedef struct { ScePspFVector4 x, y, z, w; } ScePspFMatrix4;
typedef int SceUID;
typedef unsigned int SceSize;
typedef unsigned int SceUInt;
typedef long long SceInt64;
#endif
