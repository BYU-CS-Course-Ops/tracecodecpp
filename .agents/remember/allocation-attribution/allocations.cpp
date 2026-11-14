// Spike only: ordinary throwing new/new[] and unsized/sized delete.
// No aligned, nothrow, malloc/realloc, placement-new or lifetime coverage.
#include <cstdlib>
#include <new>
extern "C" __attribute__((noinline)) void allocation_event(void* address, unsigned long size, int kind) {
    asm volatile("" : : "r"(address), "r"(size), "r"(kind) : "memory");
}
void* operator new(std::size_t size) {
    void* result = std::malloc(size ? size : 1);
    if (!result) throw std::bad_alloc();
    allocation_event(result, size, 1);
    return result;
}
void* operator new[](std::size_t size) {
    void* result = std::malloc(size ? size : 1);
    if (!result) throw std::bad_alloc();
    allocation_event(result, size, 2);
    return result;
}
void operator delete(void* address) noexcept {
    allocation_event(address, 0, -1);
    std::free(address);
}
void operator delete[](void* address) noexcept {
    allocation_event(address, 0, -2);
    std::free(address);
}
void operator delete(void* address, std::size_t) noexcept { ::operator delete(address); }
void operator delete[](void* address, std::size_t) noexcept { ::operator delete[](address); }
