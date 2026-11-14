#!/bin/sh
# Deliberately NOT a semantic-preservation gate. Preserve the observed mismatch.
set -eu
cd /work
R=.agents/remember/ast-transformations
O=.agents/scratch/ast-transformations
clang++-18 -std=c++17 -O2 "$R/fixture.cpp" -o "$O/original2"
clang++-18 -std=c++17 -O2 -I"$R" "$O/generated.cpp" "$R/storage.cpp" -o "$O/transformed2"
"$O/original2" > "$O/original2.out"
"$O/transformed2" > "$O/transformed2.out" 2> "$O/events2.txt"
if diff -u "$O/original2.out" "$O/transformed2.out" > "$O/optimized.diff"; then
 echo 'O2 stdout equal on this invocation (not a guarantee)'
else
 echo 'O2 MISMATCH: see optimized.diff; optimization is outside supported subset'
fi
