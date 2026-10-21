#!/bin/bash
# PSPLink: Мак запускает игру на PSP по кабелю, без копирования на карту.
# 1) На PSP: выйти из режима USB, в меню «Игра» запустить PSPLink. 2) Двойной клик по этому файлу.
# 3) В окне pspsh набрать:  ./EBOOT.PBP   (игра стартует с Мака, файлы уровня читаются из папки build/)
cd "$(dirname "$0")/../.." || exit 1
ROOT="$PWD"; export PATH="$ROOT/pspdev/bin:$PATH"
if [ ! -f /opt/homebrew/opt/libusb/lib/libusb-1.0.0.dylib ]; then
  echo "Ставлю libusb (нужна связи с PSP)…"; brew install libusb || { echo "Не вышло поставить libusb"; read -r; exit 1; }
fi
SERVE="${1:-$ROOT/build}"
echo "PSP видит папку как host0: $SERVE"
usbhostfs_pc -c "$SERVE" > "$ROOT/build/psplink_usbhostfs.log" 2>&1 &
HPID=$!
trap 'kill $HPID 2>/dev/null' EXIT
sleep 2
if ! kill -0 $HPID 2>/dev/null; then echo "usbhostfs_pc не запустился, смотри build/psplink_usbhostfs.log"; read -r; exit 1; fi
echo "Жду PSP (на ней должен быть запущен PSPLink)…"
pspsh
