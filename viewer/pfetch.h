// Опережающее чтение целых файлов уровня фоновым загрузчиком (traffic.shr, fx.shr): главный поток разбирает, пока загрузчик читает.
// Хук ставит main_levels.h; пусто — модули читают сами, как раньше. Возвращает память memalign(64) (владелец — вызывающий) или NULL (читать самому).
#ifndef PFETCH_H
#define PFETCH_H
extern void *(*pfTakeHook)(const char *path, unsigned *size);
#endif
