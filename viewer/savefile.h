// Сохранение файлом на карте памяти — последняя страховка правки 274 (см. savefile.c).
#ifndef SHAR_SAVEFILE_H
#define SHAR_SAVEFILE_H
int svFileWrite(const char *dir, int slot, const void *data, int n);   // 0 — записано и прочитано обратно байт в байт; <0 — ошибка
int svFileRead(const char *dir, int slot, void *buf, int n);           // число прочитанных байт; <0 — файла нет или ошибка чтения
int svFileDelete(const char *dir, int slot);                           // 0 — удалён или его не было
#endif
