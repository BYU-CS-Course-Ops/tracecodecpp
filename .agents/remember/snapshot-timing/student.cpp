#include <new>
#include <cstddef>
// Manual semantic hooks, NOT generated instrumentation. No every-write hooks.
extern "C" __attribute__((noinline)) void timing_event(int kind, void* address, unsigned long size, int type, int site) { asm volatile("" ::: "memory"); }
int x = 0;
struct Item {
  int a, b;
  Item(): a(1), b(2) {
    a = 3; a = 4; // CTOR_MUTATE
    b = 5;
  }
  ~Item() {
    a = -1; a = -2; // DTOR_MUTATE
    b = -3;
  }
};
struct Vec {
  int* data = nullptr;
  int n = 0;
  void grow() {
    int* next = new int[2]; timing_event(1, next, 8, 2, 20); // VEC_ALLOC
    next[0] = data[0]; next[1] = 20; timing_event(2, next, 8, 2, 21); // VEC_INIT
    timing_event(3, data, 4, 2, 22); delete[] data; // VEC_FREE
    data = next; n = 2; // VEC_PUBLISH
  }
};
int main() {
  x = 1; x = 2; x = 3; // MULTI
  void* raw = ::operator new(sizeof(Item)); timing_event(1, raw, sizeof(Item), 1, 30); // ITEM_ALLOC
  Item* item = new(raw) Item; timing_event(2, item, sizeof(Item), 1, 31); // ITEM_INIT
  item->a = 6; item->a = 7; // ITEM_MUTATE
  item->~Item(); timing_event(4, item, sizeof(Item), 1, 32); // ITEM_DEAD
  timing_event(3, raw, sizeof(Item), 1, 33); ::operator delete(raw); // ITEM_FREE
  Vec v;
  v.data = new int[1]; timing_event(1, v.data, 4, 2, 34); // INITIAL_ALLOC
  v.data[0] = 10; v.n = 1; timing_event(2, v.data, 4, 2, 35); // INITIAL_INIT
  int* alias = v.data;
  v.grow();
  timing_event(3, v.data, 8, 2, 36); delete[] v.data;
  int* p = new int(99); timing_event(1, p, 4, 2, 40); timing_event(2, p, 4, 2, 41); timing_event(3, p, 4, 2, 42); delete p; // IMMEDIATE
  x = 9; // END
  return x != 9;
}
