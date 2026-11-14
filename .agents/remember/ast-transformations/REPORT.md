# Automated new-expression transformation spike

## Decision

**A narrowly constrained AST-based transformation is feasible at milestone-1 settings, but a general C++ expression wrapper is not established.** This spike actually rewrites compiler-identified expressions, compiles the generated source, executes it, and compares it to the original. No fixture contains request/result hooks. Ten successful expression results join uniquely to storage generations, including nested allocations, cookie-adjusted arrays and empty arrays. Four failures are distinguished from success. A separate optimized experiment **does not preserve observable behavior**; see below.

Recommendation: retain the hybrid LLDB/storage-registry architecture. A small opt-in compiler metadata path is justified for direct student allocations at `-O0`, especially dynamic array extents. Do not make a universal source instrumenter, every-write logger, or full construction/lifetime model a milestone-1 dependency. Ship honest storage-only/unknown views for unsupported code, or reject it explicitly in an instructional subset. A broad semantic-preservation claim would require substantially more compiler engineering than these results justify.

Read the project brief, follow-up synthesis and dynamic-arrays/allocation-attribution reports. Work is confined to `.agents/remember/ast-transformations/` and `.agents/scratch/ast-transformations/`. No root Dockerfile/shared prototype/other spike edits, image builds, pruning, or commits. Existing unrelated working-tree changes were left alone.

## Approach and reproducibility

Simplest real AST approach: Python consumes **Clang 18 JSON AST**, finds `CXXNewExpr` nodes, uses their source ranges, bound child, pointer type, initialization form and allocation declaration, and recursively rewrites nested ranges. This is not manual source matching or AST inspection alone. It avoids installing LibTooling. Clang's JSON AST format is compiler-version-dependent, not a stable tooling API.

From repository root:

```sh
docker run --rm -v "$PWD:/work" -w /work tracecpp:llvm18 \
  sh .agents/remember/ast-transformations/run.sh \
  > .agents/scratch/ast-transformations/run.log 2>&1
docker run --rm -v "$PWD:/work" -w /work tracecpp:llvm18 \
  sh .agents/remember/ast-transformations/optimized-exploration.sh \
  > .agents/scratch/ast-transformations/optimized.log 2>&1
```

Existing native ARM64 `tracecpp:llvm18`, Ubuntu Clang 18.1.3, C++17, `-g -O0`, ordinary Docker permissions. No debugger needed: native execution plus an allocation shim provides enough evidence for this bounded question. Prior LLDB integration was not rerun or implemented here. All commands in `run.sh` are checked with `set -eu`; Python assertions propagate normally, unlike LLDB CLI exception handling.

The transformer runs `clang++-18 -std=c++17 -Xclang -ast-dump=json -fsyntax-only INPUT`, renders real expressions, then validates the entire generated translation unit with `-fsyntax-only` before reporting success. The runner separately compiles and executes original and generated code. Retained code: `transform.py`, `runtime.hpp`, `storage.cpp`, `fixture.cpp`, `sequencing.cpp`, `validate.py`, `run.sh`, `optimized-exploration.sh`. Generated C++, AST-derived `.sites.json` manifests, binaries, stdout, event streams, rejection fixtures/logs and optimized diff are in the scratch directory.

Final results (both commands exit 0; optimized command explicitly records rather than suppresses its mismatch):

```
transformed 14 sites
transformed 4 sites
PASS O0: 14 requests, 10 unique storage joins, 4 failures, single bound evaluation, all storage released; stdout/types agree
PASS sequencing: return expression, comma, short-circuit, outer temporary lifetime
PASS rejected wide-bound
PASS rejected class-allocator
PASS rejected temporary
PASS rejected init-temporary
PASS rejected placement
PASS rejected nothrow
PASS rejected aligned
PASS rejected multi
PASS rejected template
PASS rejected macro
PASS rejected unevaluated
PASS rejected constexpr
O2 MISMATCH: see optimized.diff; optimization is outside supported subset
```

Every negative fixture is compiled successfully *before* requiring transformation rejection, including Clang's accepted C++17 constexpr-new extension. Wide bounds are rejected during generated-code validation by the runtime helper's static assertion. Rejections are whole-invocation failures, not silently skipped main-file allocations. Header allocations are deliberately outside source ownership and not transformed.

## Transformation semantics and tested subset

For each supported expression the generated code introduces an immediately invoked reference-capturing lambda with an automatic request guard, a `try`, the original new-expression, a successful-pointer hook and `return`, then `catch (...) { failure(); throw; }`. Array bounds are replaced in situ with an identity helper taking the original expression **once** and reporting its evaluated value. The helper returns the same integral value type; allocation/initialization remain in the compiler's original new-expression. Scalar count is implicitly one. This is not a duplicated `n` read or a post-line hook.

Supported/tested: ASCII main-file expressions inside non-constexpr, non-template functions/constructors; ordinary global throwing scalar or one-dimensional array new, integral bounds up to 32 bits, no temporaries within the new-expression. The main fixture exercises:

- `n++` and function-call bounds; scalar const pointer, list/value initialization and default class construction;
- nested `new int*(new int{11})` and a constructor allocating its own member;
- nontrivial successful arrays, zero-element trivial/nontrivial arrays;
- throwing bound (request but no count/storage), throwing array constructor (count four, automatic prefix cleanup), throwing scalar constructor;
- negative bound, caught as `std::bad_alloc` on this compiler/runtime;
- `static_assert` pointer types (`int*`, `const int*`, `int**`) in both original and generated binaries.

Separate sequencing fixture covers return-position new, comma-sequenced siblings, suppressed short-circuit allocation, and an outer full-expression temporary passed alongside new. Its stdout including destructor timing matches and only three of four source sites execute. No imposed argument-evaluation order is claimed. An initial exploratory `new int[n++]{n}` emitted Clang unsequenced warnings; it was replaced by a separate initializer function and is **not** used as preservation evidence.

Temporary lifetime is a hard restriction, not solved: wrapping `new int[T()]` or `new int(T())` could destroy the conversion temporary at lambda return instead of the containing full-expression. `MaterializeTemporaryExpr`/`CXXBindTemporaryExpr` therefore cause rejection. Existing temporaries outside the new-expression are not moved, as tested. Lambdas, `this`, predefined/source-location expressions, coroutine operands, statement expressions and default-argument/default-member-init AST nodes inside the expression are also rejected conservatively. Only some of those extra exclusions have dedicated fixtures.

Macros in the new-expression, templates, placement/nothrow, aligned allocation, class-specific allocators, multidimensional arrays, constexpr functions and recognized unevaluated contexts are rejected. Generated-code compilation is another rejection gate (e.g. C++17 lambdas in missed unevaluated contexts). This is a scoped source tool, not proof that all unsupported C++ grammar/implicit semantic contexts are recognized. Generic template/header instrumentation, non-ASCII byte-offset handling, pools, custom allocation declarations, source-location-sensitive builtins hidden in called code, and unusual implicit conversions need further review. Generated names are per-site and checked for source collisions; runtime namespace `tc` is reserved. It is not a production hygienic rewrite engine.

## Captured metadata and transport

The manifest records original path, source SHA-256, source-order site ID, start/end byte offsets, original line, array flag, result pointer type, bound range and Clang initialization form (`none`, `call`, `list`). IDs are deterministic for identical input, not edit-stable across changed source; identify a site by source revision/hash plus ID. A `#line` directive restores original filename/line for diagnostics/debug info. Generated lambda columns/frames are artifacts, not precise original stepping or column mapping. No DWARF/source-map integration beyond that was built.

Runtime stderr is a deliberately simple synchronous event transport:

- `R token site`: attempt begins, **before bound evaluation**;
- `C token signed-count`: bound evaluated successfully, exactly once;
- `S token pointer storage-id candidate-count`: expression completed, pointer returned;
- `F token`: exception escaped the new-expression, rethrown unchanged;
- `A id base bytes owner-token`, `D id base`: provider allocation and pre-free events.

Array bound exceptions have no C event; a count is not fabricated. Scalar count one is known from the manifest/runtime guard, not a C event. Signed/unsigned integrals up to 32 bits fit the signed transport; wider bounds explicitly fail compilation. Overflow/invalid-size behavior is left to new, not inferred as an element count fit. There is no completed-element counter. Successful construction does not establish initialized scalar members. On failure, the stream does not classify bound-vs-allocation-vs-initialization exceptions directly; event presence only narrows the phase.

The fixture's stdout demonstrates completed elements 0/1 and reverse cleanup 1/0 for the throwing array; the instrumenter does **not** capture those as lifetime metadata. Constructor/destructor printing is only a behavioral oracle. No cookies are decoded and no per-element lifetime or initializedness claims follow from storage bytes.

Transport limitations: fprintf may perturb timing/errno, buffering and allocation behavior; I/O errors are not handled, logging is not async-signal-safe, and runtime crashes/terminate need not produce F. Registry capacity is fixed at 4096, single-thread validation only (active stack is thread_local, registry/token counters are not synchronized). No portable trace schema, LLDB checkpoints, performance benchmark or production event channel was implemented.

## Storage join

The separate replacement-global-new shim records storage generations and requested provider bytes, delegates to malloc (one physical byte for size zero), and marks frees. It is intentionally not a complete replacement allocator: no new-handler loop, aligned/nothrow/malloc coverage or production OOM semantics. Both original and transformed use ordinary compiler new-expressions, but only transformed links this shim; therefore allocator replacement and source instrumentation effects are not experimentally isolated.

Each request has a nested active token. Provider events record their active owner; success searches still-live storage **owned by that token**, with address containment and a special empty-result end/base case only for count zero. Multiple candidates produce unknown ID zero rather than arbitrary selection. Allocation IDs distinguish reused addresses. All ten successes had exactly one candidate; all twelve recorded allocations were released, including two construction-failure cleanups. For nontrivial `Obj[2]` and `Obj[0]`, the result is base+8; the empty result equals storage end. `int[0]` has zero provider bytes and result==base. Validators check these actual address relationships, not just expected event names.

Outer pointer storage and nested pointee storage have different tokens/generations. Allocating constructors are also nested correctly; lexical site 1 executes inside a later caller request, demonstrating that site ID is not invocation order. The shim's owner constraint is stronger than indiscriminate range matching but not a general provenance solution. Uninstrumented constructor/library scratch allocations share the enclosing token; result containment filters candidates, but pools, suballocation and custom allocators remain unimplemented. No class-allocator scratch-storage attribution claim is made (class allocators are explicitly rejected).

## Failures, fixes, and remaining risk

1. Initial baseline caught only bad_array_new_length for negative bounds; this Clang/libstdc++ combination threw bad_alloc and the original aborted. Catch broadened to bad_alloc in both baseline and transformed fixture. Final O0 executions exit zero.
2. Optimized exploration produced a real stdout mismatch: original O2 elides the unused negative-bound allocation and prints no `negative`; transformed prints `negative`. Instrumentation/extra calls inhibit permitted new-expression allocation elision. The mismatch is reproducible in `optimized.diff`; **no optimization-preservation claim**. Restricting the runner to O0 does not repair this general issue.
3. Review caught a generated result-name shadowing hazard; changed fixed `tc_result` to per-site collision-checked names. This was a preventive code fix, not a reported passing adversarial fixture.
4. A validation string initially contained literal escaped newlines, causing its cleanup assertion to fail. Fixed the oracle and reran the full pipeline successfully.

Even O0 passing fixtures are evidence, not a proof of general semantic preservation. Exception stack/backtrace shape, logging effects, hidden temporaries/default arguments, overload/context-sensitive expressions, allocation elision, macros/templates and source mapping deserve a compiler-level design review before shipping. A bounded opt-in array-count/result instrumenter is useful; a broad promise that ordinary C++ can always be rewritten transparently is not supported by this spike.
