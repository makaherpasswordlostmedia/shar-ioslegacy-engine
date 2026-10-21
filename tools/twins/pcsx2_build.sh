#!/bin/bash
# Близнецы · О4: свой PCSX2 v2.6.3 (GPL-3.0, открытый код) без окна и без Qt — для ввода из файла (ОРАКУЛ_PS2 §3 О4(б)).
# Зависимости x86_64 (PCSX2 на Mac — только x86_64, работает под Rosetta) собираются локально, как в
# .github/workflows/scripts/macos/build-dependencies.sh, но без Qt, KDDockWidgets, shaderc, MoltenVK, FFmpeg (ядру не нужны:
# ENABLE_QT_UI=OFF, USE_VULKAN=OFF, заголовки FFmpeg вшиты). Ничего не ставится в систему: всё в build/twins/pcsx2/.
#   tools/twins/pcsx2_build.sh deps      зависимости → build/twins/pcsx2/deps
#   tools/twins/pcsx2_build.sh core      ядро + свой хост pcsx2-twins → build/twins/pcsx2/bin/pcsx2-twins
# Процессор: nice 15, TWINS_J потоков (по умолчанию 4) — ядра делим с ботами.
set -e
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
DATA="${TWINS_ROOT:-$(cd "$HERE" && cd "$(git rev-parse --git-common-dir)/.." && pwd)}"
P="$DATA/build/twins/pcsx2"; SRC="$P/src"; DEPS="$P/deps"; DL="$P/dl"; J="${TWINS_J:-4}"
mkdir -p "$DEPS" "$DL"
export PKG_CONFIG_PATH="$DEPS/lib/pkgconfig" LDFLAGS="-L$DEPS/lib" CFLAGS="-I$DEPS/include" CXXFLAGS="-I$DEPS/include"
CM=(-DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$DEPS" -DCMAKE_INSTALL_PREFIX="$DEPS" -DCMAKE_OSX_ARCHITECTURES=x86_64
    -DCMAKE_APPLE_SILICON_PROCESSOR=x86_64 -DCMAKE_SYSTEM_PROCESSOR=x86_64 -DCMAKE_INSTALL_NAME_DIR="$DEPS/lib" -DBUILD_SHARED_LIBS=ON)
NICE=(nice -n 15)

fetch() { [ -s "$DL/$2" ] || curl -sfL -o "$DL/$2" "$1"; }
unpack() { rm -rf "$P/b/$1"; mkdir -p "$P/b"; tar xf "$DL/$2" -C "$P/b"; }
cmk() { local d="$1"; shift; "${NICE[@]}" cmake "${CM[@]}" "$@" -B "$d/_b" "$d" >"$d/_cfg.log" 2>&1 || { tail -20 "$d/_cfg.log"; exit 1; }
        "${NICE[@]}" cmake --build "$d/_b" -j "$J" >"$d/_build.log" 2>&1 || { grep -m5 -A5 error "$d/_build.log"; exit 1; }
        cmake --install "$d/_b" >/dev/null; }

deps() {
  fetch https://libsdl.org/release/SDL3-3.2.26.tar.gz SDL3-3.2.26.tar.gz
  fetch https://github.com/facebook/zstd/releases/download/v1.5.7/zstd-1.5.7.tar.gz zstd-1.5.7.tar.gz
  fetch https://github.com/lz4/lz4/releases/download/v1.10.0/lz4-1.10.0.tar.gz lz4-1.10.0.tar.gz
  fetch https://downloads.sourceforge.net/project/libpng/libpng16/1.6.53/libpng-1.6.53.tar.xz libpng-1.6.53.tar.xz
  fetch https://download.sourceforge.net/libpng-apng/libpng-1.6.53-apng.patch.gz libpng-1.6.53-apng.patch.gz
  fetch https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/3.1.2/libjpeg-turbo-3.1.2.tar.gz libjpeg-turbo-3.1.2.tar.gz
  fetch https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-1.6.0.tar.gz libwebp-1.6.0.tar.gz
  fetch "https://sourceforge.net/projects/freetype/files/freetype2/2.14.1/freetype-2.14.1.tar.xz/download" freetype-2.14.1.tar.xz
  fetch https://github.com/sammycage/plutovg/archive/v1.3.2.tar.gz plutovg-1.3.2.tar.gz
  fetch https://github.com/sammycage/plutosvg/archive/v0.0.7.tar.gz plutosvg-0.0.7.tar.gz
  ( cd "$DL" && shasum -a 256 --check --quiet <<EOF
dad488474a51a0b01d547cd2834893d6299328d2e30f479a3564088b5476bae2  SDL3-3.2.26.tar.gz
eb33e51f49a15e023950cd7825ca74a4a2b43db8354825ac24fc1b7ee09e6fa3  zstd-1.5.7.tar.gz
537512904744b35e232912055ccf8ec66d768639ff3abe5788d90d792ec5f48b  lz4-1.10.0.tar.gz
1d3fb8ccc2932d04aa3663e22ef5ef490244370f4e568d7850165068778d98d4  libpng-1.6.53.tar.xz
452a1a290bd0cf18737fad0057dc17b7fdf10a73eda2d6d4f31ba04fda25ef2c  libpng-1.6.53-apng.patch.gz
8f0012234b464ce50890c490f18194f913a7b1f4e6a03d6644179fa0f867d0cf  libjpeg-turbo-3.1.2.tar.gz
e4ab7009bf0629fd11982d4c2aa83964cf244cffba7347ecd39019a9e38c4564  libwebp-1.6.0.tar.gz
32427e8c471ac095853212a37aef816c60b42052d4d9e48230bab3bdf2936ccc  freetype-2.14.1.tar.xz
7bd4e79ce18b1d47517e7e91fbb7cf19d4f01942804a519bc7c0bf32b6325dd5  plutovg-1.3.2.tar.gz
78561b571ac224030cdc450ca2986b4de915c2ba7616004a6d71a379bffd15f3  plutosvg-0.0.7.tar.gz
EOF
  )
  echo "SDL3"; unpack SDL3-3.2.26 SDL3-3.2.26.tar.gz; cmk "$P/b/SDL3-3.2.26" -DSDL_X11=OFF -DSDL_TESTS=OFF
  echo "zstd"; unpack zstd-1.5.7 zstd-1.5.7.tar.gz; "${NICE[@]}" cmake "${CM[@]}" -DZSTD_BUILD_PROGRAMS=OFF -B "$P/b/zstd-1.5.7/_b" "$P/b/zstd-1.5.7/build/cmake" >/dev/null && cmake --build "$P/b/zstd-1.5.7/_b" -j "$J" >/dev/null && cmake --install "$P/b/zstd-1.5.7/_b" >/dev/null
  echo "lz4"; unpack lz4-1.10.0 lz4-1.10.0.tar.gz; "${NICE[@]}" cmake "${CM[@]}" -DLZ4_BUILD_CLI=OFF -DLZ4_BUILD_LEGACY_LZ4C=OFF -B "$P/b/lz4-1.10.0/_b" "$P/b/lz4-1.10.0/build/cmake" >/dev/null && cmake --build "$P/b/lz4-1.10.0/_b" -j "$J" >/dev/null && cmake --install "$P/b/lz4-1.10.0/_b" >/dev/null
  echo "libpng+apng"; unpack libpng-1.6.53 libpng-1.6.53.tar.xz; gunzip -c "$DL/libpng-1.6.53-apng.patch.gz" > "$P/b/apng.patch"; ( cd "$P/b/libpng-1.6.53" && patch -s -p1 < ../apng.patch ); cmk "$P/b/libpng-1.6.53" -DPNG_TESTS=OFF -DPNG_FRAMEWORK=OFF
  echo "libjpeg-turbo"; unpack libjpeg-turbo-3.1.2 libjpeg-turbo-3.1.2.tar.gz; cmk "$P/b/libjpeg-turbo-3.1.2" -DENABLE_STATIC=OFF -DENABLE_SHARED=ON
  echo "libwebp"; unpack libwebp-1.6.0 libwebp-1.6.0.tar.gz; cmk "$P/b/libwebp-1.6.0" -DWEBP_BUILD_ANIM_UTILS=OFF -DWEBP_BUILD_CWEBP=OFF -DWEBP_BUILD_DWEBP=OFF -DWEBP_BUILD_GIF2WEBP=OFF -DWEBP_BUILD_IMG2WEBP=OFF -DWEBP_BUILD_VWEBP=OFF -DWEBP_BUILD_WEBPINFO=OFF -DWEBP_BUILD_WEBPMUX=OFF -DWEBP_BUILD_EXTRAS=OFF
  echo "freetype"; unpack freetype-2.14.1 freetype-2.14.1.tar.xz; cmk "$P/b/freetype-2.14.1" -DFT_REQUIRE_ZLIB=ON -DFT_REQUIRE_PNG=ON -DFT_DISABLE_BZIP2=TRUE -DFT_DISABLE_BROTLI=TRUE -DFT_DISABLE_HARFBUZZ=TRUE
  echo "plutovg"; unpack plutovg-1.3.2 plutovg-1.3.2.tar.gz; cmk "$P/b/plutovg-1.3.2" -DPLUTOVG_BUILD_EXAMPLES=OFF
  echo "plutosvg"; unpack plutosvg-0.0.7 plutosvg-0.0.7.tar.gz; cmk "$P/b/plutosvg-0.0.7" -DPLUTOSVG_ENABLE_FREETYPE=ON -DPLUTOSVG_BUILD_EXAMPLES=OFF
  echo "OK зависимости → $DEPS"
}

core() {
  [ -d "$SRC/.git" ] || git clone -q --depth 1 --branch v2.6.3 https://github.com/PCSX2/pcsx2.git "$SRC"
  mkdir -p "$SRC/pcsx2-twins"
  cp -f "$HERE/tools/twins/pcsx2_twins/Main.cpp" "$SRC/pcsx2-twins/Main.cpp"
  cp -f "$HERE/tools/twins/pcsx2_twins/CMakeLists.txt" "$SRC/pcsx2-twins/CMakeLists.txt"
  grep -q "pcsx2-twins" "$SRC/CMakeLists.txt" || echo 'add_subdirectory(pcsx2-twins)' >> "$SRC/CMakeLists.txt"
  # звук для близнецов: крючок на каждый выходной сэмпл SPU2 (48 кГц, стерео) — pcsx2-twins пишет WAV с привязкой к кадрам
  if ! grep -q "g_twins_audio_sample" "$SRC/pcsx2/SPU2/spu2.cpp"; then
    sed -i '' 's|^__forceinline void spu2Output(StereoOut32 out)$|void (*g_twins_audio_sample)(s16, s16) = nullptr;   // twins\
__forceinline void spu2Output(StereoOut32 out)|' "$SRC/pcsx2/SPU2/spu2.cpp"
    sed -i '' 's|^	s_current_chunk\[s_current_chunk_pos++\] = static_cast<s16>(clamp_mix(out.Right));$|&\
	if (g_twins_audio_sample) [[unlikely]] g_twins_audio_sample(s_current_chunk[s_current_chunk_pos - 2], s_current_chunk[s_current_chunk_pos - 1]);|' "$SRC/pcsx2/SPU2/spu2.cpp"
  fi
  # v2.6.3: KDDockWidgets ищется и без Qt UI — оборачиваем в if(ENABLE_QT_UI) (только своя копия исходников)
  grep -q "twins: kddw" "$SRC/cmake/SearchForStuff.cmake" || sed -i '' 's|^	find_package(KDDockWidgets-qt6 2.3.0 REQUIRED)|if(ENABLE_QT_UI) # twins: kddw\
	find_package(KDDockWidgets-qt6 2.3.0 REQUIRED)\
endif()|' "$SRC/cmake/SearchForStuff.cmake"
  # без CMAKE_APPLE_SILICON_PROCESSOR: иначе CMake считает хост x86_64 и ставит -march=native (= apple-m1, ошибка);
  # DISABLE_ADVANCE_SIMD=ON — базовый SSE4.1 и выбор AVX на ходу, как в официальной сборке для Mac
  "${NICE[@]}" cmake -B "$P/core" "$SRC" -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$DEPS" -DCMAKE_OSX_ARCHITECTURES=x86_64 \
    -DDISABLE_ADVANCE_SIMD=ON -DENABLE_QT_UI=OFF -DENABLE_GSRUNNER=OFF -DUSE_VULKAN=OFF -DENABLE_TESTS=OFF \
    -DSKIP_POSTPROCESS_BUNDLE=ON >"$P/core_cfg.log" 2>&1 || { tail -30 "$P/core_cfg.log"; exit 1; }
  "${NICE[@]}" cmake --build "$P/core" --target pcsx2-twins -j "$J" >"$P/core_build.log" 2>&1 || { grep -m8 -B2 -A6 "error" "$P/core_build.log"; exit 1; }
  mkdir -p "$P/bin"; cp -f "$(find "$P/core" -name pcsx2-twins -type f -perm -u+x | head -1)" "$P/bin/pcsx2-twins"
  rm -rf "$P/bin/resources"; cp -R "$SRC/bin/resources" "$P/bin/resources"
  echo "OK $P/bin/pcsx2-twins"
}

case "$1" in deps) deps ;; core) core ;; *) echo "tools/twins/pcsx2_build.sh deps|core"; exit 2 ;; esac
