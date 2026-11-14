# Snapshot timing spike — executed ARM64 results

## Decision

Use **student-line stops plus selective lifecycle events**. Treat line stops as partial samples at a program counter, not as an exhaustive statement-by-statement or after-line history. Selective events recover short-lived allocations and initialization boundaries but **do not recover all intermediate writes**. Every-write instrumentation is unnecessary for the initial memory-focused recorder; require it only if an explicit product goal is to replay every assignment/expression.

Report and reproducible sources: `.agents/remember/snapshot-timing/`. Generated executable, full histories, logs, and machine-readable summary: `.agents/scratch/snapshot-timing/`.

## What was run

Read the project brief, feasibility report, and existing embedded-Python recorder/run script. Reused the existing `tracecpp:llvm18` ARM64 image without modifying it, shared prototypes, or Dockerfile. No pruning or commits.

```sh
docker image inspect tracecpp:llvm18 --format '{{.Architecture}}'
# arm64
docker run --rm -v "$PWD:/work" tracecpp:llvm18 \
  sh .agents/remember/snapshot-timing/run.sh
python3 .agents/remember/snapshot-timing/validate.py
```

`run.sh` compiles C++17 using `clang++-18 -g -O0 -fno-omit-frame-pointer`, runs LLDB 18 embedded Python three times, and validates JSON using ordinary Python. Two complete final runs passed, with exit status zero in all modes. No special Docker ptrace flags were needed here. See `run.log`, `repeat.log`, `validation.log`, and `summary.json`. The initial exploratory run exposed a demangled-name match bug (`::timing_event`), which was fixed before validation; the initial run also preceded creation of the validator.

The fixture combines same-line mutations, a placement-constructed two-field object, explicit destructor, a custom vector-like integer-buffer growth with a stale alias, and `new int(99)` followed by deletion on the same source line.

| Mode | Actual stops | First validated capture-loop time |
|---|---:|---:|
| Student-line breakpoints | 29 | 0.061 s |
| Source step-in, returning from nonstudent/hook frames | 59 | 0.122 s |
| Student lines + lifecycle hook breakpoint | 42 | 0.077 s |

Times exclude build/container/launch and are not a benchmark. First validated JSON sizes were approximately 74/161/142 KB respectively. Current timing values are in `summary.json`; addresses vary with ASLR. LLDB emitted a DWARF specification warning in breakpoint modes but successfully read the asserted data.

## Instrumentation boundary

**All event hooks are manually placed source calls, not automated AST instrumentation.** No allocator replacement or compiler plugin was implemented. The fixture calls a noinline no-op `timing_event(kind,address,size,type,site)` with these kinds: 1 storage observed, 2 initialization completed, 3 deallocation request before allocator entry, 4 explicit destructor returned. Type IDs are manual (Item or integer-buffer); size/count knowledge is fixture-provided, not inferred from a pointer.

All three modes execute the same hooked binary. Baseline breakpoint mode does not stop in or consume hook calls. Source stepping does enter the manual hook function; its 59 stops include those calls and their return locations. Therefore, **some apparent extra source-step precision is caused by hook call boundaries** and must not be claimed for uninstrumented source. Hybrid alone consumes event metadata and maintains a heap inventory. Baseline histories contain frames/locals/`this` fields but no claimed complete heap inventory.

## Captured histories, not predicted behavior

The validator asserts these observations in all three recordings:

* `x = 1; x = 2; x = 3;` gives sampled x history **0 → 3**, later 9. Neither 1 nor 2 appears, including in source stepping.
* Constructor field samples include **(1,2) → (4,2) → (4,5)**. The intermediate `a=3` is absent. An earlier entry stop reads raw `(0,0)` in these runs; those bytes are **not evidence of initialization**. The member initializers have not completed at that stop.
* After caller mutations, destructor samples are **(7,5) → (-2,5) → (-2,-3)**. The intermediate `a=-1` is absent. Constructor/destructor source lines expose phases, not atomic fully constructed-object transitions.

Hybrid recording supplies **13 lifecycle events and four allocation generations**:

| Event site | Observed heap evidence |
|---|---|
| 30 Item storage | 8 bytes exist, initialization unknown, before placement constructor |
| 31 Item init complete | fields `[4,5]`; caller pointer assignment has completed |
| 32 destructor returned | object view suppressed, storage retained until release |
| 33 Item release request | no further raw reads of this generation |
| 34/35 initial vector buffer | unknown storage then initialized `[10]` |
| 20/21 grown buffer | new 8-byte block, then `[10,20]`, while old `[10]` still exists |
| 22 old buffer release | old generation retired before allocator call; both `v.data` and `alias` still hold old address |
| 36 final vector release | `v.data` has new address and size 2; alias still holds old address |
| 40/41/42 immediate object | storage-observed → initialized `[99]` → release-request, all on one student line |

The immediate allocation has **no line-breakpoint snapshot during its lifetime**: the stop before the line precedes allocation, and the next line stop follows deletion. Hybrid captures it. Source stepping enters the manual calls on that line (and returns to the same line); this is not proof it would independently find all allocation/initialization boundaries without hooks.

For ordinary `new int(99)`, site 40 is deliberately **after the entire new-expression**, so bytes already contain 99. It does not observe allocation-before-initialization. For Item, split `operator new` plus placement new provides a genuine raw-storage-before-construction observation. A future allocation interceptor must fire at allocator return, independently of an AST new-expression completion hook.

Address reuse actually occurred: the Item address was reused by the initial vector buffer, and the grown-buffer address by the immediate integer in a validated run. Four generation IDs remain distinct. Validation does not require reuse because allocator address selection is not guaranteed.

All terminal generations have no `raw_ints`. Unknown-storage bytes are retained only as explicitly uncertain diagnostic observations; raw integers are not assertions of initialized C++ values. Other debugger locals before their declarations also contain garbage and must not be rendered as trustworthy values.

## Timing semantics and lifecycle cautions

1. A source line maps to one or more instruction locations. Breakpoints normally stop **before the instructions at that resolved PC**. A following line can show effects of the previous line, but line labels are not reliable completed-statement IDs. Step-in can return to the same line after a call with different memory.
2. Event stops are before the no-op hook body but **after preceding fixture operations and argument evaluation**. Initialization-completion is after constructor return; pre-free means the storage physically still exists. The registry conservatively suppresses it immediately; call this `deallocation_requested`, not allocator-completed.
3. Storage existence, initialization evidence, object construction/destruction phase, and physical allocator release are separate dimensions. The prototype's compact `state` field is intentionally not a sufficient production lifetime model.
4. Destructor entry is not merely a normal live-object sample: C++ class lifetime ends when the destructor call starts, while access in destruction has special rules. These bytes are destruction-phase observations. A post-destructor hook proves return, not the exact start of lifetime end. Constructor body entry similarly does not mean the entire derived object/new-expression is complete.
5. Initialization-completion events do not capture every vector copy/write or publish operation. Here separate source lines show copy-complete, old-buffer retirement, and publication; combining these operations on one line would hide the pointer-publication transition unless separately hooked. Hybrid intentionally remains partial.

## Concrete design recommendations and minimal metadata

* Retain source stops for instructional navigation and synchronous full reads of small tracked blocks. Pair them with allocator-return, new-expression/initialization-completion, and deallocation-request events. Add destructor-entry/constructor-phase markers when presenting detailed lifetime states; do not silently infer those phases from bytes.
* Label every snapshot with sequence ID, thread/frame, exact PC, source file/line/column when available, trigger kind, and timing relation (`before instruction`, `after operation`, `before free`). Preserve call-site identity separately from hook implementation location. Same-line events need distinct static site IDs; line alone is insufficient.
* An allocation event minimally needs generation ID, address, byte extent, allocator operation, origin/call site, and evidence that storage acquisition succeeded. Initialization completion additionally needs object/subrange identity, type evidence, element extent/count and completion status. Track constructed ranges for partial arrays rather than interpreting all capacity as live elements.
* A deallocation/destruction event needs generation/object identity, operation kind and phase; do not conflate destructor entry, destructor return, free request, and free completion. Retain raw pointer values after retirement; resolve against historical generations rather than declaring an address-reused pointer valid.
* Separate `storage_live`, object phase, initialization-known ranges and observation validity. Never expose readable freed bytes as current objects. If dropping uncertain raw bytes from the exported student view, retain an explicit unknown marker instead.
* A selective AST pass could eventually supply stable site IDs and successful initialization completion after new-expressions, including temporary results not stored in named locals. **That pass has not been built or validated here.** Avoid naïve text insertion that changes evaluation order, temporary lifetime, exceptions, or sequencing. Use runtime allocator interception for raw storage, not merely completion of a new-expression.

## Limits and next checks

Single-threaded, successful execution only; ARM64 Docker/Clang+LLDB 18, O0. No arrays of nontrivial objects, inheritance/virtual dispatch, exceptions/throwing constructors, partial construction unwinding, placement reuse without allocation, malloc/aligned/nothrow allocation, optimized code, implicit destructor scopes, or real AST transformations were tested. The explicit destructor fixture is intentionally controlled and does not validate automated interception of `delete` phases. Raw integer decoding is fixture-specific little-endian 4-byte int, not a portable serializer. Stop cap is 2000. No production trace schema or viewer was implemented.

Next narrow validation should cover throwing constructors and nontrivial arrays, to ensure storage acquisition survives failed initialization and element construction/destruction ranges remain honest. This experiment supports a partial lifecycle-aware timeline, **not a complete write log or proof of C++ object validity**.
