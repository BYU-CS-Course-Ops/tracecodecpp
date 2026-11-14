#!/bin/sh
set -eu
cd /work
R=.agents/remember/ast-transformations
O=.agents/scratch/ast-transformations
mkdir -p "$O"
clang++-18 --version > "$O/toolchain.txt"
python3 "$R/transform.py" "$R/fixture.cpp" "$O/generated.cpp"
for opt in 0; do
 clang++-18 -std=c++17 -g -O$opt "$R/fixture.cpp" -o "$O/original$opt"
 clang++-18 -std=c++17 -g -O$opt -I"$R" "$O/generated.cpp" "$R/storage.cpp" -o "$O/transformed$opt"
 "$O/original$opt" > "$O/original$opt.out"
 "$O/transformed$opt" > "$O/transformed$opt.out" 2> "$O/events$opt.txt"
 diff -u "$O/original$opt.out" "$O/transformed$opt.out"
done
python3 "$R/transform.py" "$R/sequencing.cpp" "$O/sequencing.generated.cpp"
clang++-18 -std=c++17 -g -O0 "$R/sequencing.cpp" -o "$O/sequence-original"
clang++-18 -std=c++17 -g -O0 -I"$R" "$O/sequencing.generated.cpp" "$R/storage.cpp" -o "$O/sequence-transformed"
"$O/sequence-original" > "$O/sequence-original.out"
"$O/sequence-transformed" > "$O/sequence-transformed.out" 2> "$O/sequence-events.txt"
diff -u "$O/sequence-original.out" "$O/sequence-transformed.out"
python3 "$R/validate.py"
