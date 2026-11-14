# Allocation attribution feasibility spike

## Result

**Feasible with explicit policy boundaries; no tested generic stack rule is sufficient.** A deterministic, registered-forwarder stack policy classified all 14 allocations in this fixture correctly. That is a fixture result, not a universal inference of ownership. A previously unregistered student allocator helper produced two false positives. Selective allocation-expression **result-pointer correlation** disambiguated real class backing storage from allocator-internal STL scratch storage. Merely being inside the dynamic extent of a student expression would not do so.

No shared prototype or root Dockerfile was changed. No resources were pruned or commits made. All new source and output are under the two allocated directories.

## Reproduction and evidence

From repository root:

```sh
docker run --rm -v "$PWD:/work" tracecpp:llvm18 \
  sh .agents/remember/allocation-attribution/run.sh
```

Uses existing ARM64 image `sha256:22b5427abbcdd0395258df2a8f005088d5613d2f65e5924dc2d1a283759e026d`, Clang/LLDB 18, embedded Python, C++17, `-g -O0 -fno-omit-frame-pointer`, default Docker permissions and ASLR enabled. Read the project brief, Phase A report, allocation shim, recorder and run script before implementing this isolated experiment.

Two final full compile/trace/validation runs exited 0 and produced **14 allocation events each**, identical including full source stacks, policies and expression matches after removing addresses. Outputs: `.agents/scratch/allocation-attribution/run.log`, `run-repeat.log`, `trace-first.json`, `trace.json`, `trace-evaluated.json`, and executable `student`. Validator checks case counts, expression matches and expected registered-policy classifications. No timing/performance claims.

Retained sources in this directory:
- `student.cpp`: labeled cases and two hand-inserted expression result hooks.
- `allocations.cpp`: independent copy of the narrow Phase A new/delete shim.
- `record.py`: synchronous embedded-LLDB driver; captures complete caller stacks, case labels, addresses, sizes, allocation IDs, policies and result-hook matches.
- `validate.py`: portable fixture oracle and policy error summary.
- `run.sh`: compile, trace, validate; stale trace removed before tracing because LLDB can swallow Python exceptions into a successful CLI exit.

Case labels are **test oracle only**, not input to the attribution policies. The student-source allowlist is the exact absolute fixture path, not a loose repository-prefix or function-name test.

## Meaning of the classification

The chosen educational contract is **request provenance**, not “student code appeared somewhere” and not “a student allocator supplied bytes.” Direct student new, a custom container's backing storage, and direct calls to a student allocator belong in the student heap. STL vector storage stays opaque even when its storage provider is student-authored. A student class's direct new expression belongs in the heap even if its class allocator delegates to standard allocator forwarding machinery. A class allocator's temporary vector buffer remains noise.

Keep three separate facts:
1. **Request provenance:** source operation / semantic consumer responsible for needing storage (student container vs opaque STL container).
2. **Storage provider path:** global new, student allocator, class allocator, standard allocator forwarders, underlying malloc, etc. More than one layer can participate; this is not ownership.
3. **Display eligibility:** a policy decision based on provenance and the opaque-STL boundary, with evidence and uncertainty.

Here the replacement global new ultimately uses malloc. The recorder observes the shim, not libc malloc itself. `MallocObject` has an explicit event in its class allocator because global new interception alone cannot observe its direct malloc. Provider coverage must be reported separately from attribution quality; an unseen allocation cannot be classified.

## Executed cases

`include` means student heap eligibility under the contract above.

| Case | Allocation IDs / sizes (bytes) | Expected |
|---|---|---|
| Direct scalar new | 1 / 4 | include |
| Student helper returning new | 2 / 4 | include |
| Nested student helpers | 3 / 4 | include |
| Minimal student vector grows twice, deletes old storage | 4 / 12; 5 / 32 | include both histories |
| Direct student allocator call | 6 / 20 | include |
| Direct std::vector reserve, push_back, reserve | 7 / 52; 8 / 116 | exclude; push within capacity allocates nothing |
| std::vector inside student helper | 9 / 68 | exclude |
| std::vector with student allocator | 10 / 92 | exclude |
| Same inside student helper | 11 / 76 | exclude |
| Student class `new Routed`: temporary vector scratch | 12 / 71 | exclude |
| Same class new: actual storage via std::allocator | 13 / 4 | include |
| Class new using malloc, with explicit provider event | 14 / 4 | include |

The minimal vector is intentionally not a full vector implementation: it allocates replacement storage and frees old storage, without element copying. This experiment measures attribution, not container correctness or object interpretation.

## Policies and measured failures

“Immediate” below is already normalized by removing tracer/global replacement new frames. Literal immediate caller of the event would just be the shim and is uninformative. Do not confuse this normalization with skipping arbitrary libraries.

| Policy | False positives | False negatives |
|---|---|---|
| Any exact student-source frame anywhere | 7, 8, 9, 10, 11, 12 | none |
| Immediate caller after tracer/global-new removal | 10, 11 | 13 |
| Skip known allocator forwarding functions | 10, 11 | none |
| Also explicitly register student `forward_storage` helper | none | none |

Known forwarding here means allocation methods of `std::allocator`, `std::__new_allocator`, allocator_traits and StudentAllocator (plus compatibility spelling for GNU new_allocator), not all std frames. The registered extension additionally skips this fixture's `StudentAllocator<T>::forward_storage`. The classifier then tests whether the **first remaining frame** is student source. It never scans past a remaining vector operation merely to find main.

Observed distinguishing stacks (event hook omitted):

```text
10: global new -> StudentAllocator::forward_storage -> StudentAllocator::allocate
    -> allocator_traits::allocate -> vector::_M_allocate -> vector::reserve -> main
12: global new -> std::__new_allocator::allocate -> allocator_traits::allocate
    -> vector::_M_allocate -> ... -> vector constructor -> Routed::operator new -> main
13: global new -> std::__new_allocator::allocate -> Routed::operator new -> main
14: MallocObject::operator new -> main
```

Thus treating *all* student functions as requests falsely includes ID 10, while treating *all* standard-library frames as opaque falsely excludes ID 13. Skipping *all* standard-library frames would conversely include the excluded vector allocations. The forwarder/consumer distinction is essential. Even a student's function named `forward_storage` needs registration or semantic annotation; names alone cannot establish its role.

## Selective source-expression experiment

Two manually inserted `expression_result(pointer)` calls immediately after `new Routed` and `new MallocObject` stopped in LLDB. The driver matched each returned pointer to the latest still-live allocation ID, yielding **13 and 14**, not scratch ID 12. This is a concrete executable surrogate for a compiler-inserted post-expression result hook, **not an implemented AST rewriter**. The matched ID remains evidence of the source request even if the stack classifier would reject it. The class example includes a useful adversary: a naive “student expression currently active” flag would cover both IDs 12 and 13 and leak the scratch vector into the view.

For real tooling, preserve expression ID/source range and correlate result address to a storage interval/ID. A temporary trace harness case ID is not a substitute. Allocation-result hooks are selective evidence, not a replacement storage inventory: IDs/size/free history still come from provider hooks. Result hooks alone do not identify arrays, cookies, dynamic type, initialization or object lifetime. This fixture's addresses match allocation bases; interior/adjusted results need range matching with ABI-aware evidence. A hook after the expression occurs after construction and cannot retrospectively provide a stopped pre-constructor snapshot; joining history is possible, recovering missed memory snapshots is not.

## Design implications

1. Keep a raw provider-event history separate from the filtered educational heap. Store request source, provider stack, classification rule/version, and confidence/unknown status. Do not lose allocation/free pairing when filtering. Track frees against allocation IDs, not the freeing caller's classification; this recorder maintains live addresses for result correlation but does not implement a full exported lifetime registry.
2. Start with exact student-source ownership and **small explicit forwarding registrations**, stop at opaque consumers, retain the reasoning stack. For unrecognized forwarding, say attribution unknown rather than promising universal classification. `skip_registered` passes this fixture because its annotation is supplied, not because stack analysis discovered intent.
3. Use selective compiler/source hooks for ambiguous student allocation expressions or allocator APIs; match returned storage to events rather than setting a broad dynamic-scope student flag. Prefer compiler-derived annotations to fragile demangled-name substring tables in production.
4. Do not count an STL allocation as student-managed merely because a student's allocator provided it. Conversely, a student's class-specific allocation may use standard allocation machinery without being STL-container noise.
5. Provider coverage requires a separate plan: a new-only shim cannot see malloc-backed class allocators or pools. The malloc case here is instrumented by hand, not automatic evidence of general malloc coverage.

## Remaining uncertainties / limits

- ARM64, this pinned Clang/LLDB and libstdc++ only. Optimized/inlined/tail-called frames, missing debug info, libc++, separate student headers, DSOs, stripped providers and alternate ABIs not tested. Unknown/nonstudent frame evidence needs explicit handling, not accidental exclusion presented as certainty.
- No universal way demonstrated to infer whether an arbitrary student helper is a forwarding allocator or semantic consumer. Registering known helpers solves these cases, not the general problem. Custom allocator instrumentation itself can allocate scratch/log storage; blanket marking of allocator bodies would be unsound.
- Only ordinary throwing scalar/array new and ordinary deletes from the copied shim; no complete new_handler behavior. Aligned/nothrow APIs, direct C allocation interception, pools/suballocations, placement new, constructor failure, threads and callbacks were not tested.
- Result-pointer correlation tested on two successful scalar expressions only. Constructor exceptions have no successful result; pooled/interior pointers may not match a fresh provider event; address reuse needs stable generation IDs and strict event ordering. No claim of general expression attribution in those cases.
- No full compiler instrumentation, automated source transformation, production schema, visualization, object-lifetime inference, or security sandbox work. Small manually labeled oracle, not a broad correctness benchmark.

**Recommendation:** retain LLDB plus targeted storage tracking. Replace the Phase A immediate-caller assumption with explicit request/provider separation, a versioned forwarding/opaque-boundary policy, and selective result hooks for cases where source evidence is necessary. Do not advertise either “any student stack frame” or “first student allocator frame” as correct student-origin attribution.
