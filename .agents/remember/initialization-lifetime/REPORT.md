# Initialization and object-lifetime feasibility spike

## Result

**LLDB remains useful for stopped-process layout and byte observation, but its ordinary SBValue/DWARF view does not establish initialization or object lifetime in these fixtures. Small manually placed source hooks supply missing event evidence. An automated Clang AST instrumenter has NOT been implemented or validated.** Keep unknowns in the initial product rather than claiming complete initialization/lifetime coverage.

This is an isolated experiment, not a production recorder. Read the project brief, prior feasibility report, and existing recorder/run script before implementing it. The root Dockerfile and shared feasibility prototype were not edited. No Docker resources were pruned and no commits were made.

## Reproduce

From repository root:

```sh
docker image inspect tracecpp:llvm18 --format '{{.Id}} {{.Architecture}}'
docker run --rm -v "$PWD:/work" tracecpp:llvm18 \
  sh .agents/remember/initialization-lifetime/run.sh
python3 .agents/remember/initialization-lifetime/validate.py \
  .agents/scratch/initialization-lifetime/default.json \
  .agents/scratch/initialization-lifetime/pattern.json
```

Image tested: `sha256:22b5427abbcdd0395258df2a8f005088d5613d2f65e5924dc2d1a283759e026d`, ARM64. Clang/LLDB 18.1.3, `aarch64-unknown-linux-gnu`, C++17, `-g -O0 -fno-omit-frame-pointer`. No added capabilities/seccomp overrides were needed here. ASLR remains enabled. Python runs **inside `lldb-18 --batch`**, not via standalone LLDB import.

The script compiles default and `-ftrivial-auto-var-init=pattern` variants, records 27 event stops in each, asserts exact event order and selected relationships/bytes, and dumps the AST with `clang++-18 -std=c++17 -fsyntax-only -Xclang -ast-dump`. Two final complete script runs passed, followed by host-side validation. Both inferiors exited 0. The expected `-Wmissing-field-initializers` warning on `Partial{11}` is deliberate: omitted `b` is zero-initialized by the language, not left uninitialized.

**Supplementary sanitizer test skipped:** attempted `-fsanitize=address,undefined` link failed because this image lacks Clang's ARM64 ASan runtime archives. The first exploratory script invocation therefore ended with a linker failure after both debugger tests passed. Final script reports that optional check as SKIP; it does not claim sanitizer validation. No packages/image changes were made. ASan/UBSan would not in any event establish general initializedness; MemorySanitizer was not tested.

## Method and safety

`event(tag,address,size,instance)` is a hand-authored noinline hook with an empty compiler barrier. Breakpoints stop in its body after arguments have been materialized. Every payload argument is an address/size or an initialized event ID, never an indeterminate student value. The driver uses `FindVariable`, `GetValue`, child inspection, and `ReadMemory`; it never uses `EvaluateExpression`, invokes student getters, or dereferences potentially stale pointers. Raw memory reads occur only in the stopped debugger, within this fixture's still-existing stack storage. No freed heap block is read. Destructor payload `x` and Throwing payload `id` are known initialized members, used while executing the corresponding special member function.

All debugger payloads are explicitly named `raw_bytes_uncertain` or `debugger_value_uncertain`; observed variables retain `initialization: unknown` and `lifetime: unknown`. This driver deliberately does not implement a lifecycle state reducer. Semantic conclusions below rely on the known fixture/source and event order, NOT on an LLDB proof of initializedness. Hooks perturb layout/timing and are not claimed to preserve every behavior of arbitrary programs.

## Observations

| Case | Experimental evidence | What it establishes / does not establish |
|---|---|---|
| Uninitialized local `int` | First hook: default bytes `ffffffff`; LLDB rendered `-1` with no read error. Pattern build: `aaaaaaaa`, rendered `-1431655766`, also no error. | Successful SBValue decoding is not evidence of a source initializer or a valid student value. Pattern mode injects compiler writes; it is not a detector of language-level initialization. Neither byte pattern is a general uninitialized-memory signature. |
| Variables declared later | At that same first stop LLDB exposed `partial`, `aggregate`, `first`, `second`, `number`, `other`, etc.; later pointer locals had plausible nonzero garbage and no error. | Debug-info scope/location availability is not declaration execution, lifetime-start, or a safe pointer-following predicate. No such pointers were followed. |
| Partially initialized struct | After `partial.a=11`: default `0b000000ffff0000`; pattern `0b000000aaaaaaaa`. After `partial.b=12`: `0b0000000c000000`. | A whole-struct initialized boolean is inadequate. Source/write evidence supports `a` only at the first event; debugger children alone do not certify `b`. No C++ read of `b` before assignment occurs. |
| Aggregate omission | `Partial aggregate{11}` observed `0b00000000000000`. | Omitted scalar aggregate members are initialized; a missing explicit field expression is not sufficient to label a member uninitialized. This conclusion needs C++ semantics plus execution evidence. |
| Constructor intermediate state | Prefilled storage was `5a` repeated eight times. First `Item` constructor-body entry showed `070000005a5a5a5a`: `x=7` initialized by member initializer, `y` not initialized. After its write: `070000000e000000`. | Constructor entry is not equivalent to all members initialized. In a constructor body, base/member initialization already ran. Construction-complete must not be emitted at allocation or function entry. |
| Same-type placement reuse | First and second Item use exactly the same address, with no heap allocation. Second constructor entry: `080000000e000000`; the old `y=14` bytes survived until assignment to 16. | Stale bytes can look perfectly reasonable inside a new object's not-yet-initialized member. Reset per-member initialization evidence for each generation, even if addresses/types/bytes match. |
| Destructor and dead object | Hook in destructor body then hook after explicit destructor call. Post-call bytes exactly matched the previously completed object (`7,14`, then `8,16`). | Readable unchanged storage does not establish a live object. The body hook is NOT destructor completion. For class objects the lifetime ends when the destructor call starts, with special construction/destruction access rules; do not model the entire destructor body as ordinary live state. |
| Different-type reuse | An `int(91)` and then `Other{123}` occupy the same aligned `mixed` buffer. Post-`~Other()` bytes still match `123`. | Placement new may end an overlapping object's lifetime without allocation/deallocation. Static pointer variable types persist independently of the new occupant's type. Address is neither dynamic-type proof nor object identity. No old pointer is dereferenced. |
| Partial array construction and throw | Constructor-body entries IDs 1,2,3; successful-body-tail markers 1,2 only; destructor-body markers 2,1, followed by catch. No destructor for 3 or constructor for 4. | A requested four-element allocation is not four completed objects. Unwinding destroys completed elements in reverse order. Constructor-body-tail hooks alone are not universal return/completion hooks; here subsequent events and source establish which constructors returned. No allocation/free registry was included for this array, so storage size/cookie/free timing are NOT established by this test. |

All hex strings above are raw observations from the retained run on little-endian ARM64, not portable layout constants or trustworthy presentations of indeterminate values. Known initialized integer bytes are asserted only for this platform. The stack local with no initializer can have begun its lifetime through vacuous/default initialization while still lacking an initialized scalar value: **uninitialized does not mean not alive**.

## Instrumentation feasibility and boundary

Manual selective hooks successfully expose:

- completion of specific scalar assignments and known declaration initializations;
- member-initializer-versus-constructor-body phases;
- post-successful-placement-new sites and post-explicit-destruction sites;
- two object generations in one storage region, including type changes;
- exceptional partial array construction and destruction ordering.

That establishes a runtime transport/event-stop mechanism, **not automatic coverage**. The AST dump contains `CXXNewExpr` (including placement arguments), `CXXConstructExpr`, `CXXDestructorDecl`, `CXXThrowExpr`, and `CXXDeleteExpr`. This is structural reconnaissance only. There is no LibTooling matcher/rewrite pass, AST-generated hook insertion, automatic write detection, source map, or demonstrated semantic preservation. Do not describe this as an AST instrumenter.

An actual instrumenter needs separate tests for evaluation order, no double evaluation, exceptions, return paths, implicit/defaulted constructors/destructors, bases/member initialization, delegating constructors, temporaries/copy elision, arrays/cookies, implicit destruction during unwinding, macros/templates, aggregate/value/default initialization, trivial types, unions, aliases, writes through references/pointers, `memcpy`, library writes, and implicit-lifetime types. Constructor-body insertion misses base/member construction and cannot alone emit correct success/failure. Destructor-body insertion misses trivial/implicit destruction and cannot alone mark completion. Wrapping a whole placement-new expression needs to preserve its result type and evaluation semantics and not report success after a throwing initializer. Merely inserting a hook after a source line misses multiple events and exceptional exits.

## Explicit design implications / recommendation

1. **Separate storage, object generation, and initialization.** Use allocation/storage IDs for regions and object-generation IDs for typed occupants; two Items here share both address and storage but are distinct generations. Stack scopes are storage sources too. Placement construction does not require an allocation event.
2. **Track orthogonal states with provenance.** Suggested independent axes: storage live/released/unknown; construction in-progress/completed/failed; destruction in-progress/completed; member/element initialization known/unknown/known-uninitialized under supported instrumentation. Include event evidence, coverage, source location, and before/after semantics. Do not pretend a coarse phase is the complete C++ lifetime model.
3. **Conservative display by default.** Uninstrumented scalar bytes, pointer values, and members should remain unknown rather than ordinary values. Debugger read success, zero bytes, changes, and old plausible values must not promote them to initialized. Retain raw bytes only behind an explicitly uncertain diagnostic view. Do not follow unknown pointers or dead-object views.
4. **Record transition boundaries, not just snapshots.** Hooks provide an ordered event stream on one source line and within special members; post-success sites differ from entry/body sites. Do not backdate a value observed after assignment to a pre-statement line stop.
5. **Arrays need per-element construction progress.** Allocation bytes/static `T*` and requested count do not prove completed elements. Exception paths need failure/unwind events; distinguish destroyed objects from released backing storage.
6. **Do not overdiagnose dangling pointers.** Retain historical target generations where evidence exists, but do not assert every old address-valued pointer is invalid after placement reuse: transparent replacement, laundering, subobjects, and type/lifetime rules require explicit handling. This spike tests identity separation, not a general validity checker.
7. **Recommended next scope:** keep LLDB + allocation history for first memory-view milestone with initializedness unknown outside a narrow supported subset. If initializedness must be shown, separately prototype a real Clang tool on simple scalar/aggregate declarations and scalar assignments with conditional/throwing paths, coverage flags, and behavioral comparison tests. Treat unsupported aliases/library writes conservatively. Do not scale manual hooks into a production promise or infer full object semantics from allocation hooks.

## Artifacts and limits

Retained here: `fixture.cpp`, `record.py`, `validate.py`, `run.sh`, `observations.json` (compact event evidence plus first-stop uncertain DWARF views), `test.log`, `toolchain.txt`, `sanitizer-build.log`, and this report. Generated executables, full debugger JSON, AST dump and an additional run log are isolated in `.agents/scratch/initialization-lifetime/`; the first exploratory command log is `.agents/scratch/initialization-lifetime/exploratory-run.log`. Other pre-existing files in this retained directory (such as `evidence.json`, `ast_inventory.py`, `run.log`, and `*-validation.txt`) are not outputs of this run and are not used by this report; use `observations.json` and `test.log` for the current evidence.

Tested only this pinned ARM64 image, single thread, C++17, O0, small deterministic fixtures. No optimized/DWARF-version matrix, watchpoint/dataflow proof, MemorySanitizer, real automated AST instrumenter, production schema/viewer, allocation interception changes, general invalid-pointer checking, or complete C++ lifetime model is claimed.
