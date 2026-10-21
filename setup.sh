#!/usr/bin/env bash
# Ставит PSPDEV v20260601 в ./pspdev и нужные утилиты для распаковки PS2-диска.
set -e
cd "$(dirname "$0")"
V=v20260601; B=https://github.com/pspdev/pspdev/releases/download/$V
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  F=pspdev-macos-latest-arm64.tar.gz ;;
  Darwin-x86_64) F=pspdev-macos-15-intel-x86_64.tar.gz ;;
  Linux-x86_64)  F=pspdev-ubuntu-latest-x86_64.tar.gz ;;
  Linux-aarch64) F=pspdev-ubuntu-24.04-arm-arm64.tar.gz ;;
  *) echo "Windows: используй https://github.com/dmang-dev/pspdev-win"; exit 1 ;;
esac
[ -d pspdev ] || { echo "Качаю $F…"; curl -L "$B/$F" | tar xz; }
if [ "$(uname -s)" = Darwin ]; then brew install cmake sevenzip python@3.11 || true
else sudo apt-get install -y cmake 7zip python3-pip || true; fi
python3 -m pip install -r hit-and-run-web/requirements.txt
echo; echo "Готово. Перед работой:  export PSPDEV=$PWD/pspdev PATH=$PWD/pspdev/bin:\$PATH"
