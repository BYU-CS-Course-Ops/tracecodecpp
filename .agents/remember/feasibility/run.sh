#!/bin/sh
set -eu
mkdir -p .agents/scratch/feasibility
rm -f .agents/scratch/feasibility/trace.json
clang++-18 -std=c++17 -g -O0 -fno-omit-frame-pointer \
  .agents/remember/feasibility/student.cpp .agents/remember/feasibility/allocations.cpp \
  -o .agents/scratch/feasibility/student
lldb-18 --batch \
  -o "script import sys; sys.argv=['record.py', '/work/.agents/remember/feasibility/student.cpp', '/work/.agents/scratch/feasibility/student', '/work/.agents/scratch/feasibility/trace.json']" \
  -o "script exec(compile(open('.agents/remember/feasibility/record.py').read(), 'record.py', 'exec'))"
# LLDB may report Python exceptions without a nonzero CLI exit code.
python3 .agents/remember/feasibility/validate.py .agents/scratch/feasibility/trace.json
