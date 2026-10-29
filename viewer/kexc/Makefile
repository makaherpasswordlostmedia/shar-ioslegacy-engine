# Ловушка вылета SHARVIEW: модуль ядра sharexc.prx (viewer/kexc/main.c). Сборка: make -C viewer/kexc (PSPDEV — pspdev/)
TARGET = sharexc
OBJS = main.o
BUILD_PRX = 1
PRX_EXPORTS =
USE_PSPSDK_LIBC = 1
USE_KERNEL_LIBS = 1
CFLAGS = -O2 -G0 -Wall
LIBS = -lpspdebug -lpspge_driver -lpspdisplay_driver -lpspkernel
PSPSDK = $(shell psp-config --pspsdk-path)
include $(PSPSDK)/lib/build.mak
