// Правка 313: частицы и свечение — функции счёта (viewer/fxdsp.h) одним файлом: игра (viewer/CMakeLists.txt, ключи как у модуля)
// и модуль ME (viewer/me/Makefile, fxdsp_me.o) собирают его одинаково — у главного процессора и у ME один машинный код
#define FXDSP_IMPL
#include "fxdsp.h"
