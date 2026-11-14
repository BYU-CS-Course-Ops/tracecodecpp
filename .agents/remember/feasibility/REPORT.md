# Phase A feasibility results

## Conclusion

**The basic memory-first architecture is feasible on Linux ARM64 under Docker Desktop.** Matching Clang/LLDB 18 can capture nested student frames, reference aliases, actual object/member addresses, pointer values, and allocation history. A tiny linked allocation shim plus debugger breakpoints provided enough evidence to associate typed pointer views with live blocks. This is a feasibility prototype, not a complete recorder or production schema.

One significant toolchain caveat: **standalone `python3` importing these LLDB bindings aborts**. Running the same driver inside LLDB's embedded Python works. Do not assume the standalone-Python driver proposed in the brief works with this package combination.

## Image and reproducibility

- Root `Dockerfile`; built/tagged **`tracecpp:llvm18`**.
- Ubuntu 24.04 base pinned to digest `sha256:2198e4c65076e9cb0b3d695219df667c0e3b0072da64ca3c2648aca17dcecaf5`.
- Clang, LLVM, LLDB and Python bindings all pinned to `1:18.1.3-1ubuntu1`.
- Python 3.12.3; native `aarch64-unknown-linux-gnu`; 8-byte pointers.
- Image ID at test: `sha256:22b5427abbcdd0395258df2a8f005088d5613d2f65e5924dc2d1a283759e026d`; approximately 717 MB uncompressed.
- Base and primary toolchain packages are pinned, but transitive OS packages are not snapshot-pinned. This is not yet a fully bit-reproducible package closure.
- Tested only ARM64, not x86-64 or other Docker runtimes.

Build without sending the repository/private files as build context:

```sh
docker build -t tracecpp:llvm18 - < Dockerfile
docker run --rm -v "$PWD:/work" tracecpp:llvm18 sh .agents/remember/feasibility/run.sh
python3 .agents/remember/feasibility/validate.py .agents/scratch/feasibility/trace.json
```

The final command runs outside Docker and has no LLDB dependency.

## Observations and checks

The fixture contains nested `main -> outer -> inner` calls, reference parameters, pointers, a stack array, two linked `Node` objects, a four-element dynamic integer array, an interior pointer mutation, and an opaque `std::vector<int>`.

The recording contains **28 snapshots, eight allocation/deallocation hook events, and three tracked student blocks**. The program exited with status 0. Two complete recording runs passed validation. The recorded stop/capture loop took approximately 0.05 seconds on this tiny fixture; that excludes build, process launch and container overhead and is not a meaningful performance benchmark. The formatted JSON is approximately 196 KiB.

| Question | Experiment result |
|---|---|
| Source stepping | LLDB `thread step-in` moved from initialization on line 11 to line 12. The recorder itself uses student-line breakpoints plus allocation-hook breakpoints, avoiding stepping through STL. |
| References | `main::x`, `outer::ref`, and `inner::alias` had the same address and observed value. The serializer uses `Dereference().GetLoadAddress()` for references. |
| Pointer storage | `inner::pointer` had its own address, distinct from `x`, while its stored target equaled the address of `x`. |
| Stack arrays | LLDB exposed all three integer elements at four-byte strides with values 1, 2, 3. |
| Struct layout | `Node` occupied 16 bytes; `value` was at offset 0 and `next` at offset 8. Offsets came from observed addresses, not a hardcoded serializer layout. |
| Allocation tracking | Linked ordinary `new`/`new[]` replacements recorded two 16-byte node allocations and a 16-byte integer-array allocation. |
| Interior pointers | `array + 2` matched offset 8 within the tracked array allocation; typed dereference observed the mutation to 30. |
| Typed heap reads | LLDB exposed node fields through pointers, and `ReadMemory` captured bytes of each live tracked block while stopped. |
| STL filtering | The vector's 64-byte allocation was observed by the shim but excluded from the student block inventory based on its immediate allocation caller. Its stack value remained opaque. |
| Deletion | All three student blocks became non-live. Later snapshots retained their historical identity/address but did not read or expose their freed bytes. |
| Portable history | Host Python loaded the JSON, validated memory relationships, and accessed the ordered snapshots in both directions. No browser viewer was built. |

Example from the latest validated run: `x` and both reference parameters used `0xffffd404ca38`, while the pointer parameter's own storage was `0xffffd404c970`. These are illustrative observations from one run, not stable expected addresses. ASLR remains enabled.

## Environment issues discovered

1. Docker's disk was full. APT misleadingly reported invalid repository signatures. With user approval, unused build cache and then unused images were pruned. This freed sufficient space; containers and volumes were preserved.
2. Ubuntu's versioned `_lldb` extension symlink pointed to `/usr/lib/llvm-18/lib/liblldb.so`, which the installed package set did not supply. The Dockerfile supplies a link to the installed `liblldb.so.1` and smoke-tests embedded Python.
3. After repairing the link, standalone Python import aborted with `PyImport_AppendInittab() may not be called after Py_Initialize()`. The working invocation is `lldb-18 --batch` with its embedded Python interpreter. The prototype uses the LLDB Python API there.
4. No `SYS_PTRACE` capability or unconfined seccomp setting was necessary on this Docker Desktop setup when launching a child and leaving ASLR enabled. This is an observation, not a portability guarantee. This development image is not an untrusted-code sandbox.

## Important limits exposed by the spike

- **Debugger-visible does not mean initialized.** LLDB returned values for locals before their initializer ran. All observations are labeled `initialization: unknown`; a real viewer must not present those values as trustworthy initialized C++ values. Tracking initialization requires additional evidence or deliberately restricted display rules.
- **Allocation is storage, not a constructed object.** The allocation hook stops after `malloc` but before `new` initialization. Typed pointer expansion is explicitly named `pointee_candidate`; its static type does not establish lifetime or dynamic type.
- **Deallocation hooks currently stop before `free`.** The registry conservatively removes the block from display at the deallocation request and labels the timing. It does not claim that the underlying allocator has already completed the free at that stop.
- **Attribution is only a narrow proof of concept.** Direct student `new` versus this vector's allocator is distinguishable from the call stack. The immediate-caller heuristic is not validated for custom allocators, forwarding helpers, custom class allocators, stripped libraries, or indirect library paths.
- **Array length is not solved by an `int*`.** The registry proves a 16-byte block; LLDB proves the pointer's static pointee type. Four `int` slots can be suggested from size here, but that alone does not prove the number of constructed objects. This recorder displays the pointed-to element and raw block bytes, not an asserted full typed dynamic array.
- **Line stops are pre-execution and incomplete.** Each stop means the next statement has not necessarily run. Multiple operations on one line and intermediate constructor mutations may not be seen. The allocation hook does expose intermediate storage states, which need careful labeling.
- Shim coverage is limited to ordinary throwing scalar/array new and unsized/sized delete. Aligned/nothrow forms, C allocation APIs, placement new, constructors/destructors, array cookies, and address reuse need separate experiments. The shim also does not fully reproduce standard `new_handler` behavior.
- No crash/undefined-behavior fixtures, local-reference variants, custom vector/BST/map fixtures, globals, thread support, trace limits beyond a small stop cap, or production viewer were implemented.

## Recommendation

Keep LLDB plus targeted allocation tracking as the working direction. Use LLDB-hosted Python for this image rather than blocking on standalone import. Before a production schema/viewer, resolve initialization visibility, explicit before/after stop semantics, attribution through student allocators, and the metadata needed to distinguish allocation extent from typed array/object lifetime.

## Files

- `Dockerfile`: development toolchain image.
- `.agents/remember/feasibility/student.cpp`: instructional fixture.
- `.agents/remember/feasibility/allocations.cpp`: narrow linked allocation shim.
- `.agents/remember/feasibility/record.py`: LLDB-hosted recorder.
- `.agents/remember/feasibility/validate.py`: dependency-free portable trace assertions.
- `.agents/remember/feasibility/run.sh`: compile, record and validate.
- `.agents/scratch/feasibility/`: generated executable, JSON, build/run logs and stepping log. Not intended as committed source.
