cmake_minimum_required(VERSION 3.10)
project(homertest C)
# Stage-4 test EBOOT: viewer/main.c + the Homer patch (tests/homer/patch_main.py -> build/game.c) + all engine modules.
set(V ${CMAKE_CURRENT_SOURCE_DIR}/../../viewer)
add_executable(homertest ${CMAKE_CURRENT_BINARY_DIR}/game.c ${V}/hud.c ${V}/col.c ${V}/car.c ${V}/props.c ${V}/coins.c ${V}/fx.c
               ${V}/groundshade.c ${V}/carvis.c ${V}/stateprops.c ${V}/skin.c ${V}/homer.c)
target_include_directories(homertest PRIVATE ${V})
target_compile_options(homertest PRIVATE -O2 -Wall -Wno-misleading-indentation -fno-math-errno -fsingle-precision-constant)
target_link_libraries(homertest pspgum pspgu pspdebug pspdisplay pspctrl psprtc psppower pspge m)
create_pbp_file(TARGET homertest TITLE "SHAR Homer test" BUILD_PRX)
