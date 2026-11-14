# Toolchain reliability feasibility spike

## Decision

**Retain Ubuntu 24.04 / LLVM 18 with LLDB-embedded Python as the current baseline.** A small distribution-matched alternative **does support standalone Python on native ARM64**: Ubuntu 22.04.5 / LLVM 14.0.0 / Python 3.10.12, after repairing the Python extension link and specifying the debug server path. Keep this as a demonstrated fallback, not an automatic downgrade: it offers no additional memory-tracing capability in this fixture, uses an older baseline, and still needs packaging repairs. If a standalone recorder becomes a hard integration requirement, this is a viable candidate pending native x86 CI and broader feature tests.

**No native x86-64 tracing was validated.** The amd64 image builds and imports the API under Rosetta; normal program execution succeeds, but debugger launch fails. That is an emulated-debugger compatibility limit in this experiment, not evidence that the native x86 toolchain is broken.

## Scope and environment

Read project brief, root Dockerfile, feasibility report and unmodified recorder/run script; reused the original student fixture, allocation shim, recorder and validator read-only. All new files are confined to `.agents/remember/toolchain-reliability/` and `.agents/scratch/toolchain-reliability/`. No root Dockerfile/prototype changes, commits, pruning, or image deletion. Only one alternative OS/toolchain combination was built, for two architectures.

Host: macOS ARM64; Docker Desktop daemon reports aarch64. Containers use Linux `7.0.12-linuxkit`. amd64 `/proc/self/maps` explicitly contains `/run/rosetta/rosetta`; `uname -m` inside that container says x86_64, which is **not** proof of native execution. Both target architectures have 8-byte pointers (ARM64 established by traces; amd64 executable/API target inspected, not a completed trace).

## Package versions and images

| Component | Alternative ARM64 and amd64 | Existing ARM64 baseline |
|---|---|---|
| Distribution | Ubuntu 22.04.5 LTS | Ubuntu 24.04.5 LTS |
| clang, lldb, python3-lldb, liblldb | `1:14.0.0-1ubuntu1.1` | `1:18.1.3-1ubuntu1` |
| Runtime Python | 3.10.12 | 3.12.3 |
| python3 interpreter package | `python3.10=3.10.12-1~22.04.18` | `python3.12=3.12.3-1ubuntu0.17` |
| python3 metapackage | `3.10.6-1~22.04.1` | `3.12.3-0ubuntu2.1` |
| libc6 | `2.35-0ubuntu3.18` | `2.39-0ubuntu8.12` |
| C++ development library | `libstdc++-11-dev=11.4.0-1ubuntu1~22.04.3` | existing image unchanged |

Alternative `llvm-14` is also `1:14.0.0-1ubuntu1.1`; `libpython3.10` is `3.10.12-1~22.04.18`. Full architecture-specific installed package manifests are retained as `packages.tsv` alongside each probe log in scratch. These distinguish the metapackage version from the actual interpreter version.

Image tags and final IDs:

- `tracecpp:reliability-llvm14-arm64-4gz`: `sha256:ffa4727fd98d9a065ad1cfe659c6eb7f36140799b834e1e038b5f6fca7ec8276` (~907 MB).
- `tracecpp:reliability-llvm14-amd64-4gz`: `sha256:5141118dc2ba8931b597962d4432bb6faddf7a08ce8c0534b7d741a47876ab35` (~983 MB).
- Existing `tracecpp:llvm18`: `sha256:22b5427abbcdd0395258df2a8f005088d5613d2f65e5924dc2d1a283759e026d` (~717 MB).

Alternative builds use official `ubuntu:22.04` and pin the three requested LLVM packages. Base tag and transitive dependencies are **not snapshot/digest pinned**; this is a reproducible procedure with recorded installed versions, not a bit-reproducible closure. Build logs and `images.json` retain resolved build/image metadata. Initial failed package-link experiments are described below; final Dockerfile contains the working setup.

## Bindings and launch setup

The first unmodified Jammy package test failed at import: `_lldb.cpython-310-<arch>-linux-gnu.so` links via `../../../../../lib/liblldb.so`, resolving incorrectly to `/usr/lib/lib/liblldb.so`. Merely adding `/usr/lib/llvm-14/lib/liblldb.so` did not fix that different path. The final alternative Dockerfile replaces the extension link with `../../../liblldb.so.1`, targeting the matching installed LLVM library. This works on both architectures without guessing a multiarch directory.

Set:

```sh
PYTHONPATH=/usr/lib/llvm-14/lib/python3.10/dist-packages
LLDB_DEBUGSERVER_PATH=/usr/lib/llvm-14/bin/lldb-server
```

`lldb-14 -P` misleadingly reports `/usr/lib/local/lib/python3.10/dist-packages`; use the installed package directory above. Without `LLDB_DEBUGSERVER_PATH`, standalone import and debugger creation succeeded, but launch failed with `unable to locate lldb-server-14.0.0`. The CLI knows its own bin directory; standalone Python needs an explicit path here. `standalone.py` initializes the debugger subsystem, runs the original recorder via `runpy`, and terminates it afterwards. No recorder changes were necessary.

Existing LLVM18 import failure was reproduced: standalone `import lldb` aborts with `PyImport_AppendInittab() may not be called after Py_Initialize()` (exit 134). Its embedded Python still records successfully. That failure is distinct from a missing shared-library link and distinct from inferior launch/ptrace failure.

## Results

| Guest and driver | Import / debugger creation | Fixture trace |
|---|---|---|
| Native ARM64 Jammy LLVM14, standalone | PASS | PASS; two successful standalone runs during setup/final verification |
| Native ARM64 Jammy LLVM14, embedded | PASS | PASS |
| Native ARM64 Noble LLVM18, standalone | ABORT 134 at import | Not attempted past import |
| Native ARM64 Noble LLVM18, embedded | PASS | PASS; baseline regression check |
| Emulated amd64 Jammy LLVM14, standalone | PASS | Launch fails: `'A' packet returned an error: -1` |
| Emulated amd64 Jammy LLVM14, standalone + debugger permissions | PASS | Same launch failure |
| Emulated amd64 Jammy LLVM14, CLI + debugger permissions | CLI starts, target identified x86_64 | Same launch failure |

Each successful trace: **28 snapshots, eight allocation events, three student blocks, inferior exit 0**. The original dependency-free validator passes reference alias equality across frames, pointer storage distinct from referent, stack array values/strides, `Node` field offsets 0 and 8, interior-pointer mutation, allocation/STL filtering, deletion and historical indexing. Full JSON artifacts remain in scratch. These are the existing narrow fixture's checks, not new coverage of arbitrary allocations, lifetimes, optimization, threads, or undefined behavior. No timing conclusions are drawn from these tiny runs.

### Permissions and emulation diagnosis

Native successful runs used Docker defaults: root in container, capability mask `00000000a80425fb`, seccomp mode 2, **no added SYS_PTRACE**, no unconfined seccomp, no privileged mode. The recorder leaves ASLR enabled. `/proc/sys/kernel/yama/ptrace_scope` is absent on this kernel. This demonstrates child-launch permissions only on this Docker Desktop setup, not general attach permission or a safe sandbox.

For amd64, retrying with `--cap-add=SYS_PTRACE --security-opt seccomp=unconfined` changed capability mask to `00000000a80c25fb` and seccomp to 0 but did not fix launch. Both standalone and CLI fail, while compilation and direct fixture execution succeed (exit 0). The debug-server log records the inferior initially stopped, then **`detected architecture unknown`**. Rosetta is independently visible in mappings.

A minimal fork/`PTRACE_TRACEME`/stop/`PTRACE_GETREGSET(NT_PRSTATUS)` probe succeeds on both guest architectures, even with default permissions. Importantly, the amd64 guest returns **272 bytes**, the same register-set length as ARM64, not the usual x86-64 general-register set (216 bytes). Thus it would be inaccurate to claim that every ptrace syscall is denied or returns ENOSYS. Available evidence points to **emulated process/register/architecture handling**, not ordinary Docker seccomp denial or the standalone binding problem. Exact Rosetta/LLDB failure internals are not proven; native amd64 Linux is required to judge native toolchain reliability. No amd64 stack/reference/allocation trace was produced.

## Reproduction and retained evidence

From repository root:

```sh
# Bounded to one alternative combination, two architectures; preserves images.
bash .agents/remember/toolchain-reliability/reproduce.sh
```

This rebuilds the alternative images with empty stdin build contexts, probes standalone and embedded modes, retries amd64 with debugger permissions, reruns the existing ARM64 baseline, and runs the ptrace probes. Uses 45-second probe deadlines and 10-second ptrace deadlines. Build network/APT availability is still required. `probe.sh` validates generated JSON because LLDB CLI can return success despite Python exceptions. The combined reproduction script is retained for convenience; individual component builds/probes described here were executed, not the entire combined wrapper.

Sources here:

- `Dockerfile.llvm14`: final dual-architecture alternative.
- `probe.sh`, `standalone.py`: package/API/compile/trace/validation checks; configurable `LLVM`, `MODE`, `LABEL`.
- `ptrace_probe.py`: direct syscall diagnostic with child cleanup.
- `server-log.sh`: optional executable wrapper for `LLDB_DEBUGSERVER_PATH`; logs `posix all` to scratch. Tested on amd64 with broad debugger permissions.
- `reproduce.sh`: commands to repeat core experiments.

Evidence under `.agents/scratch/toolchain-reliability/`:

- `build-{arm64,amd64}.log`, `images.json`, `input-sha256.txt`.
- `arm64-llvm14-{standalone,embedded}/`: `probe.log`, full package manifest, executable, validated `trace.json`.
- `arm64-llvm18-embedded/`: same artifacts for baseline, including reproduced standalone abort output.
- `amd64-llvm14-standalone/`, `amd64-debug-llvm14-standalone/`: import success, package manifests and launch failure logs; no trace JSON.
- `ptrace-matrix.log`, `emulator.log`, `amd64-diagnostics.log`, `amd64-lldb.log`, `server-diagnostic.log`, `server-amd64.log`.

## Follow-up before changing baseline

Run this same fixture on **native amd64 Linux** CI for both the existing embedded driver and any proposed standalone baseline. Add import, debugger creation, inferior launch and JSON validation as separate smoke gates: an import-only test misses server lookup and process-control failures. For now retain the working LLVM18 embedded path; do not downgrade globally or claim cross-architecture tracing reliability from the successful emulated import alone.
