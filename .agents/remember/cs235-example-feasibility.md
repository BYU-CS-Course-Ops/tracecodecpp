# Feasibility assessment: CS235 instructor examples

## Scope and evidence

Source-level review of representative examples in `~/teach/cs235/cs235-instructor/`, following the recorder and AST-transformation spikes. These course examples were inspected, **not compiled or run through the recorder**. This assessment is not an end-to-end compatibility claim, and the instructor source is not copied here.

Relevant prior evidence: [follow-up spike synthesis](feasibility-followup-summary.md) and [automated AST-transformation report](ast-transformations/REPORT.md).

## Conclusion

The course's pointer, linked-list, custom-vector and BST examples are strong targets for a memory-first recorder. However, the experimental transformer's current exclusions are too restrictive for this course: **student templates, student headers and constructor member-initializer expressions are initial-scope requirements**, not optional advanced coverage.

STL-backed hash-set and heap examples would have limited instructional visibility under a strictly opaque-STL policy. Small, explicitly semantic adapters may be needed earlier than originally proposed, without presenting their output as physical STL layout.

## Representative examples inspected

Paths below are relative to the instructor repository.

| Example | Assessment and teaching opportunities |
|---|---|
| `Unit04-Mechanics-of-lists/lecture4a-pointers/pointers.cpp` | Excellent starting target. Object copies, pointer aliases, mutations, private fields and actual addresses directly match the intended memory view. Its print/address macros also exercise interaction with macro-based source locations; not every macro requires transformation, but allocations in macro expansions need an explicit policy. |
| `Unit04-Mechanics-of-lists/lecture4b-linked-lists/sp2024/linked_list.cpp` | Strong fit. Templated doubly linked list with nested Node type, separate node allocations, next/prev changes and incremental linking. Needs template support and a small driver. The `for_class` counterpart inspected was only a placeholder. |
| `Unit04-Mechanics-of-lists/lecture4c-arrays-vector/for_class/build_vector_solution.cpp` | Relevant lecture sketch of templated growth and array allocation, but contains a syntax error and a member-initialization-order hazard: `_array` is declared before `_capacity` yet its initializer uses `_capacity`. This is not a ready-to-run compatibility fixture; use a corrected example or the homework solution rather than treating the sketch as known-correct code. |
| `Unit04-Mechanics-of-lists/homework4c-vector/solution/Vector.h` | Strong custom-vector target. Template/header allocations occur both in the constructor's member initializer and in growth. Shows runtime capacity, copying to new storage, old-buffer deletion and pointer publication. Unlike the lecture sketch, capacity is declared before the array that uses it. |
| `Unit05-Mechanics-of-trees/lecture5b-bst/bst_demo.cpp` | Useful tree construction/insertion/removal and recursive frames. Uses templated nodes with string payloads, temporary strings, printing helpers and macros. Full-file transformation is more demanding than scalar allocation fixtures; presentation helpers also allocate memory that may distract from the tree. |
| `Unit05-Mechanics-of-trees/homework5b-bst/solution/BST.h` | Strong representative BST target. Templated header, nested nodes, recursive insert/remove/delete, and `Node*&` parameters aliasing root or child-pointer fields. |
| `Unit06-Mechanics-of-hashtables/lecture6b-hashset/HashMap.h` | An unfinished interface sketch, not an implemented map to validate. |
| `Unit06-Mechanics-of-hashtables/homework6a-hashset/solution/HashSet.h` | Student-managed bucket array is visible, but each bucket is a `std::vector<T>`. Strictly opaque STL would hide bucket contents and much of insertion/rehashing. Requires careful attribution: show the student-allocated array of vector objects while excluding vector-internal buffers from the physical student heap view. |
| `Unit07-Mechanics-of-heaps/lecture7a-heaps/heap.cpp` | Heap algorithm stores elements in a `std::vector<T>`; opaque STL hides the central algorithm state. This file also contains unfinished/incorrect syntax and identifiers, so a completed version is required before execution tests. |

## Design implications

### 1. Templates and student headers are essential

The meaningful operations live inside templated classes/functions, often in headers. The existing AST spike rejects templates, does not transform header allocations and excludes relevant initializer contexts. It proves an approach, not compatibility with these examples.

A realistic next acceptance test needs a small driver instantiating a student header such as `Vector<int>` or `BST<int>`, with transformation restricted to an explicit student-source allowlist. Template instantiations must not cause duplicate edits to the same source range. Type/count metadata must reflect the concrete execution without rewriting system headers. These requirements remain unvalidated.

### 2. Reference-to-pointer aliasing needs its own test

The BST's `Node*& node` is a particularly useful teaching case. The reference parameter should display the address of the caller's pointer object—either the root pointer or a node's child-pointer field. That pointer object stores a separate address designating a node.

Earlier reference tests covered integers, not this exact combination of reference, pointer, recursion and heap-member aliasing. Add explicit address assertions rather than assuming the simpler test establishes it.

### 3. Capacity, initialization and logical size are different

The custom vector allocates `new T[cap]` and fills slots incrementally. For scalar T, allocation/default initialization does not give every slot a meaningful initialized value. For class T, constructors may run for all capacity slots while the container's logical size remains smaller.

Record allocated extent, initialization/lifetime evidence and logical container size separately. Do not render unused scalar capacity as trustworthy values. Merely recognizing a field named `len` or `_size` is not a general proof of container semantics.

### 4. Small semantic STL adapters may deserve earlier priority

- Lists/trees remain useful with an opaque string payload, but a string-value adapter would improve readability.
- Hash-set buckets and the heap's backing vector are central to their lessons. A semantic vector element view would offer substantial value.
- Keep adapter output explicitly distinct from actual physical memory layout. It should not require exposing STL implementation fields or admitting all library allocations into the student heap inventory.

### 5. Trace small demonstrations, not entire test suites

Some lecture artifacts are placeholders, incomplete implementations or intentionally exploratory code. Completed implementations need small drivers with bounded operations. Printing utilities and test harnesses can generate substantial incidental activity; source ownership and pedagogical focus should be configurable independently of allocation-provider tracking.

## Recommended acceptance targets

These are recommendations, not experiments already performed:

1. Pointer/alias demonstration from `pointers.cpp`.
2. Small `Vector<int>` driver that crosses one capacity boundary and retains an alias to old storage.
3. Small `BST<int>` driver with insertion, recursive `Node*&` aliasing and deletion.
4. Linked-list insertion/deletion with next/prev updates.
5. Hash-set and heap demonstrations once an explicitly semantic vector view is available.

The course examples support the hybrid architecture, but shift its practical baseline toward template/header support and a small number of useful STL adapters—not a universal C++ transformer.
