#!/usr/bin/env bash
# Measure the REAL flash cost of an lv_font_conv-generated LVGL font.
# The .c file size is source text; what ships is the compiled .rodata.
#
# Usage: ./measure-font.sh <font.c> [more-font.c ...]
# Requires: an ESP-IDF RISC-V (or Xtensa) toolchain on this machine.
# Override with GCC=/path/to/elf-gcc LVGL_DIR=/path/to/lvgl
set -u

GCC="${GCC:-$(find "$HOME/.espressif/tools" -name 'riscv32-esp-elf-gcc.exe' -o -name 'riscv32-esp-elf-gcc' 2>/dev/null | sort | tail -1)}"
SIZEBIN="$(dirname "$GCC")/$(ls "$(dirname "$GCC")" | grep -E 'elf-size(\.exe)?$' | head -1)"
LVGL_DIR="${LVGL_DIR:-$HOME/Downloads/esp32P4/managed_components/lvgl__lvgl}"

[ -x "$GCC" ] || { echo "toolchain gcc not found: set GCC=..."; exit 1; }
[ -f "$LVGL_DIR/lvgl.h" ] || { echo "lvgl.h not found: set LVGL_DIR=..."; exit 1; }

printf "%-34s %10s %10s %8s %6s\n" FONT ".c,B" "rodata,B" "bpp" "glyphs"
for f in "$@"; do
    o="fontmeasure_$$.o"
    "$GCC" -c -Os -w -march=rv32imafc -mabi=ilp32f \
        -DLV_CONF_SKIP=1 -DLV_LVGL_H_INCLUDE_SIMPLE -I"$LVGL_DIR" \
        "$f" -o "$o" || { echo "$(basename $f): COMPILE FAILED"; continue; }
    rd=$("$SIZEBIN" -A "$o" | awk '/^\.rodata/{print $2}')
    bpp=$(grep -m1 -o 'Bpp: [0-9]' "$f" | tr -d 'Bp: ')
    gl=$(grep -c '^    {.bitmap_index' "$f")
    printf "%-34s %10s %10s %8s %6s\n" "$(basename "$f")" "$(wc -c < "$f")" "$rd" "$bpp" "$gl"
    rm -f "$o"
done
