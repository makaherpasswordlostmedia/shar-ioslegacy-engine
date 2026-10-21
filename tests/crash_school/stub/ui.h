// Заглушка viewer/ui.h для гейта tests/crash_school/ge_host.sh: msnart.c зовёт только значок задания
#ifndef STUB_UI_H
#define STUB_UI_H
void uiSetObjIconImage(const void *pix, int tw, int th, int w, int h);
int uiMarkerSmall(int type, const float *center, const float *half);   // msnart.c: значок 16 px вместо мелкого 3D (в гейте — всегда 3D)
#endif
