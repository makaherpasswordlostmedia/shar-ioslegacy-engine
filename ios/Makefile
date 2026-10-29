# SHAR (Simpsons Hit & Run) native armv7 port - Theos project, same toolchain recipe as the Crash Bandicoot armv7 port.
# Target: any 32-bit iOS device, iOS 7.0 .. 9.3.5 (iPhone 4S/5/5c, iPad 2/3/4/mini 1, iPod touch 5). Built on Linux in CI.
export THEOS_DEVICE_IP =
ARCHS = armv7
TARGET = iphone:clang:9.3:7.0
INSTALL_TARGET_PROCESSES = SHARArmv7

include $(THEOS)/makefiles/common.mk
include sources.mk

APPLICATION_NAME = SHARArmv7
SHARArmv7_FILES = $(SHAR_SRC) src/ge_list.c src/ge_gles2.c src/psp_sys.c src/me_stub.c host/ios_host.m host/ios_availability_stub.m

ios_host.m_CFLAGS += -fobjc-arc
main.c_CFLAGS += -Dmain=shar_main
psp_sys.c_CFLAGS += -DMSIO_IMPL

# shim dir first: it provides <pspgu.h>, <pspkernel.h>, <malloc.h>, <reent.h> ...; msio.h/geguard.h are force-included like in the PSP CMake build.
ADDITIONAL_CFLAGS += -fno-modules -fno-implicit-modules -fno-implicit-module-maps -w -fno-strict-aliasing -fno-math-errno -fsingle-precision-constant \
	-Wno-error -Wno-unknown-warning-option
SHARArmv7_CFLAGS = -I$(CURDIR)/shim -I$(CURDIR)/../viewer -I$(CURDIR)/src -std=gnu11 -O2 -DNDEBUG \
	-include $(CURDIR)/../viewer/msio.h -include $(CURDIR)/../viewer/geguard.h -DSHAR_IOS=1 -DSHAR_RELEASE=1

SHARArmv7_LDFLAGS = -framework UIKit -framework Foundation -framework QuartzCore -framework CoreGraphics -framework OpenGLES \
	-framework AudioToolbox -framework AVFoundation -framework ImageIO -weak_framework GameController -lm -Wl,-dead_strip

SHARArmv7_CODESIGN_FLAGS = -SResources/entitlements.plist
SHARArmv7_PLIST = Resources/Info.plist
SHARArmv7_RESOURCE_FILES = Resources/LaunchImage.png Resources/LaunchImage@2x.png

include $(THEOS_MAKE_PATH)/application.mk

after-install::
	install.exec "killall -9 SHARArmv7 || true"
