#!/bin/sh
set -eu
base=.agents/remember/dynamic-arrays
out=.agents/scratch/dynamic-arrays
mkdir -p "$out"
clang++-18 -std=c++17 -g -O0 -fno-omit-frame-pointer "$base/student.cpp" "$base/allocations.cpp" -o "$out/student"
for n in 3 5; do
  rm -f "$out/trace-$n.json"
  ARRAY_N=$n lldb-18 --batch -o "script exec(compile(open('$base/record.py').read(), 'record.py', 'exec'))"
  python3 "$base/validate.py" "$out/trace-$n.json"
done
# Retain independent compiler evidence for new-expression types and bound expressions.
clang++-18 -std=c++17 -Xclang -ast-dump -fsyntax-only "$base/student.cpp" > "$out/ast.txt"
llvm-dwarfdump-18 --debug-info "$out/student" > "$out/dwarf.txt"
