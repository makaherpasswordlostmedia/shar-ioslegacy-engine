cmake_minimum_required(VERSION 3.10)
# (old stage-4 draft test: skin.c only, no level; kept for reference — the current Homer test is tests/homer/)
project(homertest C)
# standalone Homer test: viewer/skin.c (the real runtime) + a snapshot of viewer/hud.c
add_executable(homertest main.c ../../../viewer/skin.c hud.c)
target_include_directories(homertest PRIVATE ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/../../../viewer)
target_compile_options(homertest PRIVATE -O2 -Wall -Wno-misleading-indentation -fno-math-errno -fsingle-precision-constant)
target_link_libraries(homertest pspgum pspgu pspdebug pspdisplay pspctrl psprtc psppower pspge m)
create_pbp_file(TARGET homertest TITLE "SHAR Homer test" BUILD_PRX)
