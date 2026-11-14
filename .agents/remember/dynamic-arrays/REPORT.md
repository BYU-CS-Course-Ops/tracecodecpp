# Dynamic-array type and length feasibility spike

## Conclusion

**Dynamic arrays are feasible with explicit allocation-expression metadata joined to allocation storage events and LLDB types. Pointer debug metadata plus allocation bytes alone is insufficient to assert an array's requested length, initialization, or constructed prefix.** Manual hooks demonstrated the join, including zero-length arrays and constructor failure. No automated AST instrumentation was implemented or validated.

Scope: isolated files under `.agents/remember/dynamic-arrays/` and generated files under `.agents/scratch/dynamic-arrays/`. Read the project brief, previous feasibility report, allocation shim, recorder and runner. The root Dockerfile and shared prototype were not changed. No pruning or commits.

## Reproduce and actual test results

From repository root:

```sh
docker image inspect tracecpp:llvm18 --format '{{.Id}} {{.Architecture}}'
docker run --rm -v "$PWD:/work" -w /work tracecpp:llvm18 \
  sh .agents/remember/dynamic-arrays/run.sh \
  > .agents/scratch/dynamic-arrays/run.log 2>&1
python3 .agents/remember/dynamic-arrays/validate.py \
  .agents/scratch/dynamic-arrays/trace-3.json \
  .agents/scratch/dynamic-arrays/trace-5.json
```

Image: `sha256:22b5427abbcdd0395258df2a8f005088d5613d2f65e5924dc2d1a283759e026d`, ARM64, Clang/LLDB 18.1.3, Linux AArch64, 8-byte pointers. LLDB runs its embedded Python; no standalone binding import, added ptrace capabilities or seccomp override was needed here. The executable is compiled with `-std=c++17 -g -O0 -fno-omit-frame-pointer`. ASLR remains enabled.

Final full run and host-side independent validation passed:

```
Recorded 49 events for n = 3
PASS .../trace-3.json events= 49 n= 3 throw bytes= 24
Recorded 53 events for n = 5
PASS .../trace-5.json events= 53 n= 5 throw bytes= 32
```

Both inferiors exited 0. An earlier driver iteration recorded LLDB's `::request` spelling without normalizing the leading `::`; validation failed rather than accepting an empty test. Normalization was fixed and both cases rerun. The final runner removes old JSON before launching and validates separately because LLDB's batch exit code need not propagate a Python exception.

Runner also executes:

```sh
clang++-18 -std=c++17 -Xclang -ast-dump -fsyntax-only \
  .agents/remember/dynamic-arrays/student.cpp > .agents/scratch/dynamic-arrays/ast.txt
llvm-dwarfdump-18 --debug-info .agents/scratch/dynamic-arrays/student \
  > .agents/scratch/dynamic-arrays/dwarf.txt
```

These commands succeeded. Dumps are evidence for this compiler/fixture, not a compiler plugin.

## Fixtures and measurements

`n` comes from the executable's command line, not a constant array type. Each run covers eight requests; each allocation has an allocation-hook event and eventual delete event, including automatic cleanup on failure. The copied narrow allocation shim delegates to malloc and reports **operator new[]'s requested byte size**, not malloc's potentially larger usable chunk size.

| Expression | Element size | new[] bytes, n=3 / n=5 | Returned pointer minus storage base | Observed semantics |
|---|---:|---:|---:|---|
| `new int[n]` | 4 | 12 / 20 | 0 | Default initialization leaves scalar values indeterminate |
| `new int[n]()` | 4 | 12 / 20 | 0 | All elements zero after expression completion |
| `new int[n]{7}` | 4 | 12 / 20 | 0 | First 7, remainder zero; index 1 later changed to 99 |
| `new Plain[n]` | 16 | 48 / 80 | 0 | Trivial class, `int x; double y;`; members indeterminate |
| `new Obj[n]` | 4 | 20 / 28 | 8 | User constructor writes IDs; nontrivial destructor |
| `new Obj[0]` | 4 | 8 / 8 | 8 | No constructor/destructor calls; pointer is at storage end |
| `new int[0]` | 4 | 0 / 0 | 0 | Non-null return here; shim physically mallocs at least one byte |
| `new Throw[n+1]` | 4 | 24 / 32 | No successful expression result | Cookie prefix 8; third constructor throws |

No claim is made that these sizes or prefixes apply to other ABIs, aligned types, custom allocators or compiler settings.

### What LLDB and DWARF establish

At explicit post-expression checkpoints, LLDB reports `int *`, `Plain *`, `Obj *`, their pointer values/storage addresses and 8-byte pointer size. `IsArrayType()` is false for these dynamic pointers, including `interior` and `one_past`. `Plain` has fields `x:int` at offset 0 and `y:double` at offset 8, size 16; `Obj` has `id:int` at offset 0, size 4. These layouts come from `SBType`, not guessed offsets.

The control stack variable `fixed` is `int[3]`, 12 bytes, with three children. DWARF contains its array type/subrange `DW_AT_count (0x03)`. In contrast, `uninit`, `list` and `objects` reference pointer types; their variable entries have **no dynamic bound relationship to `n`**. `n` is independently visible as a local, which is not proof it is the allocation's original count. The first driver iteration also observed pointer child counts of 1 for int*/Obj* and 2 for Plain*: debugger child counts describe expansion, not allocated element counts.

The driver explicitly creates `SBType.GetArrayType(n)` views at the successful arrays' returned addresses. LLDB then reads `[7,0,...]`, later `[7,99,...]`, and Obj IDs `[0,...,n-1]`; validation checks all elements. **Here the driver supplies the bound. LLDB does not discover it.** This shows typed expansion once trustworthy bounds are available, not automatic heap-array inference.

### Initialization evidence is separate

In the n=3 run both the uninitialized int array and value-initialized array had identical all-zero raw bytes. Plain's bytes also happened to be zero. The inferior does not evaluate indeterminate member/scalar values. The debugger records raw storage only, and the validator deliberately does not assert values for uninitialized arrays. Zero bytes/debugger read success cannot distinguish initialization histories. The known zero/list initialization facts come from the source expression plus successful completion; arbitrary user constructors do not establish that every member or padding byte was initialized.

### Interior, one-past and empty pointers

`interior = list + 1` is exactly 4 bytes past the returned element base, and `one_past = list + n` is `4*n` past it, in both runs. LLDB still calls both `int *`. The interior mutation is verified through the explicitly bounded array view. One-past is never dereferenced.

Empty Obj arrays expose a crucial edge case: their returned pointer equals the end of the 8-byte cookie-containing storage, so a strict half-open storage containment check will not associate it. Empty int arrays have zero requested storage extent. Preserve explicit expression-result-to-allocation identity; do not invent a slot from malloc's minimum chunk or use inclusive containment as a general pointer-validity rule. This driver's inclusive address matching is a fixture-only convenience for those empty results, not a safe production resolver.

### Cookies and throwing/partial construction

For Obj and Throw, the first 8 bytes decode little-endian to the requested count. Ordinary int/Plain arrays have no observed prefix. `operator delete[]` receives the allocation **storage base**, 8 bytes before the Obj element pointer. Validators check both the delete address and cookie bytes.

Throw requests 4 or 6 elements. Constructor-body entry events occur for IDs 0,1,2; successful body-end hooks occur only for 0,1. ID 2 throws integer 42. Destructors then run for IDs 1,0, followed by `operator delete[]` on storage base, followed by the catch/failure hook. There is no successful array-result hook and no destructor for failed element 2. During all these constructor/destructor stops the cookie still holds 4 or 6, **not the number of successfully constructed or currently live elements**. Byte extent divided by sizeof(Throw) gives 6 or 8, neither the requested count nor completed prefix.

Obj successful arrays construct IDs in ascending order and destroy them in reverse. Empty Obj arrays produce no lifetime events. These are verified fixture-specific hook observations; constructor-body end is not a general language-level completion probe, and destructor-body entry is not complete storage deallocation.

## Hook feasibility versus automated instrumentation

Manual `request(site,type,count,stride,init)` runs immediately before the new expression; `complete(site,pointer)` runs only after it succeeds; a manually placed catch records failure. The two runtime lengths demonstrate that this metadata can carry evaluated runtime counts rather than static guesses. `init` codes here are 0=default, 1=value, 2=list, 3=user-constructor case, an illustrative classification rather than a schema.

The compiler AST dump exposes `CXXNewExpr`, array status, result type, bound expression (`n`, `n+1`, or zero), and initialization nodes (`ImplicitValueInitExpr`, `InitListExpr`, `CXXConstructExpr`). This supports pursuing a small AST instrumentation prototype. **No rewriter, LibTooling pass, side-effect-preserving expression wrapper, or automatic exception hook was built.** The fixture repeats side-effect-free `n`; copying that pattern to `new T[f()]` or `new T[n++]` would be wrong. AST visibility alone does not demonstrate semantic preservation.

## Required metadata and design recommendations

1. **Keep storage and array/object identities separate.** Allocation ID/generation, storage base, requested storage bytes, allocation/deallocation API and stop timing belong to the registry. Returned element pointer, stable source site/type identity, evaluated requested count, element stride/alignment and initialization form belong to a separate expression event. Join explicitly, not only by range or type-name strings.
2. **Record request, success and failure separately.** Allocation hooks fire before initialization; a successful expression establishes a fully constructed array (but not initialized scalar members for arbitrary classes). Failure must not leave a live array or lose automatic cleanup. Production correlation needs per-thread/nested expression tokens; this tiny sequential fixture has no allocations inside constructors.
3. **Use AST-derived bounds when implemented; do not decode cookies as the primary source.** Record evaluated bounds exactly once while preserving expression ordering, exceptions, overload resolution and placement/aligned/nothrow semantics. Validate this in a follow-up limited to ordinary new[] before claiming automatic support. Multidimensional arrays need outer count plus inner type extents.
4. **Until then, honest fallback:** show storage extent with static pointee candidates and uncertainty labels. At most suggest byte-capacity-derived slots when assumptions are explicit; do not label them requested/constructed elements. Cookies are ABI-specific corroboration and requested counts, not per-element lifetime counters.
5. **Use LLDB for layouts and bounded typed reads.** Expand only inside proven element ranges at stopped successful states. Exclude cookie/padding bytes from student elements. Render one-past/empty results explicitly and do not dereference them; retain allocation identity across address reuse and historical deletion.
6. **Initialization and lifetime require separate provenance.** Preserve raw observations independently of semantic initialization state. Full per-element constructor/destructor/throwing-prefix fidelity needs additional compiler/runtime instrumentation; constructor entry, line stepping and cookies are insufficient. For an initial viewer, collapse intermediate construction to “construction in progress / lifetime unknown” unless supported by stronger events.

## Limits and retained files

Only this ARM64 image, C++17, O0, ordinary throwing global new[] and these small single-threaded fixtures were tested. No sanitizer, optimized run, x86-64, aligned/nothrow/placement/class-specific allocation, overflow/negative bound, allocation failure, multidimensional array, nested allocating constructor, allocator elision or address-reuse test. The copied shim does not fully implement standard new-handler semantics; exception runtime internal malloc allocations are outside its inventory. Allocation deletes mark a block non-live at the pre-free hook. No freed storage is read; final checkpoints inspect pointer/type metadata only. Hook-only stops deliberately avoid claims about complete line-by-line state.

Retained reproducible sources: `student.cpp`, `allocations.cpp`, `record.py`, `validate.py`, `run.sh`, and this report in `.agents/remember/dynamic-arrays/`. Generated binary, two portable JSON recordings, `run.log`, AST and DWARF dumps are in `.agents/scratch/dynamic-arrays/`. No production schema or viewer was changed.
