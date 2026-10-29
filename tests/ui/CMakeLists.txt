cmake_minimum_required(VERSION 3.10)
project(uitest C)
# standalone UI test: tests/ui/main.c + the engine-side renderer viewer/ui.c (stage 7)
add_executable(uitest main.c ../../viewer/ui.c)
target_compile_options(uitest PRIVATE -O2 -Wall -Wno-misleading-indentation -fno-math-errno -fsingle-precision-constant)
target_link_libraries(uitest pspgu pspdisplay pspctrl psppower pspge m)
# own DISC_ID (not the shared homebrew UCJS10041): PPSSPP then reads the per-game config
# ~/.config/ppsspp/PSP/SYSTEM/SHARU0002_ppsspp.ini (1x internal resolution + software renderer
# for exact 480x272 test shots) without touching the shared ppsspp.ini
execute_process(COMMAND $ENV{PSPDEV}/bin/mksfoex -d MEMSIZE=1 -s DISC_ID=SHARU0002 "SHAR UI test" ${CMAKE_BINARY_DIR}/PARAM.SFO)
create_pbp_file(TARGET uitest TITLE "SHAR UI test" SFO_PATH ${CMAKE_BINARY_DIR}/PARAM.SFO BUILD_PRX)
