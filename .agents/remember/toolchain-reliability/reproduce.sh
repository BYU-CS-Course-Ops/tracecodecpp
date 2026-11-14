#!/bin/bash
# Run from repository root. Builds only two uniquely tagged images; no cleanup/prune.
set -eu
HERE=.agents/remember/toolchain-reliability
OUT=.agents/scratch/toolchain-reliability
mkdir -p "$OUT"
for arch in arm64 amd64; do
  docker build --platform linux/$arch -t tracecpp:reliability-llvm14-$arch-4gz - < "$HERE/Dockerfile.llvm14" > "$OUT/build-$arch.log" 2>&1
  for mode in standalone embedded; do
    # Nonzero is expected for debugger launch on this host's amd64 emulation.
    docker run --rm --platform linux/$arch -e MODE=$mode -e LABEL=$arch-llvm14 -v "$PWD:/work" tracecpp:reliability-llvm14-$arch-4gz timeout 45 bash "$HERE/probe.sh" && rc=0 || rc=$?
    echo "$arch $mode exit=$rc"
  done
done
docker run --rm --platform linux/amd64 --cap-add=SYS_PTRACE --security-opt seccomp=unconfined -e LABEL=amd64-debug-llvm14 -v "$PWD:/work" tracecpp:reliability-llvm14-amd64-4gz timeout 45 bash "$HERE/probe.sh" && rc=0 || rc=$?
echo "amd64 debugger permissions exit=$rc"
docker run --rm -e LLVM=18 -e MODE=embedded -e LABEL=arm64-llvm18 -v "$PWD:/work" tracecpp:llvm18 timeout 45 bash "$HERE/probe.sh"
for arch in arm64 amd64; do
  for perm in default debug; do
    flags=()
    if [ "$perm" = debug ]; then flags=(--cap-add=SYS_PTRACE --security-opt seccomp=unconfined); fi
    echo "$arch $perm"
    docker run --rm --platform linux/$arch "${flags[@]}" -v "$PWD:/work" tracecpp:reliability-llvm14-$arch-4gz timeout 10 python3 "$HERE/ptrace_probe.py"
  done
done
