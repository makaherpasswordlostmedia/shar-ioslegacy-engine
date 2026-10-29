// gevb.h — кольцо вершин кадра в кэшируемой памяти вместо sceGuGetMemory (закон «≈ 1 мкс на слово списка GE», PHDRAW kw): список GE пишется
// мимо кэша, 5–6 слов на вершину; здесь вершины пишутся в обычную память и сбрасываются в неё одним вызовом перед sceGuFinish.
// geVbBegin() — начало кадра (кольцо пусто, включено), geVbEnd() — перед sceGuFinish кадра (сброс кэша, выключено). Вне кадра и при нехватке
// места geVbAlloc отдаёт sceGuGetMemory (как раньше). Каждое место вызова пишет свой флаг _OLD: geVbAlloc(bytes, old).
#ifndef GEVB_H
#define GEVB_H
#ifdef __cplusplus
extern "C" {
#endif
void geVbBegin(void);
void geVbEnd(void);
void *geVbAlloc(unsigned bytes, int old);   // выровнено на 16 Б; old != 0 — прежний путь
unsigned geVbUsed(void);
#ifdef __cplusplus
}
#endif
#endif
