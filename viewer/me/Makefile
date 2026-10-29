# Media Engine, ступень 0 (правки Роба 269/273/276): модуль ядра sharme.prx — проба ME методом MIST
# (viewer/me/sharme.c + vendor/: github.com/mcidclan psp-media-engine-safe-task и psp-media-engine-custom-core, MIT).
# Сборка: make -C viewer/me (PSPDEV — pspdev/), как viewer/kexc. На PSP едет правилом «sharme.prx» в tools/ship_rules.txt
TARGET = sharme
OBJS = sharme.o fxdsp_me.o vendor/me-safe-task/me-stask-mist.o vendor/me-safe-task/me-stask-utils.o vendor/me-core-mapper/me-core-mapping.o
BUILD_PRX = 1
PRX_EXPORTS =
USE_PSPSDK_LIBC = 1
USE_KERNEL_LIBS = 1
INCDIR = vendor
# -G0 и без -fpic: код meTask/meWork исполняет ME — без $gp и без таблиц адресов (как у автора библиотеки).
# Правка 276 (смешивание звука на ME, viewer/mixdsp.h): циклы не превращать в вызовы memset/memcpy, деление без ловушки «на 0»
# (break 7: исключение на ME; делитель в mixdsp.h и так не 0) — код ME не зовёт ничего снаружи (проверяет tests/me/run.py)
ME_SAFE = -fno-tree-loop-distribute-patterns -mno-check-zero-division
# Правка 313 (частицы на ME, viewer/fxdsp.h): плавающая точка как у игры (viewer/CMakeLists.txt: -fno-math-errno —
# sqrt.s без вызова, -fsingle-precision-constant) и тот же libm.a (cosf, sinf, atan2f, fminf, __ieee754_expf) — у ME тот же машинный код
CFLAGS = -O2 -G0 -Wall -fno-pic -DPRX_FREE=1 -fno-math-errno -fsingle-precision-constant $(ME_SAFE)
LIBS = -lm -lpspkernel
PSPSDK = $(shell psp-config --pspsdk-path)
include $(PSPSDK)/lib/build.mak
sharme.o: sharme.c mebox.h mework.h ../mixdsp.h ../spatialdsp.h ../fxdsp.h ../fx.h ../fpuguard.h
# правка 313: частицы и свечение — тот же viewer/fxdsp.c, что у игры (те же ключи счёта)
fxdsp_me.o: ../fxdsp.c ../fxdsp.h ../fx.h
	$(CC) $(CFLAGS) -I.. -c -o $@ ../fxdsp.c
