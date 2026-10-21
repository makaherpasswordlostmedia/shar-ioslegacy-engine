cmake_minimum_required(VERSION 3.10)
project(sharaudio C)
# standalone audio test: the runtime is viewer/audio.c, compiled unchanged
add_executable(sharaudio main.c ${CMAKE_CURRENT_SOURCE_DIR}/../../viewer/audio.c)
target_include_directories(sharaudio PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/../../viewer)
target_compile_options(sharaudio PRIVATE -O2 -Wall -Wno-misleading-indentation -fno-math-errno -fsingle-precision-constant)
target_link_libraries(sharaudio pspdebug pspdisplay pspge pspctrl pspaudio psppower m)
create_pbp_file(TARGET sharaudio TITLE "SHAR Audio Test" BUILD_PRX)
