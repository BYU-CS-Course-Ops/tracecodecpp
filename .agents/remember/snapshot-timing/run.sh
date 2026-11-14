#!/bin/sh
set -eu
base=.agents/remember/snapshot-timing
out=.agents/scratch/snapshot-timing
mkdir -p "$out"
clang++-18 -std=c++17 -g -O0 -fno-omit-frame-pointer "$base/student.cpp" -o "$out/student"
for mode in lines step hybrid; do
  rm -f "$out/$mode.json"
  lldb-18 --batch -o "script import sys; sys.argv=['record.py','/work/$base/student.cpp','/work/$out/student','$mode','/work/$out/$mode.json']" -o "script exec(compile(open('$base/record.py').read(), 'record.py', 'exec'))"
done
python3 "$base/validate.py"
