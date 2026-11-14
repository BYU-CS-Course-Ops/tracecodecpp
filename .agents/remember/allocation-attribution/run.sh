#!/bin/sh
set -eu
base=.agents/remember/allocation-attribution
out=.agents/scratch/allocation-attribution
mkdir -p "$out"
clang++-18 -std=c++17 -g -O0 -fno-omit-frame-pointer "$base/student.cpp" "$base/allocations.cpp" -o "$out/student"
rm -f "$out/trace.json"
lldb-18 --batch \
 -o "script import sys; sys.argv=['record.py', '/work/$out/trace.json']" \
 -o "script exec(compile(open('$base/record.py').read(), 'record.py', 'exec'))"
python3 "$base/validate.py" "$out/trace.json"
