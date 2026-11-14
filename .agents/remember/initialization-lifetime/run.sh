#!/bin/sh
set -eu
src=.agents/remember/initialization-lifetime
out=.agents/scratch/initialization-lifetime
mkdir -p "$out"
clang++-18 --version > "$out/toolchain.txt"
lldb-18 --version >> "$out/toolchain.txt"
uname -m >> "$out/toolchain.txt"
for mode in default pattern; do
  flags=''
  if [ "$mode" = pattern ]; then flags='-ftrivial-auto-var-init=pattern'; fi
  clang++-18 -std=c++17 -g -O0 -Wall -Wextra -fno-omit-frame-pointer $flags "$src/fixture.cpp" -o "$out/$mode"
  rm -f "$out/$mode.json"
  lldb-18 --batch \
    -o "script import sys; sys.argv=['record.py', '/work/$out/$mode', '/work/$out/$mode.json']" \
    -o "script exec(compile(open('$src/record.py').read(), 'record.py', 'exec'))"
done
python3 "$src/validate.py" "$out/default.json" "$out/pattern.json"
# AST dump is inspection only: no automated AST rewriting is implemented.
clang++-18 -std=c++17 -fsyntax-only -Xclang -ast-dump "$src/fixture.cpp" > "$out/ast.txt"
# Supplementary check only; ASan/UBSan do not detect uninitialized scalar reads.
if clang++-18 -std=c++17 -g -O0 -fsanitize=address,undefined "$src/fixture.cpp" -o "$out/sanitized" > "$out/sanitizer-build.log" 2>&1; then
  "$out/sanitized"
  echo 'ASan/UBSan run passed'
else
  echo 'SKIP ASan/UBSan: sanitizer runtime unavailable; see sanitizer-build.log'
fi
