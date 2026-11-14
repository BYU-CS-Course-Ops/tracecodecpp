#!/bin/bash
# Run inside /work repository mount. MODE=standalone|embedded LLVM=14|18 LABEL=...
set -eu
LLVM=${LLVM:-14}; MODE=${MODE:-standalone}; LABEL=${LABEL:-arm64-llvm14}
OUT=/work/.agents/scratch/toolchain-reliability/$LABEL-$MODE
mkdir -p "$OUT"
exec > >(tee "$OUT/probe.log") 2>&1
ulimit -c 0
uname -a
cat /etc/os-release
python3 --version
clang++-$LLVM --version
lldb-$LLVM --version
dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > "$OUT/packages.tsv"
ls -l /usr/lib/llvm-$LLVM/lib/python*/dist-packages/lldb/_lldb* /usr/lib/llvm-$LLVM/lib/python*/site-packages/lldb/_lldb* 2>/dev/null || true
grep -E 'Cap(Eff|Bnd)|Seccomp' /proc/self/status
cat /proc/sys/kernel/yama/ptrace_scope || true
python3 -u -c 'import lldb; print(lldb.__file__); print(lldb.SBDebugger.GetVersionString()); lldb.SBDebugger.Initialize(); d=lldb.SBDebugger.Create(); print("debugger valid:", d.IsValid()); lldb.SBDebugger.Destroy(d); lldb.SBDebugger.Terminate()' && IMPORT_RC=0 || IMPORT_RC=$?
echo "standalone import/API exit: $IMPORT_RC"
SRC=/work/.agents/remember/feasibility
clang++-$LLVM -std=c++17 -g -O0 -fno-omit-frame-pointer "$SRC/student.cpp" "$SRC/allocations.cpp" -o "$OUT/student"
rm -f "$OUT/trace.json"
if [ "$MODE" = standalone ]; then
  python3 -u /work/.agents/remember/toolchain-reliability/standalone.py "$SRC/student.cpp" "$OUT/student" "$OUT/trace.json"
else
  lldb-$LLVM --batch \
    -o "script import sys; sys.argv=['record.py', '$SRC/student.cpp', '$OUT/student', '$OUT/trace.json']" \
    -o "script exec(compile(open('$SRC/record.py').read(), 'record.py', 'exec'))"
fi
python3 "$SRC/validate.py" "$OUT/trace.json"
