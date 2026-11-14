# Follow-up feasibility spikes: synthesis

Five delegates were invoked with `--model gpt-6.1-sol`. The initialization/lifetime invocation initially returned no result; its retry succeeded. All five completed reports and reproducible experiment sources are retained under `.agents/remember/`. This synthesis reviews their reports; it does not claim an independent rerun of every experiment or adopt a production schema.

## Overall conclusion

Keep the hybrid architecture: **LLDB observes stopped-process memory and layouts; allocator interception records storage history; selective compiler instrumentation supplies source semantics that neither can recover.** The experiments validate manually placed event hooks, not an automated Clang instrumenter. Automatic insertion with preserved C++ semantics is the principal unresolved engineering risk.

## Findings and recommended decisions

| Area | Learned experimentally | Recommended design implication |
|---|---|---|
| Initialization/lifetime | LLDB exposed plausible uninitialized and not-yet-declared locals, and readable unchanged bytes after destruction. Placement reuse preserved stale member bytes. Partial array construction completed two elements before unwinding. | Separate storage identity, typed object generation, initialization evidence and construction/destruction phase. Suppress ordinary value display/pointer following when evidence is insufficient; do not infer initialization from readability or zeros. |
| Dynamic arrays | Pointer DWARF did not recover runtime bounds. Supplying a count allowed correct LLDB typed expansion. Nontrivial arrays had an 8-byte cookie on this ABI; cookie count remained requested count during partial construction. Empty arrays exposed zero-size/end-of-storage pointer cases. | Record evaluated requested count, element type/stride, initialization form, successful result pointer and failure separately from allocator base/bytes. Do not derive live elements from byte size or cookies. Explicit identity joins must handle cookie-adjusted and empty results. |
| Attribution | Any-student-frame gave six false positives. Immediate-caller normalization gave two false positives and one false negative. Registered forwarders classified this fixture, but an unknown student helper broke the simpler policy. Result-pointer hooks distinguished class backing storage from temporary STL scratch storage. | Keep request provenance, storage-provider path and display eligibility separate. Stop at opaque consumers, skip explicitly known forwarders, retain classification evidence/unknowns. Match expression results to storage history instead of including every allocation during an expression. |
| Timing | 29 line stops, 59 source-step stops and 42 hybrid stops. All missed same-line intermediate assignments. Line breakpoints missed an entire same-line allocation/deletion lifetime; hybrid hooks captured it. Reallocation showed overlapping buffers and stale aliases. | Use line samples plus allocator-return, successful initialization/expression completion, and deallocation events. Label exact phases and preserve distinct events on one line. Do not promise exhaustive assignment playback. Pre-free is not free-completed. |
| Toolchain | LLVM18 embedded Python worked. LLVM14/Python3.10 standalone worked on native ARM64 with packaging/server-path repairs. Emulated amd64 built/imported/executed normally but debugger launches failed even with broader permissions; register/architecture evidence points to emulation limitations. | Retain LLVM18 embedded Python; standalone is not worth a downgrade without a requirement. Test native amd64 in CI. Gate import, debugger creation, inferior launch and full trace validation separately. Do not claim cross-architecture reliability yet. |

## Minimal conceptual model

These are distinctions required by the evidence, not a prescribed class hierarchy:

1. **Storage:** stable allocation generation, base address, byte extent, provider events and release state.
2. **Source operation:** stable site ID, evaluated bounds/type/initialization form, request token, success/failure and returned address.
3. **Typed occupants:** object generation/subrange and evidenced construction/destruction phase, independent of storage reuse.
4. **Initialization evidence:** per-member/element/range facts where supported; unknown otherwise. Construction completion does not prove that every scalar member was initialized.
5. **Observations:** sequence/PC/source/frame, trigger and before/after phase, observed bytes/values with uncertainty, linked to the evidence above.

An append-only event history assembled into replay snapshots is a natural fit. Raw provider events should remain separate from the filtered student view so attribution can be revised without discarding storage/free history. Keep raw uncertain bytes out of the default trustworthy student-value display.

## Boundaries that remain unresolved

- No real AST rewriter was built. Manually repeating a bound is not safe for `new T[n++]`; post-line insertion does not preserve nested expressions, exceptions, temporary lifetime or all sequencing rules.
- Known forwarding registrations are a policy with limits, not general ownership inference. Pools, suballocations, missing frames, custom class allocators and malloc require explicit coverage plans.
- Full initializedness needs broader write/alias/library evidence; selective construction hooks alone do not solve it.
- Constructor/destructor body markers are not universal language-level lifetime boundaries. Implicit/defaulted special members, inheritance, unwinding and transparent replacement require careful treatment.
- Hooks perturb execution. The source-step comparison ran a hooked binary, so some extra step boundaries were instrumentation artifacts.
- Tests are tiny single-threaded O0 fixtures, not production coverage or performance benchmarks. No native amd64 debugger validation or production security sandbox was established.

## Recommended next engineering decision

Before investing heavily in a viewer, implement and behaviorally validate **one small automated Clang transformation** for a tightly specified subset of ordinary scalar/array new-expressions. It should preserve one-time bound evaluation, return type and exceptions, supply stable site IDs/request-success-failure evidence, and correlate results with storage events. Compare instrumented and original behavior on side-effecting bounds, nested allocations and throwing construction. Unsupported constructs must remain explicit unknowns rather than expanding scope prematurely.

A complete write log or full C++ lifetime model is not necessary for the first memory-focused milestone. Accurate partial observations with declared coverage are.

## Detailed reports

- [Initialization and lifetime](initialization-lifetime/REPORT.md)
- [Dynamic arrays](dynamic-arrays/REPORT.md)
- [Allocation attribution](allocation-attribution/REPORT.md)
- [Snapshot timing](snapshot-timing/REPORT.md)
- [Toolchain reliability](toolchain-reliability/REPORT.md)
